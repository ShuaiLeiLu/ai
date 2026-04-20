from fastapi.testclient import TestClient

from app.main import create_app


def _assert_success_payload(response) -> dict:
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    return payload


def test_news_analysis_endpoints_smoke() -> None:
    client = TestClient(create_app())
    urls = [
        "/api/v1/news-analysis/feed",
        "/api/v1/news-analysis/ai-panels",
        "/api/v1/news-analysis/hot-stocks",
        "/api/v1/news-analysis/hot-news",
        "/api/v1/news-analysis/by-stock/000001.SZ/summary",
    ]

    for url in urls:
        response = client.get(url)
        _assert_success_payload(response)


def test_news_analysis_structure_contract() -> None:
    client = TestClient(create_app())

    feed_data = _assert_success_payload(client.get("/api/v1/news-analysis/feed"))["data"]
    assert isinstance(feed_data, dict)
    assert isinstance(feed_data["items"], list)
    assert isinstance(feed_data["total"], int)

    ai_panels_data = _assert_success_payload(client.get("/api/v1/news-analysis/ai-panels"))["data"]
    assert isinstance(ai_panels_data, dict)
    assert isinstance(ai_panels_data["items"], list)
    assert isinstance(ai_panels_data["total"], int)
    panel_keys = {item["panel_key"] for item in ai_panels_data["items"]}
    assert {"24h_digest", "hotspot_tracking", "macro_impact", "stock_interpretation"}.issubset(
        panel_keys
    )

    hot_stocks_data = _assert_success_payload(client.get("/api/v1/news-analysis/hot-stocks"))["data"]
    assert isinstance(hot_stocks_data, dict)
    assert isinstance(hot_stocks_data["items"], list)

    hot_news_data = _assert_success_payload(client.get("/api/v1/news-analysis/hot-news"))["data"]
    assert isinstance(hot_news_data, dict)
    assert isinstance(hot_news_data["items"], list)

    summary_data = _assert_success_payload(
        client.get("/api/v1/news-analysis/by-stock/000001.SZ/summary")
    )["data"]
    assert isinstance(summary_data, dict)
    assert "stock_code" in summary_data
    assert "conclusion" in summary_data
    assert "related_news_count" in summary_data
    assert "sentiment_distribution" in summary_data
