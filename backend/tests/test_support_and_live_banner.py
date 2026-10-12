"""Support inbox + Live-now Feed banner backend tests (iteration 30)."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:3000').rstrip('/')

BOT_EMAIL = 'skaliappteam@gmail.com'
BOT_PW = 'Skaliappteam_1'
TESTER_EMAIL = 'tester@skali.test'
VIEWER_EMAIL = 'viewer@skali.test'
PW = 'Test1234!'


def _login(email: str, password: str) -> str:
    r = requests.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': password}, timeout=20)
    assert r.status_code == 200, f'login {email} failed: {r.status_code} {r.text}'
    return r.json()['access_token']


@pytest.fixture(scope='module')
def bot_token():
    return _login(BOT_EMAIL, BOT_PW)


@pytest.fixture(scope='module')
def viewer_token():
    return _login(VIEWER_EMAIL, PW)


@pytest.fixture(scope='module')
def tester_token():
    return _login(TESTER_EMAIL, PW)


def _h(t): return {'Authorization': f'Bearer {t}'}


# -------- Support inbox --------

class TestSupportInbox:
    def test_bot_me_is_support_bot(self, bot_token):
        r = requests.get(f'{BASE_URL}/api/me', headers=_h(bot_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get('is_support_bot') is True
        assert d.get('handle') == 'skali_support'

    def test_support_unread_bot_ok(self, bot_token):
        r = requests.get(f'{BASE_URL}/api/admin/support/unread', headers=_h(bot_token), timeout=15)
        assert r.status_code == 200
        assert 'unread' in r.json() and isinstance(r.json()['unread'], int)

    def test_support_threads_bot_ok(self, bot_token):
        r = requests.get(f'{BASE_URL}/api/admin/support/threads', headers=_h(bot_token), timeout=15)
        assert r.status_code == 200
        threads = r.json()
        assert isinstance(threads, list)
        # ensure sort: all unread (>0) come before all read (==0)
        seen_read = False
        for t in threads:
            if t['unread'] == 0:
                seen_read = True
            else:
                assert not seen_read, 'unread thread appeared after a read thread'

    def test_support_unread_normal_user_forbidden(self, viewer_token):
        r = requests.get(f'{BASE_URL}/api/admin/support/unread', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 403

    def test_support_threads_normal_user_forbidden(self, viewer_token):
        r = requests.get(f'{BASE_URL}/api/admin/support/threads', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 403

    def test_support_flow_viewer_msg_then_bot_reply(self, bot_token, viewer_token):
        # viewer sends a DM to the bot
        r = requests.post(f'{BASE_URL}/api/dms/skali_support',
                          headers=_h(viewer_token),
                          json={'text': 'TEST_support_hello from pytest'}, timeout=20)
        assert r.status_code in (200, 201), f'send dm failed: {r.status_code} {r.text}'
        # unread count should be >=1
        r = requests.get(f'{BASE_URL}/api/admin/support/unread', headers=_h(bot_token), timeout=15)
        assert r.status_code == 200
        unread_before = r.json()['unread']
        assert unread_before >= 1
        # fetch thread (this marks read)
        r = requests.get(f'{BASE_URL}/api/admin/support/threads/viewer', headers=_h(bot_token), timeout=15)
        assert r.status_code == 200
        thread = r.json()
        assert thread['user']['handle'] == 'viewer'
        assert any('TEST_support_hello' in m.get('text', '') for m in thread['messages'])
        # unread should drop (fetching marks ALL of this user's inbound as read)
        r = requests.get(f'{BASE_URL}/api/admin/support/unread', headers=_h(bot_token), timeout=15)
        assert r.json()['unread'] < unread_before
        # bot replies
        reply_text = 'TEST_support_reply from pytest'
        r = requests.post(f'{BASE_URL}/api/admin/support/reply/viewer',
                          headers=_h(bot_token), json={'text': reply_text}, timeout=20)
        assert r.status_code == 200
        # viewer sees the bot reply in their DM thread
        r = requests.get(f'{BASE_URL}/api/dms/skali_support', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 200
        msgs = r.json() if isinstance(r.json(), list) else r.json().get('messages', [])
        assert any(reply_text in (m.get('text') or '') for m in msgs), 'bot reply not seen by viewer'


# -------- Live alerted-now banner --------

class TestLiveAlertedNow:
    def test_alerted_now_viewer_sees_fake_stream(self, viewer_token):
        r = requests.get(f'{BASE_URL}/api/live/alerted-now', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        ids = [i.get('id') for i in items]
        assert 'preview-fake-stream' in ids, f'preview-fake-stream missing; got {ids}'
        itm = next(i for i in items if i['id'] == 'preview-fake-stream')
        assert itm.get('watch_url') == '/watch/preview-fake-stream'

    def test_alerted_now_excludes_own_stream(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/live/alerted-now', headers=_h(tester_token), timeout=15)
        assert r.status_code == 200
        ids = [i.get('id') for i in r.json()]
        assert 'preview-fake-stream' not in ids, "creator shouldn't see their own stream in alerted-now"

    def test_alert_off_hides_banner(self, viewer_token):
        # turn alert OFF
        r = requests.put(f'{BASE_URL}/api/live-alerts/thisismajorofficial',
                         headers=_h(viewer_token), json={'enabled': False}, timeout=15)
        assert r.status_code == 200 and r.json()['enabled'] is False
        r = requests.get(f'{BASE_URL}/api/live/alerted-now', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 200
        ids = [i.get('id') for i in r.json()]
        assert 'preview-fake-stream' not in ids
        # turn it back on
        r = requests.put(f'{BASE_URL}/api/live-alerts/thisismajorofficial',
                         headers=_h(viewer_token), json={'enabled': True}, timeout=15)
        assert r.status_code == 200 and r.json()['enabled'] is True

    def test_alerted_now_never_includes_stories(self, viewer_token):
        r = requests.get(f'{BASE_URL}/api/live/alerted-now', headers=_h(viewer_token), timeout=15)
        assert r.status_code == 200
        for i in r.json():
            assert (i.get('kind') or 'stream') != 'story'


# -------- Moderator access --------

class TestModeratorAccess:
    def test_moderator_can_access_support(self, tester_token):
        from pymongo import MongoClient
        import os as _os
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        c = MongoClient(_os.environ['MONGO_URL'])
        db = c[_os.environ['DB_NAME']]
        try:
            db.profiles.update_one({'email': TESTER_EMAIL}, {'$set': {'role': 'moderator'}})
            r = requests.get(f'{BASE_URL}/api/admin/support/unread', headers=_h(tester_token), timeout=15)
            assert r.status_code == 200, f'moderator should access support unread, got {r.status_code}'
            r = requests.get(f'{BASE_URL}/api/admin/support/threads', headers=_h(tester_token), timeout=15)
            assert r.status_code == 200
        finally:
            db.profiles.update_one({'email': TESTER_EMAIL}, {'$set': {'role': None}})
            c.close()
