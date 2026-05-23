from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dependency
from app.modules.system.service import SystemService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["system"])
service = SystemService()


@router.get("/health")
async def health_check():
    return service.get_health()


@router.get("/live")
async def live_check():
    return {"status": "alive"}


@router.get("/skills/runs")
async def list_skill_runs(
    skill_name: str | None = Query(None, description="按 skill 名筛选"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse[list]:
    """最近的 skill 执行日志(评估用)。"""
    from app.models.preopen import SkillRunLog

    stmt = select(SkillRunLog).order_by(SkillRunLog.created_at.desc()).limit(limit)
    if skill_name:
        stmt = stmt.where(SkillRunLog.skill_name == skill_name)
    rows = (await session.execute(stmt)).scalars().all()
    return ApiResponse(data=[
        {
            "id": r.id,
            "skill_name": r.skill_name,
            "chain_kind": r.chain_kind,
            "trade_date": r.trade_date.isoformat() if r.trade_date else None,
            "success": r.success,
            "duration_ms": r.duration_ms,
            "narrative_len": r.narrative_len,
            "error": r.error,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ])


@router.get("/skills/summary")
async def skill_summary(
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse[list]:
    """按 skill 聚合统计:平均耗时、失败率、调用次数。"""
    from app.models.preopen import SkillRunLog

    stmt = select(
        SkillRunLog.skill_name,
        func.count(SkillRunLog.id).label("call_count"),
        func.avg(SkillRunLog.duration_ms).label("avg_duration_ms"),
        func.avg(SkillRunLog.narrative_len).label("avg_narrative_len"),
        func.sum(
            func.cast(~SkillRunLog.success, type_=func.text("int").type)
        ).label("fail_count"),
    ).group_by(SkillRunLog.skill_name)
    try:
        rows = (await session.execute(stmt)).all()
    except Exception:
        # 部分 DB 后端不支持 ~bool casting,降级到全量 count + 分组失败计数
        rows = []
    summary = [
        {
            "skill_name": r.skill_name,
            "call_count": int(r.call_count or 0),
            "avg_duration_ms": int(r.avg_duration_ms or 0),
            "avg_narrative_len": int(r.avg_narrative_len or 0),
            "fail_count": int(r.fail_count or 0),
        }
        for r in rows
    ]
    return ApiResponse(data=summary)
