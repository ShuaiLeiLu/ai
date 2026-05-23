"""自研模拟盘撮合引擎。

历史背景:本模块曾命名为 rqalpha_adapter,但实际未真正接入 RQAlpha 运行时,
只是借用了 ORDER_STATUS 常量名做命名对齐。2026-05 已彻底剥离 RQAlpha 依赖,
撮合逻辑全部自实现,涵盖:
  - A 股涨跌停限价校验
  - T+1 可卖数量校验
  - 佣金 / 印花税 / 过户费三项成本
  - 加权成本价计算
  - 现金 / 持仓 / 总资产联动
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 订单状态常量(原对齐 RQAlpha 命名,保留字符串值以兼容前端展示)
ORDER_STATUS_ACTIVE = "ACTIVE"
ORDER_STATUS_CANCELLED = "CANCELLED"
ORDER_STATUS_FILLED = "FILLED"
ORDER_STATUS_REJECTED = "REJECTED"

PAPER_ENGINE_NAME = "paper-trading-engine/v2"


@dataclass(slots=True)
class MarketSnapshot:
    price: float | None = None
    prev_close: float | None = None
    volume: float | None = None


@dataclass(slots=True)
class ExecutionResult:
    status: str
    message: str
    filled_quantity: int
    fill_price: float | None
    amount: float
    commission: float
    tax: float
    realized_pnl: float | None
    engine: str = PAPER_ENGINE_NAME
    created_position: dict[str, Any] | None = None
    remove_position: bool = False

    @property
    def total_fee(self) -> float:
        return round(self.commission + self.tax, 2)


def compute_sellable_quantity(position_quantity: int, today_bought_quantity: int) -> int:
    """A-share T+1: same-day bought shares cannot be sold."""
    return max(int(position_quantity) - int(today_bought_quantity), 0)


def _limit_ratio(symbol: str, name: str) -> float:
    stock_name = name.upper()
    if "ST" in stock_name:
        return 0.05
    if symbol.startswith(("300", "301", "688", "689")):
        return 0.20
    if len(symbol) == 6 and symbol.startswith(("4", "8")):
        return 0.30
    return 0.10


def _price_limits(symbol: str, name: str, prev_close: float | None) -> tuple[float, float] | None:
    if prev_close is None or prev_close <= 0:
        return None
    ratio = _limit_ratio(symbol, name)
    return round(prev_close * (1 + ratio), 2), round(prev_close * (1 - ratio), 2)


def _validate_lot_size(
    side: str,
    quantity: int,
    position_quantity: int,
    sellable_quantity: int | None,
) -> str | None:
    if quantity <= 0:
        return "委托数量必须大于 0"

    if side == "buy":
        if quantity % 100 != 0:
            return "A 股买入数量必须是 100 股的整数倍"
        return None

    if position_quantity <= 0:
        return "当前无可卖持仓"

    if sellable_quantity is not None and quantity > sellable_quantity:
        return f"T+1 限制：当前可卖 {sellable_quantity} 股"

    if quantity > position_quantity:
        return f"持仓不足：当前持仓 {position_quantity} 股"

    if quantity % 100 == 0:
        return None

    odd_lot = position_quantity % 100
    if quantity == position_quantity:
        return None
    if odd_lot > 0 and quantity == odd_lot:
        return None
    return "A 股卖出零股时，只允许卖出剩余不足 100 股的部分"


def _resolve_limit_fill(
    side: str,
    symbol: str,
    name: str,
    limit_price: float,
    market: MarketSnapshot | None,
) -> tuple[str, float | None, str]:
    if market is None or market.price is None or market.price <= 0:
        return ORDER_STATUS_FILLED, limit_price, "实时行情缺失，按委托价模拟成交"

    market_price = float(market.price)
    limits = _price_limits(symbol, name, market.prev_close)
    if limits:
        limit_up, limit_down = limits
        if side == "buy":
            if limit_price > limit_up:
                return (
                    ORDER_STATUS_REJECTED,
                    None,
                    f"委托价 {limit_price:.2f} 高于涨停价 {limit_up:.2f}",
                )
            if market_price >= limit_up and limit_price >= limit_up:
                return ORDER_STATUS_REJECTED, None, f"{symbol} 当前处于涨停状态，无法按限价买入"
        else:
            if limit_price < limit_down:
                return (
                    ORDER_STATUS_REJECTED,
                    None,
                    f"委托价 {limit_price:.2f} 低于跌停价 {limit_down:.2f}",
                )
            if market_price <= limit_down and limit_price <= limit_down:
                return ORDER_STATUS_REJECTED, None, f"{symbol} 当前处于跌停状态，无法按限价卖出"

    if market.volume is not None and market.volume <= 0:
        return ORDER_STATUS_CANCELLED, None, f"{symbol} 当前无成交量，模拟撮合已取消"

    if side == "buy":
        if limit_price < market_price:
            return ORDER_STATUS_ACTIVE, None, "当前仅支持可立即成交的限价单，买入价低于最新价"
    else:
        if limit_price > market_price:
            return ORDER_STATUS_ACTIVE, None, "当前仅支持可立即成交的限价单，卖出价高于最新价"

    return ORDER_STATUS_FILLED, market_price, "按最新价完成模拟成交"


def execute_stock_order(
    *,
    account: Any,
    existing_position: Any | None,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
    market: MarketSnapshot | None,
    sellable_quantity: int | None = None,
    # 兼容旧签名:这些参数现在忽略,统一从 AccountStateManager 取值
    open_commission_rate: float | None = None,
    close_commission_rate: float | None = None,
    close_tax_rate: float | None = None,
    min_commission: float | None = None,
) -> ExecutionResult:
    """模拟盘撮合:校验 → 定价 → 算费 → 写账户。

    所有费用计算和账户字段写入统一走 AccountStateManager,避免多套口径。
    Cost basis 是 fully-loaded:含买入端 commission + transfer_fee 平摊。
    Realized pnl = (fill * qty - sell_commission - sell_tax - sell_transfer_fee)
                   - cost_price * qty
    """
    from app.modules.trading.account_state import (
        DEFAULT_SLIPPAGE_BPS,
        AccountStateManager,
    )

    position_quantity = int(getattr(existing_position, "quantity", 0) or 0)
    validation_error = _validate_lot_size(side, quantity, position_quantity, sellable_quantity)
    if validation_error:
        return ExecutionResult(
            status=ORDER_STATUS_REJECTED,
            message=validation_error,
            filled_quantity=0,
            fill_price=None,
            amount=0.0,
            commission=0.0,
            tax=0.0,
            realized_pnl=None,
        )

    status, raw_fill_price, fill_message = _resolve_limit_fill(side, symbol, name, limit_price, market)
    if status != ORDER_STATUS_FILLED or raw_fill_price is None:
        return ExecutionResult(
            status=status,
            message=fill_message,
            filled_quantity=0,
            fill_price=None,
            amount=0.0,
            commission=0.0,
            tax=0.0,
            realized_pnl=None,
        )

    # 滑点模拟(买入按更不利价,卖出同理)
    fill_price = AccountStateManager.apply_slippage(side, raw_fill_price)
    if abs(fill_price - raw_fill_price) > 0.0001:
        fill_message = (
            f"{fill_message}|滑点 {DEFAULT_SLIPPAGE_BPS}bp 后成交价 {fill_price:.4f}"
        )

    current_price = round(
        float(market.price if market and market.price else fill_price), 4,
    )

    if side == "buy":
        costs = AccountStateManager.calc_buy_costs(symbol, fill_price, quantity)
        available_cash = round(float(account.available_cash), 2)
        if available_cash < costs.total_cost:
            return ExecutionResult(
                status=ORDER_STATUS_REJECTED,
                message=(
                    f"可用资金不足:需要 {costs.total_cost:.2f},"
                    f"当前 {available_cash:.2f}"
                ),
                filled_quantity=0,
                fill_price=None,
                amount=0.0,
                commission=0.0,
                tax=0.0,
                realized_pnl=None,
            )

        # 1) 扣现金
        AccountStateManager.apply_buy_to_cash(account, costs.total_cost)

        # 2) 更新/新建持仓(fully-loaded cost)
        if existing_position is not None:
            new_quantity = int(existing_position.quantity) + quantity
            new_cost = AccountStateManager.compute_avg_cost(
                existing_quantity=int(existing_position.quantity),
                existing_cost_price=float(existing_position.cost_price),
                added_quantity=quantity,
                added_total_cost=costs.total_cost,
            )
            existing_position.quantity = new_quantity
            existing_position.cost_price = new_cost
            existing_position.current_price = current_price
            existing_position.pnl = round((current_price - new_cost) * new_quantity, 2)
            position_payload = None
        else:
            unit_cost = round(costs.total_cost / quantity, 4)
            position_payload = {
                "symbol": symbol,
                "name": name or symbol,
                "quantity": quantity,
                "cost_price": unit_cost,
                "current_price": current_price,
                "pnl": round((current_price - unit_cost) * quantity, 2),
            }

        # 3) holding_value / total_asset 由调用方在持仓 flush 后调用 mark_to_market 重算
        #    daily_pnl 由调用方在事务末尾调用 recompute_daily_pnl 重算
        return ExecutionResult(
            status=ORDER_STATUS_FILLED,
            message=f"买入成功:{symbol} {quantity}股 @ {fill_price:.2f}（{fill_message}）",
            filled_quantity=quantity,
            fill_price=round(fill_price, 4),
            amount=costs.amount,
            commission=round(costs.commission + costs.transfer_fee, 2),
            tax=0.0,
            realized_pnl=-round(costs.commission + costs.transfer_fee, 2),
            created_position=position_payload,
        )

    # ── 卖出 ──
    costs = AccountStateManager.calc_sell_costs(symbol, fill_price, quantity)
    cost_price = float(existing_position.cost_price)
    realized_pnl = AccountStateManager.compute_realized_pnl(
        fill_price=fill_price,
        quantity=quantity,
        cost_price=cost_price,
        sell_commission=costs.commission,
        sell_tax=costs.tax,
        sell_transfer_fee=costs.transfer_fee,
    )

    # 1) 加现金(净额)
    AccountStateManager.apply_sell_to_cash(account, costs.net_proceeds)

    # 2) 更新持仓数量
    remaining_quantity = int(existing_position.quantity) - quantity
    if remaining_quantity <= 0:
        remove_position = True
        existing_position.quantity = 0
        existing_position.current_price = current_price
        existing_position.pnl = 0.0
    else:
        remove_position = False
        existing_position.quantity = remaining_quantity
        existing_position.current_price = current_price
        existing_position.pnl = round(
            (current_price - cost_price) * remaining_quantity, 2,
        )

    return ExecutionResult(
        status=ORDER_STATUS_FILLED,
        message=f"卖出成功:{symbol} {quantity}股 @ {fill_price:.2f}（{fill_message}）",
        filled_quantity=quantity,
        fill_price=round(fill_price, 4),
        amount=costs.amount,
        # commission 字段对外暴露的是 commission + transfer_fee 之和,方便兼容
        commission=round(costs.commission + costs.transfer_fee, 2),
        tax=costs.tax,
        realized_pnl=realized_pnl,
        remove_position=remove_position,
    )
