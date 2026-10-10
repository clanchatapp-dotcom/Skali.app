"""Tests for scheduled wall posts (POST/GET/PATCH/DELETE + auto-publish worker)."""
import os
import time
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://skali-scheduler.preview.emergentagent.com').rstrip('/')
OWNER = {"email": "wallowner@test.com", "password": "Test1234"}
AUTHOR = {"email": "wallauthor@test.com", "password": "Test1234"}


def _login(sess, creds):
    r = sess.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed {creds['email']}: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, r.text
    sess.headers.update({"Authorization": f"Bearer {tok}"})
    me = sess.get(f"{BASE_URL}/api/me", timeout=20)
    assert me.status_code == 200, me.text
    return me.json()


def _session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _future_iso(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# ----- Owner creates scheduled post on own wall -----
def test_schedule_post_on_own_wall():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_scheduled_owner", "scheduled_at": _future_iso(120)}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("scheduled") is True
    assert body.get("id")
    assert "TEST_scheduled_owner" in body.get("text", "")

    # List scheduled -> should contain it
    r2 = s.get(f"{BASE_URL}/api/wall/owner/scheduled", timeout=20)
    assert r2.status_code == 200, r2.text
    ids = [x["id"] for x in r2.json()]
    assert body["id"] in ids

    # Normal wall GET should NOT include it
    r3 = s.get(f"{BASE_URL}/api/wall/owner", timeout=20)
    assert r3.status_code == 200
    wall_texts = [p["text"] for p in r3.json().get("posts", [])]
    assert "TEST_scheduled_owner" not in wall_texts

    # Cleanup
    s.delete(f"{BASE_URL}/api/wall/{body['id']}", timeout=20)


# ----- Patch (edit) scheduled post -----
def test_edit_scheduled_post():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_edit_before", "scheduled_at": _future_iso(180)}, timeout=20)
    assert r.status_code == 200, r.text
    wid = r.json()["id"]

    new_time = _future_iso(300)
    r2 = s.patch(f"{BASE_URL}/api/wall/scheduled/{wid}",
                 json={"text": "TEST_edit_after", "scheduled_at": new_time}, timeout=20)
    assert r2.status_code == 200, r2.text

    r3 = s.get(f"{BASE_URL}/api/wall/owner/scheduled", timeout=20)
    hit = next((x for x in r3.json() if x["id"] == wid), None)
    assert hit is not None
    assert hit["text"] == "TEST_edit_after"
    assert hit["scheduled_at"] == new_time or hit["scheduled_at"].startswith(new_time[:19])

    s.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)


# ----- Past time -> immediate post, not scheduled -----
def test_past_scheduled_at_posts_immediately():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_past_immediate", "scheduled_at": _future_iso(-60)}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body.get("scheduled")
    assert body.get("id")
    s.delete(f"{BASE_URL}/api/wall/{body['id']}", timeout=20)


# ----- Immediate post without scheduled_at -----
def test_immediate_post_works():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner", json={"text": "TEST_immediate"}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body.get("scheduled")
    wid = body["id"]
    r2 = s.get(f"{BASE_URL}/api/wall/owner", timeout=20)
    texts = [p["text"] for p in r2.json().get("posts", [])]
    assert "TEST_immediate" in texts
    s.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)


# ----- Author must follow owner before posting; cannot see owner's scheduled posts -----
def test_other_user_cannot_see_scheduled():
    sa = _session()
    author_me = _login(sa, AUTHOR)
    # follow owner so author can post (not required for GET /scheduled to work, but validates can_wall)
    sa.post(f"{BASE_URL}/api/follow/owner", timeout=20)

    so = _session()
    _login(so, OWNER)
    r = so.post(f"{BASE_URL}/api/wall/owner",
                json={"text": "TEST_owner_only_scheduled", "scheduled_at": _future_iso(240)}, timeout=20)
    assert r.status_code == 200
    wid = r.json()["id"]

    # Author also schedules on owner wall
    ra = sa.post(f"{BASE_URL}/api/wall/owner",
                 json={"text": "TEST_author_scheduled", "scheduled_at": _future_iso(240)}, timeout=20)
    assert ra.status_code == 200, ra.text
    aid = ra.json()["id"]

    # Author GET /scheduled -> only sees their own
    r2 = sa.get(f"{BASE_URL}/api/wall/owner/scheduled", timeout=20)
    assert r2.status_code == 200
    ids = [x["id"] for x in r2.json()]
    assert aid in ids
    assert wid not in ids, "author should NOT see owner's scheduled post"

    # cleanup
    so.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)
    sa.delete(f"{BASE_URL}/api/wall/{aid}", timeout=20)


# ----- Auto-publish worker: scheduled post appears on wall after time -----
def test_auto_publish_worker():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_autopub", "scheduled_at": _future_iso(5)}, timeout=20)
    assert r.status_code == 200, r.text
    wid = r.json()["id"]

    # Wait up to ~40s for worker (runs every 20s). GET wall also triggers publish.
    appeared = False
    for _ in range(10):
        time.sleep(5)
        rw = s.get(f"{BASE_URL}/api/wall/owner", timeout=20)
        texts = [p["text"] for p in rw.json().get("posts", [])]
        if "TEST_autopub" in texts:
            appeared = True
            break
    assert appeared, "scheduled post did not auto-publish"

    # Scheduled list should no longer contain it
    rs = s.get(f"{BASE_URL}/api/wall/owner/scheduled", timeout=20)
    sids = [x["id"] for x in rs.json()]
    assert wid not in sids

    s.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)


# ----- PATCH invalid time -----
def test_patch_rejects_past_time():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_patch_past", "scheduled_at": _future_iso(200)}, timeout=20)
    wid = r.json()["id"]
    r2 = s.patch(f"{BASE_URL}/api/wall/scheduled/{wid}",
                 json={"scheduled_at": _future_iso(-30)}, timeout=20)
    assert r2.status_code == 400
    s.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)
