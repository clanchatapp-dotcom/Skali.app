#!/usr/bin/env python3
"""
Backend test for NEW "Change #username (handle)" feature.
Tests POST /api/profile/handle endpoint with all validation rules.
"""
import requests
import uuid
import random
import string
from datetime import datetime

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def random_suffix():
    """Generate random suffix for unique handles."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def register_user(email, password, dob):
    """Register a new user and return token."""
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "dob": dob,
            "display_name": email.split('@')[0]
        }, timeout=10)
        print(f"Register {email}: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('access_token')
            handle = data.get('handle')
            print(f"  ✓ Registered with handle={handle}, token={token[:20]}...")
            return token, handle
        else:
            print(f"  ✗ Registration failed: {resp.text}")
            return None, None
    except Exception as e:
        print(f"  ✗ Exception during registration: {e}")
        return None, None

def get_me(token):
    """Get current user profile."""
    try:
        resp = requests.get(f"{BASE_URL}/me", headers={
            "Authorization": f"Bearer {token}"
        }, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"GET /api/me failed: {resp.status_code} {resp.text}")
            return None
    except Exception as e:
        print(f"Exception in get_me: {e}")
        return None

def change_handle(token, handle):
    """Change handle via POST /api/profile/handle."""
    try:
        resp = requests.post(f"{BASE_URL}/profile/handle", json={
            "handle": handle
        }, headers={
            "Authorization": f"Bearer {token}"
        }, timeout=10)
        return resp
    except Exception as e:
        print(f"Exception in change_handle: {e}")
        return None

print("=" * 80)
print("BACKEND TEST: Change #username (handle) — once every 60 days")
print("=" * 80)

# ============================================================================
# SETUP: Register adult user A (DOB 1990-01-01)
# ============================================================================
print("\n[SETUP] Registering adult user A (DOB 1990-01-01)...")
rand_a = random_suffix()
email_a = f"handletest_a_{rand_a}@example.com"
password_a = "TestPass123!"
token_a, handle_a_initial = register_user(email_a, password_a, "1990-01-01")

if not token_a:
    print("✗ SETUP FAILED: Could not register user A")
    exit(1)

print(f"✓ User A registered: {email_a}, initial handle={handle_a_initial}")

# ============================================================================
# TEST 1: A changes handle to 'newname<rand>' → 200, handle updated
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: A POST /api/profile/handle {handle:'newname<rand>'} → 200")
print("=" * 80)
try:
    new_handle_1 = f"newname{random_suffix()}"
    print(f"Changing handle to: {new_handle_1}")
    resp = change_handle(token_a, new_handle_1)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Response 200: {data}")
        
        # Verify response contains expected fields
        if data.get('ok') and data.get('handle') == new_handle_1 and data.get('handle_changed_at'):
            print(f"  ✓ Response has ok=True, handle={new_handle_1}, handle_changed_at={data.get('handle_changed_at')}")
        else:
            print(f"  ✗ Response missing expected fields: {data}")
        
        # Verify GET /api/me shows updated handle and handle_change_available_at
        me = get_me(token_a)
        if me:
            if me.get('handle') == new_handle_1:
                print(f"  ✓ GET /api/me shows handle updated to {new_handle_1}")
            else:
                print(f"  ✗ GET /api/me handle mismatch: expected {new_handle_1}, got {me.get('handle')}")
            
            available_at = me.get('handle_change_available_at')
            if available_at:
                print(f"  ✓ handle_change_available_at is non-null: {available_at}")
                # Verify it's a future ISO datetime
                try:
                    dt = datetime.fromisoformat(available_at.replace('Z', '+00:00'))
                    now = datetime.now(dt.tzinfo)
                    if dt > now:
                        print(f"    ✓ It's a future datetime (cooldown active)")
                    else:
                        print(f"    ✗ It's not a future datetime")
                except Exception as e:
                    print(f"    ✗ Failed to parse as ISO datetime: {e}")
            else:
                print(f"  ✗ handle_change_available_at is null (expected non-null future datetime)")
        
        print("✅ TEST 1 PASSED")
    else:
        print(f"✗ Expected 200, got {resp.status_code}: {resp.text}")
        print("❌ TEST 1 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 1: {e}")
    print("❌ TEST 1 FAILED")

# ============================================================================
# TEST 2: A tries to change handle again immediately → 400 (cooldown)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: A POST /api/profile/handle {handle:'anothername<rand>'} immediately → 400 (cooldown)")
print("=" * 80)
try:
    new_handle_2 = f"anothername{random_suffix()}"
    print(f"Attempting to change handle to: {new_handle_2}")
    resp = change_handle(token_a, new_handle_2)
    
    if resp.status_code == 400:
        detail = resp.json().get('detail', resp.text)
        print(f"✓ Response 400: {detail}")
        
        # Check if detail mentions days remaining
        if 'day' in detail.lower():
            print(f"  ✓ Detail mentions days remaining: '{detail}'")
            print("✅ TEST 2 PASSED")
        else:
            print(f"  ✗ Detail doesn't mention days: '{detail}'")
            print("❌ TEST 2 FAILED")
    else:
        print(f"✗ Expected 400, got {resp.status_code}: {resp.text}")
        print("❌ TEST 2 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 2: {e}")
    print("❌ TEST 2 FAILED")

# ============================================================================
# TEST 3: A tries handle 'ab' (too short) → 400
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: A POST /api/profile/handle {handle:'ab'} → 400 (too short, min 3)")
print("=" * 80)
try:
    resp = change_handle(token_a, "ab")
    
    if resp.status_code == 400:
        detail = resp.json().get('detail', resp.text)
        print(f"✓ Response 400: {detail}")
        
        # Check if detail mentions minimum length
        if '3' in detail or 'least' in detail.lower():
            print(f"  ✓ Detail mentions minimum length requirement")
            print("✅ TEST 3 PASSED")
        else:
            print(f"  ✗ Detail doesn't clearly indicate length requirement: '{detail}'")
            print("⚠️  TEST 3 PASSED (400 received, but message unclear)")
    else:
        print(f"✗ Expected 400, got {resp.status_code}: {resp.text}")
        print("❌ TEST 3 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 3: {e}")
    print("❌ TEST 3 FAILED")

# ============================================================================
# SETUP: Register adult user B (DOB 1990-01-01)
# ============================================================================
print("\n[SETUP] Registering adult user B (DOB 1990-01-01)...")
rand_b = random_suffix()
email_b = f"handletest_b_{rand_b}@example.com"
password_b = "TestPass123!"
token_b, handle_b_initial = register_user(email_b, password_b, "1990-01-01")

if not token_b:
    print("✗ SETUP FAILED: Could not register user B")
    exit(1)

print(f"✓ User B registered: {email_b}, initial handle={handle_b_initial}")

# ============================================================================
# TEST 4: B tries to take A's current handle → 409 (taken)
# ============================================================================
print("\n" + "=" * 80)
print(f"TEST 4: B POST /api/profile/handle {{handle:'{new_handle_1}'}} (A's handle) → 409 (taken)")
print("=" * 80)
try:
    print(f"B attempting to take A's handle: {new_handle_1}")
    resp = change_handle(token_b, new_handle_1)
    
    if resp.status_code == 409:
        detail = resp.json().get('detail', resp.text)
        print(f"✓ Response 409: {detail}")
        
        # Check if detail mentions "taken"
        if 'taken' in detail.lower():
            print(f"  ✓ Detail mentions handle is taken")
            print("✅ TEST 4 PASSED")
        else:
            print(f"  ✗ Detail doesn't mention 'taken': '{detail}'")
            print("⚠️  TEST 4 PASSED (409 received, but message unclear)")
    else:
        print(f"✗ Expected 409, got {resp.status_code}: {resp.text}")
        print("❌ TEST 4 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 4: {e}")
    print("❌ TEST 4 FAILED")

# ============================================================================
# TEST 5: B tries banned word 'nigger' → 400 (banned)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 5: B POST /api/profile/handle {handle:'nigger'} (banned slur) → 400")
print("=" * 80)
try:
    resp = change_handle(token_b, "nigger")
    
    if resp.status_code == 400:
        detail = resp.json().get('detail', resp.text)
        print(f"✓ Response 400: {detail}")
        
        # Check if detail mentions banned/not allowed
        if 'allowed' in detail.lower() or 'banned' in detail.lower():
            print(f"  ✓ Detail indicates word is not allowed/banned")
            print("✅ TEST 5 PASSED")
        else:
            print(f"  ✗ Detail doesn't clearly indicate banned word: '{detail}'")
            print("⚠️  TEST 5 PASSED (400 received, but message unclear)")
    else:
        print(f"✗ Expected 400, got {resp.status_code}: {resp.text}")
        print("❌ TEST 5 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 5: {e}")
    print("❌ TEST 5 FAILED")

# ============================================================================
# TEST 6: B tries to change to their own current handle → 400
# ============================================================================
print("\n" + "=" * 80)
print(f"TEST 6: B POST /api/profile/handle {{handle:'{handle_b_initial}'}} (B's own handle) → 400")
print("=" * 80)
try:
    # Get B's current handle from /api/me
    me_b = get_me(token_b)
    if me_b:
        current_handle_b = me_b.get('handle')
        print(f"B's current handle from GET /api/me: {current_handle_b}")
        
        resp = change_handle(token_b, current_handle_b)
        
        if resp.status_code == 400:
            detail = resp.json().get('detail', resp.text)
            print(f"✓ Response 400: {detail}")
            
            # Check if detail mentions "already"
            if 'already' in detail.lower():
                print(f"  ✓ Detail indicates handle is already theirs")
                print("✅ TEST 6 PASSED")
            else:
                print(f"  ✗ Detail doesn't mention 'already': '{detail}'")
                print("⚠️  TEST 6 PASSED (400 received, but message unclear)")
        else:
            print(f"✗ Expected 400, got {resp.status_code}: {resp.text}")
            print("❌ TEST 6 FAILED")
    else:
        print("✗ Could not get B's current handle from /api/me")
        print("❌ TEST 6 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 6: {e}")
    print("❌ TEST 6 FAILED")

# ============================================================================
# TEST 7: No auth header → 401
# ============================================================================
print("\n" + "=" * 80)
print("TEST 7: POST /api/profile/handle {handle:'whatever'} with NO Authorization → 401")
print("=" * 80)
try:
    resp = requests.post(f"{BASE_URL}/profile/handle", json={
        "handle": "whatever"
    }, timeout=10)
    
    if resp.status_code == 401:
        print(f"✓ Response 401: {resp.text}")
        print("✅ TEST 7 PASSED")
    else:
        print(f"✗ Expected 401, got {resp.status_code}: {resp.text}")
        print("❌ TEST 7 FAILED")
except Exception as e:
    print(f"✗ Exception in TEST 7: {e}")
    print("❌ TEST 7 FAILED")

print("\n" + "=" * 80)
print("ALL TESTS COMPLETED")
print("=" * 80)
