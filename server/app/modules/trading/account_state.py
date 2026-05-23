"""账户状态统一管理器(A 计划核心)。

设计目的:把所有改账户字段(cash/holding_value/total_asset/daily_pnl)和
成本/盈亏计算的逻辑收拢到一处,避免撮合、refresh、replay 三处口径打架。

核心约定:
  1) holding_value 永远 = Σ(position.current_price × quantity),
     不再用"按成交金额累加"的近似;
  2) total_asset 永远 = available_cash + holding_value;
  3) daily_pnl 永远 = realized_today + floating_today,
     由 recompute_daily_pnl 单点写入;
  4) cost_price 是 fully-loaded 成本(含买入端 commission + transfer_fee);
  5) realized_pnl 公式统一:
     net_proceeds - cost_basis
     = (fill * qty - sell_commission - sell_tax - sell_transfer_fee)
       - (cost_price * qty)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── 费率常量(集中在此,撮合/replay/refresh 全部引用)──
OPEN_COMMISSION_RATE = 0.0003       # 买入佣金 万 3
CLOSE_COMMISSION_RATE = 0.0003      # 卖出佣金 万 3
STAMP_TAX_RATE = 0.001              # 印花税 1‰(仅卖出)
TRANSFER_FEE_RATE = 0.00001         # 过户费 0.001%(仅沪市,双边)
MIN_COMMISSION = 5.0                # 单笔最低 5 元

# 沪市股票代码前缀(用于过户费判断)
SH_STOCK_PREFIXES = ("60", "68", "9")

# 默认滑点(基点,1bp = 0.01%):买入按 fill_price * (1 + slippage),卖出反之
DEFAULT_SLIPPAGE_BPS = 5  # 5bp = 0.05%


@dataclass(slots=True)
class TradeCosts:
    """一笔成交的完整成本结构。"""
    amount: float          # 不含费用的成交金额 = fill_price * qty
    commission: float      # 佣金
    tax: float             # 印花税(买入恒为 0)
    transfer_fee: float    # 过户费
    # 买入:total_cost = 实际从现金扣的金额
    # 卖出:net_proceeds = 实际进入现金的金额
    total_cost: float = 0.0
    net_proceeds: float = 0.0

    @property
    def total_fee(self) -> float:
        """所有费用之和(用于展示和兼容旧字段)。"""
        return round(self.commission + self.tax + self.transfer_fee, 2)


class AccountStateManager:
    """账户字段唯一写入入口 + 成本/盈亏唯一公式源。"""

    # ─────────────────── 成本三件套 ───────────────────

    @staticmethod
    def is_sh_stock(symbol: str) -> bool:
        return any(symbol.startswith(p) for p in SH_STOCK_PREFIXES)

    @staticmethod
    def calc_commission(amount: float, rate: float, min_commission: float = MIN_COMMISSION) -> float:
        return round(max(amount * rate, min_commission), 2)

    @staticmethod
    def calc_stamp_tax(amount: float) -> float:
        """印花税:仅卖出收 1‰。"""
        return round(amount * STAMP_TAX_RATE, 2)

    @staticmethod
    def calc_transfer_fee(symbol: str, amount: float) -> float:
        """过户费:沪市股票双边 0.001%(0.01‰),深市免。"""
        if AccountStateManager.is_sh_stock(symbol):
            return round(amount * TRANSFER_FEE_RATE, 2)
        return 0.0

    @staticmethod
    def apply_slippage(side: str, raw_price: float, slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> float:
        """对成交价应用滑点。

        买入:实际成交 = raw * (1 + bps/10000),意味着按更不利的价格成交
        卖出:实际成交 = raw * (1 - bps/10000)

        默认 5bp 模拟流动性损耗,可通过参数调整。
        """
        if slippage_bps <= 0:
            return raw_price
        factor = 1 + slippage_bps / 10000.0
        if side == "buy":
            return round(raw_price * factor, 4)
        return round(raw_price / factor, 4)

    @staticmethod
    def calc_buy_costs(symbol: str, fill_price: float, quantity: int) -> TradeCosts:
        amount = round(fill_price * quantity, 2)
        commission = AccountStateManager.calc_commission(amount, OPEN_COMMISSION_RATE)
        transfer_fee = AccountStateManager.calc_transfer_fee(symbol, amount)
        total_cost = round(amount + commission + transfer_fee, 2)
        return TradeCosts(
            amount=amount,
            commission=commission,
            tax=0.0,
            transfer_fee=transfer_fee,
            total_cost=total_cost,
            net_proceeds=0.0,
        )

    @staticmethod
    def calc_sell_costs(symbol: str, fill_price: float, quantity: int) -> TradeCosts:
        amount = round(fill_price * quantity, 2)
        commission = AccountStateManager.calc_commission(amount, CLOSE_COMMISSION_RATE)
        tax = AccountStateManager.calc_stamp_tax(amount)
        transfer_fee = AccountStateManager.calc_transfer_fee(symbol, amount)
        net_proceeds = round(amount - commission - tax - transfer_fee, 2)
        return TradeCosts(
            amount=amount,
            commission=commission,
            tax=tax,
            transfer_fee=transfer_fee,
            total_cost=0.0,
            net_proceeds=net_proceeds,
        )

    # ─────────────────── 已实现盈亏 ───────────────────

    @staticmethod
    def compute_realized_pnl(
        *,
        fill_price: float,
        quantity: int,
        cost_price: float,
        sell_commission: float,
        sell_tax: float,
        sell_transfer_fee: float,
    ) -> float:
        """统一的卖出已实现盈亏公式。

        cost_price 必须是 fully-loaded 的(含买入端的 commission + transfer_fee 平摊)。
        """
        gross = fill_price * quantity
        net_proceeds = gross - sell_commission - sell_tax - sell_transfer_fee
        cost_basis = cost_price * quantity
        return round(net_proceeds - cost_basis, 2)

    # ─────────────────── 加权成本 ───────────────────

    @staticmethod
    def compute_avg_cost(
        *,
        existing_quantity: int,
        existing_cost_price: float,
        added_quantity: int,
        added_total_cost: float,
    ) -> float:
        """加仓时的加权成本(fully-loaded)。

        added_total_cost = amount + commission + transfer_fee
        """
        new_quantity = existing_quantity + added_quantity
        if new_quantity <= 0:
            return 0.0
        old_basis = existing_cost_price * existing_quantity
        avg = (old_basis + added_total_cost) / new_quantity
        return round(avg, 4)

    # ─────────────────── 账户字段统一更新 ───────────────────

    @staticmethod
    def apply_buy_to_cash(account: Any, total_cost: float) -> None:
        """买入扣减现金。total_cost = 成交金额 + commission + transfer_fee。"""
        account.available_cash = round(float(account.available_cash) - total_cost, 2)

    @staticmethod
    def apply_sell_to_cash(account: Any, net_proceeds: float) -> None:
        """卖出释放净现金。net_proceeds = 成交金额 - commission - tax - transfer_fee。"""
        account.available_cash = round(float(account.available_cash) + net_proceeds, 2)

    @staticmethod
    def mark_to_market(
        account: Any,
        positions: list[Any],
        quote_map: dict[str, Any] | None = None,
    ) -> tuple[float, float]:
        """盯市:用最新行情重算所有 position.current_price/pnl,
        并更新 account.holding_value + total_asset。

        如果传 quote_map,会同步更新 position.current_price 到最新行情;
        如果不传,使用 position.current_price 当前值(适合撮合后即时调用)。

        返回 (holding_value, floating_pnl_vs_prev_close):
          - holding_value = Σ(latest_price * qty)
          - floating_pnl_vs_prev_close = Σ((latest_price - prev_close) * qty),
            仅当 quote 中有 prev_close 时计入。
        """
        holding_value = 0.0
        floating_daily_pnl = 0.0
        for position in positions:
            quantity = int(position.quantity)
            if quantity <= 0:
                continue
            latest_price = float(position.current_price)
            prev_close: float | None = None
            if quote_map:
                quote = quote_map.get(position.symbol)
                if quote and float(quote.price) > 0:
                    latest_price = float(quote.price)
                    position.current_price = round(latest_price, 4)
                if quote and float(getattr(quote, "prev_close", 0.0) or 0.0) > 0:
                    prev_close = float(quote.prev_close)
            cost_price = float(position.cost_price)
            position.pnl = round((latest_price - cost_price) * quantity, 2)
            holding_value += latest_price * quantity
            if prev_close is not None:
                floating_daily_pnl += (latest_price - prev_close) * quantity

        account.holding_value = round(holding_value, 2)
        account.total_asset = round(float(account.available_cash) + account.holding_value, 2)
        return round(holding_value, 2), round(floating_daily_pnl, 2)

    @staticmethod
    async def recompute_daily_pnl(
        account: Any,
        session: Any,
        *,
        floating_daily_pnl: float,
    ) -> None:
        """重算并写入 account.daily_pnl。

        = realized_today(当日所有成交带来的现金净变化,扣费后)+ floating_today
        实现注意:只算当日 TradeRecord,不动其他天。
        """
        from sqlalchemy import select

        from app.models.trading import TradeRecord

        today = datetime.now().date()
        start_at = datetime.combine(today, time.min)
        end_at = start_at + timedelta(days=1)
        q = await session.execute(
            select(TradeRecord).where(
                TradeRecord.account_id == account.id,
                TradeRecord.created_at >= start_at,
                TradeRecord.created_at < end_at,
            ).order_by(TradeRecord.created_at)
        )
        today_records = list(q.scalars().all())
        realized = AccountStateManager._sum_realized_from_records(today_records)
        account.daily_pnl = round(realized + floating_daily_pnl, 2)

    @staticmethod
    def _sum_realized_from_records(today_records: list[Any]) -> float:
        """从今日 TradeRecord 累加已实现盈亏(净现金影响)。

        买入:贡献 -(commission + transfer_fee)(amount 平账)
        卖出:贡献 (amount - commission - tax - transfer_fee) - cost_basis
                  其中 cost_basis 需要根据持仓回放才能精确得到,
                  这里简化为:用 record 上已经算好的 realized_pnl 字段(由撮合时填)。
        注:简化版假定 TradeRecord 的 commission 字段已包含 transfer_fee。
            为防止双重扣减,这里只用 commission 字段(撮合时存的就是 commission+transfer_fee 总和)。
        """
        # 该方法在没有 realized_pnl 列时,需要外部 replay。
        # 此处只做"用现金净流"近似:卖出净额 - 卖出 cost_basis 由调用方传入。
        # 目前 TradeRecord 表没有 realized_pnl 列,realized 由 replay 提供。
        # 暂时返回 -Σ(commission),floating 由 mark_to_market 提供,
        # _refresh_account_snapshot 会用 replay 精确版覆盖此值。
        return -sum(float(r.commission or 0.0) for r in today_records)
