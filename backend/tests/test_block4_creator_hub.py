"""Skali Block 4 (Creator Hub) + verified-badge serializer tests.

Runs against the external preview URL. All webhook signatures are HMAC-SHA256
hex over the EXACT raw JSON body bytes. Every /api/creator/* endpoint is gated
by require_monetisation (identity+age verified).
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


def _hdr(tok: str) -> dict:
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


def _register(dob: str = '1990-01-01', name: str = 'TEST_User') -> dict:
    tag = uuid.uuid4().hex[:8]
    email = f'test_{tag}@example.com'
    r = requests.post(f'{BASE_URL}/api/auth/register', json={
        'email': email, 'password': 'Passw0rd!', 'name': f'{name}_{tag}', 'dob': dob,
    }, timeout=30)
    assert r.status_code == 200, f'register failed: {r.status_code} {r.text}'
    d = r.json()
    return {'email': email, 'token': d['access_token'], 'user': d['user']}


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


def _buy_and_fulfil(buyer: dict, creator_handle: str, product: str,
                    tier: int | None = None, amount: float | None = None) -> str:
    """Create checkout + send signed stripe checkout.completed. Returns session_id."""
    payload = {'product': product, 'creator_handle': creator_handle, 'vat_rate': 0.20}
    if tier is not None:
        payload['tier'] = tier
    if amount is not None:
        payload['amount'] = amount
    rc = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(buyer['token']),
                       json=payload, timeout=20)
    assert rc.status_code == 200, rc.text
    sid = rc.json()['session_id']
    body = json.dumps({'event': 'checkout.completed', 'session_id': sid}).encode()
    rw = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body,
                       headers={'Content-Type': 'application/json',
                                'Stripe-Signature': _sig(STRIPE_SECRET, body)}, timeout=20)
    assert rw.status_code == 200, rw.text
    return sid


# -------------------------------------------------------------------
# Session fixture: shared verified creator + buyer with an inner_circle
# subscription and a tip. Used across Overview/Subscribers/Finance tests.
# -------------------------------------------------------------------
@pytest.fixture(scope='module')
def scenario():
    creator = _register(name='HUBCREATOR')
    _fully_verify(creator)
    buyer = _register(name='HUBBUYER')
    creator_handle = creator['user']['handle']
    # Inner Circle subscription (£15 tier 1)
    _buy_and_fulfil(buyer, creator_handle, 'inner_circle', tier=1)
    # £5 tip
    _buy_and_fulfil(buyer, creator_handle, 'tip', amount=5)
    return {'creator': creator, 'buyer': buyer, 'creator_handle': creator_handle}


# -------------------- Gating (require_monetisation) --------------------

class TestGating:
    """Every /api/creator/* endpoint is 403 for unverified, 200 for verified."""
    ENDPOINTS = [
        ('GET', '/api/creator/overview'),
        ('GET', '/api/creator/subscribers'),
        ('GET', '/api/creator/shop'),
        ('GET', '/api/creator/finance'),
        ('GET', '/api/creator/finance/export.csv'),
        ('GET', '/api/creator/finance/tax-docs'),
        ('GET', '/api/creator/payouts'),
    ]

    def test_gating_403_then_200(self):
        u = _register(name='GATE')
        for method, path in self.ENDPOINTS:
            r = requests.request(method, f'{BASE_URL}{path}', headers=_hdr(u['token']),
                                 timeout=20)
            assert r.status_code == 403, f'{path} expected 403, got {r.status_code} {r.text}'
        _fully_verify(u)
        for method, path in self.ENDPOINTS:
            r = requests.request(method, f'{BASE_URL}{path}', headers=_hdr(u['token']),
                                 timeout=20)
            assert r.status_code == 200, f'{path} expected 200, got {r.status_code} {r.text}'


# -------------------- Overview --------------------

class TestOverview:
    def test_overview_after_subscription_and_tip(self, scenario):
        r = requests.get(f'{BASE_URL}/api/creator/overview',
                         headers=_hdr(scenario['creator']['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['revenue_this_month'] > 0, d
        assert d['new_subs_this_month'] >= 1, d
        assert d['tips_this_month'] > 0, d
        assert d['active_subscribers'] >= 1, d
        # No prior-month revenue in this fresh test creator => growth 100
        assert d['growth_pct'] == 100.0, d
        assert 'pending_payout' in d
        assert d['pending_payout'] > 0


# -------------------- Subscribers --------------------

class TestSubscribers:
    def test_subscribers_list_contains_buyer(self, scenario):
        r = requests.get(f'{BASE_URL}/api/creator/subscribers',
                         headers=_hdr(scenario['creator']['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['active'] >= 1, d
        assert 'churn_this_month' in d and 'renewals_this_month' in d
        buyer_handle = scenario['buyer']['user']['handle']
        handles = [s['buyer_handle'] for s in d['subscribers']]
        assert buyer_handle in handles, (buyer_handle, handles)


# -------------------- Shop --------------------

class TestShop:
    def test_digital_shop_flow_end_to_end(self):
        creator = _register(name='SHOPCREATOR')
        _fully_verify(creator)
        buyer = _register(name='SHOPBUYER')
        # Create digital product
        prod_body = {'title': 'TEST_Zine', 'kind': 'digital', 'price': 4.99,
                     'download_url': 'https://cdn.skali.example/zine.pdf'}
        rp = requests.post(f'{BASE_URL}/api/creator/shop/products',
                           headers=_hdr(creator['token']), json=prod_body, timeout=20)
        assert rp.status_code == 200, rp.text
        prod = rp.json()
        assert prod['kind'] == 'digital' and prod['active'] is True
        product_id = prod['id']
        # Buyer orders
        ro = requests.post(f'{BASE_URL}/api/shop/order/{product_id}',
                           headers=_hdr(buyer['token']), timeout=20)
        assert ro.status_code == 200, ro.text
        odata = ro.json()
        assert odata['psp'] == 'stripe', odata  # SFW creator
        assert 'checkout_url' in odata
        sid = odata['session_id']
        # Signed stripe checkout.completed
        body = json.dumps({'event': 'checkout.completed', 'session_id': sid}).encode()
        rw = requests.post(f'{BASE_URL}/api/webhooks/stripe', data=body,
                           headers={'Content-Type': 'application/json',
                                    'Stripe-Signature': _sig(STRIPE_SECRET, body)},
                           timeout=20)
        assert rw.status_code == 200, rw.text
        # Creator shop should show a delivered order
        rs = requests.get(f'{BASE_URL}/api/creator/shop',
                         headers=_hdr(creator['token']), timeout=20)
        assert rs.status_code == 200, rs.text
        shop = rs.json()
        orders = [o for o in shop['orders'] if o.get('product_id') == product_id]
        assert orders, shop
        assert orders[0]['fulfilment_status'] == 'delivered', orders[0]
        # Buyer entitlements now contains a 'download'
        re_ = requests.get(f'{BASE_URL}/api/entitlements',
                           headers=_hdr(buyer['token']), timeout=20)
        assert re_.status_code == 200, re_.text
        ents = re_.json()['entitlements']
        assert any(e.get('type') == 'download' for e in ents), ents
        # Soft-delete
        rd = requests.delete(f'{BASE_URL}/api/creator/shop/products/{product_id}',
                             headers=_hdr(creator['token']), timeout=20)
        assert rd.status_code == 200, rd.text
        rs2 = requests.get(f'{BASE_URL}/api/creator/shop',
                          headers=_hdr(creator['token']), timeout=20).json()
        assert product_id not in [p['id'] for p in rs2['products']], rs2

    def test_shop_order_routes_ccbill_after_nsfw_flip(self):
        creator = _register(name='NSFWSHOP')
        _fully_verify(creator)
        buyer = _register(name='NSFWSHOPBUYER')
        # Product BEFORE flip
        rp = requests.post(f'{BASE_URL}/api/creator/shop/products',
                           headers=_hdr(creator['token']),
                           json={'title': 'TEST_Print', 'kind': 'digital', 'price': 3.5,
                                 'download_url': 'https://cdn/x.pdf'}, timeout=20)
        assert rp.status_code == 200, rp.text
        product_id = rp.json()['id']
        # Flip creator to NSFW
        rf = requests.post(f'{BASE_URL}/api/account/nsfw-flip',
                           headers=_hdr(creator['token']), timeout=20)
        assert rf.status_code == 200 and rf.json().get('account_nsfw') is True, rf.text
        # New order should now route ccbill
        ro = requests.post(f'{BASE_URL}/api/shop/order/{product_id}',
                           headers=_hdr(buyer['token']), timeout=20)
        assert ro.status_code == 200, ro.text
        assert ro.json()['psp'] == 'ccbill', ro.json()


# -------------------- Finance --------------------

class TestFinance:
    def test_finance_totals_shape(self, scenario):
        r = requests.get(f'{BASE_URL}/api/creator/finance',
                         headers=_hdr(scenario['creator']['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        tot = d['totals']
        for k in ('gross', 'vat', 'psp_fee', 'skali_fee', 'creator_net'):
            assert k in tot, tot
        assert tot['gross'] > 0 and tot['creator_net'] > 0, tot

    def test_finance_csv_export(self, scenario):
        r = requests.get(f'{BASE_URL}/api/creator/finance/export.csv',
                         headers=_hdr(scenario['creator']['token']), timeout=20)
        assert r.status_code == 200, r.text
        assert 'text/csv' in r.headers.get('content-type', '').lower(), r.headers
        assert r.text.startswith('date,product,psp'), r.text[:80]

    def test_finance_tax_docs(self, scenario):
        r = requests.get(f'{BASE_URL}/api/creator/finance/tax-docs',
                         headers=_hdr(scenario['creator']['token']), timeout=20)
        assert r.status_code == 200, r.text
        docs = r.json()['tax_documents']
        assert docs, r.text
        assert 'Skali' in docs[0]['issuer'], docs[0]


# -------------------- Payouts --------------------

class TestPayouts:
    def test_payout_settings_persist(self):
        creator = _register(name='PAYCREATOR')
        _fully_verify(creator)
        r = requests.put(f'{BASE_URL}/api/creator/payout-settings',
                        headers=_hdr(creator['token']),
                        json={'schedule': 'weekly', 'currency': 'gbp'}, timeout=20)
        assert r.status_code == 200, r.text
        # Verify persistence via GET /api/creator/payouts
        r2 = requests.get(f'{BASE_URL}/api/creator/payouts',
                         headers=_hdr(creator['token']), timeout=20)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d['schedule'] == 'weekly', d
        assert d['currency'] == 'GBP', d
        for k in ('pending', 'available', 'paid', 'payout_kyc'):
            assert k in d, d

    def test_first_payout_request_returns_202_kyc_required(self):
        creator = _register(name='FIRSTPAYOUT')
        _fully_verify(creator)
        # Add pending balance via a purchase so it's realistic
        buyer = _register(name='FIRSTPAYBUYER')
        _buy_and_fulfil(buyer, creator['user']['handle'], 'inner_circle', tier=1)
        r = requests.post(f'{BASE_URL}/api/creator/payouts/request',
                          headers=_hdr(creator['token']), timeout=20)
        assert r.status_code == 202, (r.status_code, r.text)
        d = r.json()
        assert d.get('kyc_required') is True, d
        assert 'kyc_url' in d, d
        # payout_kyc status becomes 'pending'
        p = requests.get(f'{BASE_URL}/api/creator/payouts',
                        headers=_hdr(creator['token']), timeout=20).json()
        assert (p.get('payout_kyc') or {}).get('status') == 'pending', p


# -------------------- Verified badge serializer --------------------

class TestVerifiedBadge:
    def test_verified_true_for_identity_verified_creator(self):
        creator = _register(name='VERBADGE')
        _fully_verify(creator)
        handle = creator['user']['handle']
        r = requests.get(f'{BASE_URL}/api/users/{handle}',
                        headers=_hdr(creator['token']), timeout=20)
        assert r.status_code == 200, r.text
        prof = r.json()
        assert prof.get('verified') is True, prof

    def test_verified_false_for_unverified_user(self):
        u = _register(name='UNVERIFBADGE')
        handle = u['user']['handle']
        r = requests.get(f'{BASE_URL}/api/users/{handle}',
                        headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        prof = r.json()
        assert prof.get('verified') is False, prof

    def test_post_author_verified_flag(self):
        creator = _register(name='POSTAUTH')
        _fully_verify(creator)
        # Create a public post
        rp = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(creator['token']),
                           json={'tier': 'public', 'text': 'TEST_verified_badge_post'},
                           timeout=20)
        assert rp.status_code == 200, rp.text
        handle = creator['user']['handle']
        rl = requests.get(f'{BASE_URL}/api/users/{handle}/posts',
                         headers=_hdr(creator['token']), timeout=20)
        assert rl.status_code == 200, rl.text
        posts = rl.json() if isinstance(rl.json(), list) else rl.json().get('posts', [])
        assert posts, rl.text
        first = posts[0]
        author = first.get('author') or {}
        assert author.get('verified') is True, first


# -------------------- Regression --------------------

class TestRegression:
    def test_me_feed_entitlements(self):
        u = _register(name='REGB4')
        me = requests.get(f'{BASE_URL}/api/me', headers=_hdr(u['token']), timeout=20)
        assert me.status_code == 200 and 'verification' in me.json()
        f = requests.get(f'{BASE_URL}/api/feed?scope=public',
                        headers=_hdr(u['token']), timeout=20)
        assert f.status_code == 200
        e = requests.get(f'{BASE_URL}/api/entitlements',
                        headers=_hdr(u['token']), timeout=20)
        assert e.status_code == 200
        d = e.json()
        assert 'entitlements' in d and 'premium' in d
