from __future__ import annotations

import pytest
from app.engine import scheduler


@pytest.mark.asyncio
async def test_page_cache_refresh_skips_while_strategy_job_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_refresh() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.modules.news_analysis.router.refresh_news_analysis_cache",
        fake_refresh,
    )
    monkeypatch.setattr(scheduler, "_strategy_job_running", True)

    await scheduler._refresh_page_data_caches()

    assert called is False
