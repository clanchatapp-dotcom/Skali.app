"""
Backend tests for the Twitch-style tiered live streaming rework.
Covers: auth, categories, start/visibility/gating, join, end, past streams, regressions.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://clan-live.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

HOST_EMAIL = "streamer@test.com"
HOST_PASS = "test1234"
HOST_HANDLE = "tomstreamer"

VIEWER_EMAIL = "viewer@test.com"
VIEWER_PASS = "test1234"
VIEWER_HANDLE = "vickyviewer"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def host_token():
    return _login(HOST_EMAIL, HOST_PASS)


@pytest.fixture(scope="module")
def viewer_token():
    return _login(VIEWER_EMAIL, VIEWER_PASS)


@pytest.fixture(scope="module")
def extra_follower():
    """Register a disposable follower user and have them follow host."""
    email = f"TEST_follower_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "test1234",
        "name": f"TF {uuid.uuid4().hex[:4]}",
        "dob": "1995-01-01",
    }, timeout=30)
    assert r.status_code in (200, 201), f"register follower failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or _login(email, "test1234")
    # follow host
    r2 = requests.post(f"{API}/follow/{HOST_HANDLE}", headers=_h(tok), timeout=30)
    assert r2.status_code == 200, f"follow failed: {r2.status_code} {r2.text}"
    return {"email": email, "token": tok, "status": r2.json().get("status")}


@pytest.fixture(autouse=True)
def _cleanup_streams(host_token):
    """Ensure no leftover active stream for host before each test."""
    yield
    # best-effort: end any live streams by host
    try:
        r = requests.get(f"{API}/live", headers=_h(host_token), timeout=15)
        if r.status_code == 200:
            for s in r.json():
                if s.get("host", {}).get("handle") == HOST_HANDLE and s.get("status") == "live":
                    requests.post(f"{API}/live/{s['id']}/end", headers=_h(host_token), timeout=15)
    except Exception:
        pass


# ---------- Auth ----------
def test_auth_login_host_and_viewer(host_token, viewer_token):
    assert isinstance(host_token, str) and len(host_token) > 10
    assert isinstance(viewer_token, str) and len(viewer_token) > 10


def test_me_regression(host_token):
    r = requests.get(f"{API}/me", headers=_h(host_token), timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("handle") == HOST_HANDLE


# ---------- Categories ----------
def test_categories_shape(viewer_token):
    r = requests.get(f"{API}/live/categories", headers=_h(viewer_token), timeout=15)
    assert r.status_code == 200
    data = r.json()
    keys = {c["key"] for c in data}
    assert keys == {"gaming", "just_chatting", "music", "creative", "irl", "sports"}
    for c in data:
        assert "label" in c and "live" in c
        assert isinstance(c["live"], int)


def test_categories_live_count_increments(host_token, viewer_token):
    # baseline
    r0 = requests.get(f"{API}/live/categories", headers=_h(viewer_token), timeout=15).json()
    gaming_before = next(c["live"] for c in r0 if c["key"] == "gaming")

    # start gaming public stream
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "gaming", "title": "TEST gaming", "save": False},
                          timeout=15)
    assert start.status_code == 200, start.text
    live_id = start.json()["id"]
    try:
        r1 = requests.get(f"{API}/live/categories", headers=_h(viewer_token), timeout=15).json()
        gaming_after = next(c["live"] for c in r1 if c["key"] == "gaming")
        assert gaming_after == gaming_before + 1, f"expected +1, got {gaming_before} -> {gaming_after}"
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


# ---------- Start ----------
def test_live_start_public_returns_token(host_token):
    r = requests.post(f"{API}/live/start", headers=_h(host_token),
                      json={"audience": "public", "category": "gaming", "title": "TEST", "save": False},
                      timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("id", "room", "server_url", "participant_token", "category"):
        assert k in data, f"missing {k}"
    assert data["category"] == "gaming"
    assert data["audience"] == "public"
    assert data["participant_token"].count(".") == 2  # JWT shape
    requests.post(f"{API}/live/{data['id']}/end", headers=_h(host_token), timeout=15)


def test_second_start_ends_first(host_token):
    r1 = requests.post(f"{API}/live/start", headers=_h(host_token),
                       json={"audience": "public", "category": "music", "title": "TEST first"},
                       timeout=15)
    assert r1.status_code == 200
    first_id = r1.json()["id"]

    r2 = requests.post(f"{API}/live/start", headers=_h(host_token),
                       json={"audience": "public", "category": "irl", "title": "TEST second"},
                       timeout=15)
    assert r2.status_code == 200
    second_id = r2.json()["id"]
    assert first_id != second_id

    # first should no longer appear in /live
    live = requests.get(f"{API}/live", headers=_h(host_token), timeout=15).json()
    ids_live = {s["id"] for s in live}
    assert first_id not in ids_live
    assert second_id in ids_live

    requests.post(f"{API}/live/{second_id}/end", headers=_h(host_token), timeout=15)


# ---------- Public discovery ----------
def test_public_visible_to_non_follower(host_token, viewer_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "gaming", "title": "TEST public"},
                          timeout=15)
    assert start.status_code == 200
    live_id = start.json()["id"]
    try:
        all_live = requests.get(f"{API}/live", headers=_h(viewer_token), timeout=15)
        assert all_live.status_code == 200
        ids = {s["id"] for s in all_live.json()}
        assert live_id in ids, "public stream must be visible to non-follower viewer"

        # category filter
        gaming_live = requests.get(f"{API}/live?category=gaming", headers=_h(viewer_token), timeout=15)
        assert gaming_live.status_code == 200
        g_ids = {s["id"] for s in gaming_live.json()}
        assert live_id in g_ids
        for s in gaming_live.json():
            assert s.get("category") == "gaming"

        # filter mismatch
        music_live = requests.get(f"{API}/live?category=music", headers=_h(viewer_token), timeout=15).json()
        assert live_id not in {s["id"] for s in music_live}
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


# ---------- Private gating ----------
def test_followers_only_hidden_from_non_follower(host_token, viewer_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "followers", "category": "just_chatting", "title": "TEST f-only"},
                          timeout=15)
    assert start.status_code == 200
    live_id = start.json()["id"]
    try:
        # non-follower viewer should NOT see it
        v_list = requests.get(f"{API}/live", headers=_h(viewer_token), timeout=15).json()
        assert live_id not in {s["id"] for s in v_list}, "non-follower should NOT see followers-only"

        # host sees own
        h_list = requests.get(f"{API}/live", headers=_h(host_token), timeout=15).json()
        assert live_id in {s["id"] for s in h_list}

        # non-follower cannot join
        j = requests.post(f"{API}/live/{live_id}/join", headers=_h(viewer_token), timeout=15)
        assert j.status_code == 403, f"expected 403 got {j.status_code} {j.text}"
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


def test_followers_only_visible_to_follower(host_token, extra_follower):
    # Only applicable if follow was auto-approved
    if extra_follower["status"] != "approved":
        pytest.skip("host account is private; follow is pending — skipping follower-visibility check")

    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "followers", "category": "music", "title": "TEST f-visible"},
                          timeout=15)
    assert start.status_code == 200
    live_id = start.json()["id"]
    try:
        f_list = requests.get(f"{API}/live", headers=_h(extra_follower["token"]), timeout=15).json()
        assert live_id in {s["id"] for s in f_list}, "approved follower should see followers-only stream"

        j = requests.post(f"{API}/live/{live_id}/join", headers=_h(extra_follower["token"]), timeout=15)
        assert j.status_code == 200, j.text
        jd = j.json()
        assert jd.get("is_host") is False
        assert "participant_token" in jd
        assert jd.get("category") == "music"
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


def test_inner_only_hidden_from_non_inner(host_token, viewer_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "inner", "category": "creative", "title": "TEST inner"},
                          timeout=15)
    assert start.status_code == 200
    live_id = start.json()["id"]
    try:
        v_list = requests.get(f"{API}/live", headers=_h(viewer_token), timeout=15).json()
        assert live_id not in {s["id"] for s in v_list}
        j = requests.post(f"{API}/live/{live_id}/join", headers=_h(viewer_token), timeout=15)
        assert j.status_code == 403
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


# ---------- Group ----------
def test_group_audience_non_member_rejected(host_token):
    bogus_gid = uuid.uuid4().hex
    r = requests.post(f"{API}/live/start", headers=_h(host_token),
                      json={"audience": "group", "category": "gaming", "title": "TEST grp",
                            "group_id": bogus_gid},
                      timeout=15)
    assert r.status_code == 403, f"expected 403 for non-member group, got {r.status_code} {r.text}"


def test_group_audience_missing_group_id_rejected(host_token):
    r = requests.post(f"{API}/live/start", headers=_h(host_token),
                      json={"audience": "group", "category": "gaming", "title": "TEST grp missing"},
                      timeout=15)
    assert r.status_code == 403, f"expected rejection with no group_id, got {r.status_code} {r.text}"


# ---------- Join ----------
def test_join_public_as_viewer(host_token, viewer_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "sports", "title": "TEST join"},
                          timeout=15)
    live_id = start.json()["id"]
    try:
        j = requests.post(f"{API}/live/{live_id}/join", headers=_h(viewer_token), timeout=15)
        assert j.status_code == 200, j.text
        d = j.json()
        assert d["is_host"] is False
        assert d["category"] == "sports"
        assert d["participant_token"].count(".") == 2
    finally:
        requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)


def test_join_nonexistent_returns_404(viewer_token):
    r = requests.post(f"{API}/live/doesnotexist123/join", headers=_h(viewer_token), timeout=15)
    assert r.status_code == 404


def test_join_ended_returns_404(host_token, viewer_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "irl", "title": "TEST end"},
                          timeout=15)
    live_id = start.json()["id"]
    end = requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)
    assert end.status_code == 200
    j = requests.post(f"{API}/live/{live_id}/join", headers=_h(viewer_token), timeout=15)
    assert j.status_code == 404


# ---------- End ----------
def test_end_removes_from_list(host_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "gaming", "title": "TEST end2"},
                          timeout=15)
    live_id = start.json()["id"]
    end = requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)
    assert end.status_code == 200
    assert end.json().get("ok") is True
    live = requests.get(f"{API}/live", headers=_h(host_token), timeout=15).json()
    assert live_id not in {s["id"] for s in live}


# ---------- Past streams ----------
def test_past_streams(host_token):
    start = requests.post(f"{API}/live/start", headers=_h(host_token),
                          json={"audience": "public", "category": "music", "title": "TEST past"},
                          timeout=15)
    live_id = start.json()["id"]
    time.sleep(1)
    requests.post(f"{API}/live/{live_id}/end", headers=_h(host_token), timeout=15)
    r = requests.get(f"{API}/live/past/{HOST_HANDLE}", headers=_h(host_token), timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    found = [s for s in data if s["id"] == live_id]
    assert found, f"ended stream not in past list"
    s = found[0]
    for k in ("title", "category", "peak_viewers", "started_at", "ended_at", "duration"):
        assert k in s
    assert s["category"] == "music"


# ---------- Regressions ----------
def test_feed_public_regression(viewer_token):
    r = requests.get(f"{API}/feed?scope=public", headers=_h(viewer_token), timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_groups_regression(viewer_token):
    r = requests.get(f"{API}/groups", headers=_h(viewer_token), timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
