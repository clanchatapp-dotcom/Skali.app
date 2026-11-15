import os, time, jwt
os.environ['SUPABASE_JWT_SECRET'] = 'local-test-secret'
os.environ['DB_NAME'] = 'dm_secret_check'
import base64; os.environ['DM_ENC_KEY'] = base64.b64encode(os.urandom(32)).decode()
import sys; sys.path.insert(0, '/app/backend')
import server
from fastapi.testclient import TestClient
pushes = []
async def fake_push(uid, title, body, data=None): pushes.append((uid, title, body))
server.push_to_user = fake_push
tok = lambda s: {'Authorization': 'Bearer ' + jwt.encode({'sub': s, 'email': s + '@t.io', 'aud': 'authenticated', 'exp': int(time.time()) + 3600}, 'local-test-secret', algorithm='HS256')}
with TestClient(server.app) as c:
    A, B = tok('ua'), tok('ub')
    ha = c.get('/api/me', headers=A).json()['handle']; hb = c.get('/api/me', headers=B).json()['handle']
    server.can_dm = lambda *a: __import__('asyncio').sleep(0, True)
    c.post(f'/api/dms/{hb}', json={'text': 'pic', 'media_url': 'https://x/a.jpg', 'media_type': 'image'}, headers=A)
    print('default', c.get(f'/api/dms/{hb}/secret', headers=A).json())
    c.post(f'/api/dms/{hb}', json={'text': 'hello'}, headers=A); print('normal push', pushes[-1][1:])
    print('B turns on', c.post(f'/api/dms/{ha}/secret', json={'secret': True}, headers=B).json())
    print('A sees', c.get(f'/api/dms/{hb}/secret', headers=A).json())
    c.post(f'/api/dms/{hb}', json={'text': 'private'}, headers=A); print('secret push', pushes[-1][1:])
    c.post(f'/api/dms/{ha}', json={'text': 'back'}, headers=B); print('secret push other way', pushes[-1][1:])
    print('A thread list', [(t['last'], t['secret']) for t in c.get('/api/dms', headers=A).json()])
    c.post(f'/api/dms/{hb}/secret', json={'secret': False}, headers=A)
    c.post(f'/api/dms/{hb}', json={'text': 'open again'}, headers=A); print('after off', pushes[-1][1:])
    print('saveable after secret on+off', [m['allow_save'] for m in c.get(f'/api/dms/{ha}', headers=B).json()['messages'] if m.get('media_url')])
    c.post(f'/api/dms/{hb}/secret', json={'secret': True}, headers=A); c.post(f'/api/dms/{hb}', json={'text': 'v', 'media_url': 'https://x/v.m4a', 'media_type': 'audio', 'allow_save': True}, headers=A)
    print('new media in secret', [m['allow_save'] for m in c.get(f'/api/dms/{ha}', headers=B).json()['messages'] if m.get('media_url')])
    c.portal.call(lambda: server.client.drop_database('dm_secret_check'))
