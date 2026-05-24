from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.news_analysis import router as news_router
from app.modules.news_analysis.schemas import NewsAiPanel


def _fallback_panels() -> list[NewsAiPanel]:
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    return [
        NewsAiPanel(
            panel_key="24h_digest",
            title="24小时热讯解读",
            summary="涨停池实时回补。",
            highlights=["涨停家数回升"],
            confidence=0.88,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="hotspot_tracking",
            title="热点追踪",
            summary="半导体扩散。",
            highlights=["半导体涨停较多"],
            confidence=0.85,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="macro_impact",
            title="宏观影响",
            summary="市场中性偏强。",
            highlights=["强势股增加"],
            confidence=0.82,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="stock_interpretation",
            title="个股解读",
            summary="关注最高连板。",
            highlights=["龙头封单稳定"],
            confidence=0.86,
            updated_at=now,
        ),
    ]


@pytest.mark.asyncio
async def test_ai_panels_fall_back_when_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = _fallback_panels()

    async def fail_llm() -> list[NewsAiPanel]:
        raise RuntimeError("llm unavailable")

    async def fake_run_sync(fetch: object) -> list[NewsAiPanel]:
        assert callable(fetch)
        return fallback

    monkeypatch.setattr(news_router.service, "generate_ai_panels_with_llm", fail_llm)
    monkeypatch.setattr(news_router.service, "list_ai_panels", lambda: fallback)
    monkeypatch.setattr(news_router, "run_sync", fake_run_sync)

    response = await news_router.ai_panels()

    assert response.data.total == 4
    assert response.data.items[0].panel_key == "24h_digest"
    assert response.data.items[1].summary == "半导体扩散。"
