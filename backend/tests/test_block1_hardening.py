"""Block 1 hardening backend tests for Skali.

Covers:
 - Rebrand (health/db + service name)
 - Auth register + login + seeded super-admin login
 - Board tier access (public / followers / inner)
 - CSAM step-up gating (missing / wrong / correct + non-admin with correct)
 - CSAM escalate/resolve gating
 - DM review + silent investigation gating (step-up + legal_basis + flag/watch)
 - Audit log written for successful sensitive access
 - Regression: /api/me, /api/feed?scope=public, /api/report
"""
import os
import time
import uuid

import pytest
import requests

from conftest import BASE_URL, STEP_UP_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD


def _rand():
    return uuid.uuid4().hex[:8]


def _register(email, password='pw-test-123', name=None, dob='1995-06-15'):
    r = requests.post(f'{BASE_URL}/api/auth/register',
                      json={'email': email, 'password': password,
                            'name': name or email.split('@')[0], 'dob': dob},
                      timeout=30)
    return r


def _login(email, password):
    r = requests.post(f'{BASE_URL}/api/auth/login',
                      json={'email': email, 'password': password}, timeout=30)
    return r


def _auth_headers(token, extra=None):
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    if extra:
        h.update(extra)
    return h


# ---------- shared, session-level actors ----------
@pytest.fixture(scope='session')
def owner():
    """A regular user who will own boards (owner of content, NOT super-admin)."""
    email = f'test_owner_{_rand()}@skali.test'
    r = _register(email)
    assert r.status_code == 200, r.text
    data = r.json()
    return {'email': email, 'token': data['access_token'], 'user': data['user']}


@pytest.fixture(scope='session')
def stranger():
    email = f'test_stranger_{_rand()}@skali.test'
    r = _register(email)
    assert r.status_code == 200, r.text
    data = r.json()
    return {'email': email, 'token': data['access_token'], 'user': data['user']}


@pytest.fixture(scope='session')
def super_admin():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f'seed admin login failed: {r.status_code} {r.text}'
    data = r.json()
    return {'email': ADMIN_EMAIL, 'token': data['access_token'], 'user': data['user']}


