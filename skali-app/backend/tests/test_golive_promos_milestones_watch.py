"""Tests for the new review-request features:
  - Go-live gating (POST /api/live/start, /api/stream/ingress[/reset], /api/stream/start)
  - Owner-only streamer assignment (/api/admin/streamers/*)
  - /api/me can_go_live flag
  - Analytics range picker (month | 3m | all)
  - Promo codes (CRUD + checkout application)
  - Gentle milestones (surface + dismiss persistence)
  - Watch time heartbeat (viewer accumulates, host ignored, Inner Circle flag)
  - Finance CSV export honours range
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://import-assistant-7.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

CREDS = {
    'creator': ('creator@skali.test', 'Test1234!'),
    'fan': ('fan@skali.test', 'Test1234!'),
    'owner': ('owner@skali.test', 'Test1234!'),
    'mod': ('mod@skali.test', 'Test1234!'),
}


def _login(role):
    email, pw = CREDS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {role} failed: {r.status_code} {r.text}"
    return r.json()['access_token']


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope='module')
def tokens():
    return {role: _login(role) for role in CREDS}


@pytest.fixture(scope='module')
def ids(tokens):
    out = {}
    for role, tok in tokens.items():
        r = requests.get(f"{API}/me", headers=_auth(tok), timeout=30)
        assert r.status_code == 200
        out[role] = r.json()
    return out


@pytest.fixture(scope='module')
def mongo():
    client = MongoClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME')]
    yield db
    # cleanup
    db.creator_promos.delete_many({'_test_marker': 'TEST_golive'})
    db.subscriptions.delete_many({'_test_marker': 'TEST_golive'})
    db.live_streams.delete_many({'_test_marker': 'TEST_golive'})
    db.watch_sessions.delete_many({'_test_marker': 'TEST_golive'})
    db.checkout_sessions.delete_many({'_test_marker': 'TEST_golive'})


# ----- /api/me can_go_live -----
class TestCanGoLiveFlag:
    def test_fan_cannot(self, tokens, ids):
        assert ids['fan'].get('can_go_live') is False

    def test_creator_default(self, tokens, ids, mongo):
        # Flag should reflect current db state. If creator was previously granted
        # by another test, remove the grant to establish baseline, then re-fetch.
        mongo.profiles.update_one({'id': ids['creator']['id']}, {'$set': {'can_stream': False}})
        r = requests.get(f"{API}/me", headers=_auth(tokens['creator']), timeout=30)
        assert r.json().get('can_go_live') is False

    def test_mod_can(self, ids):
        assert ids['mod'].get('can_go_live') is True

    def test_owner_can(self, ids):
        assert ids['owner'].get('can_go_live') is True


# ----- Go-live gating -----
class TestGoLiveGating:
    PAYLOAD = {'audience': 'public', 'category': 'just_chatting', 'title': 'TEST'}

    def _assert_gated(self, resp):
        # 403 with 'Going live is currently limited' expected
        assert resp.status_code == 403, resp.text
        assert 'limited' in resp.text.lower()

    def test_live_start_fan_denied(self, tokens):
        r = requests.post(f"{API}/live/start", headers=_auth(tokens['fan']), json=self.PAYLOAD, timeout=30)
        self._assert_gated(r)

    def test_live_start_creator_denied(self, tokens, ids, mongo):
        mongo.profiles.update_one({'id': ids['creator']['id']}, {'$set': {'can_stream': False}})
        r = requests.post(f"{API}/live/start", headers=_auth(tokens['creator']), json=self.PAYLOAD, timeout=30)
        self._assert_gated(r)

    def test_live_start_mod_passes_gate(self, tokens):
        r = requests.post(f"{API}/live/start", headers=_auth(tokens['mod']), json=self.PAYLOAD, timeout=30)
        # LiveKit not configured in preview → 500 'LiveKit is not configured'. That means the gate was passed.
        assert r.status_code in (200, 500)
        if r.status_code == 500:
            assert 'livekit' in r.text.lower()

    def test_ingress_create_fan_denied(self, tokens):
        r = requests.post(f"{API}/stream/ingress", headers=_auth(tokens['fan']), timeout=30)
        self._assert_gated(r)

    def test_ingress_reset_fan_denied(self, tokens):
        r = requests.post(f"{API}/stream/ingress/reset", headers=_auth(tokens['fan']), timeout=30)
        self._assert_gated(r)

    def test_stream_start_fan_denied(self, tokens):
        r = requests.post(f"{API}/stream/start", headers=_auth(tokens['fan']), json={}, timeout=30)
        self._assert_gated(r)


# ----- Owner-only streamer assignment -----
class TestStreamerAssignment:
    def test_mod_cannot_assign(self, tokens):
        r = requests.post(f"{API}/admin/streamers/assign", headers=_auth(tokens['mod']),
                          json={'handle': 'creator'}, timeout=30)
        assert r.status_code == 403, r.text

    def test_owner_assigns_creator_and_me_updates(self, tokens, mongo):
        r = requests.post(f"{API}/admin/streamers/assign", headers=_auth(tokens['owner']),
                          json={'handle': 'creator'}, timeout=30)
        assert r.status_code == 200, r.text
        # list
        lst = requests.get(f"{API}/admin/streamers", headers=_auth(tokens['owner']), timeout=30)
        assert lst.status_code == 200
        handles = [p['handle'] for p in lst.json()]
        assert 'creator' in handles
        # /me as creator should now be can_go_live
        me = requests.get(f"{API}/me", headers=_auth(tokens['creator']), timeout=30).json()
        assert me.get('can_go_live') is True
        # creator can now hit /api/live/start past the gate
        r2 = requests.post(f"{API}/live/start", headers=_auth(tokens['creator']),
                           json={'audience': 'public', 'category': 'just_chatting', 'title': 'T'}, timeout=30)
        assert r2.status_code in (200, 500)

    def test_owner_removes_creator(self, tokens):
        r = requests.post(f"{API}/admin/streamers/remove", headers=_auth(tokens['owner']),
                          json={'handle': 'creator'}, timeout=30)
        assert r.status_code == 200
        me = requests.get(f"{API}/me", headers=_auth(tokens['creator']), timeout=30).json()
        assert me.get('can_go_live') is False


# ----- Analytics range picker -----
class TestAnalyticsRange:
    def test_month_default(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=month", headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d['overview']['range'] == 'month'
        assert d['overview']['compare_label'] == 'vs last month'

    def test_3m(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=3m", headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d['overview']['range'] == '3m'
        assert d['overview']['compare_label'] == 'vs previous 3 months'

    def test_all(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=all", headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d['overview']['range'] == 'all'
        assert d['overview']['compare_label'] is None
        # 12 bars for all-time
        assert len(d['overview']['trend']) == 12

    def test_overview_fields(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=month", headers=_auth(tokens['creator']), timeout=30)
        ov = r.json()['overview']
        # new field names (not revenue_this_month)
        for k in ('revenue', 'new_subs', 'tips', 'revenue_prev', 'new_subs_prev', 'tips_prev',
                  'revenue_growth_pct', 'compare_label', 'milestone', 'trend', 'sample'):
            assert k in ov, f"missing {k}"

    def test_subscribers_churn_renamed(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=month", headers=_auth(tokens['creator']), timeout=30)
        subs = r.json()['subscribers']
        assert 'churn' in subs
        assert 'churn_rate' in subs

    def test_csv_export_range(self, tokens):
        r = requests.get(f"{API}/creator/analytics/export.csv?range=3m",
                         headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        assert 'text/csv' in r.headers.get('content-type', '')
        # totals row has the range name
        assert '3m' in r.text


# ----- Promo codes -----
class TestPromos:
    @pytest.fixture(autouse=True)
    def _cleanup(self, mongo, ids):
        mongo.creator_promos.delete_many({'creator_id': ids['creator']['id'],
                                          'code': {'$in': ['TESTPROMO', 'BADCODE']}})
        yield
        mongo.creator_promos.delete_many({'creator_id': ids['creator']['id'],
                                          'code': {'$in': ['TESTPROMO', 'BADCODE']}})

    def test_fan_cannot_create(self, tokens):
        r = requests.post(f"{API}/creator/analytics/promos", headers=_auth(tokens['fan']),
                          json={'code': 'TESTPROMO', 'percent_off': 20}, timeout=30)
        assert r.status_code == 403

    def test_invalid_code_short(self, tokens):
        r = requests.post(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']),
                          json={'code': 'AB', 'percent_off': 20}, timeout=30)
        assert r.status_code == 400

    def test_invalid_percent(self, tokens):
        r = requests.post(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']),
                          json={'code': 'TESTPROMO', 'percent_off': 99}, timeout=30)
        assert r.status_code == 400
        r2 = requests.post(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']),
                           json={'code': 'TESTPROMO', 'percent_off': 2}, timeout=30)
        assert r2.status_code == 400

    def test_create_list_end(self, tokens, mongo, ids):
        r = requests.post(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']),
                          json={'code': 'TESTPROMO', 'percent_off': 20, 'max_uses': 10}, timeout=30)
        assert r.status_code == 200, r.text
        pid = r.json()['id']
        assert r.json()['code'] == 'TESTPROMO'
        assert r.json()['percent_off'] == 20.0
        # list
        lst = requests.get(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']), timeout=30)
        assert lst.status_code == 200
        codes = [p['code'] for p in lst.json().get('promos', [])]
        assert 'TESTPROMO' in codes
        # end
        end = requests.post(f"{API}/creator/analytics/promos/{pid}/end",
                            headers=_auth(tokens['creator']), timeout=30)
        assert end.status_code == 200
        lst2 = requests.get(f"{API}/creator/analytics/promos", headers=_auth(tokens['creator']), timeout=30)
        codes2 = [p['code'] for p in lst2.json().get('promos', [])]
        assert 'TESTPROMO' not in codes2
        ended = [p['code'] for p in lst2.json().get('ended_promos', [])]
        assert 'TESTPROMO' in ended


# ----- Checkout with promo -----
class TestCheckoutPromo:
    @pytest.fixture(autouse=True)
    def _setup(self, mongo, ids):
        # Ensure creator can receive checkout: creator_override True
        mongo.profiles.update_one({'id': ids['creator']['id']},
                                  {'$set': {'creator_override': True}})
        mongo.creator_promos.delete_many({'creator_id': ids['creator']['id'], 'code': 'CHKTEST'})
        mongo.creator_promos.insert_one({
            'id': str(uuid.uuid4()), 'creator_id': ids['creator']['id'], 'code': 'CHKTEST',
            'percent_off': 25.0, 'uses': 0, 'max_uses': None, 'active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            '_test_marker': 'TEST_golive',
        })
        yield
        mongo.creator_promos.delete_many({'creator_id': ids['creator']['id'], 'code': 'CHKTEST'})

    def test_checkout_applies_promo(self, tokens):
        r = requests.post(f"{API}/checkout/session", headers=_auth(tokens['fan']),
                          json={'product': 'inner_circle', 'creator_handle': 'creator',
                                'tier': 1, 'promo_code': 'CHKTEST'}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get('promo_applied') == 'CHKTEST'
        # tier 1 default price should be discounted by 25% (gross reduced)
        # No-promo baseline for comparison
        r0 = requests.post(f"{API}/checkout/session", headers=_auth(tokens['fan']),
                           json={'product': 'inner_circle', 'creator_handle': 'creator', 'tier': 1},
                           timeout=30)
        assert r0.status_code == 200
        assert d['gross'] < r0.json()['gross']

    def test_checkout_invalid_promo(self, tokens):
        r = requests.post(f"{API}/checkout/session", headers=_auth(tokens['fan']),
                          json={'product': 'inner_circle', 'creator_handle': 'creator',
                                'tier': 1, 'promo_code': 'DOESNOTEXIST'}, timeout=30)
        assert r.status_code == 400


# ----- Milestones -----
class TestMilestones:
    @pytest.fixture(autouse=True)
    def _setup(self, mongo, ids):
        cid = ids['creator']['id']
        fid = ids['fan']['id']
        mongo.subscriptions.delete_many({'_test_marker': 'TEST_golive'})
        mongo.subscriptions.update_one(
            {'creator_id': cid, 'buyer_id': fid, 'type': 'inner_circle'},
            {'$set': {'id': str(uuid.uuid4()), 'creator_id': cid, 'buyer_id': fid,
                      'type': 'inner_circle', 'status': 'active',
                      'updated_at': datetime.now(timezone.utc).isoformat(),
                      '_test_marker': 'TEST_golive'}}, upsert=True)
        # Reset dismissed milestones
        mongo.profiles.update_one({'id': cid}, {'$unset': {'analytics_milestones': ''}})
        yield
        mongo.subscriptions.delete_many({'_test_marker': 'TEST_golive'})
        mongo.profiles.update_one({'id': cid}, {'$unset': {'analytics_milestones': ''}})

    def test_milestone_surfaces(self, tokens):
        r = requests.get(f"{API}/creator/analytics?range=month", headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        ov = r.json()['overview']
        m = ov.get('milestone')
        assert m is not None, f"expected milestone, got overview={ov}"
        assert m['kind'] == 'subscribers'
        assert m['value'] >= 1
        assert isinstance(m.get('message'), str) and len(m['message']) > 10

    def test_dismiss_persists(self, tokens, ids, mongo):
        r = requests.post(f"{API}/creator/analytics/milestones/dismiss",
                          headers=_auth(tokens['creator']),
                          json={'kind': 'subscribers', 'value': 1}, timeout=30)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/creator/analytics?range=month", headers=_auth(tokens['creator']), timeout=30)
        assert r2.json()['overview'].get('milestone') is None


# ----- Watch time -----
class TestWatchTime:
    @pytest.fixture
    def live_stream(self, mongo, ids):
        live_id = 'wtest' + uuid.uuid4().hex[:6]
        mongo.live_streams.insert_one({
            'id': live_id, 'room': f'live-{live_id}', 'host_id': ids['creator']['id'],
            'host': {'handle': 'creator'},
            'audience': 'public', 'status': 'live',
            'started_at': datetime.now(timezone.utc).isoformat(),
            '_test_marker': 'TEST_golive'})
        # Ensure fan is inner member (fan is already in creator's Inner Circle per creds doc, but
        # we also keep an active subscription from the milestone test as a backup).
        yield live_id
        mongo.live_streams.delete_many({'id': live_id})
        mongo.watch_sessions.delete_many({'live_id': live_id})

    def test_host_heartbeat_not_tracked(self, tokens, live_stream):
        r = requests.post(f"{API}/watch/{live_stream}/heartbeat",
                          headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        assert r.json().get('tracked') is False

    def test_viewer_heartbeat_tracked_and_accumulates(self, tokens, live_stream, mongo, ids):
        # First heartbeat (creates session, 0s)
        r = requests.post(f"{API}/watch/{live_stream}/heartbeat",
                          headers=_auth(tokens['fan']), timeout=30)
        assert r.status_code == 200
        assert r.json().get('tracked') is True
        # Force last_seen into the past so the second heartbeat has a deterministic delta
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        mongo.watch_sessions.update_one(
            {'live_id': live_stream, 'viewer_id': ids['fan']['id']},
            {'$set': {'last_seen': past}})
        r2 = requests.post(f"{API}/watch/{live_stream}/heartbeat",
                           headers=_auth(tokens['fan']), timeout=30)
        assert r2.status_code == 200
        ws = mongo.watch_sessions.find_one({'live_id': live_stream, 'viewer_id': ids['fan']['id']})
        assert ws is not None
        assert ws['seconds'] > 0
        assert ws['seconds'] <= 45  # capped per heartbeat
        assert 'is_inner' in ws

    def test_health_watch_time_no_sample_when_sessions_exist(self, tokens, live_stream, ids, mongo):
        # Make sure fan is marked inner by inserting a watch_sessions doc with is_inner True
        # (or rely on real inner-circle membership from fixtures). Trigger one heartbeat first.
        requests.post(f"{API}/watch/{live_stream}/heartbeat", headers=_auth(tokens['fan']), timeout=30)
        time.sleep(1)
        requests.post(f"{API}/watch/{live_stream}/heartbeat", headers=_auth(tokens['fan']), timeout=30)
        # Force inner flag so health counts regardless of inner-circle membership state
        mongo.watch_sessions.update_many(
            {'live_id': live_stream, 'viewer_id': ids['fan']['id']},
            {'$set': {'is_inner': True, 'seconds': 120.0}})
        r = requests.get(f"{API}/creator/analytics?range=month",
                         headers=_auth(tokens['creator']), timeout=30)
        assert r.status_code == 200
        h = r.json()['health']
        if h.get('metrics'):
            assert h['metrics'].get('watch_sessions', 0) >= 1
            # avg_watch_time computed → should be a positive number, and no sample flag for it
            assert h['metrics'].get('avg_watch_time') is not None
