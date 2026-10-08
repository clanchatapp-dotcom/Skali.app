import os, sys, asyncio, uuid

os.environ['MONGO_URL'] = 'mongodb://localhost:27017'
os.environ['DB_NAME'] = 'skali_linktest'
os.environ.setdefault('SUPABASE_JWT_SECRET', 'testsecret')

sys.path.insert(0, '/app/backend')
import server  # noqa: E402


async def ucount(db):
    return await db.profiles.count_documents({'id': {'$ne': server.BOT_ID}})


async def main():
    db = server.db
    await db.profiles.delete_many({})
    await db.auth.delete_many({})

    # 1) email/password signup first, then Google login same email (diff sub, mixed case)
    uid_a = str(uuid.uuid4())
    p1 = await server.ensure_profile(uid_a, 'test@example.com', 'Tester', None, dob='2000-01-01')
    sub_g = str(uuid.uuid4())
    p2 = await server.ensure_profile(sub_g, 'Test@Example.com', 'Test G', None)
    assert p1['id'] == p2['id'], 'password->google should link'
    assert sub_g in p2.get('linked_ids', [])
    p3 = await server.ensure_profile(sub_g, 'test@example.com', None, None)
    assert p3['id'] == p1['id']
    assert await ucount(db) == 1
    print('CASE 1 (password->google) OK linked_ids=', p3.get('linked_ids'))

    # 2) Google first, then email/password signup same email
    await db.profiles.delete_many({})
    subg2 = str(uuid.uuid4())
    g = await server.ensure_profile(subg2, 'alice@foo.com', 'Alice', None)
    uidp = str(uuid.uuid4())
    pw = await server.ensure_profile(uidp, 'alice@foo.com', 'Alice PW', None, dob='1990-01-01')
    assert g['id'] == pw['id'], 'google->password should link'
    assert await ucount(db) == 1
    print('CASE 2 (google->password) OK linked_ids=', pw.get('linked_ids'))

    # 3) different emails stay separate
    await db.profiles.delete_many({})
    a = await server.ensure_profile(str(uuid.uuid4()), 'x@a.com', 'X', None)
    b = await server.ensure_profile(str(uuid.uuid4()), 'y@b.com', 'Y', None)
    assert a['id'] != b['id']
    assert await ucount(db) == 2
    print('CASE 3 (distinct emails) OK')

    await db.profiles.delete_many({})
    await db.auth.delete_many({})
    await db.dms.delete_many({})
    await server.client.drop_database('skali_linktest')
    print('ALL CASES PASSED')


asyncio.run(main())
