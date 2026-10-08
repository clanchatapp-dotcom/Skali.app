"""Skali Block 5 — Discovery / tags / closed NSFW / Choices / sponsored / storefront.

Runs against the external preview URL. HMAC-SHA256 hex of the raw JSON body is used
for identity+age webhook signatures (local preview secrets).
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
ADMIN_EMAIL = 'admin@skaliapp.com'
ADMIN_PASSWORD = 'SkaliLocalDev!2026'


# -------- helpers --------
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


def _login(email: str, password: str) -> str:
    r = requests.post(f'{BASE_URL}/api/auth/login',
                      json={'email': email, 'password': password}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()['access_token']


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


# ------------------------------------------------------------------
# Tag cap + dedupe + normalise
# ------------------------------------------------------------------
class TestTagRegistry:
    def test_free_user_tag_cap_dedupe_singularise(self):
        u = _register(name='TAG_free')
        r = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                          json={'tier': 'public', 'text': 'hi',
                                'tags': ['Gaming', 'gaming', 'cats', 'cats', 'art', 'music', 'design']},
                          timeout=20)
        assert r.status_code == 200, r.text
        tags = r.json().get('tags')
        # Free user cap=3, deduped, normalised, singularised (cats -> cat)
        assert tags == ['gaming', 'cat', 'art'], f'unexpected tags: {tags}'

    def test_explicit_freeform_tag_blocked_400(self):
        u = _register(name='TAG_explicit')
        r = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                          json={'tier': 'public', 'text': 'x', 'tags': ['porn']},
                          timeout=20)
        assert r.status_code == 400, r.text
        # offending word must NOT be echoed
        assert 'porn' not in r.text.lower()

    def test_hate_slur_blocked_generic_message(self):
        u = _register(name='TAG_slur')
        r = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                          json={'tier': 'public', 'text': 'x', 'tags': ['retard']},
                          timeout=20)
        assert r.status_code == 400, r.text
        assert 'retard' not in r.text.lower()

    def test_trending_and_similar_tags(self):
        # Seed a couple of gaming posts to ensure the tag exists in registry.
        u = _register(name='TAG_seed')
        for _ in range(2):
            requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                          json={'tier': 'public', 'text': 'play', 'tags': ['gaming']},
                          timeout=20)
        r = requests.get(f'{BASE_URL}/api/tags/similar?q=Gamers',
                         headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get('normalised') == 'gamer'
        found = [m['tag'] for m in data.get('matches', [])]
        assert 'gaming' in found, f'expected gaming in {found}'
        r2 = requests.get(f'{BASE_URL}/api/tags/trending',
                          headers=_hdr(u['token']), timeout=20)
        assert r2.status_code == 200, r2.text
        trend = r2.json().get('tags') or []
        assert isinstance(trend, list) and len(trend) > 0
        assert all('tag' in t and 'post_count' in t for t in trend)


# ------------------------------------------------------------------
# Auto-watchlist after >=3 blocked-tag attempts
# ------------------------------------------------------------------
class TestAutoWatchlist:
    def test_three_blocked_attempts_add_user_to_admin_watchlist(self):
        u = _register(name='TAG_abuse')
        for _ in range(3):
            requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                          json={'tier': 'public', 'text': 'x', 'tags': ['porn']},
                          timeout=20)
        # login as admin
        admin_tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.get(f'{BASE_URL}/api/admin/watchlist',
                         headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # response can be list or dict; normalise
        items = data if isinstance(data, list) else (data.get('items') or data.get('watchlist') or [])
        ids = [p.get('id') or p.get('user_id') for p in items]
        handles = [p.get('handle') for p in items]
        assert u['user']['id'] in ids or u['user']['handle'] in handles, \
            f"user {u['user']['id']} not on watchlist. items sample={items[:3]}"


# ------------------------------------------------------------------
# NSFW selector fail-closed + eligible flow
# ------------------------------------------------------------------
class TestNsfwSelector:
    def test_unverified_nsfw_tags_403_and_endpoint_returns_empty(self):
        u = _register(name='NSFW_unv')
        r = requests.get(f'{BASE_URL}/api/nsfw-tags',
                         headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json() == {'tags': [], 'eligible': False}
        rp = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                           json={'tier': 'public', 'text': 'x', 'nsfw_tags': ['@NSFW']},
                           timeout=20)
        assert rp.status_code == 403, rp.text

    def test_verified_adult_with_comfort_on_can_post_nsfw(self):
        u = _register(name='NSFW_ok', dob='1985-05-05')
        _fully_verify(u)
        # Enable Comfort-Zone NSFW
        rp = requests.put(f'{BASE_URL}/api/profile', headers=_hdr(u['token']),
                          json={'comfort_zone': {'nsfw': True, 'ai': True, 'language': True,
                                                 'violence': False, 'drugs': False}},
                          timeout=20)
        assert rp.status_code == 200, rp.text
        # /api/nsfw-tags eligible + closed vocab present
        rt = requests.get(f'{BASE_URL}/api/nsfw-tags',
                          headers=_hdr(u['token']), timeout=20)
        assert rt.status_code == 200, rt.text
        d = rt.json()
        assert d.get('eligible') is True, d
        assert '@NSFW' in d.get('tags', [])
        # Post with NSFW tags
        rpost = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                              json={'tier': 'public', 'text': 'adult',
                                    'nsfw_tags': ['@NSFW', '@GNSFW']}, timeout=20)
        assert rpost.status_code == 200, rpost.text
        assert rpost.json().get('nsfw') is True
        # /api/me should reflect account_nsfw=true
        rme = requests.get(f'{BASE_URL}/api/me', headers=_hdr(u['token']), timeout=20)
        assert rme.status_code == 200, rme.text
        assert rme.json().get('account_nsfw') is True


# ------------------------------------------------------------------
# Choices opt-in + sponsored gating + NSFW gating
# ------------------------------------------------------------------
class TestChoices:
    def test_default_opt_out_returns_empty(self):
        u = _register(name='CH_optout')
        r = requests.get(f'{BASE_URL}/api/choices', headers=_hdr(u['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d == {'opt_in': False, 'posts': [], 'sponsored': []}

    def test_opt_in_returns_lists_and_sponsored_only_here(self):
        # Verified creator seeds a public post with a common tag + sponsors it.
        creator = _register(name='CH_creator')
        _fully_verify(creator)
        rp = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(creator['token']),
                           json={'tier': 'public', 'text': 'sponsor me!',
                                 'tags': ['gaming']}, timeout=20)
        assert rp.status_code == 200, rp.text
        post_id = rp.json()['id']
        rs = requests.post(f'{BASE_URL}/api/sponsored', headers=_hdr(creator['token']),
                           json={'post_id': post_id}, timeout=20)
        assert rs.status_code == 200, rs.text
        assert rs.json().get('active') is True

        # Unverified user can't sponsor
        u2 = _register(name='CH_unv')
        rp2 = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u2['token']),
                            json={'tier': 'public', 'text': 'me too', 'tags': ['gaming']},
                            timeout=20)
        pid2 = rp2.json()['id']
        r403 = requests.post(f'{BASE_URL}/api/sponsored', headers=_hdr(u2['token']),
                             json={'post_id': pid2}, timeout=20)
        assert r403.status_code == 403, r403.text

        # Fan opts in, gets sponsored list carrying sponsored:true + sponsor_label
        fan = _register(name='CH_fan')
        opt = requests.post(f'{BASE_URL}/api/choices/opt-in', headers=_hdr(fan['token']),
                            timeout=20)
        assert opt.status_code == 200 and opt.json().get('opt_in') is True, opt.text
        rc = requests.get(f'{BASE_URL}/api/choices', headers=_hdr(fan['token']), timeout=20)
        assert rc.status_code == 200, rc.text
        d = rc.json()
        assert d.get('opt_in') is True
        assert isinstance(d.get('posts'), list)
        sp = d.get('sponsored') or []
        # Our sponsored post should be present with markers.
        got = [p for p in sp if p.get('id') == post_id]
        assert got, f'sponsored post {post_id} not surfaced. sponsored={sp[:2]}'
        assert got[0].get('sponsored') is True
        assert got[0].get('sponsor_label')

        # Sponsored labels appear only in /api/choices, not /api/feed
        rf = requests.get(f'{BASE_URL}/api/feed?scope=public',
                          headers=_hdr(fan['token']), timeout=20)
        assert rf.status_code == 200, rf.text
        feed = rf.json()
        feed_posts = feed if isinstance(feed, list) else feed.get('posts') or []
        for p in feed_posts:
            assert not p.get('sponsored'), f'feed leaked sponsored: {p.get("id")}'

    def test_nsfw_hidden_from_ineligible_in_choices(self):
        # Verified NSFW creator posts NSFW + sponsors it
        creator = _register(name='CH_nsfwCr')
        _fully_verify(creator)
        requests.put(f'{BASE_URL}/api/profile', headers=_hdr(creator['token']),
                     json={'comfort_zone': {'nsfw': True, 'ai': True, 'language': True,
                                            'violence': False, 'drugs': False}}, timeout=20)
        rp = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(creator['token']),
                           json={'tier': 'public', 'text': 'x',
                                 'tags': ['gaming'], 'nsfw_tags': ['@NSFW']}, timeout=20)
        assert rp.status_code == 200, rp.text
        pid = rp.json()['id']
        rs = requests.post(f'{BASE_URL}/api/sponsored', headers=_hdr(creator['token']),
                           json={'post_id': pid}, timeout=20)
        assert rs.status_code == 200, rs.text

        # Ineligible fan: opt-in and check NSFW hidden
        fan = _register(name='CH_inelig')
        requests.post(f'{BASE_URL}/api/choices/opt-in', headers=_hdr(fan['token']), timeout=20)
        rc = requests.get(f'{BASE_URL}/api/choices', headers=_hdr(fan['token']), timeout=20)
        assert rc.status_code == 200, rc.text
        d = rc.json()
        for p in d.get('posts', []) + d.get('sponsored', []):
            assert not p.get('nsfw'), f'NSFW leaked to ineligible user: {p.get("id")}'


# ------------------------------------------------------------------
# Offers + storefront + checkout PSP routing
# ------------------------------------------------------------------
class TestOffersStorefront:
    def test_verified_creator_offers_have_three_tiers(self):
        creator = _register(name='OFF_verif')
        _fully_verify(creator)
        handle = creator['user']['handle']
        # Unverified caller can still GET offers of a verified creator (public endpoint).
        fan = _register(name='OFF_fan')
        r = requests.get(f'{BASE_URL}/api/creators/{handle}/offers',
                         headers=_hdr(fan['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get('monetisation_enabled') is True
        tiers = d.get('tiers') or []
        prices = sorted([float(t['price']) for t in tiers])
        assert prices == [15.0, 30.0, 50.0], f'unexpected tiers: {tiers}'

    def test_storefront_lists_active_products(self):
        creator = _register(name='OFF_shop')
        _fully_verify(creator)
        rp = requests.post(f'{BASE_URL}/api/creator/shop/products',
                           headers=_hdr(creator['token']),
                           json={'title': 'TEST_ebook', 'kind': 'digital', 'price': 9.99,
                                 'description': 'test', 'download_url': 'https://x/x.pdf'},
                           timeout=20)
        assert rp.status_code == 200, rp.text
        product_id = rp.json()['id']
        handle = creator['user']['handle']
        fan = _register(name='OFF_buyer')
        r = requests.get(f'{BASE_URL}/api/creators/{handle}/shop',
                         headers=_hdr(fan['token']), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get('monetisation_enabled') is True
        ids = [p.get('id') for p in d.get('products', [])]
        assert product_id in ids

        # Buyer order
        ro = requests.post(f'{BASE_URL}/api/shop/order/{product_id}',
                           headers=_hdr(fan['token']), timeout=20)
        assert ro.status_code == 200, ro.text
        od = ro.json()
        assert od.get('checkout_url')
        assert od.get('psp') in ('stripe', 'ccbill', 'xsolla')

    def test_inner_circle_checkout_url_and_psp(self):
        creator = _register(name='OFF_icSFW')
        _fully_verify(creator)
        fan = _register(name='OFF_icFan')
        r = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(fan['token']),
                          json={'product': 'inner_circle',
                                'creator_handle': creator['user']['handle'], 'tier': 1},
                          timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get('checkout_url')
        # SFW creator => stripe
        assert d.get('psp') == 'stripe', d

    def test_nsfw_creator_routes_checkout_to_ccbill(self):
        creator = _register(name='OFF_icNSFW')
        _fully_verify(creator)
        # Flip creator NSFW ON and post one NSFW to set account_nsfw=true
        requests.put(f'{BASE_URL}/api/profile', headers=_hdr(creator['token']),
                     json={'comfort_zone': {'nsfw': True, 'ai': True, 'language': True,
                                            'violence': False, 'drugs': False}}, timeout=20)
        requests.post(f'{BASE_URL}/api/posts', headers=_hdr(creator['token']),
                      json={'tier': 'public', 'text': 'x', 'nsfw_tags': ['@NSFW']},
                      timeout=20)
        fan = _register(name='OFF_icNsfwFan')
        r = requests.post(f'{BASE_URL}/api/checkout/session', headers=_hdr(fan['token']),
                          json={'product': 'inner_circle',
                                'creator_handle': creator['user']['handle'], 'tier': 1},
                          timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get('psp') == 'ccbill', r.text


# ------------------------------------------------------------------
# Regression: existing endpoints still work
# ------------------------------------------------------------------
class TestRegression:
    def test_me_feed_entitlements_and_simple_post(self):
        u = _register(name='REG_user')
        # /api/me
        rme = requests.get(f'{BASE_URL}/api/me', headers=_hdr(u['token']), timeout=20)
        assert rme.status_code == 200, rme.text
        me = rme.json()
        assert me.get('id') == u['user']['id']
        # /api/feed?scope=public
        rf = requests.get(f'{BASE_URL}/api/feed?scope=public',
                          headers=_hdr(u['token']), timeout=20)
        assert rf.status_code == 200, rf.text
        # /api/posts SFW
        rp = requests.post(f'{BASE_URL}/api/posts', headers=_hdr(u['token']),
                           json={'tier': 'public', 'text': 'hello', 'tags': ['art']},
                           timeout=20)
        assert rp.status_code == 200, rp.text
        assert rp.json().get('tags') == ['art']
        # /api/entitlements
        re_ = requests.get(f'{BASE_URL}/api/entitlements',
                           headers=_hdr(u['token']), timeout=20)
        assert re_.status_code == 200, re_.text
