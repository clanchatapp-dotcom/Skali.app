"""Iteration 31 tests:
 - BUG FIX: profile followers/following stat blocks (API side: /api/connections, follow flow)
 - Feature: Support claim/release/takeover endpoints
"""
import os
import pytest
import requests

def _read_frontend_env():
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return None

BASE = (os.environ.get('REACT_APP_BACKEND_URL') or _read_frontend_env()).rstrip('/')
API = f"{BASE}/api"

BOT_EMAIL = 'skaliappteam@gmail.com'
BOT_PW = 'Skaliappteam_1'
TESTER_EMAIL = 'tester@skali.test'
TESTER_PW = 'Test1234!'
VIEWER_EMAIL = 'viewer@skali.test'
VIEWER_PW = 'Test1234!'

TESTER_HANDLE = 'thisismajorofficial'
VIEWER_HANDLE = 'viewer'
BOT_HANDLE = 'skali_support'


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={'email': email, 'password': pw})
    assert r.status_code == 200, (email, r.status_code, r.text)
    return r.json()['access_token']


def _h(t):
    return {'Authorization': f'Bearer {t}'}


@pytest.fixture(scope='module')
def tokens():
    return {
        'bot': _login(BOT_EMAIL, BOT_PW),
        'tester': _login(TESTER_EMAIL, TESTER_PW),
        'viewer': _login(VIEWER_EMAIL, VIEWER_PW),
    }


# ------------------------- Follow / Connections (BUG FIX) -------------------------

class TestFollowAndConnections:
    def test_viewer_follow_tester(self, tokens):
        # Ensure clean: unfollow first (ignore errors)
        requests.post(f"{API}/unfollow/{TESTER_HANDLE}", headers=_h(tokens['viewer']))
        r = requests.post(f"{API}/follow/{TESTER_HANDLE}", headers=_h(tokens['viewer']))
        assert r.status_code == 200, r.text

    def test_tester_sees_viewer_in_followers(self, tokens):
        r = requests.get(f"{API}/connections", headers=_h(tokens['tester']))
        assert r.status_code == 200
        data = r.json()
        handles = [f['handle'] for f in data.get('followers', [])]
        assert VIEWER_HANDLE in handles, f"expected viewer in followers, got {handles}"
        # counts reflect
        assert data['counts']['followers'] >= 1

    def test_viewer_sees_tester_in_following(self, tokens):
        r = requests.get(f"{API}/connections", headers=_h(tokens['viewer']))
        assert r.status_code == 200
        data = r.json()
        handles = [f['handle'] for f in data.get('following', [])]
        assert TESTER_HANDLE in handles, f"expected tester in following, got {handles}"

    def test_profile_counts_present(self, tokens):
        # Owner profile should have is_self=True and counts
        r = requests.get(f"{API}/users/{TESTER_HANDLE}", headers=_h(tokens['tester']))
        assert r.status_code == 200
        p = r.json()
        assert p.get('is_self') is True
        assert isinstance(p.get('followers_count'), int)
        assert isinstance(p.get('following_count'), int)
        assert p['followers_count'] >= 1

    def test_other_profile_marks_not_self(self, tokens):
        # Viewer views tester's profile -> is_self False (buttons disabled on UI)
        r = requests.get(f"{API}/users/{TESTER_HANDLE}", headers=_h(tokens['viewer']))
        assert r.status_code == 200
        p = r.json()
        assert p.get('is_self') is False


# ------------------------- Support claim/release/takeover -------------------------

class TestSupportClaim:
    def test_normal_user_forbidden(self, tokens):
        r = requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': True},
                          headers=_h(tokens['viewer']))
        assert r.status_code == 403, r.text

    def test_bot_claim_viewer_thread(self, tokens):
        r = requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': True},
                          headers=_h(tokens['bot']))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data['ok'] is True
        assert data['assigned'] is not None
        assert data['assigned']['handle'] == BOT_HANDLE
        assert 'at' in data['assigned'] and 'id' in data['assigned']

    def test_threads_list_includes_assigned(self, tokens):
        r = requests.get(f"{API}/admin/support/threads", headers=_h(tokens['bot']))
        assert r.status_code == 200
        threads = r.json()
        viewer_t = next((t for t in threads if t['user']['handle'] == VIEWER_HANDLE), None)
        assert viewer_t is not None
        assert viewer_t.get('assigned') is not None
        assert viewer_t['assigned']['handle'] == BOT_HANDLE

    def test_thread_detail_includes_assigned(self, tokens):
        r = requests.get(f"{API}/admin/support/threads/{VIEWER_HANDLE}", headers=_h(tokens['bot']))
        assert r.status_code == 200
        d = r.json()
        assert d.get('assigned') is not None
        assert d['assigned']['handle'] == BOT_HANDLE

    def test_solve_does_not_clear_assignment(self, tokens):
        # Mark solved then reopen; assignment should persist
        r = requests.post(f"{API}/admin/support/solve/{VIEWER_HANDLE}", json={'solved': True},
                          headers=_h(tokens['bot']))
        assert r.status_code == 200
        r2 = requests.get(f"{API}/admin/support/threads/{VIEWER_HANDLE}", headers=_h(tokens['bot']))
        assert r2.status_code == 200
        assert r2.json().get('assigned') is not None
        # reopen
        r3 = requests.post(f"{API}/admin/support/solve/{VIEWER_HANDLE}", json={'solved': False},
                          headers=_h(tokens['bot']))
        assert r3.status_code == 200
        r4 = requests.get(f"{API}/admin/support/threads/{VIEWER_HANDLE}", headers=_h(tokens['bot']))
        assert r4.json().get('assigned') is not None

    def test_moderator_takeover(self, tokens):
        """Set tester role to moderator, take over viewer's thread, then reset."""
        # Promote tester via mongo (direct)
        from pymongo import MongoClient
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'test_database')
        client = MongoClient(mongo_url)
        db = client[db_name]
        try:
            db.profiles.update_one({'handle': TESTER_HANDLE}, {'$set': {'role': 'moderator'}})
            # tester should now access support
            r = requests.get(f"{API}/admin/support/threads", headers=_h(tokens['tester']))
            assert r.status_code == 200, r.text
            # Tester takes over viewer thread
            r2 = requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': True},
                               headers=_h(tokens['tester']))
            assert r2.status_code == 200
            assert r2.json()['assigned']['handle'] == TESTER_HANDLE
            # Verify threads list
            r3 = requests.get(f"{API}/admin/support/threads", headers=_h(tokens['tester']))
            viewer_t = next((t for t in r3.json() if t['user']['handle'] == VIEWER_HANDLE), None)
            assert viewer_t['assigned']['handle'] == TESTER_HANDLE
        finally:
            # Cleanup: release & reset role
            requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': False},
                          headers=_h(tokens['bot']))
            db.profiles.update_one({'handle': TESTER_HANDLE}, {'$set': {'role': None}})
            client.close()

    def test_release_clears_assignment(self, tokens):
        # Claim then release
        requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': True},
                      headers=_h(tokens['bot']))
        r = requests.post(f"{API}/admin/support/claim/{VIEWER_HANDLE}", json={'claim': False},
                         headers=_h(tokens['bot']))
        assert r.status_code == 200
        assert r.json()['assigned'] is None
        r2 = requests.get(f"{API}/admin/support/threads/{VIEWER_HANDLE}", headers=_h(tokens['bot']))
        assert r2.json().get('assigned') is None
