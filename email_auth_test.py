#!/usr/bin/env python3
"""
Backend test for Email/Password Auth + HS256 Regression
Tests the NEW email/password authentication endpoints and verifies HS256 tokens still work.
"""
import requests
import json
import sys
import random
import string

# Base URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

# Generate random suffix for unique emails per run
RANDOM_SUFFIX = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    if not passed:
        sys.exit(1)

def headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

print("\n" + "="*80)
print("EMAIL/PASSWORD AUTH + HS256 REGRESSION TESTS")
print(f"Random suffix for this run: {RANDOM_SUFFIX}")
print("="*80 + "\n")

# ============================================================================
# TEST 1: REGISTER NEW USER WITH EMAIL/PASSWORD
# ============================================================================
print("TEST 1: REGISTER NEW USER")
print("-" * 80 + "\n")

email1 = f"newuser1_{RANDOM_SUFFIX}@example.com"
password1 = "secret123"
name1 = "New User"

register_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": email1, "password": password1, "name": name1}
)

print_test(
    f"POST /api/auth/register with valid data → 200",
    register_resp.status_code == 200,
    f"Status: {register_resp.status_code}, Response: {register_resp.text[:200]}"
)

if register_resp.status_code == 200:
    register_data = register_resp.json()
    
    # Verify response structure
    print_test(
        "Response contains 'access_token'",
        'access_token' in register_data,
        f"Keys: {list(register_data.keys())}"
    )
    
    print_test(
        "Response contains 'user' with id, handle, display_name, email",
        'user' in register_data and 
        'id' in register_data['user'] and
        'handle' in register_data['user'] and
        'display_name' in register_data['user'] and
        'email' in register_data['user'],
        f"User: {register_data.get('user', {})}"
    )
    
    # Save token and user for later tests
    user1_token = register_data.get('access_token')
    user1_data = register_data.get('user', {})
    user1_handle = user1_data.get('handle')
    
    print(f"  Registered user: {user1_handle} (email: {email1})")
    print(f"  Token length: {len(user1_token)} chars")
    
    # Test that token works on GET /api/me
    me_resp = requests.get(f"{BASE_URL}/me", headers=headers(user1_token))
    print_test(
        "GET /api/me with new token → 200",
        me_resp.status_code == 200,
        f"Status: {me_resp.status_code}"
    )
    
    if me_resp.status_code == 200:
        me_data = me_resp.json()
        print_test(
            "GET /api/me returns handle",
            'handle' in me_data and me_data['handle'] == user1_handle,
            f"Handle: {me_data.get('handle')}"
        )
else:
    print("❌ Registration failed, cannot continue with user1 tests")
    sys.exit(1)

# ============================================================================
# TEST 2: DUPLICATE EMAIL REGISTRATION
# ============================================================================
print("\n" + "="*80)
print("TEST 2: DUPLICATE EMAIL REGISTRATION")
print("-" * 80 + "\n")

duplicate_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": email1, "password": "different123", "name": "Another User"}
)

print_test(
    "POST /api/auth/register with duplicate email → 400",
    duplicate_resp.status_code == 400,
    f"Status: {duplicate_resp.status_code}, Response: {duplicate_resp.text}"
)

# ============================================================================
# TEST 3: SHORT PASSWORD VALIDATION
# ============================================================================
print("\n" + "="*80)
print("TEST 3: SHORT PASSWORD VALIDATION")
print("-" * 80 + "\n")

email2 = f"newuser2_{RANDOM_SUFFIX}@example.com"
short_pw_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": email2, "password": "123", "name": "Short PW User"}
)

print_test(
    "POST /api/auth/register with password '123' → 400",
    short_pw_resp.status_code == 400,
    f"Status: {short_pw_resp.status_code}, Response: {short_pw_resp.text}"
)

# ============================================================================
# TEST 4: INVALID EMAIL VALIDATION
# ============================================================================
print("\n" + "="*80)
print("TEST 4: INVALID EMAIL VALIDATION")
print("-" * 80 + "\n")

