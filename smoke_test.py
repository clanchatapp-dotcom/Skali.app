#!/usr/bin/env python3
"""
SMOKE REGRESSION TEST - ClanChat Backend
Quick smoke test after deployment packaging fix (requirements.txt flattened).
Tests core API health: auth, feed, encrypted DMs, admin gating.
"""
import requests
import json
import sys

# Base URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    return passed

def create_user(name):
    """Create a dev user and return (token, user_data)"""
    resp = requests.post(f"{BASE_URL}/dev/token", json={"name": name})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create user {name}: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    return data['access_token'], data['user']

def headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

print("\n" + "="*80)
print("SMOKE REGRESSION TEST - ClanChat Backend")
print("Testing: Auth, Feed, Encrypted DMs, Admin Gating")
print("="*80 + "\n")

# Track test results
all_passed = True

# ============================================================================
# TEST 1: AUTH - POST /api/dev/token + GET /api/me
# ============================================================================
print("TEST 1: AUTH - dev/token + /api/me")
print("-" * 80)

# 1a: Create SmokeA user
smokeA_token, smokeA_user = create_user("SmokeA")
if smokeA_token and smokeA_user:
    all_passed &= print_test(
        "POST /api/dev/token {name:'SmokeA'} -> access_token",
        True,
        f"Token length: {len(smokeA_token)}, Handle: {smokeA_user['handle']}"
    )
else:
    all_passed &= print_test("POST /api/dev/token {name:'SmokeA'}", False, "Failed to create user")
    sys.exit(1)

# 1b: GET /api/me with valid token -> 200
me_resp = requests.get(f"{BASE_URL}/me", headers=headers(smokeA_token))
if me_resp.status_code == 200:
    me_data = me_resp.json()
    has_handle = 'handle' in me_data
    all_passed &= print_test(
        "GET /api/me with token -> 200 (has handle)",
        has_handle,
        f"Status: {me_resp.status_code}, Handle: {me_data.get('handle')}"
    )
else:
    all_passed &= print_test(
        "GET /api/me with token -> 200",
        False,
        f"Status: {me_resp.status_code}, Response: {me_resp.text}"
    )

# 1c: GET /api/me without token -> 401
me_notoken_resp = requests.get(f"{BASE_URL}/me")
all_passed &= print_test(
    "GET /api/me without token -> 401",
    me_notoken_resp.status_code == 401,
    f"Status: {me_notoken_resp.status_code}"
)

# 1d: GET /api/me with malformed token -> 401
me_badtoken_resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": "Bearer invalid.token.here"})
all_passed &= print_test(
    "GET /api/me with malformed token -> 401",
    me_badtoken_resp.status_code == 401,
    f"Status: {me_badtoken_resp.status_code}"
)

# ============================================================================
# TEST 2: FEED - GET /api/feed?scope=general
# ============================================================================
print("\nTEST 2: FEED - GET /api/feed?scope=general")
print("-" * 80)

feed_resp = requests.get(f"{BASE_URL}/feed?scope=general", headers=headers(smokeA_token))
if feed_resp.status_code == 200:
    feed_data = feed_resp.json()
    is_array = isinstance(feed_data, list)
    has_seeded_posts = False
    
    # Check for seeded ClanChat posts
    if is_array:
        for post in feed_data:
            author = post.get('author', {})
            if author.get('handle') == 'clanchat':
                has_seeded_posts = True
                break
    
    all_passed &= print_test(
        "GET /api/feed?scope=general -> 200 (array)",
        is_array,
        f"Status: {feed_resp.status_code}, Type: {type(feed_data).__name__}, Count: {len(feed_data) if is_array else 0}"
    )
    
    all_passed &= print_test(
        "Feed includes seeded ClanChat public posts",
        has_seeded_posts,
        f"Found ClanChat posts: {has_seeded_posts}"
    )
else:
    all_passed &= print_test(
        "GET /api/feed?scope=general -> 200",
        False,
        f"Status: {feed_resp.status_code}, Response: {feed_resp.text}"
    )

# ============================================================================
# TEST 3: ENCRYPTED DMs - Inner Circle + DM Exchange
# ============================================================================
print("\nTEST 3: ENCRYPTED DMs - Inner Circle + DM Exchange")
print("-" * 80)

# 3a: Create SmokeB user
smokeB_token, smokeB_user = create_user("SmokeB")
if smokeB_token and smokeB_user:
    all_passed &= print_test(
        "POST /api/dev/token {name:'SmokeB'} -> access_token",
        True,
        f"Handle: {smokeB_user['handle']}"
    )
else:
    all_passed &= print_test("POST /api/dev/token {name:'SmokeB'}", False, "Failed to create user")
    sys.exit(1)

# 3b: SmokeA invites SmokeB to inner circle
invite_resp = requests.post(
    f"{BASE_URL}/inner/invite/{smokeB_user['handle']}",
    headers=headers(smokeA_token)
)
all_passed &= print_test(
    f"SmokeA POST /api/inner/invite/{smokeB_user['handle']} -> 200",
    invite_resp.status_code == 200,
    f"Status: {invite_resp.status_code}"
)

