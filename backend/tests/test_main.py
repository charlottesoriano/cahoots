from fastapi.testclient import TestClient

from database.database import get_session
from main import app


client = TestClient(app)


def test_cors_allows_configured_origin_without_credentials():
    response = client.get("/", headers={"Origin": "https://app.example.com"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://app.example.com"
    )
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unconfigured_origin():
    response = client.get("/", headers={"Origin": "https://attacker.example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_configured_origin_and_methods():
    response = client.options(
        "/",
        headers={
            "Origin": "https://admin.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://admin.example.com"
    )
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers


def test_database_health_endpoint_returns_server_version():
    class Result:
        def scalar(self):
            return "PostgreSQL test version"

    class Session:
        async def execute(self, statement):
            assert str(statement) == "SELECT version();"
            return Result()

    async def override_session():
        yield Session()

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/test-db-connection")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "connected",
        "postgres_version": "PostgreSQL test version",
    }


def test_database_health_endpoint_reports_connection_errors():
    class FailingSession:
        async def execute(self, statement):
            raise RuntimeError("database unavailable")

    async def override_session():
        yield FailingSession()

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/test-db-connection")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "message": "database unavailable",
    }
