"""Tests for scheduled feed posts + schedule_reminder activity (wall & feed)."""
import os
import time
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
assert BASE_URL, 'REACT_APP_BACKEND_URL must be set'
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


# ---- POST /api/posts with scheduled_at future -> scheduled true ----
def test_create_scheduled_feed_post():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_sched", "tier": "public", "scheduled_at": _future_iso(180)}, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b.get("scheduled") is True
    assert b.get("id")
    assert b.get("text") == "TEST_feed_sched"

    # List scheduled -> contains it
    r2 = s.get(f"{BASE_URL}/api/posts/scheduled", timeout=20)
    assert r2.status_code == 200, r2.text
    ids = [x["id"] for x in r2.json()]
    assert b["id"] in ids

    # Feed GET should NOT include it
    rf = s.get(f"{BASE_URL}/api/feed", timeout=20)
    assert rf.status_code == 200, rf.text
    data = rf.json() if isinstance(rf.json(), list) else rf.json().get("posts", [])
    texts = [p.get("text") for p in data]
    assert "TEST_feed_sched" not in texts

    # Cleanup
    s.delete(f"{BASE_URL}/api/posts/scheduled/{b['id']}", timeout=20)


# ---- Immediate post without scheduled_at ----
def test_immediate_feed_post_works():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_immediate", "tier": "public"}, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()
    assert not b.get("scheduled")
    pid = b["id"]
    rf = s.get(f"{BASE_URL}/api/feed", timeout=20)
    assert rf.status_code == 200
    data = rf.json() if isinstance(rf.json(), list) else rf.json().get("posts", [])
    texts = [p.get("text") for p in data]
    assert "TEST_feed_immediate" in texts
    s.delete(f"{BASE_URL}/api/posts/{pid}", timeout=20)


# ---- PATCH scheduled feed post (edit text + time) ----
def test_edit_scheduled_feed_post():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_edit_before", "tier": "public", "scheduled_at": _future_iso(240)}, timeout=20)
    pid = r.json()["id"]
    new_time = _future_iso(360)
    r2 = s.patch(f"{BASE_URL}/api/posts/scheduled/{pid}",
                 json={"text": "TEST_feed_edit_after", "scheduled_at": new_time}, timeout=20)
    assert r2.status_code == 200, r2.text

    r3 = s.get(f"{BASE_URL}/api/posts/scheduled", timeout=20)
    hit = next((x for x in r3.json() if x["id"] == pid), None)
    assert hit is not None
    assert hit["text"] == "TEST_feed_edit_after"
    assert hit["scheduled_at"].startswith(new_time[:19])
    s.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)


# ---- PATCH rejects past time ----
def test_patch_feed_rejects_past_time():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_past_patch", "tier": "public", "scheduled_at": _future_iso(200)}, timeout=20)
    pid = r.json()["id"]
    r2 = s.patch(f"{BASE_URL}/api/posts/scheduled/{pid}",
                 json={"scheduled_at": _future_iso(-30)}, timeout=20)
    assert r2.status_code == 400
    s.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)


# ---- DELETE scheduled feed post ----
def test_cancel_scheduled_feed_post():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_cancel", "tier": "public", "scheduled_at": _future_iso(250)}, timeout=20)
    pid = r.json()["id"]
    r2 = s.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)
    assert r2.status_code == 200, r2.text
    r3 = s.get(f"{BASE_URL}/api/posts/scheduled", timeout=20)
    ids = [x["id"] for x in r3.json()]
    assert pid not in ids


# ---- Scheduled list is per-caller (another user cannot see/edit/cancel owner's) ----
def test_other_user_cannot_edit_or_cancel_feed_scheduled():
    so = _session()
    _login(so, OWNER)
    r = so.post(f"{BASE_URL}/api/posts",
                json={"text": "TEST_feed_owner_only", "tier": "public", "scheduled_at": _future_iso(300)}, timeout=20)
    pid = r.json()["id"]

    sa = _session()
    _login(sa, AUTHOR)
    # Author's /scheduled should not include owner's
    r2 = sa.get(f"{BASE_URL}/api/posts/scheduled", timeout=20)
    ids = [x["id"] for x in r2.json()]
    assert pid not in ids
    # Author PATCH -> 404
    r3 = sa.patch(f"{BASE_URL}/api/posts/scheduled/{pid}",
                  json={"text": "hacked"}, timeout=20)
    assert r3.status_code == 404
    # Author DELETE -> 404
    r4 = sa.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)
    assert r4.status_code == 404

    so.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)


