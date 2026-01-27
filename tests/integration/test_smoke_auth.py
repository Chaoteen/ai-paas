import pytest
import httpx

@pytest.mark.integration
def test_opa_health():
    import os
    import httpx
    opa_url = os.getenv("OPA_URL", "http://127.0.0.1:8181").rstrip("/")
    r = httpx.get(f"{opa_url}/health", timeout=3.0)
    assert r.status_code == 200, r.text
