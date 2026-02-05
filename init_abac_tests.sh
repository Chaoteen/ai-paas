#!/usr/bin/env bash
set -e

# ========= 配置区 =========
REPO_DIR="$HOME/work/ai-paas"
# =========================

if [ ! -d "$REPO_DIR" ]; then
  echo "❌ Repo directory not found: $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"
echo "📁 Working directory: $(pwd)"

echo "🚀 Initializing AI PaaS ABAC test skeleton..."

# ---------
# 1. Directory layout
# ---------
mkdir -p tests/integration tests/abac

# ---------
# 2. pytest.ini (force pytest to ONLY scan tests/)
# ---------
cat > pytest.ini << 'PYTEST'
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    integration: integration tests (requires running services)
    unit: unit tests
addopts = -ra
PYTEST

# ---------
# 3. conftest.py
# ---------
cat > tests/conftest.py << 'CONFTEST'
import os
import pytest
import httpx

def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v

@pytest.fixture(scope="session")
def base_url() -> str:
    return _env("AI_PAAS_BASE_URL")

@pytest.fixture(scope="session")
def tenant_a() -> str:
    return os.getenv("AI_PAAS_TENANT_A", "tenant_a")

@pytest.fixture(scope="session")
def tenant_b() -> str:
    return os.getenv("AI_PAAS_TENANT_B", "tenant_b")

@pytest.fixture(scope="session")
def token_tenant_a_admin() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_A_ADMIN")

@pytest.fixture(scope="session")
def token_tenant_b_user() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_B_USER")

@pytest.fixture
def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)
CONFTEST

# ---------
# 4. Smoke + Auth integration test
# ---------
cat > tests/integration/test_smoke_auth.py << 'SMOKE'
import pytest
import httpx

def _auth_headers(token: str, tenant: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant,
    }

@pytest.mark.integration
def test_healthz(client: httpx.Client):
    r = client.get("/healthz")
    assert r.status_code in (200, 204), r.text

@pytest.mark.integration
def test_unauthorized_without_token(client: httpx.Client, tenant_a: str):
    r = client.get("/api/me", headers={"X-Tenant-ID": tenant_a})
    assert r.status_code in (401, 403), r.text

@pytest.mark.integration
def test_authorized_with_token(
    client: httpx.Client, tenant_a: str, token_tenant_a_admin: str
):
    r = client.get("/api/me", headers=_auth_headers(token_tenant_a_admin, tenant_a))
    assert r.status_code == 200, r.text
SMOKE

echo "✅ Test skeleton created successfully."
echo
echo "Next steps:"
echo "1) export AI_PAAS_BASE_URL / tokens"
echo "2) pytest -q --collect-only"
echo "3) pytest -m integration"
