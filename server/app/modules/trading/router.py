"""
模拟交易路由

提供：
  - 账户概况查询（按研究员）
  - 持仓列表（按研究员）
  - 成交记录（按研究员）
  - 下单撮合

所有查询接口支持 researcher_id 参数，DB 优先，fallback 到 mock。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
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
    TradingStats,
)
from app.modules.trading.service import TradingService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/trading", tags=["trading"])
service = TradingService()


@router.get("/account")
async def account(
    researcher_id: str = Query(default="", description="研究员ID，传入后查该研究员的模拟盘"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingAccount]:
    """模拟账户概况（DB 优先，fallback 到 mock）"""
    if session and researcher_id:
        try:
            data = await service.async_get_account(session, user_id, researcher_id)
            return ApiResponse(data=data)
        except Exception:
            pass
    return ApiResponse(data=service.get_account())


@router.get("/positions")
async def positions(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[PositionItem]]:
    """持仓列表（DB 优先，fallback 到 mock）"""
    if session and researcher_id:
        try:
            acct = await service.async_get_account(session, user_id, researcher_id)
            items = await service.async_list_positions(session, acct.account_id)
            return ApiResponse(data=ListResponse(items=items, total=len(items)))
        except Exception:
            pass
    items = service.list_positions()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/records")
async def records(
    researcher_id: str = Query(default="", description="研究员ID"),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TradeRecord]]:
    """成交记录（DB 优先，fallback 到 mock）"""
    if session and researcher_id:
        try:
            acct = await service.async_get_account(session, user_id, researcher_id)
            items = await service.async_list_records(session, acct.account_id, limit=limit)
            return ApiResponse(data=ListResponse(items=items, total=len(items)))
        except Exception:
            pass
    items = service.list_records(limit=limit)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/logs")
async def list_trade_logs(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TradeLogItem]]:
    """获取交易日志（trade 表格 + analysis 富文本）"""
    if session and researcher_id:
        try:
            acct = await service.async_get_account(session, user_id, researcher_id)
            items = await service.async_list_logs(session, acct.account_id, limit=200)
            return ApiResponse(data=ListResponse(items=items, total=len(items)))
        except Exception:
            pass
    return ApiResponse(data=ListResponse(items=[], total=0))


@router.get("/stats")
async def trading_stats(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingStats]:
    """获取历史交易统计（收益曲线、月度收益、风控指标、日收益序列）"""
    if session and researcher_id:
        try:
            acct = await service.async_get_account(session, user_id, researcher_id)
            stats = await service.async_get_stats(session, acct.account_id)
            return ApiResponse(data=stats)
        except Exception:
            pass
    from app.modules.trading.schemas import RiskMetrics
    empty_risk = RiskMetrics(
        total_return=0, annual_return=0, max_drawdown=0, sharpe=0,
        win_rate=0, profit_loss_ratio=0, total_trades=0,
        win_trades=0, lose_trades=0, max_profit=0, max_loss=0, avg_hold_days=0,
    )
    return ApiResponse(data=TradingStats(
        initial_capital=100000, total_asset=100000,
        equity_curve=[], monthly_returns=[], daily_returns=[], risk=empty_risk,
    ))


@router.post("/execute-strategy")
async def execute_strategy(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse:
    """手动触发策略执行（调试用）"""
    if not session:
        return ApiResponse(success=False, detail="数据库不可用")
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
    if session and payload.researcher_id:
        data = await service.async_place_order(session, user_id, payload)
        return ApiResponse(data=data)
    return ApiResponse(data=service.place_order(payload))
