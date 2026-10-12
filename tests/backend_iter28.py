"""Iteration 28 backend tests for Skali rearrangement: streamers, unread.activity, live gating."""
import os, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://open-to-workspace.preview.emergentagent.com").rstrip("/")

def login(email, pw="Test1234!"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]

@pytest.fixture(scope="module")
def tester_token():
    return login("tester@skali.test")

@pytest.fixture(scope="module")
def viewer_token():
    return login("viewer@skali.test")

def _h(t):
    return {"Authorization": f"Bearer {t}"}

def test_streamers_shape(tester_token):
    r = requests.get(f"{BASE}/api/streamers", headers=_h(tester_token), timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "live" in data and "creators" in data, data
    assert isinstance(data["live"], list) and isinstance(data["creators"], list)
    # tester should be in creators list
    handles = [c.get("handle") for c in data["creators"]]
    assert any("thisismajorofficial" in (h or "") for h in handles), f"tester creator missing: {handles}"

def test_unread_includes_activity(tester_token):
    r = requests.get(f"{BASE}/api/unread", headers=_h(tester_token), timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "activity" in data, data

def test_live_start_stream_blocked_for_viewer(viewer_token):
    r = requests.post(f"{BASE}/api/live/start", headers=_h(viewer_token), json={"kind": "stream", "title": "x"}, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"

def test_live_start_story_passes_gate(viewer_token):
    # LiveKit not configured; expect 500 with configuration message (gate passed)
    r = requests.post(f"{BASE}/api/live/start", headers=_h(viewer_token), json={"kind": "story", "title": "x"}, timeout=15)
    assert r.status_code in (200, 500, 503), f"unexpected: {r.status_code} {r.text[:200]}"
    if r.status_code != 200:
        assert "livekit" in r.text.lower() or "not configured" in r.text.lower(), r.text[:300]

def test_interests_endpoint(viewer_token):
    r = requests.get(f"{BASE}/api/interests", headers=_h(viewer_token), timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    # typically {interests: [...]}, allow either dict or list
    assert isinstance(data, (dict, list))
