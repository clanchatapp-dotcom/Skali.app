#!/usr/bin/env python3
"""
Backend test for Change Password feature
Tests the NEW POST /api/auth/change-password endpoint + has_password flag on /api/me
"""
import requests
import json
import sys
import secrets

# Base URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    if not passed:
        print(f"\n❌ TEST FAILED: {name}")
        sys.exit(1)

def headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

print("\n" + "="*80)
print("CHANGE PASSWORD FEATURE TESTS")
print("="*80 + "\n")

# ============================================================================
# TEST 1: Register throwaway user with unique email
# ============================================================================
print("TEST 1: Register throwaway user with unique email cp+<rand>@example.com")
print("-" * 80)

# Generate unique random email
user_suffix = secrets.token_hex(4)
user_email = f"cp+{user_suffix}@example.com"
user_password = "secret123"

# Register user
register_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": user_email, "password": user_password, "name": "Change Password Test"}
)
print_test(
    f"POST /api/auth/register {{email:'{user_email}', password:'secret123'}} → 200",
    register_resp.status_code == 200,
    f"Status: {register_resp.status_code}"
)

register_data = register_resp.json()
user_token = register_data.get('access_token')
user_handle = register_data.get('user', {}).get('handle')
print(f"  → Registered user: {user_handle} (email: {user_email})")
print(f"  → Token captured: {user_token[:50]}...")

# ============================================================================
# TEST 2: GET /api/me -> 200 and has_password=true (email/password account)
# ============================================================================
print("\nTEST 2: GET /api/me -> 200 and has_password=true (email/password account)")
print("-" * 80)

me_resp = requests.get(f"{BASE_URL}/me", headers=headers(user_token))
print_test(
    "GET /api/me → 200",
    me_resp.status_code == 200,
    f"Status: {me_resp.status_code}"
)

me_data = me_resp.json()
print_test(
    "has_password=true (email/password account)",
    me_data.get('has_password') == True,
    f"has_password: {me_data.get('has_password')}"
)

# ============================================================================
# TEST 3: POST /api/auth/change-password with NO auth token -> 401
# ============================================================================
print("\nTEST 3: POST /api/auth/change-password with NO auth token -> 401")
print("-" * 80)

change_pw_no_auth_resp = requests.post(
    f"{BASE_URL}/auth/change-password",
    json={"current_password": "secret123", "new_password": "newsecret1"}
)
print_test(
    "POST /api/auth/change-password without auth token → 401",
    change_pw_no_auth_resp.status_code == 401,
    f"Status: {change_pw_no_auth_resp.status_code}"
)

# ============================================================================
# TEST 4: POST /api/auth/change-password with wrong current password -> 400
# ============================================================================
print("\nTEST 4: POST /api/auth/change-password with wrong current password -> 400")
print("-" * 80)

change_pw_wrong_resp = requests.post(
    f"{BASE_URL}/auth/change-password",
    headers=headers(user_token),
    json={"current_password": "wrongpass", "new_password": "newsecret1"}
)
print_test(
    "POST /api/auth/change-password {{current_password:'wrongpass', new_password:'newsecret1'}} → 400",
    change_pw_wrong_resp.status_code == 400,
    f"Status: {change_pw_wrong_resp.status_code}, Message: {change_pw_wrong_resp.text}"
)

# ============================================================================
# TEST 5: POST /api/auth/change-password with new password too short (<6) -> 400
# ============================================================================
print("\nTEST 5: POST /api/auth/change-password with new password too short (<6) -> 400")
print("-" * 80)

change_pw_short_resp = requests.post(
    f"{BASE_URL}/auth/change-password",
    headers=headers(user_token),
    json={"current_password": "secret123", "new_password": "123"}
)
print_test(
    "POST /api/auth/change-password {{current_password:'secret123', new_password:'123'}} → 400",
    change_pw_short_resp.status_code == 400,
    f"Status: {change_pw_short_resp.status_code}, Message: {change_pw_short_resp.text}"
)

# ============================================================================
# TEST 6: POST /api/auth/change-password with correct credentials -> 200
# ============================================================================
print("\nTEST 6: POST /api/auth/change-password with correct credentials -> 200")
print("-" * 80)

change_pw_success_resp = requests.post(
    f"{BASE_URL}/auth/change-password",
    headers=headers(user_token),
    json={"current_password": "secret123", "new_password": "newsecret1"}
)
print_test(
    "POST /api/auth/change-password {{current_password:'secret123', new_password:'newsecret1'}} → 200",
    change_pw_success_resp.status_code == 200,
    f"Status: {change_pw_success_resp.status_code}"
)

change_pw_data = change_pw_success_resp.json()
print_test(
    "Response includes ok=true",
    change_pw_data.get('ok') == True,
    f"ok: {change_pw_data.get('ok')}"
)

# ============================================================================
# TEST 7: Verify the change took effect
# ============================================================================
print("\nTEST 7: Verify the change took effect")
print("-" * 80)

# 7a: Try to login with OLD password -> should fail (401)
print("  7a: Login with OLD password 'secret123' -> should fail (401)")
login_old_pw_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": user_email, "password": "secret123"}
)
print_test(
    "POST /api/auth/login {{email, password:'secret123'}} → 401 (old password no longer works)",
    login_old_pw_resp.status_code == 401,
    f"Status: {login_old_pw_resp.status_code}"
)

