import os

from fastapi.testclient import TestClient


def test_runtime_bootstrap_memory_mode():
    os.environ["AI_PAAS_USE_POSTGRES"] = "false"

    from main import app

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["runtime_mode"] == "memory"


def test_runtime_info_endpoint():
    os.environ["AI_PAAS_USE_POSTGRES"] = "false"

    from main import app

    with TestClient(app) as client:
        resp = client.get("/runtime/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] if "ok" in body else True
        assert body["runtime_mode"] in {"memory", "postgres"}