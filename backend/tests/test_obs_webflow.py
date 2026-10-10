"""Phase 3 OBS web flow tests (iteration 35).

Covers:
- /api/stream/settings PUT/GET with validation
- Default auto_live True; invalid category/audience ignored
- Auth gating
- Unit test on streaming._maybe_auto_start (monkeypatched; no real LiveKit)
- streaming._sweep_auto_live clears hold and auto-starts
- POST /api/stream/end sets stream_settings.hold=True
"""
import os
import sys
import types
import asyncio
import uuid
import pytest
import requests


# Shared asyncio loop so motor's AsyncIOMotorClient stays bound to one loop.
_LOOP = asyncio.new_event_loop()


def run(coro):
    return _LOOP.run_until_complete(coro)


BASE_URL = os.environ.get('REACT_APP_BACKEND_URL',
                          'https://skali-scheduler.preview.emergentagent.com').rstrip('/')

OWNER_EMAIL = 'wallowner@test.com'
OWNER_PW = 'Test1234'
AUTHOR_EMAIL = 'wallauthor@test.com'
AUTHOR_PW = 'Test1234'


def _login(email, pw):
    r = requests.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': pw}, timeout=15)
    assert r.status_code == 200, f'login {email} failed: {r.status_code} {r.text}'
    return r.json()['access_token']


@pytest.fixture(scope='module')
def owner_token():
    return _login(OWNER_EMAIL, OWNER_PW)


@pytest.fixture(scope='module')
def author_token():
    return _login(AUTHOR_EMAIL, AUTHOR_PW)


def H(tok):
    return {'Authorization': f'Bearer {tok}'}


# ---------------- API /api/stream/settings tests ----------------