invalid_email_resp = requests.post(
    f"{BASE_URL}/auth/register",
    json={"email": "notanemail", "password": "secret123", "name": "Invalid Email User"}
)

print_test(
    "POST /api/auth/register with invalid email 'notanemail' → 400",
    invalid_email_resp.status_code == 400,
    f"Status: {invalid_email_resp.status_code}, Response: {invalid_email_resp.text}"
)

# ============================================================================
# TEST 5: LOGIN WITH CORRECT CREDENTIALS
# ============================================================================
print("\n" + "="*80)
print("TEST 5: LOGIN WITH CORRECT CREDENTIALS")
print("-" * 80 + "\n")

login_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": email1, "password": password1}
)

print_test(
    "POST /api/auth/login with correct credentials → 200",
    login_resp.status_code == 200,
    f"Status: {login_resp.status_code}, Response: {login_resp.text[:200]}"
)

if login_resp.status_code == 200:
    login_data = login_resp.json()
    
    print_test(
        "Login response contains 'access_token'",
        'access_token' in login_data,
        f"Keys: {list(login_data.keys())}"
    )
    
    login_token = login_data.get('access_token')
    print(f"  Login token length: {len(login_token)} chars")
    
    # Test that login token works on GET /api/me
    me_login_resp = requests.get(f"{BASE_URL}/me", headers=headers(login_token))
    print_test(
        "GET /api/me with login token → 200",
        me_login_resp.status_code == 200,
        f"Status: {me_login_resp.status_code}"
    )
else:
    print("❌ Login failed")
    sys.exit(1)

# ============================================================================
# TEST 6: LOGIN WITH WRONG PASSWORD
# ============================================================================
print("\n" + "="*80)
print("TEST 6: LOGIN WITH WRONG PASSWORD")
print("-" * 80 + "\n")

wrong_pw_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": email1, "password": "wrongpassword"}
)

print_test(
    "POST /api/auth/login with wrong password → 401",
    wrong_pw_resp.status_code == 401,
    f"Status: {wrong_pw_resp.status_code}, Response: {wrong_pw_resp.text}"
)

# ============================================================================
# TEST 7: LOGIN WITH UNKNOWN EMAIL
# ============================================================================
print("\n" + "="*80)
print("TEST 7: LOGIN WITH UNKNOWN EMAIL")
print("-" * 80 + "\n")

unknown_email = f"unknown_{RANDOM_SUFFIX}@example.com"
unknown_email_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": unknown_email, "password": "secret123"}
)

print_test(
    "POST /api/auth/login with unknown email → 401",
    unknown_email_resp.status_code == 401,
    f"Status: {unknown_email_resp.status_code}, Response: {unknown_email_resp.text}"
)

# ============================================================================
# TEST 8: HS256 REGRESSION - DEV TOKEN STILL WORKS
# ============================================================================
print("\n" + "="*80)
print("TEST 8: HS256 REGRESSION - DEV TOKEN STILL WORKS")
print("-" * 80 + "\n")

dev_token_resp = requests.post(
    f"{BASE_URL}/dev/token",
    json={"name": "RegChk"}
)

print_test(
    "POST /api/dev/token → 200",
    dev_token_resp.status_code == 200,
    f"Status: {dev_token_resp.status_code}, Response: {dev_token_resp.text[:200]}"
)

if dev_token_resp.status_code == 200:
    dev_data = dev_token_resp.json()
    dev_token = dev_data.get('access_token')
    dev_user = dev_data.get('user', {})
    
    print(f"  Dev user: {dev_user.get('handle')}")
    print(f"  Dev token length: {len(dev_token)} chars")
    
    # Test that dev token works on GET /api/me
    me_dev_resp = requests.get(f"{BASE_URL}/me", headers=headers(dev_token))
    print_test(
        "GET /api/me with dev token → 200 (HS256 verification working)",
        me_dev_resp.status_code == 200,
        f"Status: {me_dev_resp.status_code}"
    )
