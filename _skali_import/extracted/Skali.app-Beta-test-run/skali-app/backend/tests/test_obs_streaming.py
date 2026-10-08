"""Phase 2 (OBS → LiveKit) streaming backend tests.

Covers:
- /api/stream/* auth gating (401/403 without token)
- VOD endpoints (host-only listing; cross-host download → 404)
- Moderator eligibility (403 when target not in host's Inner Circle)
- Chat moderation permission (non-mod → 403 on /chat/delete)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('preview_endpoint', 'https://699f8874-5189-442a-9e2c-3a2f8dbf3a24.preview.emergentagent.com').rstrip('/')
LIVE_ID = '194f3fb9d93a'  # tester (skalitester) OBS session that is already live


def _login(email: str, password: str) -> str:
    r = requests.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': password}, timeout=15)
    assert r.status_code == 200, f'login failed {r.status_code} {r.text}'
    return r.json()['access_token']


@pytest.fixture(scope='module')
def tester_token():
    return _login('tester@skali.local', 'Tester123!')


@pytest.fixture(scope='module')
def tester2_token():
    return _login('tester2@skali.local', 'Tester123!')


@pytest.fixture(scope='module')
def fresh_user():
    """Create a brand new user NOT in tester's inner circle. Returns (handle, token, user_id)."""
    import time
    handle = f'tmoduser{int(time.time()) % 100000}'
    email = f'{handle}@skali.local'
    payload = {'email': email, 'password': 'Tester123!', 'handle': handle,
               'display_name': handle, 'dob': '1995-05-05'}
    r = requests.post(f'{BASE_URL}/api/auth/register', json=payload, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f'register failed: {r.status_code} {r.text}')
    tok = r.json().get('access_token') or _login(email, 'Tester123!')
    me = requests.get(f'{BASE_URL}/api/auth/me', headers={'Authorization': f'Bearer {tok}'}, timeout=10).json()
    uid = me.get('id')
    yield handle, tok, uid
    # cleanup: delete account
    try:
        requests.delete(f'{BASE_URL}/api/auth/me', headers={'Authorization': f'Bearer {tok}'}, timeout=10)
    except Exception:
        pass


# ---------- Auth gating ----------

class TestAuthGating:
    def test_ingress_requires_auth(self):
        r = requests.get(f'{BASE_URL}/api/stream/ingress', timeout=10)
        assert r.status_code in (401, 403), f'got {r.status_code}: {r.text[:200]}'

    def test_mods_requires_auth(self):
        r = requests.get(f'{BASE_URL}/api/stream/mods', timeout=10)
        assert r.status_code in (401, 403)

    def test_vods_requires_auth(self):
        r = requests.get(f'{BASE_URL}/api/stream/vods', timeout=10)
        assert r.status_code in (401, 403)

    def test_stream_info_requires_auth(self):
        r = requests.get(f'{BASE_URL}/api/stream/{LIVE_ID}', timeout=10)
        assert r.status_code in (401, 403)

    def test_start_requires_auth(self):
        r = requests.post(f'{BASE_URL}/api/stream/start', json={}, timeout=10)
        assert r.status_code in (401, 403)


# ---------- Ingress + live state ----------

class TestIngressAndLive:
    def test_ingress_returns_url_and_key(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/stream/ingress',
                         headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data['configured'] is True
        assert data['ingress'] is not None
        assert 'url' in data['ingress'] and 'stream_key' in data['ingress']
        assert data['ingress']['url'].startswith(('rtmp://', 'rtmps://'))
        # live info present since ffmpeg is pushing
        assert data['live'] is not None
        assert data['live']['id'] == LIVE_ID

    def test_stream_info_as_host(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/stream/{LIVE_ID}',
                         headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d['id'] == LIVE_ID
        assert d['is_host'] is True
        assert d['can_moderate'] is True
        assert d.get('source') == 'obs'

    def test_live_appears_in_live_feed(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/live',
                         headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get('items', [])
        ids = [i.get('id') for i in items]
        assert LIVE_ID in ids, f'live id missing from /api/live: {ids}'

    def test_reset_key_blocked_while_live(self, tester_token):
        r = requests.post(f'{BASE_URL}/api/stream/ingress/reset',
                          headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 409


# ---------- Mods ----------

class TestMods:
    def test_mods_list_contains_tester2_as_candidate(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/stream/mods',
                         headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        all_handles = {m['handle'] for m in d['mods']} | {c['handle'] for c in d['candidates']}
        assert 'tester2' in all_handles

    def test_add_mod_requires_inner_circle(self, tester_token, fresh_user):
        handle, _tok, _uid = fresh_user
        r = requests.post(f'{BASE_URL}/api/stream/mods',
                          json={'handle': handle},
                          headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 403
        body = r.json()
        msg = body.get('detail') or body.get('message') or ''
        assert 'Inner Circle' in msg


# ---------- Chat moderation permission ----------

class TestChatModeration:
    def test_non_mod_cannot_delete(self, fresh_user):
        _handle, tok, _uid = fresh_user
        r = requests.post(f'{BASE_URL}/api/stream/{LIVE_ID}/chat/delete',
                          json={'msg_id': 'fake'},
                          headers={'Authorization': f'Bearer {tok}'}, timeout=15)
        # Could be 403 (perm) or 404 (can't see stream). Spec says 403.
        assert r.status_code == 403, f'expected 403, got {r.status_code}: {r.text[:200]}'


# ---------- VODs ----------

class TestVods:
    def test_vods_list_host(self, tester_token):
        r = requests.get(f'{BASE_URL}/api/stream/vods',
                         headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_cross_host_vod_download_404(self, tester2_token):
        # tester2 trying to download LIVE_ID (owned by tester) → 404
        r = requests.get(f'{BASE_URL}/api/stream/vods/{LIVE_ID}/download',
                         headers={'Authorization': f'Bearer {tester2_token}'}, timeout=15)
        assert r.status_code == 404
