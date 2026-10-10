"""
Audit log role-separation feature tests.
Covers:
- GET /api/admin/audit role-scoped view and 403 without grant
- POST /api/admin/audit/access/request (new, duplicate, own-role)
- GET /api/admin/audit/access overview (my_log, logs, granted, incoming, outgoing)
- POST /api/admin/audit/access/{id}/{approve|deny} permissions and transitions
- 24h expiry: after Mongo update to past expires_at, access becomes 403 and outgoing shows 'expired'
- 'audit_log_view' entry written to the viewed log when accessed via grant
- Non-staff user gets 403 on all /admin/audit* endpoints
- log_role field present on new audit entries; startup backfill fills legacy entries
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = 'http://localhost:8001'

STAFF = {
    'super_admin': ('sa@test.skali', 'Test1234!'),
    'co_admin':    ('co@test.skali', 'Test1234!'),
    'moderator':   ('mod@test.skali', 'Test1234!'),
}


def _login(email, password):
    r = requests.post(f'{BASE_URL}/api/auth/login',
                      json={'email': email, 'password': password}, timeout=10)
    assert r.status_code == 200, f'login failed for {email}: {r.status_code} {r.text}'
    return r.json()['access_token']


def _hdr(tok):
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


@pytest.fixture(scope='module')
def tokens():
    return {role: _login(e, p) for role, (e, p) in STAFF.items()}


@pytest.fixture(scope='module')
def regular_user():
    """Create (or reuse) a non-staff user."""
    email = f'reg_{uuid.uuid4().hex[:8]}@test.skali'
    r = requests.post(f'{BASE_URL}/api/auth/register',
                      json={'email': email, 'password': 'Test1234!',
                            'name': 'reg', 'dob': '1990-01-01'}, timeout=10)
    assert r.status_code in (200, 201), r.text
    tok = r.json().get('access_token') or _login(email, 'Test1234!')
    return tok


@pytest.fixture(scope='module', autouse=True)
def _cleanup(tokens):
    """Clean audit_access rows for our test staff before and after."""
    import pymongo
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')
    cli = pymongo.MongoClient(mongo_url)
    db = cli[db_name]
    # pre-clean
    ids = [p['id'] for p in db.profiles.find(
        {'email': {'$in': [v[0] for v in STAFF.values()]}}, {'id': 1})]
    db.audit_access.delete_many({'$or': [
        {'requester_id': {'$in': ids}}, {'log_role': {'$in': list(STAFF.keys())}}]})
    yield db
    # post-clean
    db.audit_access.delete_many({'$or': [
        {'requester_id': {'$in': ids}}, {'log_role': {'$in': list(STAFF.keys())}}]})


# ---------- basics ----------

def test_overview_shape(tokens):
    for role, tok in tokens.items():
        r = requests.get(f'{BASE_URL}/api/admin/audit/access', headers=_hdr(tok), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['my_log'] == role
        assert set(d['logs']) == {'super_admin', 'co_admin', 'moderator'}
        for k in ('granted', 'incoming', 'outgoing'):
            assert isinstance(d[k], list)


def test_get_audit_default_scoped_to_my_log(tokens):
    for role, tok in tokens.items():
        r = requests.get(f'{BASE_URL}/api/admin/audit', headers=_hdr(tok), timeout=10)
        assert r.status_code == 200, r.text
        entries = r.json()
        for e in entries:
            assert e.get('log_role') == role, f'{role} saw cross-role entry {e}'


def test_other_log_requires_grant(tokens):
    r = requests.get(f'{BASE_URL}/api/admin/audit?log=super_admin',
                     headers=_hdr(tokens['moderator']), timeout=10)
    assert r.status_code == 403
    assert 'request access' in r.text.lower()


def test_unknown_log_param_400(tokens):
    r = requests.get(f'{BASE_URL}/api/admin/audit?log=nope',
                     headers=_hdr(tokens['super_admin']), timeout=10)
    assert r.status_code == 400


# ---------- request ----------

def test_request_own_log_rejected(tokens):
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                      headers=_hdr(tokens['moderator']),
                      json={'log': 'moderator'}, timeout=10)
    assert r.status_code == 400


def test_request_unknown_log_rejected(tokens):
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                      headers=_hdr(tokens['moderator']),
                      json={'log': 'root'}, timeout=10)
    assert r.status_code == 400


def test_mod_requests_super_admin_log_pending_and_dedup(tokens):
    r1 = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                       headers=_hdr(tokens['moderator']),
                       json={'log': 'super_admin'}, timeout=10)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1['status'] == 'pending'
    rid = d1['id']
    # Duplicate must return same pending id
    r2 = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                       headers=_hdr(tokens['moderator']),
                       json={'log': 'super_admin'}, timeout=10)
    assert r2.status_code == 200
    assert r2.json()['id'] == rid
    # Mod outgoing contains it
    ov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                      headers=_hdr(tokens['moderator']), timeout=10).json()
    assert any(x['id'] == rid and x['status'] == 'pending' for x in ov['outgoing'])
    # Super-admin incoming contains it
    sov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                       headers=_hdr(tokens['super_admin']), timeout=10).json()
    assert any(x['id'] == rid for x in sov['incoming'])


# ---------- decide ----------

def test_non_owner_cannot_decide(tokens):
    # mod requested super_admin log; co_admin (wrong owner) tries to approve
    sov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                       headers=_hdr(tokens['super_admin']), timeout=10).json()
    pend = [x for x in sov['incoming'] if x['requester_role'] == 'moderator' and x['log_role'] == 'super_admin']
    assert pend, 'no pending request found for test setup'
    rid = pend[0]['id']
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/{rid}/approve',
                      headers=_hdr(tokens['co_admin']), timeout=10)
    assert r.status_code == 403


def test_approve_grants_24h_and_access_works(tokens, _cleanup):
    sov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                       headers=_hdr(tokens['super_admin']), timeout=10).json()
    rid = [x for x in sov['incoming']
           if x['requester_role'] == 'moderator' and x['log_role'] == 'super_admin'][0]['id']
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/{rid}/approve',
                      headers=_hdr(tokens['super_admin']), timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['status'] == 'approved'
    assert 'expires_at' in body
    # Approx 24h in the future
    exp = datetime.fromisoformat(body['expires_at'])
    delta = exp - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=30) < delta <= timedelta(hours=24, minutes=5)

    # Mod can now view super_admin log
    r2 = requests.get(f'{BASE_URL}/api/admin/audit?log=super_admin',
                      headers=_hdr(tokens['moderator']), timeout=10)
    assert r2.status_code == 200, r2.text
    # audit_log_view was written into the super_admin log
    r3 = requests.get(f'{BASE_URL}/api/admin/audit?log=super_admin',
                      headers=_hdr(tokens['moderator']), timeout=10).json()
    assert any(e.get('action') == 'audit_log_view' and e.get('log_role') == 'super_admin' for e in r3)

    # Overview: outgoing shows approved; granted includes super_admin
    ov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                      headers=_hdr(tokens['moderator']), timeout=10).json()
    assert 'super_admin' in ov['granted']
    assert any(x['id'] == rid and x['status'] == 'approved' for x in ov['outgoing'])


def test_already_decided_rejected(tokens):
    sov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                       headers=_hdr(tokens['super_admin']), timeout=10).json()
    # Find any approved for moderator->super_admin
    approved = [x for x in sov['incoming'] if x.get('status') == 'pending']
    # No pending now; so pick from outgoing of mod
    ov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                      headers=_hdr(tokens['moderator']), timeout=10).json()
    done = [x for x in ov['outgoing'] if x['status'] == 'approved' and x['log_role'] == 'super_admin']
    assert done
    rid = done[0]['id']
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/{rid}/approve',
                      headers=_hdr(tokens['super_admin']), timeout=10)
    assert r.status_code == 400


def test_expiry_forces_403_and_shows_expired(tokens, _cleanup):
    db = _cleanup
    # Pick the approved mod->super_admin grant
    ov = requests.get(f'{BASE_URL}/api/admin/audit/access',
                     headers=_hdr(tokens['moderator']), timeout=10).json()
    done = [x for x in ov['outgoing'] if x['status'] == 'approved' and x['log_role'] == 'super_admin']
    rid = done[0]['id']
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    res = db.audit_access.update_one({'id': rid}, {'$set': {'expires_at': past}})
    assert res.modified_count == 1
    # Access should now 403
    r = requests.get(f'{BASE_URL}/api/admin/audit?log=super_admin',
                     headers=_hdr(tokens['moderator']), timeout=10)
    assert r.status_code == 403
    # outgoing marks it 'expired'
    ov2 = requests.get(f'{BASE_URL}/api/admin/audit/access',
                      headers=_hdr(tokens['moderator']), timeout=10).json()
    assert any(x['id'] == rid and x['status'] == 'expired' for x in ov2['outgoing'])
    assert 'super_admin' not in ov2['granted']


def test_deny_flow(tokens):
    # mod requests co_admin log, co_admin denies
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                      headers=_hdr(tokens['moderator']),
                      json={'log': 'co_admin'}, timeout=10).json()
    rid = r['id']
    r2 = requests.post(f'{BASE_URL}/api/admin/audit/access/{rid}/deny',
                       headers=_hdr(tokens['co_admin']), timeout=10)
    assert r2.status_code == 200
    assert r2.json()['status'] == 'denied'
    # Mod still 403 on co_admin log
    r3 = requests.get(f'{BASE_URL}/api/admin/audit?log=co_admin',
                      headers=_hdr(tokens['moderator']), timeout=10)
    assert r3.status_code == 403


def test_invalid_decision_rejected(tokens):
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/request',
                      headers=_hdr(tokens['moderator']),
                      json={'log': 'co_admin'}, timeout=10).json()
    rid = r.get('id')
    assert rid
    r2 = requests.post(f'{BASE_URL}/api/admin/audit/access/{rid}/bogus',
                       headers=_hdr(tokens['co_admin']), timeout=10)
    assert r2.status_code == 400


def test_decide_nonexistent_404(tokens):
    r = requests.post(f'{BASE_URL}/api/admin/audit/access/{uuid.uuid4()}/approve',
                      headers=_hdr(tokens['super_admin']), timeout=10)
    assert r.status_code == 404


# ---------- non-staff ----------

def test_regular_user_blocked(regular_user):
    tok = regular_user
    for path, method, payload in [
        ('/api/admin/audit', 'GET', None),
        ('/api/admin/audit/access', 'GET', None),
        ('/api/admin/audit/access/request', 'POST', {'log': 'super_admin'}),
        (f'/api/admin/audit/access/{uuid.uuid4()}/approve', 'POST', None),
    ]:
        fn = getattr(requests, method.lower())
        kwargs = {'headers': _hdr(tok), 'timeout': 10}
        if payload:
            kwargs['json'] = payload
        r = fn(f'{BASE_URL}{path}', **kwargs)
        assert r.status_code == 403, f'{method} {path} => {r.status_code}'


# ---------- log_role on new entries + backfill ----------

def test_new_entries_have_log_role(_cleanup):
    db = _cleanup
    # 'audit_access_request' was written during this test run
    sample = db.audit.find_one({'action': 'audit_access_request'}, {'_id': 0})
    assert sample is not None
    assert sample.get('log_role') in {'super_admin', 'co_admin', 'moderator'}


def test_backfill_covers_legacy(_cleanup):
    db = _cleanup
    # No audit entry should remain without log_role after startup backfill
    missing = db.audit.count_documents({'log_role': {'$exists': False}})
    assert missing == 0, f'{missing} legacy audit entries missing log_role'
