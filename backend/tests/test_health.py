from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_versioned_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["service"] == "QueueLess API"


def test_readiness_checks_database_without_external_services(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.health._check_database", lambda: None)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_preview_origin_is_allowed_for_api_requests() -> None:
    response = client.options(
        "/api/v1/catalog/services",
        headers={
            "Origin": "http://localhost:4173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4173"
    assert "authorization" in response.headers["access-control-allow-headers"]
    assert "content-type" in response.headers["access-control-allow-headers"]
