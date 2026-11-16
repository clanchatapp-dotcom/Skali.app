import os, time, jwt, base64
os.environ['SUPABASE_JWT_SECRET'] = 'local-test-secret'
os.environ['DB_NAME'] = 'nsfw_check'
os.environ['ADMIN_EMAILS'] = 'boss@t.io'
os.environ['DM_ENC_KEY'] = base64.b64encode(os.urandom(32)).decode()
import sys; sys.path.insert(0, '/app/backend')
import server
from fastapi.testclient import TestClient

tok = lambda s: {'Authorization': 'Bearer ' + jwt.encode({'sub': s, 'email': s + '@t.io', 'aud': 'authenticated', 'exp': int(time.time()) + 3600}, 'local-test-secret', algorithm='HS256')}
with TestClient(server.app) as c:
    V, C, R = tok('viewer'), tok('creator'), tok('regular')
    for h in (V, C, R):
        c.get('/api/me', headers=h)
    db = server.db
    c.portal.call(lambda: db.profiles.update_one({'id': 'viewer'}, {'$set': {'verification.age.status': 'verified', 'is_minor': False}}))
    c.portal.call(lambda: db.profiles.update_one({'id': 'creator'}, {'$set': {'account_nsfw': True, 'verification.age.status': 'verified'}}))
    print('adult t1', c.post('/api/posts', json={'text': 'creator tier1', 'tier': 'public'}, headers=C).status_code)
    print('adult t3', c.post('/api/posts', json={'text': 'creator tier3', 'tier': 'inner'}, headers=C).status_code)
    print('normal post', c.post('/api/posts', json={'text': 'regular post', 'tier': 'public'}, headers=R).status_code)
    texts = lambda r: [p['text'] for p in r.json()] if r.status_code == 200 else r.status_code
    print('regular feed (viewer)', texts(c.get('/api/feed', headers=V)))
    print('status regular', c.get('/api/nsfw/status', headers=R).json(), 'viewer', c.get('/api/nsfw/status', headers=V).json())
    print('unverified set pin', c.post('/api/nsfw/pin', json={'pin': '123456'}, headers=R).status_code)
    print('feed no session', c.get('/api/nsfw/feed', headers=V).status_code)
    print('set pin', c.post('/api/nsfw/pin', json={'pin': '123456'}, headers=V).json())
    print('wrong', c.post('/api/nsfw/unlock', json={'pin': '000000'}, headers=V).json())
    t = c.post('/api/nsfw/unlock', json={'pin': '123456'}, headers=V).json()['token']
    S = {**V, 'X-NSFW-Session': t}
    print('nsfw feed (not in inner circle)', texts(c.get('/api/nsfw/feed', headers=S)))
    c.portal.call(lambda: db.inner.insert_one({'owner_id': 'creator', 'member_id': 'viewer', 'status': 'accepted'}))
    print('nsfw feed (inner circle member)', texts(c.get('/api/nsfw/feed', headers=S)))
    print('regular feed (inner member)', texts(c.get('/api/feed', headers=V)))
    print('creators', [p['handle'] for p in c.get('/api/nsfw/creators', headers=S).json()])
    print('session for other user', c.get('/api/nsfw/feed', headers={**R, 'X-NSFW-Session': t}).status_code)
    print('change w/o current', c.post('/api/nsfw/pin', json={'pin': '654321'}, headers=V).status_code)
    print('change with current', c.post('/api/nsfw/pin', json={'pin': '654321', 'current_pin': '123456'}, headers=V).status_code)
    print('lockout', [c.post('/api/nsfw/unlock', json={'pin': '111111'}, headers=V).status_code for _ in range(5)])
    B, CO = tok('boss'), tok('coadm')
    c.get('/api/me', headers=B); c.get('/api/me', headers=CO)
    c.portal.call(lambda: db.profiles.update_one({'id': 'coadm'}, {'$set': {'role': 'co_admin'}}))
    c.portal.call(lambda: db.nsfw_pins.update_one({'user_id': 'viewer'}, {'$unset': {'locked_until': ''}}))
    print('reset request', c.post('/api/nsfw/reset-request', headers=V).json(), 'status', c.get('/api/nsfw/status', headers=V).json()['reset_pending'])
    print('co-admin list', [r['handle'] for r in c.get('/api/admin/nsfw-resets', headers=CO).json()])
    print('co-admin activity', [a['text'] for a in c.portal.call(lambda: db.activity.find({'user_id': 'coadm'}).to_list(10))])
    vh = c.get('/api/me', headers=V).json()['handle']
    print('co-admin reset', c.post(f'/api/admin/nsfw-resets/{vh}/reset', headers=CO).status_code)
    print('super reset', c.post(f'/api/admin/nsfw-resets/{vh}/reset', headers=B).status_code, c.get('/api/nsfw/status', headers=V).json())
    c.portal.call(lambda: server.client.drop_database('nsfw_check'))
