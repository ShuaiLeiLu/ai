from fastapi.testclient import TestClient

from app.main import create_app


def test_module_routes_smoke() -> None:
    client = TestClient(create_app())

    urls = [
        "/api/v1/auth/me",
        "/api/v1/researchers",
        "/api/v1/researchers/market",
        "/api/v1/researchers/mine",
        "/api/v1/researchers/workbench/overview",
        "/api/v1/documents",
        "/api/v1/tasks",
        "/api/v1/tasks/runs",
        "/api/v1/news",
        "/api/v1/community/posts",
        "/api/v1/notes/folders",
        "/api/v1/webhooks",
        "/api/v1/billing/membership",
        "/api/v1/ecosystem/skills",
        "/api/v1/trading/account",
        "/api/v1/news-analysis/feed",
        "/api/v1/preopen/hot-news",
        "/api/v1/preopen/ai-digest",
        "/api/v1/preopen/market-indicators",
        "/api/v1/preopen/anomalies",
        "/api/v1/preopen/trends",
        "/api/v1/preopen/limit-up-ladder",
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "data" in payload


def test_tasks_dynamic_routes_smoke() -> None:
    client = TestClient(create_app())

    tasks_response = client.get("/api/v1/tasks")
    assert tasks_response.status_code == 200
    tasks_payload = tasks_response.json()
    assert tasks_payload["success"] is True
    items = tasks_payload["data"]["items"]

    if items:
        task_id = items[0].get("task_id") or items[0].get("id")
    else:
        create_response = client.post(
            "/api/v1/tasks",
            json={
                "title": "route-smoke-task",
                "researcher_id": "r_alpha",
                "schedule_type": "cron",
                "schedule_config": {"expr": "0 9 * * 1-5"},
                "prompt_template": "route smoke {{date}}",
            },
        )
        assert create_response.status_code in (200, 201)
        create_payload = create_response.json()
        assert create_payload["success"] is True
        task_id = create_payload["data"].get("task_id") or create_payload["data"].get("id")

    assert isinstance(task_id, str) and task_id

    task_runs_response = client.get(f"/api/v1/tasks/{task_id}/runs")
    assert task_runs_response.status_code == 200
    assert task_runs_response.json()["success"] is True

    activate_response = client.post(f"/api/v1/tasks/{task_id}/activate")
    assert activate_response.status_code in (200, 202)
    assert activate_response.json()["success"] is True

    pause_response = client.post(f"/api/v1/tasks/{task_id}/pause")
    assert pause_response.status_code in (200, 202)
    assert pause_response.json()["success"] is True


def test_auth_login_success() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "17607176885", "password": "Fuck@123.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
