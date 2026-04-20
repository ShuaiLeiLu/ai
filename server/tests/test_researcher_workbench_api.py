from fastapi.testclient import TestClient

from app.main import create_app


def _assert_success_payload(response) -> dict:
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    return payload


def _assert_list_response_container(data: dict) -> None:
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


def test_researcher_workbench_endpoints_smoke() -> None:
    client = TestClient(create_app())
    urls = [
        "/api/v1/researchers/workbench/hired",
        "/api/v1/researchers/workbench/hot-documents",
        "/api/v1/researchers/workbench/public-rank",
        "/api/v1/researchers/workbench/overview",
    ]

    for url in urls:
        response = client.get(url)
        _assert_success_payload(response)


def test_researcher_workbench_list_response_contract() -> None:
    client = TestClient(create_app())

    hired_data = _assert_success_payload(client.get("/api/v1/researchers/workbench/hired"))["data"]
    _assert_list_response_container(hired_data)

    hot_documents_data = _assert_success_payload(
        client.get("/api/v1/researchers/workbench/hot-documents")
    )["data"]
    _assert_list_response_container(hot_documents_data)

    public_rank_data = _assert_success_payload(
        client.get("/api/v1/researchers/workbench/public-rank", params={"sort_by": "today"})
    )["data"]
    _assert_list_response_container(public_rank_data)


def test_researcher_workbench_public_rank_sort_by_today_and_month() -> None:
    client = TestClient(create_app())

    for sort_by in ("today", "month"):
        response = client.get("/api/v1/researchers/workbench/public-rank", params={"sort_by": sort_by})
        data = _assert_success_payload(response)["data"]
        _assert_list_response_container(data)


def test_researcher_workbench_overview_structure_contract() -> None:
    client = TestClient(create_app())
    data = _assert_success_payload(client.get("/api/v1/researchers/workbench/overview"))["data"]

    assert isinstance(data, dict)
    assert "hired" in data
    assert "hot_documents" in data
    assert "rankings" in data
    assert "quick_actions" in data
    assert "risk_disclaimer" in data
    assert "partial_failures" in data
