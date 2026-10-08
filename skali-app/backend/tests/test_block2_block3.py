"""Skali Block 2 (Verification spine) + Block 3 (Payments/entitlements) tests.

Runs against the external preview URL (per test policy). All webhook signatures
are HMAC-SHA256 hex over the EXACT raw JSON body bytes (must send same bytes).
"""
import os
import json
import hmac
import hashlib
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    'EXPO_BACKEND_URL',
    'https://1364d24c-2629-41c4-b227-b4ccdd97873e.preview.emergentagent.com',
).rstrip('/')

YOTI_SECRET = 'local_yoti_secret'
ONEID_SECRET = 'local_oneid_secret'
STRIPE_SECRET = 'local_stripe_secret'


def _sig(secret: str, raw: bytes) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _register(dob: str, name: str = 'TEST_User') -> dict:
    tag = uuid.uuid4().hex[:8]
    email = f'test_{tag}@example.com'
    r = requests.post(f'{BASE_URL}/api/auth/register', json={
        'email': email, 'password': 'Passw0rd!', 'name': f'{name}_{tag}', 'dob': dob,
    }, timeout=30)
    assert r.status_code == 200, f'register failed: {r.status_code} {r.text}'
    d = r.json()
    return {'email': email, 'token': d['access_token'], 'user': d['user']}


def _hdr(tok: str) -> dict:
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


# ------------------- Block 2: verification spine -------------------

class TestBlock2Verification:
    def test_new_user_unverified_and_monetisation_locked(self):
        u = _register('1990-01-01')
        r = requests.get(f'{BASE_URL}/api/me', headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me['verification']['identity']['status'] == 'unverified'
        assert me['verification']['age']['status'] == 'unverified'
        assert me['monetisation_enabled'] is False

    def test_verification_start_sets_pending(self):
        u = _register('1990-01-01')
        r = requests.post(f'{BASE_URL}/api/verification/start',
                          headers=_hdr(u['token']),
                          json={'type': 'identity', 'provider': 'yoti'}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['status'] == 'pending'
        assert d.get('redirect_url', '').startswith('http')
        # verify /api/verification/status reflects pending
        s = requests.get(f'{BASE_URL}/api/verification/status',
                         headers=_hdr(u['token']), timeout=20).json()
        assert s['verification']['identity']['status'] == 'pending'
        assert s['monetisation_enabled'] is False

    def test_unsigned_yoti_webhook_rejected(self):
        body = json.dumps({'user_id': 'x', 'type': 'identity', 'status': 'verified'}).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/yoti', data=body,
                          headers={'Content-Type': 'application/json'}, timeout=20)
        assert r.status_code == 401

    def test_wrong_signature_yoti_webhook_rejected(self):
        body = json.dumps({'user_id': 'x', 'type': 'identity', 'status': 'verified'}).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/yoti', data=body,
                          headers={'Content-Type': 'application/json',
                                   'X-Yoti-Signature': 'deadbeef'}, timeout=20)
        assert r.status_code == 401

    def test_signed_yoti_oneid_flip_monetisation_true(self):
        u = _register('1990-01-01')
        # identity via yoti
        body_id = json.dumps({'user_id': u['user']['id'], 'type': 'identity',
                              'status': 'verified'}).encode()
        r1 = requests.post(f'{BASE_URL}/api/webhooks/yoti', data=body_id,
                           headers={'Content-Type': 'application/json',
                                    'X-Yoti-Signature': _sig(YOTI_SECRET, body_id)},
                           timeout=20)
        assert r1.status_code == 200, r1.text
        # age via oneid
        body_age = json.dumps({'user_id': u['user']['id'], 'type': 'age',
                               'status': 'verified', 'region': 'GB'}).encode()
        r2 = requests.post(f'{BASE_URL}/api/webhooks/oneid', data=body_age,
                           headers={'Content-Type': 'application/json',
                                    'X-OneID-Signature': _sig(ONEID_SECRET, body_age)},
                           timeout=20)
        assert r2.status_code == 200, r2.text
        s = requests.get(f'{BASE_URL}/api/verification/status',
                         headers=_hdr(u['token']), timeout=20).json()
        assert s['verification']['identity']['status'] == 'verified'
        assert s['verification']['age']['status'] == 'verified'
        assert s['monetisation_enabled'] is True
        me = requests.get(f'{BASE_URL}/api/me', headers=_hdr(u['token']), timeout=20).json()
        assert me['monetisation_enabled'] is True

    def test_minor_age_verified_forced_failed(self):
        u = _register('2012-01-01')  # under 18
        body = json.dumps({'user_id': u['user']['id'], 'type': 'age',
                           'status': 'verified', 'region': 'GB'}).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/oneid', data=body,
                          headers={'Content-Type': 'application/json',
                                   'X-OneID-Signature': _sig(ONEID_SECRET, body)},
                          timeout=20)
        assert r.status_code == 200, r.text
        s = requests.get(f'{BASE_URL}/api/verification/status',
                         headers=_hdr(u['token']), timeout=20).json()
        assert s['verification']['age']['status'] == 'failed', s
        assert s['monetisation_enabled'] is False


