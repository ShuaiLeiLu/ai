from fastapi.testclient import TestClient

from app.main import create_app


def test_preopen_endpoints_smoke_and_structure() -> None:
    client = TestClient(create_app())

    urls = [
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


def test_preopen_data_container_type() -> None:
    client = TestClient(create_app())

    hot_news = client.get("/api/v1/preopen/hot-news").json()["data"]
    assert isinstance(hot_news, dict)
    assert isinstance(hot_news["items"], list)
    assert isinstance(hot_news["total"], int)

    ai_digest = client.get("/api/v1/preopen/ai-digest").json()["data"]
    assert isinstance(ai_digest, dict)
    assert "headline" in ai_digest

    market_indicators = client.get("/api/v1/preopen/market-indicators").json()["data"]
    assert isinstance(market_indicators, dict)
    assert isinstance(market_indicators["items"], list)
    assert isinstance(market_indicators["total"], int)

    anomalies = client.get("/api/v1/preopen/anomalies").json()["data"]
    assert isinstance(anomalies, dict)
    assert isinstance(anomalies["tail_session_moves"], list)
    assert isinstance(anomalies["severe_volatility"], list)

    trends = client.get("/api/v1/preopen/trends").json()["data"]
    assert isinstance(trends, dict)
    assert isinstance(trends["series"], list)

    ladder = client.get("/api/v1/preopen/limit-up-ladder").json()["data"]
    assert isinstance(ladder, dict)
    assert isinstance(ladder["items"], list)
    assert isinstance(ladder["total"], int)
