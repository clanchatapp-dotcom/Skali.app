#!/usr/bin/env python3
"""
Comprehensive backend test for Staff roles feature.
Tests role assignment, removal, require_mod gating, and serializers.
"""
import asyncio
import httpx
import uuid
from datetime import datetime

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"
SUPER_ADMIN_EMAIL = "admin@clanchat.app"
SUPER_ADMIN_PASSWORD = "ClanChatAdmin!2025"

# Test results tracking
test_results = []

def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": test_name, "passed": passed, "details": details})
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")

async def register_user(client: httpx.AsyncClient, email: str, password: str, dob: str = "1990-01-01") -> dict:
    """Register a new user and return login response with token"""
    resp = await client.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "dob": dob
    })
    if resp.status_code != 200:
        raise Exception(f"Registration failed: {resp.status_code} {resp.text}")
    return resp.json()

async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """Login and return access token"""
    resp = await client.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("access_token") or data.get("token")

async def get_me(client: httpx.AsyncClient, token: str) -> dict:
    """Get current user profile"""
    resp = await client.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise Exception(f"Get me failed: {resp.status_code} {resp.text}")
    return resp.json()

async def main():
    print("=" * 80)
    print("STAFF ROLES BACKEND TEST")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Login as super admin
        print("\n[SETUP] Logging in as super admin...")
        try:
            super_token = await login(client, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
            super_me = await get_me(client, super_token)
            super_handle = super_me["handle"]
            print(f"✓ Super admin logged in: {super_handle}")
            log_test("Super admin login", True, f"handle={super_handle}, is_admin={super_me.get('is_admin')}")
        except Exception as e:
            log_test("Super admin login", False, str(e))
            return
        
        # Step 2: Register 4 throwaway adult users
        print("\n[SETUP] Registering throwaway adult users...")
        users = {}
        user_names = ["MOD", "CO", "FT", "NORMAL"]
        
        for name in user_names:
            try:
                uid = str(uuid.uuid4())[:8]
                email = f"staffrole{name.lower()}{uid}@example.com"
                password = "Test1234!"
                
                reg_resp = await register_user(client, email, password, "1990-01-01")
                token = reg_resp.get("access_token") or reg_resp.get("token")
                me = await get_me(client, token)
                
                users[name] = {
                    "email": email,
                    "password": password,
                    "token": token,
                    "handle": me["handle"],
                    "id": me["id"]
                }
                print(f"✓ Registered {name}: {me['handle']}")
            except Exception as e:
                log_test(f"Register {name} user", False, str(e))
                return
        
        log_test("Register 4 adult users", True, f"MOD={users['MOD']['handle']}, CO={users['CO']['handle']}, FT={users['FT']['handle']}, NORMAL={users['NORMAL']['handle']}")
        
        # ===== TEST 1: Super assigns roles =====
        print("\n[TEST 1] Super admin assigns roles...")
        
        # Assign moderator role to MOD
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign", 
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["MOD"]["handle"], "role": "moderator"})
            
            if resp.status_code == 200:
                # Verify MOD has moderator role
                mod_me = await get_me(client, users["MOD"]["token"])
                has_can_moderate = mod_me.get("can_moderate") == True
                is_not_admin = mod_me.get("is_admin") == False
                
                log_test("Assign moderator role to MOD", 
                    has_can_moderate and is_not_admin,
                    f"can_moderate={mod_me.get('can_moderate')}, is_admin={mod_me.get('is_admin')}")
            else:
                log_test("Assign moderator role to MOD", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("Assign moderator role to MOD", False, str(e))
        
        # Assign co_admin role to CO
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["CO"]["handle"], "role": "co_admin"})
            
            if resp.status_code == 200:
                # Verify CO has is_admin=true
                co_me = await get_me(client, users["CO"]["token"])
                is_admin = co_me.get("is_admin") == True
                
                log_test("Assign co_admin role to CO",
                    is_admin,
                    f"is_admin={co_me.get('is_admin')}")
            else:
                log_test("Assign co_admin role to CO", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("Assign co_admin role to CO", False, str(e))
        
        # Assign first_tester role to FT
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["FT"]["handle"], "role": "first_tester"})
            
            if resp.status_code == 200:
                # Verify FT has account_type='verified', is_admin=false, can_moderate=false
                ft_me = await get_me(client, users["FT"]["token"])
                is_verified = ft_me.get("account_type") == "verified"
                is_not_admin = ft_me.get("is_admin") == False
                cannot_moderate = ft_me.get("can_moderate") == False
                
                log_test("Assign first_tester role to FT",
                    is_verified and is_not_admin and cannot_moderate,
                    f"account_type={ft_me.get('account_type')}, is_admin={ft_me.get('is_admin')}, can_moderate={ft_me.get('can_moderate')}")
            else:
                log_test("Assign first_tester role to FT", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("Assign first_tester role to FT", False, str(e))
        
        # ===== TEST 2: Validation tests =====
        print("\n[TEST 2] Validation tests...")
        
        # Invalid role 'boss'
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["NORMAL"]["handle"], "role": "boss"})
            
            log_test("Assign invalid role 'boss'",
                resp.status_code == 400,
                f"Expected 400, got {resp.status_code}")
        except Exception as e:
            log_test("Assign invalid role 'boss'", False, str(e))
        
        # Nonexistent handle
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": "nonexistenthandle123", "role": "moderator"})
            
            log_test("Assign role to nonexistent handle",
                resp.status_code == 404,
                f"Expected 404, got {resp.status_code}")
        except Exception as e:
            log_test("Assign role to nonexistent handle", False, str(e))
        
        # Protected super admin (assign to super admin's own handle)
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": super_handle, "role": "moderator"})
            
            log_test("Assign role to protected super admin",
                resp.status_code == 400,
                f"Expected 400 (protected), got {resp.status_code}")
        except Exception as e:
            log_test("Assign role to protected super admin", False, str(e))
        
        # ===== TEST 3: Co-admin restrictions =====
        print("\n[TEST 3] Co-admin restrictions...")
        
        # CO tries to assign co_admin role (should fail - only super can assign co_admin)
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {users['CO']['token']}"},
                json={"handle": users["NORMAL"]["handle"], "role": "co_admin"})
            
            log_test("CO tries to assign co_admin role",
                resp.status_code == 403,
                f"Expected 403 (only super can assign co_admin), got {resp.status_code}")
        except Exception as e:
            log_test("CO tries to assign co_admin role", False, str(e))
        
        # CO assigns moderator role (should succeed)
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {users['CO']['token']}"},
                json={"handle": users["NORMAL"]["handle"], "role": "moderator"})
            
            log_test("CO assigns moderator role to NORMAL",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}")
        except Exception as e:
            log_test("CO assigns moderator role to NORMAL", False, str(e))
        
        # ===== TEST 4: require_mod gating (moderator access) =====
        print("\n[TEST 4] require_mod gating - moderator can access these endpoints...")
        
        mod_token = users["MOD"]["token"]
        
        # MOD can access require_mod endpoints
        mod_endpoints = [
            ("GET /api/admin/reports", "get", f"{BASE_URL}/admin/reports"),
            ("GET /api/admin/stats", "get", f"{BASE_URL}/admin/stats"),
            ("GET /api/admin/nsfw", "get", f"{BASE_URL}/admin/nsfw"),
        ]
        
        for name, method, url in mod_endpoints:
            try:
                if method == "get":
                    resp = await client.get(url, headers={"Authorization": f"Bearer {mod_token}"})
                else:
                    resp = await client.post(url, headers={"Authorization": f"Bearer {mod_token}"}, json={})
                
                log_test(f"MOD access {name}",
                    resp.status_code == 200,
                    f"Expected 200, got {resp.status_code}")
            except Exception as e:
                log_test(f"MOD access {name}", False, str(e))
        
        # MOD can flag a user
        try:
            resp = await client.post(f"{BASE_URL}/admin/users/{users['NORMAL']['handle']}/flag",
                headers={"Authorization": f"Bearer {mod_token}"},
                json={"reason": "test flag"})
            
            log_test("MOD flags NORMAL user",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}")
        except Exception as e:
            log_test("MOD flags NORMAL user", False, str(e))
        
        # MOD CANNOT access require_admin endpoints
        admin_only_endpoints = [
            ("GET /api/admin/roles", "get", f"{BASE_URL}/admin/roles"),
            ("GET /api/admin/audit", "get", f"{BASE_URL}/admin/audit"),
            ("GET /api/admin/investigate/{NORMAL}", "get", f"{BASE_URL}/admin/investigate/{users['NORMAL']['handle']}"),
        ]
        
        for name, method, url in admin_only_endpoints:
            try:
                if method == "get":
                    resp = await client.get(url, headers={"Authorization": f"Bearer {mod_token}"})
                else:
                    resp = await client.post(url, headers={"Authorization": f"Bearer {mod_token}"}, json={})
                
                log_test(f"MOD blocked from {name}",
                    resp.status_code == 403,
                    f"Expected 403, got {resp.status_code}")
            except Exception as e:
                log_test(f"MOD blocked from {name}", False, str(e))
        
        # MOD cannot assign roles
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {mod_token}"},
                json={"handle": users["FT"]["handle"], "role": "moderator"})
            
            log_test("MOD blocked from POST /api/admin/roles/assign",
                resp.status_code == 403,
                f"Expected 403, got {resp.status_code}")
        except Exception as e:
            log_test("MOD blocked from POST /api/admin/roles/assign", False, str(e))
        
        # ===== TEST 5: First tester and normal user restrictions =====
        print("\n[TEST 5] First tester and normal user restrictions...")
        
        # FT cannot access require_mod endpoints
        try:
            resp = await client.get(f"{BASE_URL}/admin/reports",
                headers={"Authorization": f"Bearer {users['FT']['token']}"})
            
            log_test("FT blocked from GET /api/admin/reports",
                resp.status_code == 403,
                f"Expected 403, got {resp.status_code}")
        except Exception as e:
            log_test("FT blocked from GET /api/admin/reports", False, str(e))
        
        # NORMAL user (now has moderator role from test 3) should be able to access require_mod endpoints
        # But let's test with a fresh normal user first - need to remove NORMAL's moderator role
        # Actually, NORMAL now has moderator role, so let's just verify they can access mod endpoints
        try:
            resp = await client.get(f"{BASE_URL}/admin/reports",
                headers={"Authorization": f"Bearer {users['NORMAL']['token']}"})
            
            # NORMAL has moderator role now, so should get 200
            log_test("NORMAL (with moderator role) can access GET /api/admin/reports",
                resp.status_code == 200,
                f"Expected 200 (NORMAL has moderator role), got {resp.status_code}")
        except Exception as e:
            log_test("NORMAL (with moderator role) can access GET /api/admin/reports", False, str(e))
        
        # ===== TEST 6: GET /api/admin/roles listing =====
        print("\n[TEST 6] GET /api/admin/roles listing...")
        
        try:
            resp = await client.get(f"{BASE_URL}/admin/roles",
                headers={"Authorization": f"Bearer {super_token}"})
            
            if resp.status_code == 200:
                roles_list = resp.json()
                
                # Check if all expected users are in the list
                handles_in_list = {r["handle"] for r in roles_list}
                roles_by_handle = {r["handle"]: r for r in roles_list}
                
                has_mod = users["MOD"]["handle"] in handles_in_list
                has_co = users["CO"]["handle"] in handles_in_list
                has_ft = users["FT"]["handle"] in handles_in_list
                has_normal = users["NORMAL"]["handle"] in handles_in_list
                has_super = super_handle in handles_in_list
                
                # Check super admin is marked as protected
                super_protected = False
                if super_handle in roles_by_handle:
                    super_protected = roles_by_handle[super_handle].get("protected") == True
                    super_role = roles_by_handle[super_handle].get("role")
                
                log_test("GET /api/admin/roles includes all role-holders",
                    has_mod and has_co and has_ft and has_normal and has_super and super_protected,
                    f"MOD={has_mod}, CO={has_co}, FT={has_ft}, NORMAL={has_normal}, SUPER={has_super} (protected={super_protected}, role={super_role if super_handle in roles_by_handle else 'N/A'})")
            else:
                log_test("GET /api/admin/roles", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("GET /api/admin/roles", False, str(e))
        
        # ===== TEST 7: Remove role tests =====
        print("\n[TEST 7] Remove role tests...")
        
        # Super removes MOD's role
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/remove",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["MOD"]["handle"]})
            
            if resp.status_code == 200:
                # Verify MOD can no longer access require_mod endpoints
                resp2 = await client.get(f"{BASE_URL}/admin/reports",
                    headers={"Authorization": f"Bearer {users['MOD']['token']}"})
                
                log_test("Remove MOD's role and verify access revoked",
                    resp2.status_code == 403,
                    f"Remove: 200, MOD access after removal: {resp2.status_code} (expected 403)")
            else:
                log_test("Remove MOD's role", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("Remove MOD's role", False, str(e))
        
        # Try to remove super admin's own role (should fail - protected)
        try:
            resp = await client.post(f"{BASE_URL}/admin/roles/remove",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": super_handle})
            
            log_test("Remove protected super admin's role",
                resp.status_code == 400,
                f"Expected 400 (protected), got {resp.status_code}")
        except Exception as e:
            log_test("Remove protected super admin's role", False, str(e))
        
        # Test 'only super removes co_admin': Make NORMAL a co_admin, then CO tries to remove NORMAL
        try:
            # First, make NORMAL a co_admin
            resp1 = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["NORMAL"]["handle"], "role": "co_admin"})
            
            if resp1.status_code == 200:
                # Now CO tries to remove NORMAL (should fail - only super can remove co_admin)
                resp2 = await client.post(f"{BASE_URL}/admin/roles/remove",
                    headers={"Authorization": f"Bearer {users['CO']['token']}"},
                    json={"handle": users["NORMAL"]["handle"]})
                
                log_test("CO tries to remove co_admin NORMAL",
                    resp2.status_code == 403,
                    f"Expected 403 (only super removes co_admin), got {resp2.status_code}")
            else:
                log_test("CO tries to remove co_admin NORMAL", False, f"Setup failed: {resp1.status_code}")
        except Exception as e:
            log_test("CO tries to remove co_admin NORMAL", False, str(e))
        
        # ===== TEST 8: Serializers (role field in profiles and posts) =====
        print("\n[TEST 8] Serializers - role field in profiles and posts...")
        
        # Check role in user profile (GET /api/users/{handle})
        try:
            resp = await client.get(f"{BASE_URL}/users/{users['CO']['handle']}",
                headers={"Authorization": f"Bearer {super_token}"})
            
            if resp.status_code == 200:
                profile = resp.json()
                has_role = "role" in profile
                role_value = profile.get("role")
                
                log_test("GET /api/users/{CO_handle} includes role field",
                    has_role and role_value == "co_admin",
                    f"role={role_value} (expected 'co_admin')")
            else:
                log_test("GET /api/users/{CO_handle}", False, f"{resp.status_code}: {resp.text}")
        except Exception as e:
            log_test("GET /api/users/{CO_handle}", False, str(e))
        
        # Create a public post as MOD (before we removed their role, but we already removed it)
        # Let's reassign moderator to MOD first
        try:
            # Reassign moderator to MOD
            resp1 = await client.post(f"{BASE_URL}/admin/roles/assign",
                headers={"Authorization": f"Bearer {super_token}"},
                json={"handle": users["MOD"]["handle"], "role": "moderator"})
            
            if resp1.status_code == 200:
                # MOD creates a public post
                resp2 = await client.post(f"{BASE_URL}/posts",
                    headers={"Authorization": f"Bearer {users['MOD']['token']}"},
                    json={"tier": "public", "text": "Test post by moderator"})
                
                if resp2.status_code == 200:
                    post_id = resp2.json().get("id")
                    
                    # Get feed and check if MOD's post has role field
                    resp3 = await client.get(f"{BASE_URL}/feed?scope=general",
                        headers={"Authorization": f"Bearer {super_token}"})
                    
                    if resp3.status_code == 200:
                        feed = resp3.json()
                        mod_post = None
                        for post in feed:
                            if post.get("id") == post_id:
                                mod_post = post
                                break
                        
                        if mod_post:
                            author_role = mod_post.get("author", {}).get("role")
                            log_test("GET /api/feed shows author.role for MOD's post",
                                author_role == "moderator",
                                f"author.role={author_role} (expected 'moderator')")
                        else:
                            log_test("GET /api/feed shows author.role for MOD's post", False, "Post not found in feed")
                    else:
                        log_test("GET /api/feed", False, f"{resp3.status_code}: {resp3.text}")
                else:
                    log_test("MOD creates post", False, f"{resp2.status_code}: {resp2.text}")
            else:
                log_test("Reassign moderator to MOD", False, f"{resp1.status_code}: {resp1.text}")
        except Exception as e:
            log_test("Serializers - post author.role", False, str(e))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n❌ {total - passed} test(s) failed:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r['details']}")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
