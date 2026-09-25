#!/usr/bin/env python3
"""
Test script for Safety Spine: DOB at signup + minor flag + hardcoded minor protection
Tests the NEW safety spine feature in ClanChat FastAPI backend.
"""
import asyncio
import httpx
import uuid
from datetime import datetime, timezone

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def rand_suffix():
    return uuid.uuid4().hex[:8]

def compute_dob_dates():
    """Compute dates dynamically based on current year."""
    current_year = datetime.now(timezone.utc).year
    MINOR_DOB = f"{current_year - 15}-06-15"  # ~15 years ago
    UNDERAGE_DOB = f"{current_year - 5}-03-10"  # ~5 years ago
    ADULT_DOB = "1990-01-01"
    ANOTHER_ADULT_DOB = "1992-03-03"
    return MINOR_DOB, UNDERAGE_DOB, ADULT_DOB, ANOTHER_ADULT_DOB

async def main():
    print("=" * 80)
    print("SAFETY SPINE BACKEND TEST: DOB + minor flag + hardcoded minor protection")
    print("=" * 80)
    
    MINOR_DOB, UNDERAGE_DOB, ADULT_DOB, ANOTHER_ADULT_DOB = compute_dob_dates()
    print(f"\nComputed DOB dates:")
    print(f"  MINOR_DOB (age ~15): {MINOR_DOB}")
    print(f"  UNDERAGE_DOB (age ~5): {UNDERAGE_DOB}")
    print(f"  ADULT_DOB: {ADULT_DOB}")
    print(f"  ANOTHER_ADULT_DOB: {ANOTHER_ADULT_DOB}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # ========== STEP (a): Registration validation ==========
        print("\n" + "=" * 80)
        print("STEP (a): Registration validation")
        print("=" * 80)
        
        # Test 1: Register with UNDERAGE_DOB (age ~5) -> 400
        print("\n[TEST a.1] Register with UNDERAGE_DOB (age ~5) -> expect 400")
        try:
            r = await client.post(f"{BASE_URL}/auth/register", json={
                "email": f"underage+{rand_suffix()}@example.com",
                "password": "secret123",
                "name": "Underage User",
                "dob": UNDERAGE_DOB
            })
            if r.status_code == 400:
                print(f"✅ PASS: Got 400 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 400, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test 2: Register with NO dob field -> 400
        print("\n[TEST a.2] Register with NO dob field -> expect 400")
        try:
            r = await client.post(f"{BASE_URL}/auth/register", json={
                "email": f"nodob+{rand_suffix()}@example.com",
                "password": "secret123",
                "name": "No DOB User"
            })
            if r.status_code == 400:
                print(f"✅ PASS: Got 400 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 400, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test 3: Register with ADULT_DOB -> 200
        print("\n[TEST a.3] Register with ADULT_DOB -> expect 200")
        adult_email = f"adult+{rand_suffix()}@example.com"
        try:
            r = await client.post(f"{BASE_URL}/auth/register", json={
                "email": adult_email,
                "password": "secret123",
                "name": "Adult User",
                "dob": ADULT_DOB
            })
            if r.status_code == 200:
                data = r.json()
                adult_token = data.get("access_token")
                adult_handle = data.get("user", {}).get("handle")
                print(f"✅ PASS: Got 200. Account created with handle={adult_handle}")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
                return
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
            return
        
        # ========== STEP (b): Register MINOR, ADULT, ANOTHER_ADULT and check /api/me ==========
        print("\n" + "=" * 80)
        print("STEP (b): Register MINOR, ADULT, ANOTHER_ADULT and check /api/me")
        print("=" * 80)
        
        # Register MINOR
        print("\n[TEST b.1] Register MINOR with MINOR_DOB")
        minor_email = f"minor+{rand_suffix()}@example.com"
        try:
            r = await client.post(f"{BASE_URL}/auth/register", json={
                "email": minor_email,
                "password": "secret123",
                "name": "Minor User",
                "dob": MINOR_DOB
            })
            if r.status_code == 200:
                data = r.json()
                minor_token = data.get("access_token")
                minor_handle = data.get("user", {}).get("handle")
                print(f"✅ PASS: MINOR registered with handle={minor_handle}")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
                return
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
            return
        
        # Register ANOTHER_ADULT
        print("\n[TEST b.2] Register ANOTHER_ADULT with ANOTHER_ADULT_DOB")
        another_adult_email = f"anotheradult+{rand_suffix()}@example.com"
        try:
            r = await client.post(f"{BASE_URL}/auth/register", json={
                "email": another_adult_email,
                "password": "secret123",
                "name": "Another Adult",
                "dob": ANOTHER_ADULT_DOB
            })
            if r.status_code == 200:
                data = r.json()
                another_adult_token = data.get("access_token")
                another_adult_handle = data.get("user", {}).get("handle")
                print(f"✅ PASS: ANOTHER_ADULT registered with handle={another_adult_handle}")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
                return
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
            return
        
        # Check MINOR GET /api/me
        print("\n[TEST b.3] MINOR GET /api/me -> is_minor=true, dob_set=true, nsfw_locked=true, comfort_zone.nsfw=false")
        try:
            r = await client.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {minor_token}"})
            if r.status_code == 200:
                data = r.json()
                is_minor = data.get("is_minor")
                dob_set = data.get("dob_set")
                nsfw_locked = data.get("nsfw_locked")
                comfort_zone = data.get("comfort_zone", {})
                nsfw_pref = comfort_zone.get("nsfw")
                
                checks = [
                    ("is_minor", is_minor, True),
                    ("dob_set", dob_set, True),
                    ("nsfw_locked", nsfw_locked, True),
                    ("comfort_zone.nsfw", nsfw_pref, False)
                ]
                
                all_pass = True
                for field, actual, expected in checks:
                    if actual == expected:
                        print(f"  ✅ {field}={actual} (expected {expected})")
                    else:
                        print(f"  ❌ {field}={actual} (expected {expected})")
                        all_pass = False
                
                if all_pass:
                    print("✅ PASS: All MINOR flags correct")
                else:
                    print("❌ FAIL: Some MINOR flags incorrect")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Check ADULT GET /api/me
        print("\n[TEST b.4] ADULT GET /api/me -> is_minor=false")
        try:
            r = await client.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 200:
                data = r.json()
                is_minor = data.get("is_minor")
                if is_minor == False:
                    print(f"✅ PASS: ADULT is_minor=false")
                else:
                    print(f"❌ FAIL: ADULT is_minor={is_minor} (expected False)")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (c): Adult<->Minor barrier for follow and DM ==========
        print("\n" + "=" * 80)
        print("STEP (c): Adult<->Minor barrier for follow and DM")
        print("=" * 80)
        
        # Test c.1: ADULT POST /api/follow/{MINOR_handle} -> 403
        print(f"\n[TEST c.1] ADULT POST /api/follow/{minor_handle} -> expect 403")
        try:
            r = await client.post(f"{BASE_URL}/follow/{minor_handle}", 
                                 headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 403:
                print(f"✅ PASS: Got 403 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 403, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test c.2: MINOR POST /api/follow/{ADULT_handle} -> 403
        print(f"\n[TEST c.2] MINOR POST /api/follow/{adult_handle} -> expect 403")
        try:
            r = await client.post(f"{BASE_URL}/follow/{adult_handle}", 
                                 headers={"Authorization": f"Bearer {minor_token}"})
            if r.status_code == 403:
                print(f"✅ PASS: Got 403 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 403, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test c.3: ADULT POST /api/dms/{MINOR_handle} -> 403
        print(f"\n[TEST c.3] ADULT POST /api/dms/{minor_handle} {{text:'hi'}} -> expect 403")
        try:
            r = await client.post(f"{BASE_URL}/dms/{minor_handle}", 
                                 headers={"Authorization": f"Bearer {adult_token}"},
                                 json={"text": "hi"})
            if r.status_code == 403:
                print(f"✅ PASS: Got 403 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 403, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test c.4: MINOR POST /api/dms/{ADULT_handle} -> 403
        print(f"\n[TEST c.4] MINOR POST /api/dms/{adult_handle} {{text:'hi'}} -> expect 403")
        try:
            r = await client.post(f"{BASE_URL}/dms/{adult_handle}", 
                                 headers={"Authorization": f"Bearer {minor_token}"},
                                 json={"text": "hi"})
            if r.status_code == 403:
                print(f"✅ PASS: Got 403 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 403, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (d): Adult inner invite to Minor -> 403 ==========
        print("\n" + "=" * 80)
        print("STEP (d): Adult inner invite to Minor -> 403")
        print("=" * 80)
        
        print(f"\n[TEST d.1] ADULT POST /api/inner/invite/{minor_handle} -> expect 403")
        try:
            r = await client.post(f"{BASE_URL}/inner/invite/{minor_handle}", 
                                 headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 403:
                print(f"✅ PASS: Got 403 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 403, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (e): Search hides users across age boundary ==========
        print("\n" + "=" * 80)
        print("STEP (e): Search hides users across age boundary")
        print("=" * 80)
        
        # Test e.1: ADULT GET /api/search?q=<MINOR handle> -> MINOR NOT in users[]
        print(f"\n[TEST e.1] ADULT GET /api/search?q={minor_handle} -> MINOR NOT in users[]")
        try:
            r = await client.get(f"{BASE_URL}/search?q={minor_handle}", 
                                headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 200:
                data = r.json()
                users = data.get("users", [])
                minor_found = any(u.get("handle") == minor_handle for u in users)
                if not minor_found:
                    print(f"✅ PASS: MINOR NOT found in search results (users count: {len(users)})")
                else:
                    print(f"❌ FAIL: MINOR found in search results (should be hidden)")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test e.2: MINOR GET /api/search?q=<ADULT handle> -> ADULT NOT in users[]
        print(f"\n[TEST e.2] MINOR GET /api/search?q={adult_handle} -> ADULT NOT in users[]")
        try:
            r = await client.get(f"{BASE_URL}/search?q={adult_handle}", 
                                headers={"Authorization": f"Bearer {minor_token}"})
            if r.status_code == 200:
                data = r.json()
                users = data.get("users", [])
                adult_found = any(u.get("handle") == adult_handle for u in users)
                if not adult_found:
                    print(f"✅ PASS: ADULT NOT found in search results (users count: {len(users)})")
                else:
                    print(f"❌ FAIL: ADULT found in search results (should be hidden)")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (f): Adults unaffected ==========
        print("\n" + "=" * 80)
        print("STEP (f): Adults unaffected (can follow/search each other)")
        print("=" * 80)
        
        # Test f.1: ADULT POST /api/follow/{ANOTHER_ADULT_handle} -> 200/approved
        print(f"\n[TEST f.1] ADULT POST /api/follow/{another_adult_handle} -> expect 200/approved")
        try:
            r = await client.post(f"{BASE_URL}/follow/{another_adult_handle}", 
                                 headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                if status == "approved":
                    print(f"✅ PASS: Got 200 with status='approved' (adults unaffected)")
                else:
                    print(f"❌ FAIL: Got 200 but status={status} (expected 'approved')")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # Test f.2: ADULT GET /api/search?q=<ANOTHER_ADULT handle> -> present
        print(f"\n[TEST f.2] ADULT GET /api/search?q={another_adult_handle} -> ANOTHER_ADULT present")
        try:
            r = await client.get(f"{BASE_URL}/search?q={another_adult_handle}", 
                                headers={"Authorization": f"Bearer {adult_token}"})
            if r.status_code == 200:
                data = r.json()
                users = data.get("users", [])
                another_adult_found = any(u.get("handle") == another_adult_handle for u in users)
                if another_adult_found:
                    print(f"✅ PASS: ANOTHER_ADULT found in search results (adults can find each other)")
                else:
                    print(f"❌ FAIL: ANOTHER_ADULT NOT found in search results (should be visible)")
            else:
                print(f"❌ FAIL: Expected 200, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (g): Minor cannot enable NSFW ==========
        print("\n" + "=" * 80)
        print("STEP (g): Minor cannot enable NSFW (hardcoded lock)")
        print("=" * 80)
        
        print(f"\n[TEST g.1] MINOR PUT /api/profile {{comfort_zone:{{nsfw:true}}}} -> then GET /api/me comfort_zone.nsfw still false")
        try:
            # Try to enable NSFW
            r = await client.put(f"{BASE_URL}/profile", 
                                headers={"Authorization": f"Bearer {minor_token}"},
                                json={"comfort_zone": {"nsfw": True}})
            if r.status_code == 200:
                print(f"  PUT /api/profile returned 200")
                
                # Check if NSFW is still false
                r2 = await client.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {minor_token}"})
                if r2.status_code == 200:
                    data = r2.json()
                    comfort_zone = data.get("comfort_zone", {})
                    nsfw_pref = comfort_zone.get("nsfw")
                    if nsfw_pref == False:
                        print(f"✅ PASS: comfort_zone.nsfw still false (hardcoded lock working)")
                    else:
                        print(f"❌ FAIL: comfort_zone.nsfw={nsfw_pref} (expected False, lock failed)")
                else:
                    print(f"❌ FAIL: GET /api/me returned {r2.status_code}")
            else:
                print(f"❌ FAIL: PUT /api/profile returned {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        # ========== STEP (h): DOB write-once ==========
        print("\n" + "=" * 80)
        print("STEP (h): DOB write-once (cannot change after set)")
        print("=" * 80)
        
        print(f"\n[TEST h.1] MINOR POST /api/auth/dob {{dob:'2000-01-01'}} -> expect 400 (already set)")
        try:
            r = await client.post(f"{BASE_URL}/auth/dob", 
                                 headers={"Authorization": f"Bearer {minor_token}"},
                                 json={"dob": "2000-01-01"})
            if r.status_code == 400:
                print(f"✅ PASS: Got 400 as expected. Error: {r.json().get('detail', '')}")
            else:
                print(f"❌ FAIL: Expected 400, got {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception: {e}")
        
        print("\n" + "=" * 80)
        print("SAFETY SPINE BACKEND TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
