#!/usr/bin/env python3
"""
Test FCM push: device-token registration endpoints + guarded send helper
Tests the NEW push token storage and DM push hook (fail-open when FCM unconfigured).
"""
import asyncio
import httpx
import uuid
from datetime import datetime, timedelta

# Backend URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def random_email():
    return f"fcmtest+{uuid.uuid4().hex[:8]}@example.com"

async def register_user(email: str, handle: str, dob: str = "1990-01-01"):
    """Register a new user and return their auth token and actual handle."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "handle": handle,
            "display_name": handle,
            "dob": dob
        })
        print(f"Register {handle}: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  Error: {resp.text}")
            return None, None
        data = resp.json()
        token = data.get('access_token') or data.get('token')
        actual_handle = data.get('user', {}).get('handle', handle)
        return token, actual_handle

async def test_fcm_push():
    """Test FCM push token registration endpoints + DM push hook regression."""
    print("\n=== FCM PUSH TOKEN REGISTRATION + DM PUSH HOOK REGRESSION TEST ===\n")
    
    # Test 1: Register adult user U (DOB 1990-01-01)
    print("TEST 1: Register adult user U (DOB 1990-01-01)")
    u_email = random_email()
    u_handle = f"useru{uuid.uuid4().hex[:6]}"
    u_token, u_handle = await register_user(u_email, u_handle, "1990-01-01")
    if not u_token:
        print("❌ TEST 1 FAILED: Could not register user U\n")
        return
    print(f"✅ TEST 1 PASSED: User U registered (handle={u_handle})\n")
    
    headers_u = {"Authorization": f"Bearer {u_token}"}
    
    # Test 2: U POST /api/push/register {token:'test-fcm-tok-123', platform:'android'} → 200 {ok:true}
    print("TEST 2: U POST /api/push/register {token:'test-fcm-tok-123', platform:'android'} → 200 {ok:true}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/push/register", 
                                 json={"token": "test-fcm-tok-123", "platform": "android"},
                                 headers=headers_u)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {data}")
            if data.get('ok') == True:
                print("✅ TEST 2 PASSED: Token registered successfully\n")
            else:
                print(f"❌ TEST 2 FAILED: Expected {{ok:true}}, got {data}\n")
        else:
            print(f"❌ TEST 2 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # Test 3: U POST /api/push/register {token:'test-fcm-tok-123', platform:'android'} again → 200 (idempotent upsert)
    print("TEST 3: U POST /api/push/register {token:'test-fcm-tok-123', platform:'android'} again → 200 (idempotent upsert)")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/push/register", 
                                 json={"token": "test-fcm-tok-123", "platform": "android"},
                                 headers=headers_u)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {data}")
            if data.get('ok') == True:
                print("✅ TEST 3 PASSED: Idempotent upsert works (no duplicate error)\n")
            else:
                print(f"❌ TEST 3 FAILED: Expected {{ok:true}}, got {data}\n")
        else:
            print(f"❌ TEST 3 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # Test 4: U POST /api/push/register {token:''} → 400
    print("TEST 4: U POST /api/push/register {token:''} → 400")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/push/register", 
                                 json={"token": ""},
                                 headers=headers_u)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 400:
            print(f"  Response: {resp.text}")
            print("✅ TEST 4 PASSED: Empty token correctly rejected with 400\n")
        else:
            print(f"❌ TEST 4 FAILED: Expected 400, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    # Test 5: POST /api/push/register {token:'x'} with NO Authorization header → 401
    print("TEST 5: POST /api/push/register {token:'x'} with NO Authorization header → 401")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/push/register", 
                                 json={"token": "x"})
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 401:
            print(f"  Response: {resp.text}")
            print("✅ TEST 5 PASSED: No auth correctly rejected with 401\n")
        else:
            print(f"❌ TEST 5 FAILED: Expected 401, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    # Test 6: U DELETE /api/push/register/test-fcm-tok-123 → 200 {ok:true}
    print("TEST 6: U DELETE /api/push/register/test-fcm-tok-123 → 200 {ok:true}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/push/register/test-fcm-tok-123",
                                    headers=headers_u)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {data}")
            if data.get('ok') == True:
                print("✅ TEST 6 PASSED: Token unregistered successfully\n")
            else:
                print(f"❌ TEST 6 FAILED: Expected {{ok:true}}, got {data}\n")
        else:
            print(f"❌ TEST 6 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # Test 7: REGRESSION (push hook must not break DMs)
    print("TEST 7: REGRESSION - DM send with push hook (must not raise even though FCM unconfigured)")
    
    # Register A and B
    print("  7a. Register user A")
    a_email = random_email()
    a_handle = f"usera{uuid.uuid4().hex[:6]}"
    a_token, a_handle = await register_user(a_email, a_handle, "1990-01-01")
    if not a_token:
        print("❌ TEST 7 FAILED: Could not register user A\n")
        return
    print(f"  ✓ User A registered (handle={a_handle})")
    
    print("  7b. Register user B")
    b_email = random_email()
    b_handle = f"userb{uuid.uuid4().hex[:6]}"
    b_token, b_handle = await register_user(b_email, b_handle, "1990-01-01")
    if not b_token:
        print("❌ TEST 7 FAILED: Could not register user B\n")
        return
    print(f"  ✓ User B registered (handle={b_handle})")
    
    headers_a = {"Authorization": f"Bearer {a_token}"}
    headers_b = {"Authorization": f"Bearer {b_token}"}
    
    # Put B in A's inner circle (A invite, B accept)
    print("  7c. A invites B to inner circle")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/inner/invite/{b_handle}",
                                 headers=headers_a)
        print(f"    Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"    Error: {resp.text}")
            print("❌ TEST 7 FAILED: Could not invite B to inner circle\n")
            return
        print(f"    ✓ A invited B to inner circle")
    
    print("  7d. B accepts A's inner circle invite")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/inner/accept/{a_handle}",
                                 headers=headers_b)
        print(f"    Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"    Error: {resp.text}")
            print("❌ TEST 7 FAILED: B could not accept inner circle invite\n")
            return
        print(f"    ✓ B accepted A's inner circle invite")
    
    # A POST /api/dms/{B_handle} {text:'hi from A'} → 200 (push hook must not raise)
    print("  7e. A POST /api/dms/{B_handle} {text:'hi from A'} → 200 (push hook must NOT raise)")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/dms/{b_handle}",
                                 json={"text": "hi from A"},
                                 headers=headers_a)
        print(f"    Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"    Response: {data}")
            print(f"    ✓ DM sent successfully (push hook did NOT raise error)")
        else:
            print(f"    ❌ FAILED: Expected 200, got {resp.status_code}")
            print(f"    Error: {resp.text}")
            print("❌ TEST 7 FAILED: DM send failed (push hook may have raised error)\n")
            return
    
    # B GET /api/dms/{A_handle} → message 'hi from A' present
    print("  7f. B GET /api/dms/{A_handle} → message 'hi from A' present")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/dms/{a_handle}",
                                headers=headers_b)
        print(f"    Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get('messages', [])
            print(f"    Found {len(messages)} message(s)")
            found = False
            for msg in messages:
                if msg.get('text') == 'hi from A':
                    found = True
                    print(f"    ✓ Message 'hi from A' found in B's DM history")
                    break
            if found:
                print("✅ TEST 7 PASSED: DM regression test passed (push hook did not break DMs)\n")
            else:
                print(f"    ❌ Message 'hi from A' NOT found in B's DM history")
                print(f"    Messages: {messages}")
                print("❌ TEST 7 FAILED: Message not found\n")
        else:
            print(f"    ❌ FAILED: Expected 200, got {resp.status_code}")
            print(f"    Error: {resp.text}")
            print("❌ TEST 7 FAILED: Could not retrieve DM history\n")
    
    print("\n=== FCM PUSH TOKEN REGISTRATION + DM PUSH HOOK REGRESSION TEST COMPLETE ===\n")

if __name__ == "__main__":
    asyncio.run(test_fcm_push())
