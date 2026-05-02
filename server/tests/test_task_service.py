from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.modules.tasks.service import TaskService


@pytest.mark.asyncio
async def test_trade_day_check_uses_market_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    trade_days = {date(2026, 5, 5), date(2026, 5, 7)}

    def fake_recent_trade_dates(end_date: date, count: int) -> list[date]:
        eligible = sorted(day for day in trade_days if day <= end_date)
        return eligible[-count:]

    monkeypatch.setattr("app.modules.tasks.service.list_recent_trade_dates", fake_recent_trade_dates)

    service = TaskService()

    assert await service._is_trade_day(datetime(2026, 5, 6, 9, 30, tzinfo=UTC)) is False
    assert await service._shift_trade_day(datetime(2026, 5, 6, 9, 30, tzinfo=UTC), -1) == date(2026, 5, 5)
    assert await service._shift_trade_day(datetime(2026, 5, 6, 9, 30, tzinfo=UTC), 1) == date(2026, 5, 7)


@pytest.mark.asyncio
async def test_finish_run_persists_scheduler_next_run_at(monkeypatch: pytest.MonkeyPatch) -> None:
    next_run_at = datetime(2026, 5, 7, 9, 30, tzinfo=UTC)

    class FakeSession:
        async def flush(self) -> None:
            pass

    monkeypatch.setattr(
        "app.engine.scheduler.get_orchestration_task_next_run_at",
        lambda task_id: next_run_at if task_id == "task_1" else None,
    )

    task = SimpleNamespace(
        id="task_1",
        lifecycle_status="ACTIVE",
        last_run_at=None,
        last_run_status=None,
        next_run_at=datetime(2026, 5, 6, 9, 30, tzinfo=UTC),
    )
    run = SimpleNamespace(status="RUNNING", end_time=None, result_type="none", error_message=None)

    await TaskService()._finish_run(FakeSession(), task, run, "SUCCESS", "message", None)  # type: ignore[arg-type]

    assert task.next_run_at == next_run_at