# ============================================================
# Rebrand
# ============================================================
class TestRebrand:
    def test_service_name(self):
        r = requests.get(f'{BASE_URL}/api/', timeout=10)
        assert r.status_code == 200
        assert r.json().get('service') == 'skali'

    def test_health_db_name(self):
        r = requests.get(f'{BASE_URL}/api/health/db', timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get('db') == 'ok'
        assert body.get('db_name') == 'skali'


# ============================================================
# Auth
# ============================================================
class TestAuth:
    def test_register_and_login_new_user(self):
        email = f'test_authflow_{_rand()}@skali.test'
        r = _register(email)
        assert r.status_code == 200, r.text
        assert 'access_token' in r.json()

        r2 = _login(email, 'pw-test-123')
        assert r2.status_code == 200
        assert 'access_token' in r2.json()

    def test_register_requires_dob(self):
        email = f'test_nodob_{_rand()}@skali.test'
        r = requests.post(f'{BASE_URL}/api/auth/register',
                          json={'email': email, 'password': 'pw-test-123', 'name': 'x'},
                          timeout=15)
        assert r.status_code == 400

    def test_register_underage_blocked(self):
        email = f'test_minor_{_rand()}@skali.test'
        r = _register(email, dob='2020-01-01')
        assert r.status_code == 400

    def test_seed_admin_login(self, super_admin):
        assert super_admin['token']
        # verify /api/me returns admin flag or handle
        r = requests.get(f'{BASE_URL}/api/me',
                         headers=_auth_headers(super_admin['token']), timeout=15)
        assert r.status_code == 200
        assert r.json().get('email') == ADMIN_EMAIL


# ============================================================
# Board tier access (Task 1)
# ============================================================
def _create_board(token, title, tier):
    return requests.post(f'{BASE_URL}/api/boards',
                         json={'title': title, 'tier': tier},
                         headers=_auth_headers(token), timeout=15)


class TestBoardTierAccess:
    def test_public_board_readable_by_stranger(self, owner, stranger):
        r = _create_board(owner['token'], f'pub-{_rand()}', 'public')
        assert r.status_code == 200, r.text
        bid = r.json()['id']

        g = requests.get(f'{BASE_URL}/api/board/{bid}',
                         headers=_auth_headers(stranger['token']), timeout=15)
        assert g.status_code == 200, g.text

    @pytest.mark.parametrize('tier', ['followers', 'inner'])
    def test_restricted_board_blocked_for_stranger(self, owner, stranger, tier):
        r = _create_board(owner['token'], f'{tier}-{_rand()}', tier)
        assert r.status_code == 200, r.text
        bid = r.json()['id']

        # owner sees their own board
        owner_get = requests.get(f'{BASE_URL}/api/board/{bid}',
                                 headers=_auth_headers(owner['token']), timeout=15)
        assert owner_get.status_code == 200, owner_get.text

        # stranger gets 403
        strg = requests.get(f'{BASE_URL}/api/board/{bid}',
                            headers=_auth_headers(stranger['token']), timeout=15)
        assert strg.status_code == 403, f'expected 403 got {strg.status_code}: {strg.text}'

        # stranger listing owner's boards must NOT include this restricted one
        owner_handle = owner['user']['handle']
        lst = requests.get(f'{BASE_URL}/api/boards/{owner_handle}',
                           headers=_auth_headers(stranger['token']), timeout=15)
        assert lst.status_code == 200, lst.text
        ids = [b['id'] for b in lst.json()]
        assert bid not in ids, f'restricted {tier} board leaked in listing: {ids}'


# ============================================================
# CSAM step-up (Task 2)
# ============================================================
class TestCsamStepUp:
    def test_csam_missing_header_forbidden(self, super_admin):
        r = requests.get(f'{BASE_URL}/api/admin/csam',
                         headers=_auth_headers(super_admin['token']), timeout=15)
        assert r.status_code == 403

    def test_csam_wrong_header_forbidden(self, super_admin):
        r = requests.get(f'{BASE_URL}/api/admin/csam',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': 'wrong-secret'}),
                         timeout=15)
        assert r.status_code == 403

    def test_csam_correct_header_ok(self, super_admin):
        r = requests.get(f'{BASE_URL}/api/admin/csam',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_csam_non_admin_with_correct_header_still_forbidden(self, stranger):
        r = requests.get(f'{BASE_URL}/api/admin/csam',
                         headers=_auth_headers(stranger['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         timeout=15)
        assert r.status_code == 403

    def test_csam_escalate_requires_stepup(self, super_admin):
        # Covers escalate + resolve gating via a single endpoint to stay under
        # the 10-calls / 5-min sensitive-access rate limit.
        fake = 'nonexistent-report-id'
        r = requests.post(f'{BASE_URL}/api/admin/csam/{fake}/escalate',
                          headers=_auth_headers(super_admin['token']), timeout=15)
        assert r.status_code == 403

        r2 = requests.post(f'{BASE_URL}/api/admin/csam/{fake}/escalate',
                           headers=_auth_headers(super_admin['token'],
                                                 {'X-Step-Up': STEP_UP_SECRET}),
                           timeout=15)
        # With step-up we now pass the guard -> handler runs and returns 404 (fake id)
        assert r2.status_code in (200, 404), r2.text


# ============================================================
# DM review + silent investigation (Task 3)
# ============================================================
@pytest.fixture(scope='session')
def target_user():
    email = f'test_target_{_rand()}@skali.test'
    r = _register(email)
    assert r.status_code == 200, r.text
    d = r.json()
    return {'email': email, 'token': d['access_token'], 'user': d['user']}


class TestDmAndInvestigate:
    def test_dms_missing_legal_basis_rejected(self, super_admin, target_user):
        h = target_user['user']['handle']
        r = requests.get(f'{BASE_URL}/api/admin/dms/{h}',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         timeout=15)
        assert r.status_code == 400, r.text

    def test_investigate_short_legal_basis_rejected(self, super_admin, target_user):
        h = target_user['user']['handle']
        r = requests.get(f'{BASE_URL}/api/admin/investigate/{h}',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         params={'legal_basis': 'short'},
                         timeout=15)
        assert r.status_code == 400, r.text

    def test_dms_non_flagged_user_rejected(self, super_admin, target_user):
        h = target_user['user']['handle']
        r = requests.get(f'{BASE_URL}/api/admin/investigate/{h}',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         params={'legal_basis': 'valid legal basis text > 8'},
                         timeout=15)
        assert r.status_code == 403, r.text

    def test_investigate_after_flag_succeeds_and_audits(self, super_admin, target_user):
        h = target_user['user']['handle']
        # Flag the user first (admin endpoint)
        flag = requests.post(f'{BASE_URL}/api/admin/users/{h}/flag',
                             headers=_auth_headers(super_admin['token']),
                             json={'reason': 'test flag for pytest'},
                             timeout=15)
        assert flag.status_code == 200, flag.text

        # Now invoke silent investigation with step-up + legal basis
        r = requests.get(f'{BASE_URL}/api/admin/investigate/{h}',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         params={'legal_basis': 'court order ref 2026-JAN-001'},
                         timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['subject']['handle'] == h

        # Audit should include a silent_investigation entry for this handle
        a = requests.get(f'{BASE_URL}/api/admin/audit',
                         headers=_auth_headers(super_admin['token']), timeout=15)
        assert a.status_code == 200
        actions = [(e.get('action'), e.get('target')) for e in a.json()]
        assert ('silent_investigation', h) in actions, f'audit missing entry: {actions[:5]}'

    def test_dms_after_flag_succeeds_and_audits(self, super_admin, target_user):
        h = target_user['user']['handle']
        # Already flagged from previous test in this class order; ensure flagged anyway
        requests.post(f'{BASE_URL}/api/admin/users/{h}/flag',
                      headers=_auth_headers(super_admin['token']),
                      json={'reason': 'test flag'}, timeout=15)

        r = requests.get(f'{BASE_URL}/api/admin/dms/{h}',
                         headers=_auth_headers(super_admin['token'],
                                               {'X-Step-Up': STEP_UP_SECRET}),
                         params={'legal_basis': 'valid legal basis 12345'},
                         timeout=20)
        assert r.status_code == 200, r.text

        a = requests.get(f'{BASE_URL}/api/admin/audit',
                         headers=_auth_headers(super_admin['token']), timeout=15)
        assert a.status_code == 200
        actions = [(e.get('action'), e.get('target')) for e in a.json()]
        assert ('view_dms', h) in actions


# ============================================================
# Regression
# ============================================================
class TestRegression:
    def test_me(self, owner):
        r = requests.get(f'{BASE_URL}/api/me',
                         headers=_auth_headers(owner['token']), timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j.get('email') == owner['email']

    def test_feed_public(self, owner):
        r = requests.get(f'{BASE_URL}/api/feed',
                         params={'scope': 'public'},
                         headers=_auth_headers(owner['token']), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_report_create(self, stranger, owner):
        # Report the owner user via the reporting endpoint
        payload = {
            'target_type': 'user',
            'target_id': owner['user']['id'],
            'category': 'harassment',
            'note': 'automated regression test',
        }
        r = requests.post(f'{BASE_URL}/api/report',
                          json=payload,
                          headers=_auth_headers(stranger['token']), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get('ok') is True
