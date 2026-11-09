from fastapi.testclient import TestClient

from app.main import app, create_app


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
    monkeypatch.setattr(
        "app.api.routes.health._check_database",
        lambda: ("0024_durable_job_leases", "wal"),
    )
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database_revision"] == "0024_durable_job_leases"
    assert response.json()["journal_mode"] == "wal"


def test_local_frontend_origins_are_allowed_for_api_requests(monkeypatch) -> None:
    origins = (
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    )
    monkeypatch.setattr("app.main.settings.allowed_origins", ",".join(origins))
    local_client = TestClient(create_app())

    for origin in origins:
        response = local_client.options(
            "/api/v1/catalog/services",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "authorization" in response.headers["access-control-allow-headers"]
        assert "content-type" in response.headers["access-control-allow-headers"]