else:
    print("❌ Dev token creation failed")
    sys.exit(1)

# ============================================================================
# TEST 9: NO TOKEN → 401
# ============================================================================
print("\n" + "="*80)
print("TEST 9: NO TOKEN → 401")
print("-" * 80 + "\n")

no_token_resp = requests.get(f"{BASE_URL}/me")

print_test(
    "GET /api/me without token → 401",
    no_token_resp.status_code == 401,
    f"Status: {no_token_resp.status_code}"
)

# ============================================================================
# TEST 10: MALFORMED TOKEN → 401
# ============================================================================
print("\n" + "="*80)
print("TEST 10: MALFORMED TOKEN → 401")
print("-" * 80 + "\n")

malformed_resp = requests.get(
    f"{BASE_URL}/me",
    headers={"Authorization": "Bearer invalid.token.here"}
)

print_test(
    "GET /api/me with malformed token → 401",
    malformed_resp.status_code == 401,
    f"Status: {malformed_resp.status_code}"
)

# ============================================================================
# TEST 11: EMAIL-AUTH TOKEN CAN CREATE POSTS
# ============================================================================
print("\n" + "="*80)
print("TEST 11: EMAIL-AUTH TOKEN CAN CREATE POSTS")
print("-" * 80 + "\n")

post_text = f"hi from email user {RANDOM_SUFFIX}"
create_post_resp = requests.post(
    f"{BASE_URL}/posts",
    headers=headers(user1_token),
    json={"tier": "public", "text": post_text}
)

print_test(
    "POST /api/posts with email-auth token → 200",
    create_post_resp.status_code == 200,
    f"Status: {create_post_resp.status_code}, Response: {create_post_resp.text[:200]}"
)

if create_post_resp.status_code == 200:
    post_data = create_post_resp.json()
    post_id = post_data.get('id')
    print(f"  Created post ID: {post_id}")
    
    # ============================================================================
    # TEST 12: POST APPEARS IN FEED
    # ============================================================================
    print("\n" + "="*80)
    print("TEST 12: POST APPEARS IN FEED")
    print("-" * 80 + "\n")
    
    feed_resp = requests.get(
        f"{BASE_URL}/feed?scope=general",
        headers=headers(user1_token)
    )
    
    print_test(
        "GET /api/feed?scope=general → 200",
        feed_resp.status_code == 200,
        f"Status: {feed_resp.status_code}"
    )
    
    if feed_resp.status_code == 200:
        feed_data = feed_resp.json()
        
        # Find our post in the feed
        our_post = None
        for post in feed_data:
            if post.get('id') == post_id or post.get('text') == post_text:
                our_post = post
                break
        
        print_test(
            f"Feed contains our post '{post_text}'",
            our_post is not None,
            f"Found: {our_post is not None}, Feed has {len(feed_data)} posts"
        )
        
        if our_post:
            print_test(
                "Post has correct author handle",
                our_post.get('author', {}).get('handle') == user1_handle,
                f"Author handle: {our_post.get('author', {}).get('handle')}"
            )
else:
    print("❌ Post creation failed")
    sys.exit(1)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("ALL EMAIL/PASSWORD AUTH + HS256 REGRESSION TESTS PASSED ✅")
print("="*80)
print("\nSUMMARY:")
print("  ✅ Email/password registration working (validation + token generation)")
print("  ✅ Duplicate email detection working (400)")
print("  ✅ Password length validation working (400 for <6 chars)")
print("  ✅ Email format validation working (400 for invalid)")
print("  ✅ Email/password login working (token generation)")
print("  ✅ Login error handling working (401 for wrong password/unknown email)")
print("  ✅ HS256 regression: Dev tokens still verify correctly")
print("  ✅ HS256 regression: Email-auth tokens still verify correctly")
print("  ✅ HS256 regression: No token → 401, malformed token → 401")
print("  ✅ HS256 regression: Email-auth tokens can create posts")
print("  ✅ HS256 regression: Posts appear in feed correctly")
print("\n" + "="*80 + "\n")
