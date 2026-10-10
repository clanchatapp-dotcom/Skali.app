"""Smoke test to verify backend starts after livekit dependency fix
and core auth + /api/livekit/token route are reachable."""
import os, uuid, requests, pytest

BASE_URL = "http://localhost:8001"


def test_import_server_module():
    # Ensures `from livekit import api as lk_api` resolves at import time
    import importlib, sys
    sys.path.insert(0, "/app/backend")
    mod = importlib.import_module("server")
    assert hasattr(mod, "app")


def test_health_endpoint():
    r = requests.get(f"{BASE_URL}/api/", timeout=10)
    assert r.status_code == 200


@pytest.fixture(scope="module")
def auth_token():
    email = f"test+{uuid.uuid4().hex[:8]}@example.com"
    password = "Testpass123!"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": password, "name": "Smoke Tester",
        "dob": "2000-01-01"
    }, timeout=15)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data and data["user"]["email"] == email
    # Verify login works too
    r2 = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email, "password": password
    }, timeout=15)
    assert r2.status_code == 200, f"login failed: {r2.status_code} {r2.text}"
    assert "access_token" in r2.json()
    return r2.json()["access_token"]


def test_livekit_token_route_reachable(auth_token):
    # The import crash would manifest as 502/no-response or 500 with ImportError.
    # Since LIVEKIT_API_KEY/SECRET are not set locally, 500 'LiveKit not configured'
    # is expected and acceptable — it proves the module imported successfully.
    r = requests.post(
        f"{BASE_URL}/api/livekit/token",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"room": "smoke-test-room"},
        timeout=15,
    )
    assert r.status_code in (200, 400, 500), f"unexpected status: {r.status_code} {r.text}"
    if r.status_code == 500:
        body = r.text.lower()
        assert "not configured" in body or "livekit" in body, f"unexpected 500 body: {r.text}"
        assert "modulenotfounderror" not in body and "no module named" not in body
