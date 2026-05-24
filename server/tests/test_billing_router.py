from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
from app.modules.billing.router import router


@pytest.mark.asyncio
async def test_billing_power_packages_fallback_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    async def fake_user_id():
        return "u_test"

    app.dependency_overrides[get_optional_session] = no_session
    app.dependency_overrides[get_current_user_id] = fake_user_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/billing/battery/packages")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 4
    assert payload["items"][1]["name"] == "5,000 算力"
    assert payload["items"][1]["battery_count"] == 5000
