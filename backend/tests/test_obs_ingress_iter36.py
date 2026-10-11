"""Iteration 36: verify GET /api/stream/ingress for wallowner returns configured=true,
ingress with rtmps:// url, empty error. Also verify author (no can_stream) returns
configured=true, ingress=null (either with or without error depending on LiveKit)."""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL',
                          'https://skali-scheduler.preview.emergentagent.com').rstrip('/')


def _login(email, pw):
    r = requests.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()['access_token']


def _h(t):
    return {'Authorization': f'Bearer {t}'}


def test_owner_ingress_ok():
    tok = _login('wallowner@test.com', 'Test1234')
    r = requests.get(f'{BASE_URL}/api/stream/ingress', headers=_h(tok), timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['configured'] is True
    assert d.get('error', '') == '', f'unexpected error: {d.get("error")}'
    assert d['ingress'] is not None, 'owner should have an ingress already'
    url = d['ingress']['url']
    assert url.startswith('rtmps://') or url.startswith('rtmp://'), f'bad url: {url}'
    assert d['ingress'].get('stream_key'), 'should have stream_key'


def test_author_ingress_no_key_no_can_stream():
    tok = _login('wallauthor@test.com', 'Test1234')
    r = requests.get(f'{BASE_URL}/api/stream/ingress', headers=_h(tok), timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['configured'] is True
    # Author has no ingress yet
    assert d['ingress'] is None
    # error may or may not be set depending on LiveKit reachability
    # settings defaults should be present
    assert 'settings' in d


def test_unauth():
    r = requests.get(f'{BASE_URL}/api/stream/ingress', timeout=10)
    assert r.status_code in (401, 403)
