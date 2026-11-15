import os, time, jwt, asyncio
os.environ['SUPABASE_JWT_SECRET'] = 'local-test-secret'
os.environ['DB_NAME'] = 'audit_access_check'
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
import sys; sys.path.insert(0, '/app/backend')
import server
from fastapi.testclient import TestClient

def tok(sub, email):
    return jwt.encode({'sub': sub, 'email': email, 'aud': 'authenticated', 'exp': int(time.time()) + 3600}, 'local-test-secret', algorithm='HS256')

with TestClient(server.app) as c:
    H = {n: {'Authorization': f'Bearer {tok(n, n + "@t.io")}'} for n in ('sup', 'co', 'mod')}
    for n in H: c.get('/api/me', headers=H[n])
    db = server.db
    async def roles():
        await db.profiles.update_one({'id': 'sup'}, {'$set': {'role': 'super_admin'}})
        await db.profiles.update_one({'id': 'co'}, {'$set': {'role': 'co_admin'}})
        await db.profiles.update_one({'id': 'mod'}, {'$set': {'role': 'moderator'}})
    c.portal.call(roles)
    for n in H:
        r = c.get('/api/admin/audit', headers=H[n]); print(n, 'own log', r.status_code, r.json().get('log'))
    print('co->super no grant', c.get('/api/admin/audit?log=super_admin', headers=H['co']).status_code)
    print('mod request', c.post('/api/admin/audit/access/request', json={'log_role': 'co_admin'}, headers=H['mod']).status_code)
    rq = c.post('/api/admin/audit/access/request', json={'log_role': 'super_admin'}, headers=H['co']).json(); print('co request', rq)
    print('mod decide (not owner)', c.post(f'/api/admin/audit/access/{rq["id"]}/approve', headers=H['mod']).status_code)
    inc = c.get('/api/admin/audit/access', headers=H['sup']).json(); print('super incoming', len(inc['incoming']))
    print('super approve', c.post(f'/api/admin/audit/access/{rq["id"]}/approve', headers=H['sup']).json())
    r = c.get('/api/admin/audit?log=super_admin', headers=H['co']); print('co->super after grant', r.status_code, {e['log_role'] for e in r.json()['entries']})
    print('super->co no grant', c.get('/api/admin/audit?log=co_admin', headers=H['sup']).status_code)
    print('co own log roles', {e['log_role'] for e in c.get('/api/admin/audit', headers=H['co']).json()['entries']})
    print('co access', c.get('/api/admin/audit/access', headers=H['co']).json()['active'])
    c.portal.call(lambda: server.client.drop_database('audit_access_check'))