# 3c: SmokeB accepts SmokeA's inner circle invite
accept_resp = requests.post(
    f"{BASE_URL}/inner/accept/{smokeA_user['handle']}",
    headers=headers(smokeB_token)
)
all_passed &= print_test(
    f"SmokeB POST /api/inner/accept/{smokeA_user['handle']} -> 200",
    accept_resp.status_code == 200,
    f"Status: {accept_resp.status_code}"
)

# 3d: SmokeA sends DM "smoke ok" to SmokeB
dm_send_resp = requests.post(
    f"{BASE_URL}/dms/{smokeB_user['handle']}",
    headers=headers(smokeA_token),
    json={"text": "smoke ok"}
)
all_passed &= print_test(
    f"SmokeA POST /api/dms/{smokeB_user['handle']} {{text:'smoke ok'}} -> 200",
    dm_send_resp.status_code == 200,
    f"Status: {dm_send_resp.status_code}"
)

# 3e: SmokeB retrieves DMs from SmokeA - should see decrypted "smoke ok" + can_dm true
dm_get_resp = requests.get(
    f"{BASE_URL}/dms/{smokeA_user['handle']}",
    headers=headers(smokeB_token)
)
if dm_get_resp.status_code == 200:
    dm_data = dm_get_resp.json()
    can_dm = dm_data.get('can_dm', False)
    messages = dm_data.get('messages', [])
    
    # Check for decrypted "smoke ok" message
    found_smoke_ok = False
    for msg in messages:
        if msg.get('text') == 'smoke ok':
            found_smoke_ok = True
            break
    
    all_passed &= print_test(
        f"SmokeB GET /api/dms/{smokeA_user['handle']} -> 200",
        True,
        f"Status: {dm_get_resp.status_code}, can_dm: {can_dm}, Message count: {len(messages)}"
    )
    
    all_passed &= print_test(
        "DM shows decrypted 'smoke ok'",
        found_smoke_ok,
        f"Found 'smoke ok': {found_smoke_ok}"
    )
    
    all_passed &= print_test(
        "can_dm is true",
        can_dm,
        f"can_dm: {can_dm}"
    )
else:
    all_passed &= print_test(
        f"SmokeB GET /api/dms/{smokeA_user['handle']} -> 200",
        False,
        f"Status: {dm_get_resp.status_code}, Response: {dm_get_resp.text}"
    )

# ============================================================================
# TEST 4: ADMIN GATING
# ============================================================================
print("\nTEST 4: ADMIN GATING")
print("-" * 80)

# 4a: Create Admin user (email will be admin@sandbox.clanchat)
admin_token, admin_user = create_user("Admin")
if admin_token and admin_user:
    all_passed &= print_test(
        "POST /api/dev/token {name:'Admin'} -> access_token",
        True,
        f"Handle: {admin_user['handle']}"
    )
else:
    all_passed &= print_test("POST /api/dev/token {name:'Admin'}", False, "Failed to create admin user")
    sys.exit(1)

# 4b: Verify Admin has is_admin=true
admin_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(admin_token))
if admin_me_resp.status_code == 200:
    admin_me_data = admin_me_resp.json()
    is_admin = admin_me_data.get('is_admin', False)
    all_passed &= print_test(
        "Admin user has is_admin=true",
        is_admin,
        f"is_admin: {is_admin}"
    )
else:
    all_passed &= print_test(
        "Admin user verification",
        False,
        f"GET /me failed: {admin_me_resp.status_code}"
    )

# 4c: Regular user (SmokeA) GET /api/admin/stats -> 403
regular_admin_resp = requests.get(f"{BASE_URL}/admin/stats", headers=headers(smokeA_token))
all_passed &= print_test(
    "Regular user GET /api/admin/stats -> 403",
    regular_admin_resp.status_code == 403,
    f"Status: {regular_admin_resp.status_code}"
)

# 4d: No token GET /api/admin/stats -> 401
notoken_admin_resp = requests.get(f"{BASE_URL}/admin/stats")
all_passed &= print_test(
    "No token GET /api/admin/stats -> 401",
    notoken_admin_resp.status_code == 401,
    f"Status: {notoken_admin_resp.status_code}"
)

# 4e: Admin user GET /api/admin/stats -> 200
admin_stats_resp = requests.get(f"{BASE_URL}/admin/stats", headers=headers(admin_token))
if admin_stats_resp.status_code == 200:
    stats_data = admin_stats_resp.json()
    all_passed &= print_test(
        "Admin user GET /api/admin/stats -> 200",
        True,
        f"Status: {admin_stats_resp.status_code}, Stats: {stats_data}"
    )
else:
    all_passed &= print_test(
        "Admin user GET /api/admin/stats -> 200",
        False,
        f"Status: {admin_stats_resp.status_code}, Response: {admin_stats_resp.text}"
    )

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "="*80)
if all_passed:
    print("✅ SMOKE REGRESSION TEST PASSED - NO REGRESSIONS DETECTED")
    print("All core backend functionality working correctly:")
    print("  • Auth (dev/token + /api/me with 401 validation)")
    print("  • Feed (general scope with seeded posts)")
    print("  • Encrypted DMs (inner circle + decryption)")
    print("  • Admin gating (403/401/200 enforcement)")
else:
    print("❌ SMOKE REGRESSION TEST FAILED - REGRESSIONS DETECTED")
    print("One or more tests failed. See details above.")
print("="*80 + "\n")

sys.exit(0 if all_passed else 1)
