from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openclaw.client import OpenClawTradePushClient

logger = logging.getLogger(__name__)

_SESSION_KEY = "openclaw_strategy_trade_pushes"


def queue_strategy_trade_push(
    session: AsyncSession,
    *,
    researcher: Any,
    account: Any,
    record: Any,
    amount: float,
    reason: str,
) -> bool:
    """Queue a strategy trade push for delivery after the strategy transaction commits."""
    strategy_config = getattr(researcher, "strategy_config", None)
    researcher_id = str(getattr(researcher, "id", "") or "")
    account_researcher_id = str(getattr(account, "researcher_id", "") or "")
    if not strategy_config or not researcher_id or account_researcher_id != researcher_id:
        return False

    event = _build_trade_event(
        researcher=researcher,
        account=account,
        record=record,
        amount=amount,
        reason=reason,
    )
    session.info.setdefault(_SESSION_KEY, []).append(event)
    return True


async def flush_strategy_trade_pushes(
    session: AsyncSession,
    *,
    client: OpenClawTradePushClient | None = None,
) -> int:
    events = list(session.info.get(_SESSION_KEY) or [])
    if not events:
        return 0
    session.info[_SESSION_KEY] = []

    owns_client = client is None
    push_client = client or OpenClawTradePushClient()
    delivered = 0
    try:
        for event in events:
            try:
                await push_client.push_trade(event)
                delivered += 1
            except Exception as exc:
                logger.warning(
                    "OpenClaw 策略成交推送失败: event_id=%s error=%s",
                    event.get("event_id"),
                    exc,
                )
    finally:
        if owns_client:
            await push_client.close()
    return delivered


def discard_strategy_trade_pushes(session: AsyncSession) -> None:
    session.info[_SESSION_KEY] = []


def _build_trade_event(
    *,
    researcher: Any,
    account: Any,
    record: Any,
    amount: float,
    reason: str,
) -> dict[str, Any]:
    created_at = getattr(record, "created_at", None)
    created_at_text = (
        created_at.isoformat()
        if isinstance(created_at, datetime)
        else datetime.now(tz=UTC).isoformat()
    )
    strategy_config = getattr(researcher, "strategy_config", None) or {}
    side = str(getattr(record, "side", ""))
    side_label = "买入" if side == "buy" else "卖出" if side == "sell" else side
    symbol = str(getattr(record, "symbol", ""))
    name = str(getattr(record, "name", ""))
    quantity = int(getattr(record, "quantity", 0) or 0)
    price = float(getattr(record, "price", 0.0) or 0.0)
    commission = round(float(getattr(record, "commission", 0.0) or 0.0), 2)
    amount_text = f"{round(float(amount), 2):.2f}"
    message = (
        "【极睿智投｜研究员模拟盘成交提醒】\n"
        f"研究员：{getattr(researcher, 'name', '')}\n"
        f"操作：{side_label}\n"
        f"标的：{name}（{symbol}）\n"
        f"成交：{quantity} 股 @ {price:.2f} 元\n"
        f"金额：{amount_text} 元\n"
        f"费用：{commission:.2f} 元\n"
        f"策略：{strategy_config.get('strategy_type') or 'unknown'}\n"
        f"策略依据：{reason}\n"
        "提示：以上为模拟盘策略执行信息，不构成投资建议。"
    )
    return {
        "event_type": "researcher_paper_trade",
        "event_id": str(record.id),
        "occurred_at": created_at_text,
        "source": "jirui.strategy",
        "researcher_id": str(researcher.id),
        "researcher_name": str(getattr(researcher, "name", "")),
        "strategy_type": str(strategy_config.get("strategy_type") or "unknown"),
        "account_id": str(account.id),
        "user_id": str(getattr(account, "user_id", "")),
        "reason": reason,
        "message": message,
        "trade": {
            "trade_id": str(record.id),
            "symbol": symbol,
            "name": name,
            "side": side,
            "quantity": quantity,
            "price": price,
            "amount": round(float(amount), 2),
            "commission": commission,
        },
    }
