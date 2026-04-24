from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.researchers.schemas import (
    WorkbenchHiredResearcher,
    WorkbenchHotDocument,
    WorkbenchPublicRankItem,
)
from app.modules.researchers.service import ResearcherService, _workbench_overview_cache


@pytest.mark.asyncio
async def test_async_get_workbench_overview_combines_main_entry_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workbench_overview_cache.clear()
    service = ResearcherService()

    async def fake_hired(*_args: object, **_kwargs: object) -> list[WorkbenchHiredResearcher]:
        return [
            WorkbenchHiredResearcher(
                researcher_id="r_b08dba104a",
                avatar_url=None,
                name="小市值轮动",
                summary="小市值策略研究员",
                status="active",
                tags=["小市值"],
                today_yield=0.012,
                win_rate_30d=0.56,
                level="LV.2",
            )
        ]

    async def fake_hot_documents(*_args: object, **_kwargs: object) -> list[WorkbenchHotDocument]:
        return [
            WorkbenchHotDocument(
                id="doc_1",
                title="今日复盘",
                summary="市场情绪回暖，小市值组合继续观察。",
                researcher_name="小市值轮动",
                create_time=datetime(2026, 4, 24, 9, 30),
                view_count=120,
                comment_count=3,
            )
        ]

    async def fake_rankings(*_args: object, **_kwargs: object) -> list[WorkbenchPublicRankItem]:
        return [
            WorkbenchPublicRankItem(
                researcher_id="r_b08dba104a",
                name="小市值轮动",
                total_asset=1_008_000.0,
                today_yield_rate=0.008,
                month_yield_rate=0.018,
                risk_note="模拟盘",
            )
        ]

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "async_list_workbench_hot_documents", fake_hot_documents)
    monkeypatch.setattr(service, "async_list_public_rankings", fake_rankings)

    overview = await service.async_get_workbench_overview(object(), "u_demo", sort_by="today")  # type: ignore[arg-type]

    assert [item.name for item in overview.hired] == ["小市值轮动"]
    assert [item.title for item in overview.hot_documents] == ["今日复盘"]
    assert [item.total_asset for item in overview.rankings] == [1_008_000.0]
    assert overview.risk_disclaimer
    assert overview.partial_failures == []


@pytest.mark.asyncio
async def test_async_get_workbench_overview_keeps_page_usable_when_optional_sections_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workbench_overview_cache.clear()
    service = ResearcherService()

    async def fake_hired(*_args: object, **_kwargs: object) -> list[WorkbenchHiredResearcher]:
        return []

    async def fail_hot_documents(*_args: object, **_kwargs: object) -> list[WorkbenchHotDocument]:
        raise RuntimeError("document source unavailable")

    async def fail_rankings(*_args: object, **_kwargs: object) -> list[WorkbenchPublicRankItem]:
        raise RuntimeError("ranking source unavailable")

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "async_list_workbench_hot_documents", fail_hot_documents)
    monkeypatch.setattr(service, "async_list_public_rankings", fail_rankings)

    overview = await service.async_get_workbench_overview(object(), "u_demo", sort_by="today")  # type: ignore[arg-type]

    assert overview.hired == []
    assert overview.hot_documents == []
    assert overview.rankings == []
    assert overview.partial_failures == ["hot_documents", "rankings"]
