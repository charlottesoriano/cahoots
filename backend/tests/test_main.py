from fastapi.testclient import TestClient

import main
from database.database import get_session


client = TestClient(main.app)


def test_health_check():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_preflight_allows_a_configured_origin_without_credentials():
    response = client.options(
        "/",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_rejects_an_unconfigured_origin():
    response = client.options(
        "/",
        headers={
            "Origin": "https://attacker.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_database_connection_endpoint_returns_the_server_version():
    class Result:
        def scalar(self):
            return "PostgreSQL test version"

    class Session:
        async def execute(self, statement):
            assert str(statement) == "SELECT version();"
            return Result()

    async def override_session():
        yield Session()

    main.app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/test-db-connection")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "connected",
        "postgres_version": "PostgreSQL test version",
    }


def test_database_connection_endpoint_reports_driver_errors():
    class FailingSession:
        async def execute(self, _statement):
            raise RuntimeError("database unavailable")

    async def override_session():
        yield FailingSession()

    main.app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/test-db-connection")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "message": "database unavailable",
    }
