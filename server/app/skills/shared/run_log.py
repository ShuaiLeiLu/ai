"""SkillRunLog 落库辅助。"""
from __future__ import annotations

import logging
from datetime import date
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preopen import SkillRunLog
from app.skills.base import SkillResult

logger = logging.getLogger(__name__)


async def write_skill_run_logs(
    session: AsyncSession,
    *,
    chain_kind: str,
    trade_date: date,
    outputs: dict[str, SkillResult],
    researcher_id: str | None = None,
) -> None:
    """把 chain 全部 skill 的结果落 skill_run_logs。

    失败不抛,只 warn:这是评估用的旁路日志,不应阻断主流程。
    """
    try:
        for name, r in outputs.items():
            log = SkillRunLog(
                id=f"srl_{uuid4().hex[:16]}",
                skill_name=name,
                chain_kind=chain_kind,
                trade_date=trade_date,
                researcher_id=researcher_id,
                success=r.success,
                duration_ms=r.duration_ms,
                tokens_used=r.tokens_used,
                narrative_len=len(r.narrative or ""),
                error=(r.error or "")[:500] if r.error else None,
            )
            session.add(log)
        await session.flush()
    except Exception:
        logger.exception("write_skill_run_logs 失败,忽略")