class TestStreamSettings:
    def test_requires_auth_get(self):
        r = requests.get(f'{BASE_URL}/api/stream/settings', timeout=10)
        assert r.status_code in (401, 403)

    def test_requires_auth_put(self):
        r = requests.put(f'{BASE_URL}/api/stream/settings', json={'title': 'x'}, timeout=10)
        assert r.status_code in (401, 403)

    def test_default_auto_live_true(self, author_token):
        # author who's not a streamer still can GET their default settings
        r = requests.get(f'{BASE_URL}/api/stream/settings', headers=H(author_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get('auto_live') is True
        assert d.get('category') == 'just_chatting'
        assert d.get('audience') == 'public'

    def test_put_saves_and_get_returns(self, owner_token):
        payload = {'title': 'My OBS stream', 'category': 'gaming', 'audience': 'followers', 'auto_live': False}
        r = requests.put(f'{BASE_URL}/api/stream/settings', json=payload, headers=H(owner_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['title'] == 'My OBS stream'
        assert d['category'] == 'gaming'
        assert d['audience'] == 'followers'
        assert d['auto_live'] is False
        # GET returns the same
        r2 = requests.get(f'{BASE_URL}/api/stream/settings', headers=H(owner_token), timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2 == d

    def test_invalid_category_and_audience_ignored(self, owner_token):
        # Reset to a known good state first
        requests.put(f'{BASE_URL}/api/stream/settings',
                     json={'category': 'just_chatting', 'audience': 'public'},
                     headers=H(owner_token), timeout=15)
        r = requests.put(f'{BASE_URL}/api/stream/settings',
                         json={'category': 'bogus_cat', 'audience': 'nobody'},
                         headers=H(owner_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        # unchanged
        assert d['category'] == 'just_chatting'
        assert d['audience'] == 'public'

    def test_title_truncated_to_120(self, owner_token):
        long = 'A' * 200
        r = requests.put(f'{BASE_URL}/api/stream/settings', json={'title': long}, headers=H(owner_token), timeout=15)
        assert r.status_code == 200
        assert len(r.json()['title']) <= 120

    def test_auto_live_true_restore(self, owner_token):
        r = requests.put(f'{BASE_URL}/api/stream/settings', json={'auto_live': True, 'title': ''},
                         headers=H(owner_token), timeout=15)
        assert r.status_code == 200
        assert r.json()['auto_live'] is True


# ---------------- Unit tests on streaming module (no real LiveKit) ----------------

@pytest.fixture(scope='module')
def streaming_mod():
    """Import backend streaming with its real srv (server module)."""
    sys.path.insert(0, '/app/backend')
    # Load backend .env before importing server so Mongo + DB_NAME are configured
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env', override=False)
    import server  # noqa: F401
    import streaming
    # make sure srv is set (setup() runs on app startup). Fallback: inject.
    if streaming.srv is None:
        streaming.srv = server
    return streaming, server


class _FakeIngressState:
    def __init__(self, status_name='ENDPOINT_PUBLISHING'):
        self._name = status_name

    @property
    def status(self):
        return self._name  # streaming._STATUS maps by string via lk_api.IngressState.Status.Name


class _FakeIngressInfo:
    def __init__(self, ingress_id, publishing=True):
        self.ingress_id = ingress_id
        self.url = 'rtmp://fake'
        self.stream_key = 'fake'
        s = types.SimpleNamespace()
        s.status = 'ENDPOINT_PUBLISHING' if publishing else 'ENDPOINT_BUFFERING'
        s.error = ''
        self.state = s


def test_maybe_auto_start_creates_live(streaming_mod, owner_token, monkeypatch):
    streaming, server = streaming_mod

    async def _body():
        # resolve owner user doc
        me = requests.get(f'{BASE_URL}/api/me', headers=H(owner_token), timeout=15).json()
        uid = me['id']
        u = await server.db.profiles.find_one({'id': uid}, {'_id': 0})
        assert u, 'owner profile missing'
        await server.db.stream_settings.update_one({'user_id': uid},
                                                   {'$set': {'user_id': uid, 'title': 'Preset', 'category': 'gaming',
                                                             'audience': 'public', 'auto_live': True, 'hold': False}},
                                                   upsert=True)
        await server.db.live_streams.update_many({'host_id': uid, 'status': 'live'},
                                                 {'$set': {'status': 'ended'}})

        async def fake_lk(fn):
            return None
        async def fake_notify(doc, user):
            return None
        monkeypatch.setattr(streaming, '_lk', fake_lk)
        monkeypatch.setattr(streaming, 'lk_configured', lambda: True)
        monkeypatch.setattr(streaming, '_s3_upload', lambda: None)
        monkeypatch.setattr(server, '_notify_live', fake_notify)

        doc = await streaming._maybe_auto_start(u)
        assert doc is not None, 'should create a live doc'
        assert doc['source'] == 'obs'
        assert doc['title'] == 'Preset'
        assert doc['category'] == 'gaming'
        assert doc['audience'] == 'public'

        doc2 = await streaming._maybe_auto_start(u)
        assert doc2 is not None
        assert doc2['id'] == doc['id']

        await server.db.live_streams.update_many({'host_id': uid, 'status': 'live'},
                                                 {'$set': {'status': 'ended'}})
        await server.db.stream_settings.update_one({'user_id': uid}, {'$set': {'auto_live': False}})
        none_doc = await streaming._maybe_auto_start(u)
        assert none_doc is None

        await server.db.stream_settings.update_one({'user_id': uid}, {'$set': {'auto_live': True, 'hold': True}})
        none_doc2 = await streaming._maybe_auto_start(u)
        assert none_doc2 is None

        await server.db.live_streams.delete_many({'host_id': uid, 'source': 'obs'})
        await server.db.stream_vods.delete_many({'host_id': uid})
        await server.db.stream_settings.update_one({'user_id': uid}, {'$set': {'hold': False, 'auto_live': True}})

    run(_body())


def test_maybe_auto_start_blocked_for_non_streamer(streaming_mod, author_token, monkeypatch):
    streaming, server = streaming_mod

    async def _body():
        me = requests.get(f'{BASE_URL}/api/me', headers=H(author_token), timeout=15).json()
        uid = me['id']
        u = await server.db.profiles.find_one({'id': uid}, {'_id': 0})
        monkeypatch.setattr(streaming, 'lk_configured', lambda: True)
        doc = await streaming._maybe_auto_start(u)
        assert doc is None, 'non-streamer should not auto-start'

    run(_body())


def test_end_sets_hold_true(streaming_mod, owner_token, monkeypatch):
    streaming, server = streaming_mod

    async def _prep(uid, u):
        live_id = uuid.uuid4().hex[:12]
        live = {'id': live_id, 'room': streaming.room_for(uid), 'host_id': uid, 'source': 'obs',
                'status': 'live', 'title': 'test', 'category': 'just_chatting', 'audience': 'public',
                'host': {'handle': u['handle'], 'display_name': u.get('display_name'),
                         'avatar_url': u.get('avatar_url'), 'account_nsfw': False, 'role': 'member'},
                'started_at': streaming._now().isoformat(), 'peak_viewers': 0, 'lk_viewers': 0,
                'last_publishing_at': streaming._now().isoformat()}
        await server.db.live_streams.insert_one(dict(live))
        return live_id

    async def _check(uid):
        return await server.db.stream_settings.find_one({'user_id': uid}, {'_id': 0})

    async def _cleanup(uid, live_id):
        await server.db.live_streams.delete_many({'host_id': uid, 'id': live_id})
        await server.db.stream_settings.update_one({'user_id': uid}, {'$set': {'hold': False}})

    me = requests.get(f'{BASE_URL}/api/me', headers=H(owner_token), timeout=15).json()
    uid = me['id']
    u = run(server.db.profiles.find_one({'id': uid}, {'_id': 0}))
    live_id = run(_prep(uid, u))

    r = requests.post(f'{BASE_URL}/api/stream/end', headers=H(owner_token), timeout=15)
    st = run(_check(uid))
    if r.status_code != 404:
        assert st and st.get('hold') is True, f'hold not set after /end (status={r.status_code})'

    run(_cleanup(uid, live_id))


def test_sweep_auto_live(streaming_mod, owner_token, monkeypatch):
    streaming, server = streaming_mod

    async def _body():
        me = requests.get(f'{BASE_URL}/api/me', headers=H(owner_token), timeout=15).json()
        uid = me['id']
        u = await server.db.profiles.find_one({'id': uid}, {'_id': 0})
        assert u

        ing_id = 'ING_TEST_' + uuid.uuid4().hex[:8]
        await server.db.stream_ingress.update_one(
            {'user_id': uid},
            {'$set': {'user_id': uid, 'ingress_id': ing_id, 'room': streaming.room_for(uid),
                      'created_at': streaming._now().isoformat()}}, upsert=True)
        await server.db.stream_settings.update_one({'user_id': uid},
                                                   {'$set': {'user_id': uid, 'auto_live': True, 'hold': True,
                                                             'title': 'T', 'category': 'just_chatting',
                                                             'audience': 'public'}}, upsert=True)
        await server.db.live_streams.update_many({'host_id': uid, 'status': 'live'},
                                                 {'$set': {'status': 'ended'}})

        class _ListRes:
            def __init__(self, items): self.items = items

        not_pub = _FakeIngressInfo(ing_id, publishing=False)

        async def fake_lk_notpub(fn):
            return _ListRes([not_pub])
        async def fake_notify(*a, **k): return None
        monkeypatch.setattr(streaming, '_lk', fake_lk_notpub)
        monkeypatch.setattr(streaming, 'lk_configured', lambda: True)
        monkeypatch.setattr(streaming, '_s3_upload', lambda: None)
        monkeypatch.setattr(server, '_notify_live', fake_notify)
        from livekit import api as lk_api
        monkeypatch.setattr(lk_api.IngressState.Status, 'Name',
                            staticmethod(lambda s: s if isinstance(s, str) else 'ENDPOINT_PUBLISHING'))

        await streaming._sweep_auto_live()
        st = await server.db.stream_settings.find_one({'user_id': uid}, {'_id': 0})
        assert st.get('hold') is False, 'hold should be cleared when not publishing'
        live_now = await server.db.live_streams.find_one({'host_id': uid, 'status': 'live', 'source': 'obs'})
        assert live_now is None, 'should not auto-start when not publishing'

        pub = _FakeIngressInfo(ing_id, publishing=True)

        async def fake_lk_pub(fn):
            return _ListRes([pub])
        monkeypatch.setattr(streaming, '_lk', fake_lk_pub)

        await streaming._sweep_auto_live()
        live_now = await server.db.live_streams.find_one({'host_id': uid, 'status': 'live', 'source': 'obs'}, {'_id': 0})
        assert live_now is not None, 'should auto-start when publishing'
        assert live_now['title'] == 'T'

        await server.db.live_streams.delete_many({'host_id': uid, 'source': 'obs'})
        await server.db.stream_vods.delete_many({'host_id': uid})
        await server.db.stream_ingress.delete_one({'user_id': uid, 'ingress_id': ing_id})
        await server.db.stream_settings.update_one({'user_id': uid},
                                                   {'$set': {'hold': False, 'auto_live': True}})

    run(_body())
