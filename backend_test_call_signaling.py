#!/usr/bin/env python3
"""
Backend test for Call signaling (ringing) feature.
Tests POST /api/call/ring, /cancel, /decline, /accept endpoints.
"""
import requests
import uuid
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def random_email():
    return f"calltest+{uuid.uuid4().hex[:8]}@example.com"

def register_user(email, password, dob="1990-01-01"):
    """Register a new user (adult with DOB 1990-01-01)."""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "dob": dob
    })
    if resp.status_code != 200:
        print(f"❌ Register failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    user = data.get("user", {})
    return {
        "email": email,
        "password": password,
        "token": data.get("access_token"),
        "handle": user.get("handle"),
        "user_id": user.get("id")
    }

def login_user(email, password):
    """Login existing user."""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get("access_token")

def headers(token):
    return {"Authorization": f"Bearer {token}"}

def main():
    print("=" * 80)
    print("CALL SIGNALING (RINGING) BACKEND TEST")
    print("=" * 80)
    
    # Setup: Register OWNER and MEMBER as adult users
    print("\n[SETUP] Registering OWNER and MEMBER users...")
    owner_email = random_email()
    member_email = random_email()
    
    owner = register_user(owner_email, "Test1234!", "1990-01-01")
    if not owner:
        print("❌ SETUP FAILED: Could not register OWNER")
        sys.exit(1)
    print(f"✅ OWNER registered: {owner['handle']}")
    
    member = register_user(member_email, "Test1234!", "1990-01-01")
    if not member:
        print("❌ SETUP FAILED: Could not register MEMBER")
        sys.exit(1)
    print(f"✅ MEMBER registered: {member['handle']}")
    
    # Setup inner circle: OWNER invites MEMBER, MEMBER accepts
    print(f"\n[SETUP] Setting up inner circle relationship...")
    
    # OWNER invites MEMBER
    resp = requests.post(
        f"{BASE_URL}/inner/invite/{member['handle']}",
        headers=headers(owner['token'])
    )
    if resp.status_code != 200:
        print(f"❌ SETUP FAILED: OWNER invite failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ OWNER invited MEMBER to inner circle")
    
    # MEMBER accepts OWNER's invite
    resp = requests.post(
        f"{BASE_URL}/inner/accept/{owner['handle']}",
        headers=headers(member['token'])
    )
    if resp.status_code != 200:
        print(f"❌ SETUP FAILED: MEMBER accept failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ MEMBER accepted OWNER's inner circle invite")
    
    # Test counters
    passed = 0
    failed = 0
    
    # TEST 1: MEMBER rings OWNER (happy path)
    print("\n" + "=" * 80)
    print("TEST 1: MEMBER POST /api/call/ring {peer:OWNER, room:'r1', media:'video'} → 200")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/ring",
            headers=headers(member['token']),
            json={"peer": owner['handle'], "room": "r1", "media": "video"}
        )
        if resp.status_code == 200 and resp.json().get("ok") == True:
            print(f"✅ TEST 1 PASSED: Ring successful → 200 {resp.json()}")
            passed += 1
        else:
            print(f"❌ TEST 1 FAILED: Expected 200 with ok:true, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 1 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 2: Ring with NO Authorization header → 401
    print("\n" + "=" * 80)
    print("TEST 2: POST /api/call/ring with NO Authorization header → 401")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/ring",
            json={"peer": owner['handle'], "room": "r1", "media": "video"}
        )
        if resp.status_code == 401:
            print(f"✅ TEST 2 PASSED: No auth correctly rejected → 401")
            passed += 1
        else:
            print(f"❌ TEST 2 FAILED: Expected 401, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 2 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 3: Ring nonexistent peer → 404
    print("\n" + "=" * 80)
    print("TEST 3: MEMBER POST /api/call/ring {peer:'nosuchhandle123', room:'r'} → 404")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/ring",
            headers=headers(member['token']),
            json={"peer": "nosuchhandle123", "room": "r", "media": "video"}
        )
        if resp.status_code == 404:
            print(f"✅ TEST 3 PASSED: Nonexistent peer correctly rejected → 404")
            passed += 1
        else:
            print(f"❌ TEST 3 FAILED: Expected 404, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 3 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 4: Ring self → 400
    print("\n" + "=" * 80)
    print("TEST 4: MEMBER POST /api/call/ring {peer:MEMBER_handle (self), room:'r'} → 400")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/ring",
            headers=headers(member['token']),
            json={"peer": member['handle'], "room": "r", "media": "video"}
        )
        if resp.status_code == 400:
            print(f"✅ TEST 4 PASSED: Self-call correctly rejected → 400")
            passed += 1
        else:
            print(f"❌ TEST 4 FAILED: Expected 400, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 4 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 5: Call permission turned off
    print("\n" + "=" * 80)
    print("TEST 5: OWNER turns off call permission, MEMBER rings → 403, then restore → 200")
    print("=" * 80)
    try:
        # OWNER turns off call permission for MEMBER
        resp = requests.put(
            f"{BASE_URL}/inner/{member['handle']}/perms",
            headers=headers(owner['token']),
            json={"call": False}
        )
        if resp.status_code != 200:
            print(f"❌ TEST 5 FAILED: Could not set perms: {resp.status_code} {resp.text}")
            failed += 1
        else:
            print(f"✅ OWNER set call:false for MEMBER")
            
            # MEMBER tries to ring OWNER → should get 403
            resp = requests.post(
                f"{BASE_URL}/call/ring",
                headers=headers(member['token']),
                json={"peer": owner['handle'], "room": "r", "media": "video"}
            )
            if resp.status_code == 403 and "turned off calls" in resp.text.lower():
                print(f"✅ MEMBER ring correctly rejected → 403 (detail mentions calls turned off)")
                
                # OWNER restores call permission
                resp = requests.put(
                    f"{BASE_URL}/inner/{member['handle']}/perms",
                    headers=headers(owner['token']),
                    json={"call": True}
                )
                if resp.status_code != 200:
                    print(f"❌ TEST 5 FAILED: Could not restore perms: {resp.status_code} {resp.text}")
                    failed += 1
                else:
                    print(f"✅ OWNER restored call:true for MEMBER")
                    
                    # MEMBER rings OWNER again → should work now
                    resp = requests.post(
                        f"{BASE_URL}/call/ring",
                        headers=headers(member['token']),
                        json={"peer": owner['handle'], "room": "r", "media": "video"}
                    )
                    if resp.status_code == 200 and resp.json().get("ok") == True:
                        print(f"✅ TEST 5 PASSED: Ring works again after restoring perms → 200")
                        passed += 1
                    else:
                        print(f"❌ TEST 5 FAILED: Expected 200 after restore, got {resp.status_code} {resp.text}")
                        failed += 1
            else:
                print(f"❌ TEST 5 FAILED: Expected 403 with 'turned off calls', got {resp.status_code} {resp.text}")
                failed += 1
    except Exception as e:
        print(f"❌ TEST 5 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 6: Cancel call
    print("\n" + "=" * 80)
    print("TEST 6: MEMBER POST /api/call/cancel {peer:OWNER, room:'r'} → 200")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/cancel",
            headers=headers(member['token']),
            json={"peer": owner['handle'], "room": "r"}
        )
        if resp.status_code == 200 and resp.json().get("ok") == True:
            print(f"✅ TEST 6 PASSED: Cancel successful → 200")
            passed += 1
        else:
            print(f"❌ TEST 6 FAILED: Expected 200, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 6 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 7: Decline call
    print("\n" + "=" * 80)
    print("TEST 7: MEMBER POST /api/call/decline {peer:OWNER, room:'r'} → 200")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/decline",
            headers=headers(member['token']),
            json={"peer": owner['handle'], "room": "r"}
        )
        if resp.status_code == 200 and resp.json().get("ok") == True:
            print(f"✅ TEST 7 PASSED: Decline successful → 200")
            passed += 1
        else:
            print(f"❌ TEST 7 FAILED: Expected 200, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 7 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 8: Accept call
    print("\n" + "=" * 80)
    print("TEST 8: MEMBER POST /api/call/accept {peer:OWNER, room:'r'} → 200")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/call/accept",
            headers=headers(member['token']),
            json={"peer": owner['handle'], "room": "r"}
        )
        if resp.status_code == 200 and resp.json().get("ok") == True:
            print(f"✅ TEST 8 PASSED: Accept successful → 200")
            passed += 1
        else:
            print(f"❌ TEST 8 FAILED: Expected 200, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 8 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 9: Cancel/decline/accept with nonexistent peer → 404
    print("\n" + "=" * 80)
    print("TEST 9: cancel/decline/accept each with nonexistent peer handle → 404")
    print("=" * 80)
    try:
        endpoints = [
            ("cancel", "/api/call/cancel"),
            ("decline", "/api/call/decline"),
            ("accept", "/api/call/accept")
        ]
        test9_passed = True
        for name, endpoint in endpoints:
            resp = requests.post(
                f"{BASE_URL}{endpoint.replace('/api', '')}",
                headers=headers(member['token']),
                json={"peer": "nonexistenthandle999", "room": "r"}
            )
            if resp.status_code == 404:
                print(f"✅ {name} with nonexistent peer → 404")
            else:
                print(f"❌ {name} with nonexistent peer: Expected 404, got {resp.status_code} {resp.text}")
                test9_passed = False
        
        if test9_passed:
            print(f"✅ TEST 9 PASSED: All cancel/decline/accept correctly reject nonexistent peer → 404")
            passed += 1
        else:
            print(f"❌ TEST 9 FAILED: Some endpoints did not return 404 for nonexistent peer")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 9 FAILED: Exception: {e}")
        failed += 1
    
    # TEST 10: Regression - LiveKit token endpoint still works
    print("\n" + "=" * 80)
    print("TEST 10: REGRESSION - MEMBER POST /api/livekit/token {room:'r', peer:OWNER} → 200")
    print("=" * 80)
    try:
        resp = requests.post(
            f"{BASE_URL}/livekit/token",
            headers=headers(member['token']),
            json={"room": "r", "peer": owner['handle']}
        )
        if resp.status_code == 200 and "participant_token" in resp.json():
            print(f"✅ TEST 10 PASSED: LiveKit token endpoint still works → 200")
            passed += 1
        else:
            print(f"❌ TEST 10 FAILED: Expected 200 with participant_token, got {resp.status_code} {resp.text}")
            failed += 1
    except Exception as e:
        print(f"❌ TEST 10 FAILED: Exception: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = passed + failed
    print(f"Total tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success rate: {(passed/total*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
