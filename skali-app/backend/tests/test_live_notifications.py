"""Backend tests for the Go-Live notifications feature (issue 2) + regression on
POST /api/live/start now that LIVEKIT_* dummy keys and SUPABASE_JWT_SECRET are set.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get('LOCAL_BACKEND_URL', 'http://localhost:8001')


def _register(suffix: str):
    """Register fresh account. dob is accepted directly on register (adult)."""
    email = f"TEST_{suffix}_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        'email': email,
        'password': 'password123',
        'name': f'Test {suffix}',
        'dob': '1995-05-05',
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert 'access_token' in data and 'user' in data
    return {
        'email': email,
        'token': data['access_token'],
        'id': data['user']['id'],
        'handle': data['user']['handle'],
        'headers': {'Authorization': f"Bearer {data['access_token']}"},
    }


def _get(path, user):
    return requests.get(f"{BASE_URL}{path}", headers=user['headers'], timeout=15)


def _post(path, user, json=None):
    return requests.post(f"{BASE_URL}{path}", headers=user['headers'], json=(json or {}), timeout=15)


# ---------- Regression: /api/live/start works with dummy LIVEKIT keys ----------

def test_live_start_regression_200():
    host = _register('host_reg')
    r = _post('/api/live/start', host,
              {'audience': 'followers', 'title': 'Smoke', 'save': False})
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert 'id' in body or 'live' in body or 'token' in body, body


# ---------- Issue 2: followers audience notifies approved followers via activity ----------

def test_followers_audience_notifies_approved_follower_and_not_host():
    host = _register('host_fol')
    follower = _register('fol')
    stranger = _register('stranger')  # not following; should NOT get activity

    # follower follows host (open follow_mode -> approved)
    r = _post(f"/api/follow/{host['handle']}", follower)
    assert r.status_code == 200, r.text
    assert r.json().get('status') == 'approved', r.json()

    # Host starts a followers-audience live
    r = _post('/api/live/start', host,
              {'audience': 'followers', 'title': 'Hello world', 'save': False})
    assert r.status_code == 200, r.text

    # Follower sees a 'live' activity from host
    r = _get('/api/activity', follower)
    assert r.status_code == 200, r.text
    acts = r.json()
    live_from_host = [a for a in acts if a.get('type') == 'live' and a.get('actor_id') == host['id']]
    assert live_from_host, f"follower did not receive live activity. acts={acts}"
    txt = (live_from_host[0].get('text') or '').lower()
    assert 'live' in txt, live_from_host[0]

    # Host should NOT self-notify
    r = _get('/api/activity', host)
    assert r.status_code == 200
    host_live = [a for a in r.json() if a.get('type') == 'live' and a.get('actor_id') == host['id']]
    assert not host_live, f"host notified themselves: {host_live}"

    # Stranger (no follow) should NOT get the live activity
    r = _get('/api/activity', stranger)
    assert r.status_code == 200
    stranger_live = [a for a in r.json() if a.get('type') == 'live' and a.get('actor_id') == host['id']]
    assert not stranger_live, f"non-follower got live activity: {stranger_live}"


# ---------- Issue 2: 'inner' audience only notifies inner-circle members ----------

def test_inner_audience_only_notifies_inner_members():
    host = _register('host_inner')
    inner_member = _register('inner_m')
    plain_follower = _register('plain_fol')

    # Plain follower follows host
    r = _post(f"/api/follow/{host['handle']}", plain_follower)
    assert r.status_code == 200 and r.json().get('status') == 'approved'

    # Host invites inner_member; inner_member accepts
    r = _post(f"/api/inner/invite/{inner_member['handle']}", host)
    assert r.status_code == 200, r.text
    r = _post(f"/api/inner/accept/{host['handle']}", inner_member)
    assert r.status_code == 200 and r.json().get('status') == 'accepted', r.text

    # Host goes live with audience=inner
    r = _post('/api/live/start', host,
              {'audience': 'inner', 'title': 'Inner only', 'save': False})
    assert r.status_code == 200, r.text

    # Inner member receives 'live' activity
    r = _get('/api/activity', inner_member)
    assert r.status_code == 200
    inner_live = [a for a in r.json() if a.get('type') == 'live' and a.get('actor_id') == host['id']]
    assert inner_live, f"inner member did not get live activity: {r.json()}"

    # Plain follower should NOT (audience=inner excludes plain followers)
    r = _get('/api/activity', plain_follower)
    assert r.status_code == 200
    pf_live = [a for a in r.json() if a.get('type') == 'live' and a.get('actor_id') == host['id']]
    assert not pf_live, f"plain follower got inner-audience live activity: {pf_live}"
