from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _assert_success_payload(response) -> dict:
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    return payload


def _assert_sorted_desc_by_datetime_then_id(items: list[dict], datetime_field: str, id_field: str) -> None:
    sort_key = lambda item: (datetime.fromisoformat(item[datetime_field]), item[id_field])
    expected = sorted(items, key=sort_key, reverse=True)
    assert items == expected


def test_webhooks_toggle_delete_and_not_found() -> None:
    client = TestClient(create_app())

    create_payload = {
        "name": f"ops-hook-{uuid4().hex[:8]}",
        "url": "https://example.com/webhook",
        "secret": "secret123456",
    }
    created = _assert_success_payload(client.post("/api/v1/webhooks", json=create_payload))["data"]
    webhook_id = created["webhook_id"]
    assert created["enabled"] is True

    toggled = _assert_success_payload(
        client.patch(
            f"/api/v1/webhooks/{webhook_id}/toggle",
            json={"enabled": False},
        )
    )["data"]
    assert toggled["webhook_id"] == webhook_id
    assert toggled["enabled"] is False

    deleted = _assert_success_payload(client.delete(f"/api/v1/webhooks/{webhook_id}"))["data"]
    assert deleted["webhook_id"] == webhook_id

    current_items = _assert_success_payload(client.get("/api/v1/webhooks"))["data"]["items"]
    assert all(item["webhook_id"] != webhook_id for item in current_items)

    missing_id = "wh_missing"
    patch_missing = client.patch(f"/api/v1/webhooks/{missing_id}/toggle", json={"enabled": True})
    assert patch_missing.status_code == 404
    assert patch_missing.json()["success"] is False

    delete_missing = client.delete(f"/api/v1/webhooks/{missing_id}")
    assert delete_missing.status_code == 404
    assert delete_missing.json()["success"] is False


def test_trading_positions_records_order_and_limit() -> None:
    client = TestClient(create_app())

    positions = _assert_success_payload(client.get("/api/v1/trading/positions"))["data"]["items"]
    expected_positions = sorted(
        positions,
        key=lambda item: (abs(item["pnl"]), item["pnl"], item["symbol"]),
        reverse=True,
    )
    assert positions == expected_positions

    default_records = _assert_success_payload(client.get("/api/v1/trading/records"))["data"]["items"]
    assert len(default_records) <= 20
    _assert_sorted_desc_by_datetime_then_id(default_records, "created_at", "trade_id")

    limited_records = _assert_success_payload(client.get("/api/v1/trading/records", params={"limit": 1}))["data"][
        "items"
    ]
    assert len(limited_records) <= 1
    _assert_sorted_desc_by_datetime_then_id(limited_records, "created_at", "trade_id")

    over_limit = client.get("/api/v1/trading/records", params={"limit": 101})
    assert over_limit.status_code == 422


def test_ecosystem_skills_installed_filter() -> None:
    client = TestClient(create_app())

    all_items = _assert_success_payload(client.get("/api/v1/ecosystem/skills"))["data"]["items"]
    all_ids = {item["skill_id"] for item in all_items}

    installed_items = _assert_success_payload(
        client.get("/api/v1/ecosystem/skills", params={"installed": True})
    )["data"]["items"]
    assert all(item["installed"] is True for item in installed_items)

    uninstalled_items = _assert_success_payload(
        client.get("/api/v1/ecosystem/skills", params={"installed": False})
    )["data"]["items"]
    assert all(item["installed"] is False for item in uninstalled_items)

    filtered_ids = {item["skill_id"] for item in installed_items + uninstalled_items}
    assert filtered_ids.issubset(all_ids)


def test_billing_battery_ledger_limit_and_validation() -> None:
    client = TestClient(create_app())

    default_ledger = _assert_success_payload(client.get("/api/v1/billing/battery/ledger"))["data"]["items"]
    assert len(default_ledger) <= 50
    _assert_sorted_desc_by_datetime_then_id(default_ledger, "created_at", "item_id")

    limited_ledger = _assert_success_payload(
        client.get("/api/v1/billing/battery/ledger", params={"limit": 1})
    )["data"]["items"]
    assert len(limited_ledger) <= 1
    _assert_sorted_desc_by_datetime_then_id(limited_ledger, "created_at", "item_id")

    over_limit = client.get("/api/v1/billing/battery/ledger", params={"limit": 201})
    assert over_limit.status_code == 422
