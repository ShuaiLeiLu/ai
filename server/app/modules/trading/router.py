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

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dependency, get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.modules.trading.schemas import (
    DailyReviewResponse,
    GenerateTradeReflectionResponse,
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
from app.modules.trading.skill_service import (
    get_existing_daily_review_report,
    stream_daily_review,
)
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/trading", tags=["trading"])
service = TradingService()
_CACHE_TTL_SECONDS = 45
_ALL_ADAPTER = TypeAdapter(TradingAllData)
_PORTFOLIO_ADAPTER = TypeAdapter(TradingPortfolioData)
_ACCOUNT_ADAPTER = TypeAdapter(TradingAccount)
_POSITIONS_ADAPTER = TypeAdapter(list[PositionItem])
_RECORDS_ADAPTER = TypeAdapter(list[TradeRecord])
_LOGS_ADAPTER = TypeAdapter(list[TradeLogItem])
_STATS_ADAPTER = TypeAdapter(TradingStats)


async def _load_trading_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_trading_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


async def _delete_trading_cache(*names: str) -> None:
    try:
        redis = get_container().redis.get_client()
        for name in names:
            await delete_cached(redis, name)
    except Exception:
        return


def _trading_cache_name(section: str, user_id: str, researcher_id: str, suffix: str = "") -> str:
    return f"trading:{section}:{user_id}:{researcher_id}{suffix}"


async def _invalidate_trading_page_cache(user_id: str, researcher_id: str) -> None:
    await _delete_trading_cache(
        _trading_cache_name("all", user_id, researcher_id),
        _trading_cache_name("portfolio", user_id, researcher_id),
        _trading_cache_name("account", user_id, researcher_id),
        _trading_cache_name("positions", user_id, researcher_id),
        _trading_cache_name("records", user_id, researcher_id, ":limit=20"),
        _trading_cache_name("logs", user_id, researcher_id),
        _trading_cache_name("stats", user_id, researcher_id),
    )


async def _resolve_researcher_id(
    session: AsyncSession, user_id: str, researcher_id: str
) -> str:
    """若未指定 researcher_id，自动选取用户名下第一个研究员（雇佣或自创）。"""
    if researcher_id:
        return researcher_id
    from sqlalchemy import select

    from app.models.researcher import Researcher, ResearcherHire

    # 1) 自创研究员（Researcher.id 即 researcher_id）
    own = await session.execute(
        select(Researcher.id)
        .where(Researcher.owner_id == user_id)
        .limit(1)
    )
    own_id = own.scalar_one_or_none()
    if own_id:
        return own_id
    # 2) 雇佣的研究员
    hired = await session.execute(
        select(ResearcherHire.researcher_id)
        .where(ResearcherHire.user_id == user_id)
        .limit(1)
    )
    hired_id = hired.scalar_one_or_none()
    return hired_id or ""


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
    cache_name = _trading_cache_name("all", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _ALL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_all(session, user_id, researcher_id)
    await _save_trading_cache(cache_name, data)
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
    cache_name = _trading_cache_name("portfolio", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _PORTFOLIO_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_portfolio(session, user_id, researcher_id)
    await _save_trading_cache(cache_name, data)
    return ApiResponse(data=data)


@router.get("/account")
async def account(
    researcher_id: str = Query(default="", description="研究员ID，传入后查该研究员的模拟盘；未传则用户首个研究员"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingAccount]:
    """模拟账户概况。"""
    if not session:
        return ApiResponse(data=_empty_account())
    researcher_id = await _resolve_researcher_id(session, user_id, researcher_id)
    if not researcher_id:
        return ApiResponse(data=_empty_account())
    cache_name = _trading_cache_name("account", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _ACCOUNT_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_account(session, user_id, researcher_id)
    await _save_trading_cache(cache_name, data)
    return ApiResponse(data=data)


@router.get("/positions")
async def positions(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[PositionItem]]:
    """持仓列表。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    researcher_id = await _resolve_researcher_id(session, user_id, researcher_id)
    if not researcher_id:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _trading_cache_name("positions", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _POSITIONS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_positions(session, account_id)
    await _save_trading_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/records")
async def records(
    researcher_id: str = Query(default="", description="研究员ID"),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TradeRecord]]:
    """成交记录。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    researcher_id = await _resolve_researcher_id(session, user_id, researcher_id)
    if not researcher_id:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _trading_cache_name("records", user_id, researcher_id, f":limit={limit}")
    cached = await _load_trading_cache(cache_name, _RECORDS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_records(session, account_id, limit=limit)
    await _save_trading_cache(cache_name, items)
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
    cache_name = _trading_cache_name("logs", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _LOGS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    items = await service.async_list_logs(session, account_id, limit=200)
    await _save_trading_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("/logs/reflect")
async def generate_trade_reflection(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[GenerateTradeReflectionResponse]:
    """基于最近一笔真实成交日志，手动生成并保存 AI 交易复盘。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    if not researcher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="researcher_id 缺失")
    account_model = await service.async_resolve_account_model(session, user_id, researcher_id)
    researcher = await service._load_researcher_model(session, researcher_id)
    log = await service.async_generate_reflection_for_latest_trade(
        session,
        account=account_model,
        researcher=researcher,
    )
    return ApiResponse(data=GenerateTradeReflectionResponse(log=log))


@router.get("/stats")
async def trading_stats(
    researcher_id: str = Query(default="", description="研究员ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TradingStats]:
    """获取历史交易统计（收益曲线、月度收益、风控指标、日收益序列）"""
    if not session or not researcher_id:
        return ApiResponse(data=_empty_stats())
    cache_name = _trading_cache_name("stats", user_id, researcher_id)
    cached = await _load_trading_cache(cache_name, _STATS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    account_id = await service.async_resolve_account_id(session, user_id, researcher_id)
    stats = await service.async_get_stats(session, account_id)
    await _save_trading_cache(cache_name, stats)
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
    await _invalidate_trading_page_cache(user_id, payload.researcher_id)
    return ApiResponse(data=data)


@router.get("/pending-orders")
async def list_pending(
    researcher_id: str = Query(..., description="研究员 ID"),
    status_filter: str | None = Query(None, alias="status", description="ACTIVE / FILLED / CANCELLED / EXPIRED"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """查询挂单列表(默认全部状态;status=ACTIVE 只看未成交)。"""
    from sqlalchemy import select
    from app.models.trading import TradingAccount
    from app.modules.trading.pending_order_service import list_pending_orders

    acc_q = await session.execute(
        select(TradingAccount.id).where(
            TradingAccount.user_id == user_id,
            TradingAccount.researcher_id == researcher_id,
        ).limit(1)
    )
    account_id = acc_q.scalar_one_or_none()
    if not account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到模拟账户")
    orders = await list_pending_orders(
        session,
        account_id=account_id,
        statuses=[status_filter] if status_filter else None,
    )
    return ApiResponse(data={
        "account_id": account_id,
        "orders": [
            {
                "id": o.id,
                "symbol": o.symbol, "name": o.name,
                "side": o.side, "quantity": o.quantity,
                "limit_price": o.limit_price,
                "status": o.status,
                "expires_at": o.expires_at.isoformat() if o.expires_at else None,
                "filled_trade_id": o.filled_trade_id,
                "filled_price": o.filled_price,
                "filled_at": o.filled_at.isoformat() if o.filled_at else None,
                "cancel_reason": o.cancel_reason,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    })


@router.post("/pending-orders/{order_id}/cancel")
async def cancel_pending(
    order_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """用户主动取消挂单。"""
    from app.modules.trading.pending_order_service import cancel_pending_order
    order = await cancel_pending_order(session, order_id=order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="挂单不存在或已成交/取消/过期",
        )
    await session.commit()
    return ApiResponse(data={"id": order.id, "status": order.status})


@router.get("/symbol-chart")
async def symbol_chart(
    symbol: str = Query(..., description="股票代码,不含交易所前缀"),
    researcher_id: str = Query(..., description="研究员 ID"),
    days: int = Query(60, ge=5, le=365, description="回看 K 线天数"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """持仓股 K 线 + 我的买卖点叠加。"""
    from datetime import date, timedelta

    from sqlalchemy import select

    from app.integrations.akshare.client import (
        get_stock_history,
        run_sync,
    )
    from app.models.trading import TradeRecord, TradingAccount

    acc_q = await session.execute(
        select(TradingAccount.id).where(
            TradingAccount.user_id == user_id,
            TradingAccount.researcher_id == researcher_id,
        ).limit(1)
    )
    account_id = acc_q.scalar_one_or_none()
    if not account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到模拟账户")

    end_date = date.today()
    start_date = end_date - timedelta(days=days * 3 // 2)  # 多取一些防止节假日不够
    bars = await run_sync(get_stock_history, symbol, start_date, end_date)
    bars = bars[-days:] if bars else []

    rec_q = await session.execute(
        select(TradeRecord).where(
            TradeRecord.account_id == account_id,
            TradeRecord.symbol == symbol,
        ).order_by(TradeRecord.created_at)
    )
    trades = [
        {
            "trade_id": t.id,
            "side": t.side,
            "price": float(t.price),
            "quantity": int(t.quantity),
            "timestamp": t.created_at.isoformat() if t.created_at else None,
            "date": t.created_at.date().isoformat() if t.created_at else None,
        }
        for t in rec_q.scalars().all()
    ]

    return ApiResponse(data={
        "symbol": symbol,
        "kline": [
            {
                "date": b.date,
                "open": b.open, "close": b.close,
                "high": b.high, "low": b.low,
                "volume": b.volume, "amount": b.amount,
                "change_pct": b.change_pct, "turnover": b.turnover,
            }
            for b in bars
        ],
        "trades": trades,
    })


@router.get("/portfolio-analytics")
async def portfolio_analytics(
    researcher_id: str = Query(..., description="研究员 ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """持仓集中度 + 行业分布 + 跌停最大损失估算。"""
    from sqlalchemy import select

    from app.integrations.akshare.client import get_stock_quote_by_symbols, run_sync
    from app.models.trading import Position, TradingAccount

    acc_q = await session.execute(
        select(TradingAccount).where(
            TradingAccount.user_id == user_id,
            TradingAccount.researcher_id == researcher_id,
        ).limit(1)
    )
    account = acc_q.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到模拟账户")

    pos_q = await session.execute(
        select(Position).where(Position.account_id == account.id)
    )
    positions = list(pos_q.scalars().all())
    total_asset = float(account.total_asset) or 1.0
    holding_value = float(account.holding_value) or 0.0

    # 取行业(akshare)
    quote_map = {}
    if positions:
        symbols = [p.symbol for p in positions]
        quote_map = await run_sync(get_stock_quote_by_symbols, symbols)

    # 单股市值 + 占比
    items = []
    for p in positions:
        mv = float(p.current_price) * int(p.quantity)
        items.append({
            "symbol": p.symbol,
            "name": p.name,
            "market_value": round(mv, 2),
            "weight_in_total_asset": round(mv / total_asset, 4),
            "weight_in_holding": round(mv / holding_value, 4) if holding_value > 0 else 0,
            "industry": getattr(quote_map.get(p.symbol), "industry", "") or "未知",
            "limit_down_loss": round(mv * 0.1, 2),  # 跌停 10% 损失估算
        })
    items.sort(key=lambda x: x["market_value"], reverse=True)

    # 集中度
    sorted_weights = [x["weight_in_total_asset"] for x in items]
    top1 = sorted_weights[0] if sorted_weights else 0
    top3 = sum(sorted_weights[:3])
    top5 = sum(sorted_weights[:5])

    # 行业聚合
    industry_map: dict[str, float] = {}
    for it in items:
        industry_map[it["industry"]] = industry_map.get(it["industry"], 0) + it["market_value"]
    industry_list = sorted(
        [
            {
                "industry": k,
                "market_value": round(v, 2),
                "weight": round(v / holding_value, 4) if holding_value > 0 else 0,
            }
            for k, v in industry_map.items()
        ],
        key=lambda x: x["market_value"], reverse=True,
    )

    # 仓位水平
    position_ratio = round(holding_value / total_asset, 4) if total_asset > 0 else 0
    position_label = (
        "满仓" if position_ratio >= 0.95
        else "重仓" if position_ratio >= 0.7
        else "半仓" if position_ratio >= 0.4
        else "轻仓" if position_ratio >= 0.1
        else "空仓"
    )

    return ApiResponse(data={
        "account_id": account.id,
        "total_asset": round(total_asset, 2),
        "holding_value": round(holding_value, 2),
        "position_ratio": position_ratio,
        "position_label": position_label,
        "concentration": {
            "top1": round(top1, 4),
            "top3": round(top3, 4),
            "top5": round(top5, 4),
        },
        "max_limit_down_loss": round(sum(x["limit_down_loss"] for x in items), 2),
        "max_limit_down_loss_pct": round(
            sum(x["limit_down_loss"] for x in items) / total_asset, 4,
        ) if total_asset > 0 else 0,
        "positions": items,
        "industry_distribution": industry_list,
    })


@router.get("/records/{trade_id}")
async def trade_record_detail(
    trade_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """单笔成交详情 + 同股该账户历史成交。"""
    from sqlalchemy import select

    from app.models.trading import TradeLog, TradeRecord, TradingAccount

    rec_q = await session.execute(
        select(TradeRecord).where(TradeRecord.id == trade_id)
    )
    record = rec_q.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成交不存在")
    # 验账户归属
    acc_q = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == record.account_id,
            TradingAccount.user_id == user_id,
        ).limit(1)
    )
    if acc_q.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此成交")

    # 同股历史(按 created_at 降序)
    hist_q = await session.execute(
        select(TradeRecord).where(
            TradeRecord.account_id == record.account_id,
            TradeRecord.symbol == record.symbol,
            TradeRecord.id != trade_id,
        ).order_by(TradeRecord.created_at.desc()).limit(20)
    )
    history = hist_q.scalars().all()

    # 关联 TradeLog(可能有同 trade_id 的 trade 日志 + analysis 日志)
    log_q = await session.execute(
        select(TradeLog).where(
            TradeLog.account_id == record.account_id,
            TradeLog.trade_record_ids.like(f"%{trade_id}%"),
        ).order_by(TradeLog.created_at)
    )
    logs = log_q.scalars().all()

    return ApiResponse(data={
        "trade": {
            "trade_id": record.id,
            "symbol": record.symbol, "name": record.name,
            "side": record.side, "quantity": record.quantity,
            "price": float(record.price),
            "amount": round(float(record.price) * int(record.quantity), 2),
            "commission_total": float(record.commission),  # 含 transfer_fee
            "created_at": record.created_at.isoformat() if record.created_at else None,
        },
        "history": [
            {
                "trade_id": h.id, "side": h.side,
                "quantity": h.quantity, "price": float(h.price),
                "commission_total": float(h.commission),
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ],
        "logs": [
            {
                "log_id": l.id, "log_type": l.log_type,
                "title": l.title, "content": l.content,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    })


async def _load_hs300_benchmark(snapshot_rows) -> dict[str, float]:
    """把沪深 300 归一化到与账户初始资金同量纲。

    snapshot_rows: list[TradingAccountSnapshot],按 trade_date 升序
    返回: {date_iso: benchmark_value}
    实现:基准 = 沪深300当日收盘 / 沪深300起始日收盘 × 起始账户权益
    """
    if not snapshot_rows:
        return {}
    from app.integrations.akshare.client import get_index_daily_bars, run_sync

    initial_equity = float(snapshot_rows[0].total_asset)
    try:
        bars = await run_sync(get_index_daily_bars, "sh000300", 250)
    except Exception:
        return {}
    if not bars:
        return {}

    price_by_date: dict[str, float] = {}
    for b in bars:
        if b.close > 0:
            price_by_date[str(b.trade_date)] = float(b.close)

    # 起点价格:取 snapshot 首日(或之前最近一天)的沪深300收盘
    sorted_dates = sorted(price_by_date.keys())
    first_account_date = snapshot_rows[0].trade_date.isoformat()
    start_price = 0.0
    for d in sorted_dates:
        if d <= first_account_date:
            start_price = price_by_date[d]
        else:
            break
    if start_price <= 0:
        # 兜底:取最早一条
        start_price = price_by_date[sorted_dates[0]]

    out: dict[str, float] = {}
    for r in snapshot_rows:
        d_iso = r.trade_date.isoformat()
        # 找到该日或之前最近一日的沪深300价
        close_price = 0.0
        for d in sorted_dates:
            if d <= d_iso:
                close_price = price_by_date[d]
            else:
                break
        if close_price > 0:
            out[d_iso] = round(initial_equity * close_price / start_price, 2)
    return out


@router.get("/equity-curve")
async def equity_curve(
    researcher_id: str = Query(..., description="研究员 ID"),
    granularity: str = Query("1m", description="粒度 1m / 5m / 15m / 1h / 1d"),
    hours: int | None = Query(None, description="回看小时数(默认按粒度推荐)"),
    days: int | None = Query(None, description="回看天数(1d 粒度专用)"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse:
    """模拟盘权益曲线 —— 多粒度。

    1m  : 直接读 trading_account_minute_snapshots
    5m/15m/1h:从分钟表降采样(取每个时间窗最后一条)
    1d  : 读 trading_account_snapshots(日级)
    """
    from datetime import datetime as _dt
    from datetime import timedelta, timezone

    from sqlalchemy import select

    from app.models.trading import (
        TradingAccount,
        TradingAccountMinuteSnapshot,
        TradingAccountSnapshot,
    )
    from app.modules.trading.schemas import EquityCurvePoint, EquityCurveResponse

    # resolve account_id
    acc_q = await session.execute(
        select(TradingAccount.id).where(
            TradingAccount.user_id == user_id,
            TradingAccount.researcher_id == researcher_id,
        ).limit(1)
    )
    account_id = acc_q.scalar_one_or_none()
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="未找到该研究员的模拟账户",
        )

    granularity = granularity.lower()
    now = _dt.now(tz=timezone.utc)

    if granularity == "1d":
        lookback_days = days or 90
        cutoff_date = (now - timedelta(days=lookback_days)).date()
        stmt = (
            select(TradingAccountSnapshot)
            .where(
                TradingAccountSnapshot.account_id == account_id,
                TradingAccountSnapshot.trade_date >= cutoff_date,
            )
            .order_by(TradingAccountSnapshot.trade_date)
        )
        rows = (await session.execute(stmt)).scalars().all()
        # 沪深 300 基准对照:把基准归一化到与账户初始资金同量纲
        benchmark_map = await _load_hs300_benchmark(rows)
        points = [
            EquityCurvePoint(
                timestamp=r.trade_date.isoformat(),
                total_asset=float(r.total_asset),
                available_cash=float(r.available_cash),
                holding_value=float(r.holding_value),
                daily_pnl=float(r.daily_pnl),
                benchmark=benchmark_map.get(r.trade_date.isoformat(), 0.0),
            )
            for r in rows
        ]
        return ApiResponse(data=EquityCurveResponse(
            granularity="1d", account_id=account_id, points=points,
        ))

    # 1m / 5m / 15m / 1h:全部从分钟表来
    lookback_hours = hours or {"1m": 6, "5m": 24, "15m": 72, "1h": 168}.get(granularity, 24)
    cutoff = now - timedelta(hours=lookback_hours)
    stmt = (
        select(TradingAccountMinuteSnapshot)
        .where(
            TradingAccountMinuteSnapshot.account_id == account_id,
            TradingAccountMinuteSnapshot.snapshot_at >= cutoff,
        )
        .order_by(TradingAccountMinuteSnapshot.snapshot_at)
    )
    rows = (await session.execute(stmt)).scalars().all()

    if granularity == "1m":
        points = [
            EquityCurvePoint(
                timestamp=r.snapshot_at.isoformat(),
                total_asset=float(r.total_asset),
                available_cash=float(r.available_cash),
                holding_value=float(r.holding_value),
                daily_pnl=float(r.daily_pnl),
            )
            for r in rows
        ]
    else:
        # 降采样:按时间窗取最后一条
        bucket_minutes = {"5m": 5, "15m": 15, "1h": 60}.get(granularity, 1)
        buckets: dict[int, TradingAccountMinuteSnapshot] = {}
        for r in rows:
            ts = r.snapshot_at
            bucket_key = (
                int(ts.timestamp()) // (bucket_minutes * 60)
            )
            buckets[bucket_key] = r  # 时间序排序后,后写入的覆盖前者 = 取窗口最后一条
        sorted_keys = sorted(buckets.keys())
        points = [
            EquityCurvePoint(
                timestamp=buckets[k].snapshot_at.isoformat(),
                total_asset=float(buckets[k].total_asset),
                available_cash=float(buckets[k].available_cash),
                holding_value=float(buckets[k].holding_value),
                daily_pnl=float(buckets[k].daily_pnl),
            )
            for k in sorted_keys
        ]

    return ApiResponse(data=EquityCurveResponse(
        granularity=granularity, account_id=account_id, points=points,
    ))


@router.post("/daily-review/stream")
async def daily_review_stream(
    researcher_id: str = Query(..., description="研究员 ID"),
    session: AsyncSession = Depends(db_session_dependency),
) -> StreamingResponse:
    """盘后教练复盘 —— SSE 流式输出。"""
    return StreamingResponse(
        stream_daily_review(session, researcher_id=researcher_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/daily-review")
async def daily_review(
    researcher_id: str = Query(..., description="研究员 ID"),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse[DailyReviewResponse]:
    """盘后教练复盘 —— 用户侧只读取当天已生成报告，不触发 LLM。"""
    report = await get_existing_daily_review_report(
        session, researcher_id=researcher_id, trade_date=date.today(),
    )
    if report is None:
        raise HTTPException(status_code=404, detail="今日盘后教练复盘尚未生成")
    return ApiResponse(data=DailyReviewResponse(
        report_id=report.id,
        trade_date=report.trade_date.isoformat(),
        researcher_id=report.researcher_id,
        coach_report_md=report.coach_report_md,
        alpha_vs_index=report.alpha_vs_index,
        alpha_vs_sector=report.alpha_vs_sector,
        win_rate=report.win_rate,
        total_pnl=report.total_pnl,
        generated_at=report.generated_at,
        reused=True,
    ))
