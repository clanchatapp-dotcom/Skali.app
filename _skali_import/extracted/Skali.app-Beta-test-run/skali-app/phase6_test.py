#!/usr/bin/env python3
"""
Backend test for Phase 6: Admin+ & Safety
Tests NSFW AI scanner queue, Watchlist, Admin notes, CSAM/CEOP escalate/resolve
"""
import asyncio
import httpx
import secrets
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "admin@clanchat.app"
ADMIN_PASSWORD = "ClanChatAdmin!2025"

# Test results tracking
tests_passed = 0
tests_failed = 0

def log_test(name: str, passed: bool, details: str = ""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        tests_failed += 1
        print(f"❌ {name}")
        if details:
            print(f"   {details}")

async def register_user(client: httpx.AsyncClient, name: str) -> dict:
    """Register a throwaway user and return {token, handle, id, email}"""
    rand = secrets.token_hex(4)
    email = f"{name.lower().replace(' ', '')}+{rand}@example.com"
    password = "secret123"
    r = await client.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "name": name})
    if r.status_code != 200:
        raise Exception(f"Register failed: {r.status_code} {r.text}")
    data = r.json()
    return {"token": data["access_token"], "handle": data["user"]["handle"], 
            "id": data["user"]["id"], "email": email}

async def admin_login(client: httpx.AsyncClient) -> dict:
    """Login as admin and return {token, handle, id}"""
    r = await client.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        raise Exception(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data["access_token"]
    
    # Get admin profile
    r = await client.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Get admin profile failed: {r.status_code} {r.text}")
    
    profile = r.json()
    return {"token": token, "handle": profile["handle"], "id": profile["id"], "is_admin": profile.get("is_admin", False)}

async def test_admin_gating():
    """Test (A) GATING - admin endpoints require auth and admin role"""
    print("\n" + "="*80)
    print("TEST A: ADMIN ENDPOINT GATING")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login as admin
        print("\n[A.1] Admin login...")
        admin = await admin_login(client)
        log_test("Admin login successful", admin["is_admin"] == True, 
                f"handle={admin['handle']}, is_admin={admin['is_admin']}")
        
        # Register a regular user
        print("\n[A.2] Register regular user...")
        regular = await register_user(client, "Regular User")
        print(f"   Regular user: {regular['handle']}")
        
        # Register target user for testing
        print("\n[A.3] Register target user...")
        target = await register_user(client, "Target User")
        print(f"   Target user: {target['handle']}")
        
        # Test GET /api/admin/nsfw
        print("\n[A.4] Testing GET /api/admin/nsfw gating...")
        
        # No token → 401
        r = await client.get(f"{BASE_URL}/admin/nsfw")
        log_test("GET /api/admin/nsfw without token → 401", r.status_code == 401,
                f"status={r.status_code}")
        
        # Regular user → 403
        r = await client.get(f"{BASE_URL}/admin/nsfw", 
                            headers={"Authorization": f"Bearer {regular['token']}"})
        log_test("GET /api/admin/nsfw as regular user → 403", r.status_code == 403,
                f"status={r.status_code}")
        
        # Admin → 200
        r = await client.get(f"{BASE_URL}/admin/nsfw", 
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/nsfw as admin → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        # Test GET /api/admin/watchlist
        print("\n[A.5] Testing GET /api/admin/watchlist gating...")
        
        # No token → 401
        r = await client.get(f"{BASE_URL}/admin/watchlist")
        log_test("GET /api/admin/watchlist without token → 401", r.status_code == 401,
                f"status={r.status_code}")
        
        # Regular user → 403
        r = await client.get(f"{BASE_URL}/admin/watchlist", 
                            headers={"Authorization": f"Bearer {regular['token']}"})
        log_test("GET /api/admin/watchlist as regular user → 403", r.status_code == 403,
                f"status={r.status_code}")
        
        # Admin → 200
        r = await client.get(f"{BASE_URL}/admin/watchlist", 
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/watchlist as admin → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        # Test POST /api/admin/users/{handle}/watch
        print("\n[A.6] Testing POST /api/admin/users/{handle}/watch gating...")
        
        # No token → 401
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/watch",
                             json={"reason": "test"})
        log_test("POST /api/admin/users/{h}/watch without token → 401", r.status_code == 401,
                f"status={r.status_code}")
        
        # Regular user → 403
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/watch",
                             json={"reason": "test"},
                             headers={"Authorization": f"Bearer {regular['token']}"})
        log_test("POST /api/admin/users/{h}/watch as regular user → 403", r.status_code == 403,
                f"status={r.status_code}")
        
        # Admin → 200
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/watch",
                             json={"reason": "test gating"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{h}/watch as admin → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        # Test POST /api/admin/users/{handle}/note
        print("\n[A.7] Testing POST /api/admin/users/{handle}/note gating...")
        
        # No token → 401
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/note",
                             json={"note": "test"})
        log_test("POST /api/admin/users/{h}/note without token → 401", r.status_code == 401,
                f"status={r.status_code}")
        
        # Regular user → 403
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/note",
                             json={"note": "test"},
                             headers={"Authorization": f"Bearer {regular['token']}"})
        log_test("POST /api/admin/users/{h}/note as regular user → 403", r.status_code == 403,
                f"status={r.status_code}")
        
        # Admin → 200
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/note",
                             json={"note": "test gating note"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{h}/note as admin → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        # Test GET /api/admin/users/{handle}/notes
        print("\n[A.8] Testing GET /api/admin/users/{handle}/notes gating...")
        
        # No token → 401
        r = await client.get(f"{BASE_URL}/admin/users/{target['handle']}/notes")
        log_test("GET /api/admin/users/{h}/notes without token → 401", r.status_code == 401,
                f"status={r.status_code}")
        
        # Regular user → 403
        r = await client.get(f"{BASE_URL}/admin/users/{target['handle']}/notes",
                            headers={"Authorization": f"Bearer {regular['token']}"})
        log_test("GET /api/admin/users/{h}/notes as regular user → 403", r.status_code == 403,
                f"status={r.status_code}")
        
        # Admin → 200
        r = await client.get(f"{BASE_URL}/admin/users/{target['handle']}/notes",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/users/{h}/notes as admin → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        return admin, regular, target

async def test_nsfw_queue(admin):
    """Test (B) NSFW QUEUE endpoints"""
    print("\n" + "="*80)
    print("TEST B: NSFW QUEUE")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test GET /api/admin/nsfw?status=open
        print("\n[B.1] Testing GET /api/admin/nsfw?status=open...")
        r = await client.get(f"{BASE_URL}/admin/nsfw?status=open",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/nsfw?status=open → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            queue = r.json()
            log_test("Response is a list", isinstance(queue, list),
                    f"type={type(queue).__name__}, length={len(queue) if isinstance(queue, list) else 'N/A'}")
        
        # Test POST /api/admin/nsfw/nonexistentid/resolve → 404
        print("\n[B.2] Testing POST /api/admin/nsfw/{nonexistent}/resolve → 404...")
        r = await client.post(f"{BASE_URL}/admin/nsfw/nonexistentid123/resolve",
                             json={"action": "dismiss"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/nsfw/nonexistentid/resolve → 404", r.status_code == 404,
                f"status={r.status_code}")
        
        # Test POST /api/admin/nsfw/{anyid}/resolve with bad action → 400
        print("\n[B.3] Testing POST /api/admin/nsfw/{id}/resolve with bad action → 400...")
        r = await client.post(f"{BASE_URL}/admin/nsfw/anyid123/resolve",
                             json={"action": "badaction"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/nsfw/{id}/resolve {action:'badaction'} → 400", r.status_code == 400,
                f"status={r.status_code}")

async def test_watchlist(admin, target):
    """Test (C) WATCHLIST endpoints"""
    print("\n" + "="*80)
    print("TEST C: WATCHLIST")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test POST /api/admin/users/{handle}/watch
        print("\n[C.1] Testing POST /api/admin/users/{TARGET}/watch...")
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/watch",
                             json={"reason": "spam suspicion"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{TARGET}/watch → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            log_test("Response has ok=True", data.get("ok") == True,
                    f"ok={data.get('ok')}")
            log_test("Response has watchlisted=True", data.get("watchlisted") == True,
                    f"watchlisted={data.get('watchlisted')}")
        
        # Test GET /api/admin/watchlist → TARGET present
        print("\n[C.2] Testing GET /api/admin/watchlist → TARGET present...")
        r = await client.get(f"{BASE_URL}/admin/watchlist",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/watchlist → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            watchlist = r.json()
            target_entry = next((u for u in watchlist if u.get('handle') == target['handle']), None)
            log_test("TARGET present in watchlist", target_entry is not None,
                    f"found={target_entry is not None}")
            if target_entry:
                log_test("TARGET has watch_reason", target_entry.get('watch_reason') == 'spam suspicion',
                        f"watch_reason='{target_entry.get('watch_reason')}'")
        
        # Test GET /api/admin/stats → watchlisted >= 1 AND nsfw_open field present
        print("\n[C.3] Testing GET /api/admin/stats...")
        r = await client.get(f"{BASE_URL}/admin/stats",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/stats → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            stats = r.json()
            watchlisted_count = stats.get('watchlisted', 0)
            log_test("Stats has 'watchlisted' >= 1", watchlisted_count >= 1,
                    f"watchlisted={watchlisted_count}")
            log_test("Stats has 'nsfw_open' field", 'nsfw_open' in stats,
                    f"nsfw_open={stats.get('nsfw_open', 'MISSING')}")
        
        # Test GET /api/admin/users?q={TARGET_handle} → watchlisted:true
        print("\n[C.4] Testing GET /api/admin/users?q={TARGET}...")
        r = await client.get(f"{BASE_URL}/admin/users?q={target['handle']}",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/users?q={TARGET} → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            users = r.json()
            target_user = next((u for u in users if u.get('handle') == target['handle']), None)
            if target_user:
                log_test("TARGET has watchlisted=True", target_user.get('watchlisted') == True,
                        f"watchlisted={target_user.get('watchlisted')}")
            else:
                log_test("TARGET found in search results", False, "TARGET not found")
        
        # Test POST /api/admin/users/{TARGET}/unwatch
        print("\n[C.5] Testing POST /api/admin/users/{TARGET}/unwatch...")
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/unwatch",
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{TARGET}/unwatch → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            log_test("Response has watchlisted=False", data.get("watchlisted") == False,
                    f"watchlisted={data.get('watchlisted')}")
        
        # Test GET /api/admin/watchlist → TARGET absent
        print("\n[C.6] Testing GET /api/admin/watchlist → TARGET absent...")
        r = await client.get(f"{BASE_URL}/admin/watchlist",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/watchlist → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            watchlist = r.json()
            target_entry = next((u for u in watchlist if u.get('handle') == target['handle']), None)
            log_test("TARGET absent from watchlist", target_entry is None,
                    f"found={target_entry is not None}")

async def test_admin_notes(admin, target):
    """Test (D) ADMIN NOTES endpoints"""
    print("\n" + "="*80)
    print("TEST D: ADMIN NOTES")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test POST /api/admin/users/{TARGET}/note
        print("\n[D.1] Testing POST /api/admin/users/{TARGET}/note...")
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/note",
                             json={"note": "reviewed 2025, no action"},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{TARGET}/note → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        note_id = None
        if r.status_code == 200:
            data = r.json()
            note_id = data.get('id')
            log_test("Response has 'id' field", note_id is not None,
                    f"id={note_id}")
            log_test("Response has correct 'note'", data.get('note') == 'reviewed 2025, no action',
                    f"note='{data.get('note')}'")
            log_test("Response has 'admin_handle'", data.get('admin_handle') == admin['handle'],
                    f"admin_handle='{data.get('admin_handle')}'")
        
        # Test GET /api/admin/users/{TARGET}/notes
        print("\n[D.2] Testing GET /api/admin/users/{TARGET}/notes...")
        r = await client.get(f"{BASE_URL}/admin/users/{target['handle']}/notes",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("GET /api/admin/users/{TARGET}/notes → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            notes = r.json()
            log_test("Response is a list", isinstance(notes, list),
                    f"type={type(notes).__name__}")
            
            if note_id:
                found_note = next((n for n in notes if n.get('id') == note_id), None)
                log_test("Note with matching id found", found_note is not None,
                        f"found={found_note is not None}")
                if found_note:
                    log_test("Note has correct text", found_note.get('note') == 'reviewed 2025, no action',
                            f"note='{found_note.get('note')}'")
        
        # Test empty note → 400
        print("\n[D.3] Testing POST /api/admin/users/{TARGET}/note with empty note → 400...")
        r = await client.post(f"{BASE_URL}/admin/users/{target['handle']}/note",
                             json={"note": ""},
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/users/{TARGET}/note {note:''} → 400", r.status_code == 400,
                f"status={r.status_code}")

async def test_csam_ceop(admin):
    """Test (E) CSAM/CEOP escalate/resolve"""
    print("\n" + "="*80)
    print("TEST E: CSAM/CEOP ESCALATE/RESOLVE")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register user V
        print("\n[E.1] Register user V...")
        V = await register_user(client, "User V")
        print(f"   User V: {V['handle']}")
        
        # V creates a public post
        print("\n[E.2] V creates a public post...")
        r = await client.post(f"{BASE_URL}/posts",
                             json={"tier": "public", "text": "Test post for CSAM report"},
                             headers={"Authorization": f"Bearer {V['token']}"})
        log_test("V creates public post → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code != 200:
            print("   ERROR: Cannot create post, skipping remaining CSAM tests")
            return
        
        post_id = r.json().get('id')
        print(f"   Post ID: {post_id}")
        
        # Register user W
        print("\n[E.3] Register user W...")
        W = await register_user(client, "User W")
        print(f"   User W: {W['handle']}")
        
        # W reports the post as CSAM
        print("\n[E.4] W reports post as CSAM...")
        r = await client.post(f"{BASE_URL}/report",
                             json={"target_type": "post", "target_id": post_id, "category": "csam"},
                             headers={"Authorization": f"Bearer {W['token']}"})
        log_test("W POST /api/report {category:'csam'} → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            report_data = r.json()
            log_test("Report created successfully", report_data.get('ok') == True,
                    f"ok={report_data.get('ok')}")
        
        # Admin gets CSAM reports
        print("\n[E.5] Admin gets CSAM reports...")
        r = await client.get(f"{BASE_URL}/admin/csam",
                            headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("Admin GET /api/admin/csam → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        report_id = None
        if r.status_code == 200:
            csam_reports = r.json()
            log_test("Response is a list", isinstance(csam_reports, list),
                    f"type={type(csam_reports).__name__}")
            
            # Find the report for our post
            matching_report = next((r for r in csam_reports if r.get('target_id') == post_id), None)
            if matching_report:
                report_id = matching_report.get('id')
                log_test("Found CSAM report for our post", True,
                        f"report_id={report_id}")
            else:
                log_test("Found CSAM report for our post", False,
                        f"No matching report found (searched {len(csam_reports)} reports)")
        
        if not report_id:
            print("   ERROR: Cannot find CSAM report, skipping escalate/resolve tests")
            return
        
        # Admin escalates the report
        print("\n[E.6] Admin escalates CSAM report...")
        r = await client.post(f"{BASE_URL}/admin/csam/{report_id}/escalate",
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("Admin POST /api/admin/csam/{id}/escalate → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            log_test("Response has ok=True", data.get('ok') == True,
                    f"ok={data.get('ok')}")
            log_test("Response has escalated=True", data.get('escalated') == True,
                    f"escalated={data.get('escalated')}")
            ceop_ref = data.get('ceop_ref', '')
            log_test("Response has ceop_ref starting with 'CEOP-'", ceop_ref.startswith('CEOP-'),
                    f"ceop_ref='{ceop_ref}'")
        
        # Admin resolves the report
        print("\n[E.7] Admin resolves CSAM report...")
        r = await client.post(f"{BASE_URL}/admin/csam/{report_id}/resolve",
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("Admin POST /api/admin/csam/{id}/resolve → 200", r.status_code == 200,
                f"status={r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            log_test("Response has ok=True", data.get('ok') == True,
                    f"ok={data.get('ok')}")
            log_test("Response has status='resolved'", data.get('status') == 'resolved',
                    f"status='{data.get('status')}'")
        
        # Test escalate on nonexistent id → 404
        print("\n[E.8] Testing escalate on nonexistent id → 404...")
        r = await client.post(f"{BASE_URL}/admin/csam/nonexistent123/escalate",
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/csam/nonexistent/escalate → 404", r.status_code == 404,
                f"status={r.status_code}")
        
        # Test resolve on nonexistent id → 404
        print("\n[E.9] Testing resolve on nonexistent id → 404...")
        r = await client.post(f"{BASE_URL}/admin/csam/nonexistent123/resolve",
                             headers={"Authorization": f"Bearer {admin['token']}"})
        log_test("POST /api/admin/csam/nonexistent/resolve → 404", r.status_code == 404,
                f"status={r.status_code}")

async def main():
    print("\n" + "="*80)
    print("CLANCHAT PHASE 6: ADMIN+ & SAFETY BACKEND TEST")
    print("="*80)
    print("Testing:")
    print("(A) GATING - admin endpoints require auth and admin role")
    print("(B) NSFW QUEUE - AI-flagged media queue endpoints")
    print("(C) WATCHLIST - watch/unwatch users")
    print("(D) ADMIN NOTES - add/retrieve admin notes on users")
    print("(E) CSAM/CEOP - escalate/resolve CSAM reports")
    print("="*80)
    
    try:
        # Test A: Admin gating
        admin, regular, target = await test_admin_gating()
        
        # Test B: NSFW queue
        await test_nsfw_queue(admin)
        
        # Test C: Watchlist
        await test_watchlist(admin, target)
        
        # Test D: Admin notes
        await test_admin_notes(admin, target)
        
        # Test E: CSAM/CEOP
        await test_csam_ceop(admin)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"Total: {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n🎉 ALL PHASE 6 TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {tests_failed} TEST(S) FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