# 7b: Try to login with NEW password -> should succeed (200)
print("\n  7b: Login with NEW password 'newsecret1' -> should succeed (200)")
login_new_pw_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": user_email, "password": "newsecret1"}
)
print_test(
    "POST /api/auth/login {{email, password:'newsecret1'}} → 200 (new password works)",
    login_new_pw_resp.status_code == 200,
    f"Status: {login_new_pw_resp.status_code}"
)

login_new_pw_data = login_new_pw_resp.json()
new_token = login_new_pw_data.get('access_token')
print(f"  → New token obtained: {new_token[:50]}...")

# ============================================================================
# TEST 8: Idempotency/reuse - change password again with ORIGINAL token
# ============================================================================
print("\nTEST 8: Idempotency/reuse - change password again with ORIGINAL token")
print("-" * 80)

# The ORIGINAL token should still be valid (JWT doesn't expire immediately)
# Change password again from 'newsecret1' to 'evenNewer2'
change_pw_again_resp = requests.post(
    f"{BASE_URL}/auth/change-password",
    headers=headers(user_token),  # Using ORIGINAL token
    json={"current_password": "newsecret1", "new_password": "evenNewer2"}
)
print_test(
    "POST /api/auth/change-password {{current_password:'newsecret1', new_password:'evenNewer2'}} with ORIGINAL token → 200",
    change_pw_again_resp.status_code == 200,
    f"Status: {change_pw_again_resp.status_code}"
)

# Verify login with 'evenNewer2' works
login_even_newer_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": user_email, "password": "evenNewer2"}
)
print_test(
    "POST /api/auth/login {{email, password:'evenNewer2'}} → 200 (even newer password works)",
    login_even_newer_resp.status_code == 200,
    f"Status: {login_even_newer_resp.status_code}"
)

# ============================================================================
# TEST 9: Seeded admin - login and check has_password=true
# ============================================================================
print("\nTEST 9: Seeded admin - login and check has_password=true")
print("-" * 80)

# Login as seeded admin
admin_login_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": "admin@clanchat.app", "password": "ClanChatAdmin!2025"}
)
print_test(
    "POST /api/auth/login {{email:'admin@clanchat.app', password:'ClanChatAdmin!2025'}} → 200",
    admin_login_resp.status_code == 200,
    f"Status: {admin_login_resp.status_code}"
)

admin_login_data = admin_login_resp.json()
admin_token = admin_login_data.get('access_token')
print(f"  → Admin token obtained: {admin_token[:50]}...")

# GET /api/me as admin
admin_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(admin_token))
print_test(
    "GET /api/me (as admin) → 200",
    admin_me_resp.status_code == 200,
    f"Status: {admin_me_resp.status_code}"
)

admin_me_data = admin_me_resp.json()
print_test(
    "Admin has_password=true",
    admin_me_data.get('has_password') == True,
    f"has_password: {admin_me_data.get('has_password')}"
)

# ============================================================================
# TEST 10: REGRESSION - register + /api/me returns comfort_zone
# ============================================================================
print("\nTEST 10: REGRESSION - register + /api/me returns comfort_zone")
print("-" * 80)

# Register another user for regression test
regression_suffix = secrets.token_hex(4)
regression_email = f"regression+{regression_suffix}@example.com"
regression_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": regression_email, "password": "secret123", "name": "Regression Test"}
)
print_test(
    f"POST /api/auth/register {{email:'{regression_email}'}} → 200",
    regression_resp.status_code == 200,
    f"Status: {regression_resp.status_code}"
)

regression_data = regression_resp.json()
regression_token = regression_data.get('access_token')

# GET /api/me
regression_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(regression_token))
print_test(
    "GET /api/me → 200",
    regression_me_resp.status_code == 200,
    f"Status: {regression_me_resp.status_code}"
)

regression_me_data = regression_me_resp.json()
print_test(
    "GET /api/me returns comfort_zone",
    'comfort_zone' in regression_me_data,
    f"comfort_zone present: {'comfort_zone' in regression_me_data}"
)

comfort_zone = regression_me_data.get('comfort_zone', {})
expected_keys = {'nsfw', 'ai', 'language', 'violence', 'drugs'}
print_test(
    "comfort_zone has all 5 keys",
    set(comfort_zone.keys()) == expected_keys,
    f"Keys: {sorted(comfort_zone.keys())}"
)

# ============================================================================
# TEST 11: REGRESSION - PUT /api/profile display_name works
# ============================================================================
print("\nTEST 11: REGRESSION - PUT /api/profile display_name works")
print("-" * 80)

# Update display_name
update_name_resp = requests.put(
    f"{BASE_URL}/profile",
    headers=headers(regression_token),
    json={"display_name": "Updated Regression Name"}
)
print_test(
    "PUT /api/profile {{display_name:'Updated Regression Name'}} → 200",
    update_name_resp.status_code == 200,
    f"Status: {update_name_resp.status_code}"
)

# Verify display_name persisted
regression_me_resp2 = requests.get(f"{BASE_URL}/me", headers=headers(regression_token))
regression_me_data2 = regression_me_resp2.json()
print_test(
    "display_name persisted as 'Updated Regression Name'",
    regression_me_data2.get('display_name') == 'Updated Regression Name',
    f"display_name: {regression_me_data2.get('display_name')}"
)

print("\n" + "="*80)
print("ALL CHANGE PASSWORD TESTS PASSED ✅")
print("="*80 + "\n")
