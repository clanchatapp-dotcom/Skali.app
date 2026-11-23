import os, time, jwt, base64
os.environ['SUPABASE_JWT_SECRET'] = 'local-test-secret'
os.environ['DB_NAME'] = 'secret_chat_check'
os.environ['DM_ENC_KEY'] = base64.b64encode(os.urandom(32)).decode()
import sys; sys.path.insert(0, '/app/backend')
import server
from fastapi.testclient import TestClient
pushes = []
async def fake_push(uid, title, body, data=None): pushes.append((title, body))
server.push_to_user = fake_push
tok = lambda s: {'Authorization': 'Bearer ' + jwt.encode({'sub': s, 'email': s + '@t.io', 'aud': 'authenticated', 'exp': int(time.time()) + 3600}, 'local-test-secret', algorithm='HS256')}
with TestClient(server.app) as c:
    A, B = tok('ua'), tok('ub')
    ha = c.get('/api/me', headers=A).json()['handle']; hb = c.get('/api/me', headers=B).json()['handle']
    async def yes(*a): return True
    server.can_dm = yes
    c.post(f'/api/dms/{hb}', json={'text': 'normal hello'}, headers=A); print('normal push', pushes[-1])
    c.post(f'/api/dms/{hb}?secret=true', json={'text': 'secret hi'}, headers=A); print('secret push', pushes[-1])
    c.post(f'/api/dms/{hb}?secret=true', json={'media_url': 'https://x/y.jpg', 'media_type': 'image', 'allow_save': True}, headers=A)
    norm = c.get(f'/api/dms/{ha}', headers=B).json()['messages']; sec = c.get(f'/api/dms/{ha}?secret=true', headers=B).json()['messages']
    print('B normal chat', [m['text'] for m in norm])
    print('B secret chat', [m['text'] for m in sec], 'saveable', [m['allow_save'] for m in sec])
    print('B threads', [(t['last'], t['secret']) for t in c.get('/api/dms', headers=B).json()])
    print('unread B', c.get('/api/unread', headers=B).json()['dms'])
    c.portal.call(lambda: server.client.drop_database('secret_chat_check'))
