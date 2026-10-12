"""Tests for avatar/story chooser prerequisites and VOD download endpoint (iteration 23).

- Backend reads for /u profile exposing has_active_story + avatar_url for both testers.
- VOD download: tester (host) returns presigned URL; tester2 → 404 cross-host.
- Signed URL honors HTTP Range and content-type/content-disposition.
"""
import os
import requests
import pytest

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else 'https://699f8874-5189-442a-9e2c-3a2f8dbf3a24.preview.emergentagent.com'
VOD_ID = 'bc5978cacdc8'


def _login(email, pw):
    r = requests.post(f'{BASE}/api/auth/login', json={'email': email, 'password': pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()['access_token']


@pytest.fixture(scope='module')
def tester_token():
    return _login('tester@skali.local', 'Tester123!')


@pytest.fixture(scope='module')
def tester2_token():
    return _login('tester2@skali.local', 'Tester123!')


# ---- Profile prerequisites for the chooser ----
def test_tester2_profile_has_photo_and_story(tester_token):
    r = requests.get(f'{BASE}/api/users/tester2', headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p.get('avatar_url'), f'tester2 expected an avatar_url, got {p.get("avatar_url")!r}'
    assert p.get('has_active_story') is True, f'tester2 expected has_active_story=True, got {p.get("has_active_story")!r}'


def test_skalitester_profile_has_neither(tester_token):
    r = requests.get(f'{BASE}/api/users/skalitester', headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    assert not p.get('avatar_url'), f'skalitester expected no avatar, got {p.get("avatar_url")!r}'
    assert not p.get('has_active_story'), f'skalitester expected no active story'


# ---- VOD download endpoint ----
def test_vod_download_host_returns_presigned_url(tester_token):
    r = requests.get(f'{BASE}/api/stream/vods/{VOD_ID}/download',
                     headers={'Authorization': f'Bearer {tester_token}'}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'url' in data and data['url'].startswith('http'), data
    assert 'expires_at' in data

    # Perform a RANGE request to avoid downloading the whole file.
    rr = requests.get(data['url'], headers={'Range': 'bytes=0-1023'}, timeout=30, stream=True)
    try:
        assert rr.status_code in (200, 206), f'range status {rr.status_code}; headers={dict(rr.headers)}'
        ct = rr.headers.get('Content-Type', '')
        assert 'video/mp4' in ct or 'octet-stream' in ct, f'unexpected content-type {ct}'
        cd = rr.headers.get('Content-Disposition', '')
        assert 'attachment' in cd.lower(), f'expected attachment disposition, got {cd!r}'
    finally:
        rr.close()


def test_vod_download_cross_host_404(tester2_token):
    r = requests.get(f'{BASE}/api/stream/vods/{VOD_ID}/download',
                     headers={'Authorization': f'Bearer {tester2_token}'}, timeout=15)
    assert r.status_code == 404, r.text


def test_vods_list_includes_the_vod(tester_token):
    r = requests.get(f'{BASE}/api/stream/vods',
                     headers={'Authorization': f'Bearer {tester_token}'}, timeout=15)
    assert r.status_code == 200, r.text
    ids = [v.get('id') for v in r.json()]
    assert VOD_ID in ids, f'VOD {VOD_ID} not in {ids}'
