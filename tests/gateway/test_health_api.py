from fastapi.testclient import TestClient

from gateway.main import app


client = TestClient(app)


def test_health_api_returns_200():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_api_returns_json():
    response = client.get("/api/health")
    assert response.headers["content-type"].startswith("application/json")