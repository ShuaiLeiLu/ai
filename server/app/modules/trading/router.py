"""
模拟交易路由

提供：
  - 账户概况查询（按研究员）
  - 持仓列表（按研究员）
  - 成交记录（按研究员）
  - 下单撮合

所有查询接口优先返回真实数据库数据。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
from app.modules.trading.schemas import (
    PlaceOrderRequest,
    PlaceOrderResponse,
    PositionItem,
    TradeLogItem,
    TradeRecord,
    TradingAccount,
    TradingAllData,
    TradingPortfolioData,
    TradingStats,
)
from app.modules.trading.service import TradingService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/trading", tags=["trading"])
service = TradingService()


def _empty_account() -> TradingAccount:
    return TradingAccount(
        account_id="",
        initial_capital=0.0,
        total_asset=0.0,
        available_cash=0.0,
        holding_value=0.0,
        daily_pnl=0.0,
    )


def _empty_all_data() -> TradingAllData:
    return TradingAllData(account=_empty_account(), positions=[], records=[], logs=[])


def _empty_portfolio_data() -> TradingPortfolioData:
    return TradingPortfolioData(account=_empty_account(), positions=[])


def _empty_stats() -> TradingStats:
    from app.modules.trading.schemas import RiskMetrics

    return TradingStats(
        initial_capital=0.0,
        total_asset=0.0,
        equity_curve=[],
        monthly_returns=[],
        daily_returns=[],
        risk=RiskMetrics(
            total_return=0.0,
            annual_return=0.0,
            max_drawdown=0.0,
            sharpe=0.0,
            win_rate=0.0,
            profit_loss_ratio=0.0,
            total_trades=0,
            win_trades=0,
            lose_trades=0,
            max_profit=0.0,
            max_loss=0.0,
            avg_hold_days=0.0,
        ),
    )


@router.get("/all")
async def trading_all(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingAllData]:
    """模拟盘聚合接口 —— 一次返回 account + positions + records + logs。

    核心优化：只加载一次成交记录并回放一次，相比 4 个独立接口减少 3 次重复查库与回放。
    """
    if not session or not researcher_id:
        return ApiResponse(data=_empty_all_data())
    data = await service.async_get_all(session, user_id, researcher_id)
    return ApiResponse(data=data)


@router.get("/portfolio")
async def trading_portfolio(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingPortfolioData]:
    """模拟盘轻量组合接口 —— 只返回 account + positions。"""
    if not session or not researcher_id:
        return ApiResponse(data=_empty_portfolio_data())
    data = await service.async_get_portfolio(session, user_id, researcher_id)
    return ApiResponse(data=data)


@router.get("/account")
async def account(
    researcher_id: str = Query(default="", description="研究员ID，传入后查该研究员的模拟盘"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingAccount]:
    """模拟账户概况。"""
    if not session or not researcher_id:
        return ApiResponse(data=_empty_account())
    data = await service.async_get_account(session, user_id, researcher_id)
    return ApiResponse(data=data)


@router.get("/positions")
async def positions(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[PositionItem]]:
    """持仓列表。"""
    if not session or not researcher_id:
        return ApiResponse(data=ListResponse(items=[], total=0))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_positions(session, account_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/records")
async def records(
    researcher_id: str = Query(default="", description="研究员ID"),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TradeRecord]]:
    """成交记录。"""
    if not session or not researcher_id:
        return ApiResponse(data=ListResponse(items=[], total=0))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_records(session, account_id, limit=limit)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/logs")
async def list_trade_logs(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TradeLogItem]]:
    """获取交易日志（trade 表格 + analysis 富文本）"""
    if not session or not researcher_id:
        return ApiResponse(data=ListResponse(items=[], total=0))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_logs(session, account_id, limit=200)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/stats")
async def trading_stats(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingStats]:
    """获取历史交易统计（收益曲线、月度收益、风控指标、日收益序列）"""
    if not session or not researcher_id:
        return ApiResponse(data=_empty_stats())
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    stats = await service.async_get_stats(session, account_id)
    return ApiResponse(data=stats)


@router.post("/execute-strategy")
async def execute_strategy(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse:
    """手动触发策略执行（调试用）"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    from app.engine.strategy_engine import execute_daily_rotation
    result = await execute_daily_rotation(session)
    return ApiResponse(data=result)


@router.post("/order")
async def place_order(
    payload: PlaceOrderRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[PlaceOrderResponse]:
    """模拟下单 —— 即时撮合（限价单）

    买入：扣减资金，增加持仓
    卖出：释放资金，减少持仓
    """
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    if not payload.researcher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="researcher_id 缺失")
    data = await service.async_place_order(session, user_id, payload)
    return ApiResponse(data=data)