# ---- Auto-publish worker: scheduled feed post appears in feed after time ----
def test_feed_auto_publish_worker():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_autopub", "tier": "public", "scheduled_at": _future_iso(20)}, timeout=20)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    sched_at = r.json()["scheduled_at"]

    appeared = None
    for _ in range(14):  # up to ~70s
        time.sleep(5)
        rf = s.get(f"{BASE_URL}/api/feed", timeout=20)
        data = rf.json() if isinstance(rf.json(), list) else rf.json().get("posts", [])
        hit = next((p for p in data if p.get("text") == "TEST_feed_autopub"), None)
        if hit:
            appeared = hit
            break
    assert appeared, "scheduled feed post did not auto-publish"
    # created_at should match scheduled_at
    assert appeared.get("created_at", "").startswith(sched_at[:19])

    # Scheduled list should no longer contain it
    rs = s.get(f"{BASE_URL}/api/posts/scheduled", timeout=20)
    assert pid not in [x["id"] for x in rs.json()]

    s.delete(f"{BASE_URL}/api/posts/{pid}", timeout=20)


# ---- Reminder: short-lead (<6min) scheduled posts get NO reminder ----
def test_short_lead_no_reminder_feed():
    s = _session()
    me = _login(s, OWNER)
    # baseline activity count of type schedule_reminder
    r0 = s.get(f"{BASE_URL}/api/activity", timeout=20)
    assert r0.status_code == 200
    acts0 = r0.json() if isinstance(r0.json(), list) else r0.json().get("items", [])
    before = sum(1 for a in acts0 if a.get("type") == "schedule_reminder")

    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_short_lead", "tier": "public", "scheduled_at": _future_iso(90)}, timeout=20)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # Wait ~30s and ensure reminder count did NOT increase
    time.sleep(30)
    r2 = s.get(f"{BASE_URL}/api/activity", timeout=20)
    acts = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
    after = sum(1 for a in acts if a.get("type") == "schedule_reminder")
    assert after == before, f"unexpected reminder for short-lead post (before={before} after={after})"

    s.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)


# ---- Reminder: >6min scheduled feed post - schedule 6.5min out, then edit to ~5min out so reminder window hits ----
def test_reminder_fires_feed_after_edit():
    s = _session()
    _login(s, OWNER)
    # Start with 7-min lead -> reminded=False
    r = s.post(f"{BASE_URL}/api/posts",
               json={"text": "TEST_feed_reminder", "tier": "public", "scheduled_at": _future_iso(60 * 7)}, timeout=20)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # Edit to 6min 15s out (still > 6min threshold -> reminded stays False, i.e. re-armed)
    new_time = _future_iso(60 * 6 + 15)
    r2 = s.patch(f"{BASE_URL}/api/posts/scheduled/{pid}",
                 json={"scheduled_at": new_time}, timeout=20)
    assert r2.status_code == 200, r2.text

    # Wait up to ~90s so lead-time shrinks below 5min and worker (every 20s) fires reminder.
    seen = False
    for _ in range(20):
        time.sleep(5)
        ra = s.get(f"{BASE_URL}/api/activity", timeout=20)
        acts = ra.json() if isinstance(ra.json(), list) else ra.json().get("items", [])
        if any(a.get("type") == "schedule_reminder" and a.get("post_id") == pid for a in acts):
            seen = True
            break
    # Fallback: match by ref/id or message text
    if not seen:
        ra = s.get(f"{BASE_URL}/api/activity", timeout=20)
        acts = ra.json() if isinstance(ra.json(), list) else ra.json().get("items", [])
        seen = any(a.get("type") == "schedule_reminder" and (a.get("post_id") == pid or pid in str(a)) for a in acts)
    assert seen, "schedule_reminder activity not generated for feed post"

    s.delete(f"{BASE_URL}/api/posts/scheduled/{pid}", timeout=20)


# ---- Reminder for a scheduled WALL post (same mechanism) ----
def test_reminder_fires_wall_after_edit():
    s = _session()
    _login(s, OWNER)
    r = s.post(f"{BASE_URL}/api/wall/owner",
               json={"text": "TEST_wall_reminder", "scheduled_at": _future_iso(60 * 7)}, timeout=20)
    assert r.status_code == 200, r.text
    wid = r.json()["id"]

    new_time = _future_iso(60 * 6 + 15)
    r2 = s.patch(f"{BASE_URL}/api/wall/scheduled/{wid}",
                 json={"scheduled_at": new_time}, timeout=20)
    assert r2.status_code == 200, r2.text

    seen = False
    for _ in range(20):
        time.sleep(5)
        ra = s.get(f"{BASE_URL}/api/activity", timeout=20)
        acts = ra.json() if isinstance(ra.json(), list) else ra.json().get("items", [])
        if any(a.get("type") == "schedule_reminder" and (a.get("post_id") == wid or wid in str(a)) for a in acts):
            seen = True
            break
    assert seen, "schedule_reminder activity not generated for wall post"

    s.delete(f"{BASE_URL}/api/wall/{wid}", timeout=20)