# ------------------- Block 3: entitlements + checkout + PSP -------------------

def _fully_verify(u: dict):
    for vtype, secret, path, header in [
        ('identity', YOTI_SECRET, 'yoti', 'X-Yoti-Signature'),
        ('age', ONEID_SECRET, 'oneid', 'X-OneID-Signature'),
    ]:
        payload = {'user_id': u['user']['id'], 'type': vtype, 'status': 'verified'}
        if vtype == 'age':
            payload['region'] = 'GB'
        body = json.dumps(payload).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/{path}', data=body,
                          headers={'Content-Type': 'application/json',
                                   header: _sig(secret, body)}, timeout=20)
        assert r.status_code == 200, r.text


class TestBlock3Payments:
    def test_fresh_user_entitlements_empty(self):
        u = _register('1990-01-01')
        r = requests.get(f'{BASE_URL}/api/entitlements', headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['entitlements'] == []
        assert d['premium'] is False

    def test_premium_checkout_quote_and_psp(self):
        buyer = _register('1990-01-01')
        r = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                          json={'product': 'premium', 'amount': 6, 'vat_rate': 0.20}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['psp'] == 'stripe'
        assert d['quote']['creator_net'] == 0
        assert 'session_id' in d

    def test_inner_circle_quote_and_stripe_when_sfw(self):
        creator = _register('1990-01-01', name='CREATOR')
        _fully_verify(creator)
        buyer = _register('1990-01-01', name='BUYER')
        creator_handle = creator['user']['handle']
        r = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                          json={'product': 'inner_circle', 'creator_handle': creator_handle,
                                'tier': 1, 'vat_rate': 0.20}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['psp'] == 'stripe', d
        q = d['quote']
        assert q['net_ex_vat'] == 12.5
        assert q['skali_fee'] == 1.25
        assert abs(q['creator_net'] - 10.82) <= 0.02, q
        return {'buyer': buyer, 'creator': creator, 'session_id': d['session_id']}

    def test_stripe_webhook_unsigned_rejected(self):
        body = json.dumps({'event': 'checkout.completed', 'session_id': 'x'}).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body,
                          headers={'Content-Type': 'application/json'}, timeout=20)
        assert r.status_code == 401

    def test_stripe_webhook_fulfils_premium(self):
        buyer = _register('1990-01-01')
        rc = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                           json={'product': 'premium', 'amount': 6, 'vat_rate': 0.20}, timeout=20)
        sid = rc.json()['session_id']
        body = json.dumps({'event': 'checkout.completed', 'session_id': sid}).encode()
        r = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body,
                          headers={'Content-Type': 'application/json',
                                   'Stripe-Signature': _sig(STRIPE_SECRET, body)}, timeout=20)
        assert r.status_code == 200, r.text
        ent = requests.get(f'{BASE_URL}/api/entitlements',
                           headers=_hdr(buyer['token']), timeout=20).json()
        assert ent['premium'] is True, ent

    def test_nsfw_flip_routes_tip_to_ccbill_with_tip_fee(self):
        creator = _register('1990-01-01', name='NSFWCREATOR')
        _fully_verify(creator)
        # flip creator to NSFW
        rf = requests.post(f'{BASE_URL}/api/account/nsfw-flip',
                           headers=_hdr(creator['token']), timeout=20)
        assert rf.status_code == 200, rf.text
        assert rf.json().get('account_nsfw') is True
        buyer = _register('1990-01-01', name='TIPBUYER')
        # tip £10, vat 0.20 -> net 8.33, tip fee 7.5% => 0.625 ≈ 0.62 or 0.63
        r = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                          json={'product': 'tip', 'creator_handle': creator['user']['handle'],
                                'amount': 10, 'vat_rate': 0.20}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['psp'] == 'ccbill', d
        # 7.5% of net_ex_vat (10/1.2 = 8.333...) ~= 0.625
        assert abs(d['quote']['skali_fee'] - 0.625) < 0.02, d['quote']

    def test_chargeback_clawback(self):
        creator = _register('1990-01-01', name='CHARGEBACKCREATOR')
        _fully_verify(creator)
        buyer = _register('1990-01-01', name='CHARGEBUYER')
        # Inner circle checkout
        rc = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                           json={'product': 'inner_circle',
                                 'creator_handle': creator['user']['handle'],
                                 'tier': 1, 'vat_rate': 0.20}, timeout=20)
        assert rc.status_code == 200, rc.text
        sid = rc.json()['session_id']
        # Fulfil
        body = json.dumps({'event': 'checkout.completed', 'session_id': sid}).encode()
        rf = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body,
                           headers={'Content-Type': 'application/json',
                                    'Stripe-Signature': _sig(STRIPE_SECRET, body)}, timeout=20)
        assert rf.status_code == 200, rf.text
        # Read creator finance before chargeback
        fin_before = requests.get(f'{BASE_URL}/api/creator/finance',
                                  headers=_hdr(creator['token']), timeout=20).json()
        pending_before = fin_before['pending_payout']
        # Chargeback
        body_cb = json.dumps({'event': 'charge.dispute.created', 'session_id': sid}).encode()
        rc2 = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body_cb,
                            headers={'Content-Type': 'application/json',
                                     'Stripe-Signature': _sig(STRIPE_SECRET, body_cb)}, timeout=20)
        assert rc2.status_code == 200, rc2.text
        fin_after = requests.get(f'{BASE_URL}/api/creator/finance',
                                 headers=_hdr(creator['token']), timeout=20).json()
        assert fin_after['pending_payout'] < pending_before, (pending_before, fin_after)

    def test_require_monetisation_creator_finance(self):
        u = _register('1990-01-01', name='UNVERIFIED')
        r = requests.get(f'{BASE_URL}/api/creator/finance', headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 403
        _fully_verify(u)
        r2 = requests.get(f'{BASE_URL}/api/creator/finance', headers=_hdr(u['token']), timeout=20)
        assert r2.status_code == 200, r2.text


# ------------------- Regression: existing flows unaffected -------------------

class TestRegression:
    def test_register_login_me_feed(self):
        u = _register('1990-01-01', name='REG')
        # Login
        r = requests.post(f'{BASE_URL}/api/auth/login',
                          json={'email': u['email'], 'password': 'Passw0rd!'}, timeout=20)
        assert r.status_code == 200, r.text
        tok = r.json()['access_token']
        # /me
        me = requests.get(f'{BASE_URL}/api/me', headers=_hdr(tok), timeout=20)
        assert me.status_code == 200
        assert 'verification' in me.json()
        # public feed
        f = requests.get(f'{BASE_URL}/api/feed?scope=public', headers=_hdr(tok), timeout=20)
        assert f.status_code == 200, f.text
