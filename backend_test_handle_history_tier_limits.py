#!/usr/bin/env python3
"""
Backend test for Handle history resolution + Account tier limits enforcement.
Tests TWO features:
(A) HANDLE HISTORY: change_handle records OLD handle in db.handle_history, 
    resolve_profile(handle) finds by current handle or falls back to handle_history
(B) TIER LIMITS: TIER_LIMITS map with pinned/bio/links/upload caps per tier (free/premium/verified)
"""
import requests
import random
import string
import sys

# Backend URL
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

# Super admin credentials
SUPER_ADMIN_EMAIL = "admin@clanchat.app"
SUPER_ADMIN_PASSWORD = "ClanChatAdmin!2025"

def rand_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def register_adult(email, password):
    """Register an adult user (DOB 1990-01-01)"""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        'email': email,
        'password': password,
        'dob': '1990-01-01'
    })
    return resp

def login(email, password):
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        'email': email,
        'password': password
    })
    if resp.status_code == 200:
        return resp.json().get('access_token')
    return None

def get_me(token):
    """GET /api/me"""
    resp = requests.get(f"{BASE_URL}/me", headers={'Authorization': f'Bearer {token}'})
    return resp

def get_user_profile(handle, token):
    """GET /api/users/{handle}"""
    resp = requests.get(f"{BASE_URL}/users/{handle}", headers={'Authorization': f'Bearer {token}'})
    return resp

def get_user_posts(handle, token):
    """GET /api/users/{handle}/posts"""
    resp = requests.get(f"{BASE_URL}/users/{handle}/posts", headers={'Authorization': f'Bearer {token}'})
    return resp

def change_handle(new_handle, token):
    """POST /api/profile/handle"""
    resp = requests.post(f"{BASE_URL}/profile/handle", 
                        json={'handle': new_handle},
                        headers={'Authorization': f'Bearer {token}'})
    return resp

def update_profile(token, **kwargs):
    """PUT /api/profile"""
    resp = requests.put(f"{BASE_URL}/profile", 
                       json=kwargs,
                       headers={'Authorization': f'Bearer {token}'})
    return resp

def admin_set_account_type(handle, account_type, admin_token):
    """POST /api/admin/users/{handle}/account-type"""
    resp = requests.post(f"{BASE_URL}/admin/users/{handle}/account-type",
                        json={'account_type': account_type},
                        headers={'Authorization': f'Bearer {admin_token}'})
    return resp

def create_post(token, tier='public', text='test post'):
    """POST /api/posts"""
    resp = requests.post(f"{BASE_URL}/posts",
                        json={'tier': tier, 'text': text},
                        headers={'Authorization': f'Bearer {token}'})
    return resp

def pin_post(post_id, token):
    """POST /api/posts/{id}/pin"""
    resp = requests.post(f"{BASE_URL}/posts/{post_id}/pin",
                        headers={'Authorization': f'Bearer {token}'})
    return resp

def main():
    print("=" * 80)
    print("BACKEND TEST: Handle history resolution + Account tier limits enforcement")
    print("=" * 80)
    
    # Login super admin
    print("\n[SETUP] Logging in super admin...")
    super_token = login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    if not super_token:
        print("❌ FAILED: Could not login super admin")
        return False
    print(f"✅ Super admin logged in (token: {super_token[:20]}...)")
    
    # Get super admin handle
    super_me = get_me(super_token)
    if super_me.status_code != 200:
        print(f"❌ FAILED: Could not get super admin profile: {super_me.status_code}")
        return False
    super_handle = super_me.json().get('handle')
    print(f"✅ Super admin handle: {super_handle}")
    
    # ========================================================================
    # PART A: HANDLE HISTORY RESOLUTION
    # ========================================================================
    print("\n" + "=" * 80)
    print("PART A: HANDLE HISTORY RESOLUTION")
    print("=" * 80)
    
    # Register adult A
    print("\n[TEST A.1] Register adult A...")
    email_a = f"handletest_a_{rand_suffix()}@example.com"
    password_a = "Test1234!"
    resp_a = register_adult(email_a, password_a)
    if resp_a.status_code != 200:
        print(f"❌ FAILED: Could not register user A: {resp_a.status_code} {resp_a.text}")
        return False
    print(f"✅ User A registered: {email_a}")
    
    # Login A and get original handle
    token_a = login(email_a, password_a)
    if not token_a:
        print("❌ FAILED: Could not login user A")
        return False
    
    me_a = get_me(token_a)
    if me_a.status_code != 200:
        print(f"❌ FAILED: Could not get user A profile: {me_a.status_code}")
        return False
    
    original_handle = me_a.json().get('handle')
    print(f"✅ User A ORIGINAL handle captured: {original_handle}")
    
    # A changes handle to H1
    print("\n[TEST A.2] A changes handle to H1...")
    new_handle_h1 = f"newalpha{rand_suffix()}"
    resp_change = change_handle(new_handle_h1, token_a)
    if resp_change.status_code != 200:
        print(f"❌ FAILED: Could not change handle: {resp_change.status_code} {resp_change.text}")
        return False
    print(f"✅ A changed handle to: {new_handle_h1}")
    
    # Verify GET /api/me shows new handle
    me_a_after = get_me(token_a)
    if me_a_after.status_code != 200:
        print(f"❌ FAILED: Could not get user A profile after change: {me_a_after.status_code}")
        return False
    current_handle = me_a_after.json().get('handle')
    if current_handle != new_handle_h1:
        print(f"❌ FAILED: Handle not updated in profile. Expected {new_handle_h1}, got {current_handle}")
        return False
    print(f"✅ GET /api/me shows updated handle: {current_handle}")
    
    # TEST: GET /api/users/{ORIGINAL_handle} should resolve to H1
    print(f"\n[TEST A.3] GET /api/users/{original_handle} (OLD handle) should resolve to H1...")
    resp_old = get_user_profile(original_handle, token_a)
    if resp_old.status_code != 200:
        print(f"❌ FAILED: GET /api/users/{original_handle} returned {resp_old.status_code}")
        print(f"   Expected: 200 (should resolve via handle_history)")
        print(f"   Response: {resp_old.text}")
        return False
    
    resolved_handle = resp_old.json().get('handle')
    if resolved_handle != new_handle_h1:
        print(f"❌ FAILED: OLD handle did not resolve to new handle")
        print(f"   Expected handle: {new_handle_h1}")
        print(f"   Got handle: {resolved_handle}")
        return False
    print(f"✅ GET /api/users/{original_handle} → 200 AND resolved to handle={new_handle_h1}")
    
    # TEST: GET /api/users/{H1} should also work
    print(f"\n[TEST A.4] GET /api/users/{new_handle_h1} (NEW handle) should work...")
    resp_new = get_user_profile(new_handle_h1, token_a)
    if resp_new.status_code != 200:
        print(f"❌ FAILED: GET /api/users/{new_handle_h1} returned {resp_new.status_code}")
        return False
    print(f"✅ GET /api/users/{new_handle_h1} → 200")
    
    # TEST: GET /api/users/{ORIGINAL_handle}/posts should work
    print(f"\n[TEST A.5] GET /api/users/{original_handle}/posts (OLD handle) should work...")
    resp_posts_old = get_user_posts(original_handle, token_a)
    if resp_posts_old.status_code != 200:
        print(f"❌ FAILED: GET /api/users/{original_handle}/posts returned {resp_posts_old.status_code}")
        print(f"   Expected: 200 (should resolve via handle_history)")
        return False
    print(f"✅ GET /api/users/{original_handle}/posts → 200")
    
    # TEST: GET /api/users/{random-nonexistent} should 404
    print(f"\n[TEST A.6] GET /api/users/{{random-nonexistent}} should 404...")
    random_handle = f"totally-random-xyz{rand_suffix()}"
    resp_404 = get_user_profile(random_handle, token_a)
    if resp_404.status_code != 404:
        print(f"❌ FAILED: GET /api/users/{random_handle} returned {resp_404.status_code}, expected 404")
        return False
    print(f"✅ GET /api/users/{random_handle} → 404")
    
    print("\n" + "=" * 80)
    print("✅ PART A: ALL HANDLE HISTORY TESTS PASSED (6/6)")
    print("=" * 80)
    
    # ========================================================================
    # PART B: ACCOUNT TIER LIMITS ENFORCEMENT
    # ========================================================================
    print("\n" + "=" * 80)
    print("PART B: ACCOUNT TIER LIMITS ENFORCEMENT")
    print("=" * 80)
    
    # Register adult C (free by default)
    print("\n[TEST B.1] Register adult C (free tier by default)...")
    email_c = f"tiertest_c_{rand_suffix()}@example.com"
    password_c = "Test1234!"
    resp_c = register_adult(email_c, password_c)
    if resp_c.status_code != 200:
        print(f"❌ FAILED: Could not register user C: {resp_c.status_code} {resp_c.text}")
        return False
    print(f"✅ User C registered: {email_c}")
    
    token_c = login(email_c, password_c)
    if not token_c:
        print("❌ FAILED: Could not login user C")
        return False
    
    me_c = get_me(token_c)
    if me_c.status_code != 200:
        print(f"❌ FAILED: Could not get user C profile: {me_c.status_code}")
        return False
    
    handle_c = me_c.json().get('handle')
    account_type_c = me_c.json().get('account_type', 'free')
    print(f"✅ User C handle: {handle_c}, account_type: {account_type_c}")
    
    # TEST B.1: C PUT /api/profile {bio: 200-char string} → 400 (free bio max 150)
    print("\n[TEST B.2] C PUT /api/profile with 200-char bio (free max 150) → 400...")
    bio_200 = "x" * 200
    resp_bio_200 = update_profile(token_c, bio=bio_200)
    if resp_bio_200.status_code != 400:
        print(f"❌ FAILED: Expected 400, got {resp_bio_200.status_code}")
        print(f"   Response: {resp_bio_200.text}")
        return False
    if 'bio' not in resp_bio_200.text.lower() or '150' not in resp_bio_200.text:
        print(f"❌ FAILED: Error message doesn't mention bio limit")
        print(f"   Response: {resp_bio_200.text}")
        return False
    print(f"✅ C PUT /api/profile {{bio: 200-char}} → 400 (bio limit enforced)")
    
    # TEST B.2: C PUT /api/profile {bio: 140-char string} → 200
    print("\n[TEST B.3] C PUT /api/profile with 140-char bio (within free limit) → 200...")
    bio_140 = "x" * 140
    resp_bio_140 = update_profile(token_c, bio=bio_140)
    if resp_bio_140.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp_bio_140.status_code}")
        print(f"   Response: {resp_bio_140.text}")
        return False
    print(f"✅ C PUT /api/profile {{bio: 140-char}} → 200")
    
    # TEST B.3: C PUT /api/profile {links: [4 urls]} → 400 (free max 3)
    print("\n[TEST B.4] C PUT /api/profile with 4 links (free max 3) → 400...")
    links_4 = [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
        "https://example.com/4"
    ]
    resp_links_4 = update_profile(token_c, links=links_4)
    if resp_links_4.status_code != 400:
        print(f"❌ FAILED: Expected 400, got {resp_links_4.status_code}")
        print(f"   Response: {resp_links_4.text}")
        return False
    if 'link' not in resp_links_4.text.lower() or '3' not in resp_links_4.text:
        print(f"❌ FAILED: Error message doesn't mention link limit")
        print(f"   Response: {resp_links_4.text}")
        return False
    print(f"✅ C PUT /api/profile {{links: 4 urls}} → 400 (link limit enforced)")
    
    # TEST B.4: C PUT /api/profile {links: [3 urls]} → 200
    print("\n[TEST B.5] C PUT /api/profile with 3 links (within free limit) → 200...")
    links_3 = [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3"
    ]
    resp_links_3 = update_profile(token_c, links=links_3)
    if resp_links_3.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp_links_3.status_code}")
        print(f"   Response: {resp_links_3.text}")
        return False
    print(f"✅ C PUT /api/profile {{links: 3 urls}} → 200")
    
    # TEST B.5: Super admin upgrades C to premium
    print("\n[TEST B.6] Super admin upgrades C to premium...")
    resp_upgrade = admin_set_account_type(handle_c, 'premium', super_token)
    if resp_upgrade.status_code != 200:
        print(f"❌ FAILED: Could not upgrade C to premium: {resp_upgrade.status_code}")
        print(f"   Response: {resp_upgrade.text}")
        return False
    print(f"✅ Super admin upgraded C to premium")
    
    # Verify C is now premium
    me_c_premium = get_me(token_c)
    if me_c_premium.status_code != 200:
        print(f"❌ FAILED: Could not get user C profile after upgrade: {me_c_premium.status_code}")
        return False
    account_type_c_premium = me_c_premium.json().get('account_type')
    if account_type_c_premium != 'premium':
        print(f"❌ FAILED: C account_type not updated. Expected 'premium', got '{account_type_c_premium}'")
        return False
    print(f"✅ C account_type verified: {account_type_c_premium}")
    
    # TEST B.5a: C PUT /api/profile {bio: 250-char} → 200 (premium max 300)
    print("\n[TEST B.7] C PUT /api/profile with 250-char bio (premium max 300) → 200...")
    bio_250 = "x" * 250
    resp_bio_250 = update_profile(token_c, bio=bio_250)
    if resp_bio_250.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp_bio_250.status_code}")
        print(f"   Response: {resp_bio_250.text}")
        return False
    print(f"✅ C PUT /api/profile {{bio: 250-char}} → 200 (premium limit)")
    
    # TEST B.5b: C PUT /api/profile {links: [8 urls]} → 200 (premium max 8)
    print("\n[TEST B.8] C PUT /api/profile with 8 links (premium max 8) → 200...")
    links_8 = [f"https://example.com/{i}" for i in range(1, 9)]
    resp_links_8 = update_profile(token_c, links=links_8)
    if resp_links_8.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp_links_8.status_code}")
        print(f"   Response: {resp_links_8.text}")
        return False
    print(f"✅ C PUT /api/profile {{links: 8 urls}} → 200 (premium limit)")
    
    # TEST B.6: PINNED POSTS - C creates 7 public posts, pins 6 → all 200, pin 7th → 400
    print("\n[TEST B.9] C creates 7 public posts...")
    post_ids = []
    for i in range(1, 8):
        resp_post = create_post(token_c, tier='public', text=f'post {i}')
        if resp_post.status_code != 200:
            print(f"❌ FAILED: Could not create post {i}: {resp_post.status_code}")
            return False
        post_id = resp_post.json().get('id')
        post_ids.append(post_id)
        print(f"   Created post {i}: {post_id}")
    print(f"✅ C created 7 public posts")
    
    print("\n[TEST B.10] C pins first 6 posts (premium max 6)...")
    for i in range(6):
        resp_pin = pin_post(post_ids[i], token_c)
        if resp_pin.status_code != 200:
            print(f"❌ FAILED: Could not pin post {i+1}: {resp_pin.status_code}")
            print(f"   Response: {resp_pin.text}")
            return False
        print(f"   Pinned post {i+1}: {post_ids[i]}")
    print(f"✅ C pinned 6 posts successfully")
    
    print("\n[TEST B.11] C tries to pin 7th post (should fail, premium max 6)...")
    resp_pin_7 = pin_post(post_ids[6], token_c)
    if resp_pin_7.status_code != 400:
        print(f"❌ FAILED: Expected 400, got {resp_pin_7.status_code}")
        print(f"   Response: {resp_pin_7.text}")
        return False
    if '6' not in resp_pin_7.text or 'pin' not in resp_pin_7.text.lower():
        print(f"❌ FAILED: Error message doesn't mention pin limit")
        print(f"   Response: {resp_pin_7.text}")
        return False
    print(f"✅ C pin 7th post → 400 (premium max 6 pins enforced)")
    
    # TEST B.7: GET /api/me as C → response contains 'limits' object
    print("\n[TEST B.12] GET /api/me as C → verify 'limits' object...")
    me_c_limits = get_me(token_c)
    if me_c_limits.status_code != 200:
        print(f"❌ FAILED: Could not get user C profile: {me_c_limits.status_code}")
        return False
    
    limits = me_c_limits.json().get('limits')
    if not limits:
        print(f"❌ FAILED: 'limits' object not found in /api/me response")
        print(f"   Response keys: {list(me_c_limits.json().keys())}")
        return False
    
    # Verify limits match premium tier
    expected_limits = {
        'pinned': 6,
        'bio': 300,
        'links': 8
    }
    
    for key, expected_value in expected_limits.items():
        actual_value = limits.get(key)
        if actual_value != expected_value:
            print(f"❌ FAILED: limits.{key} = {actual_value}, expected {expected_value}")
            return False
        print(f"   limits.{key} = {actual_value} ✓")
    
    print(f"✅ GET /api/me contains 'limits' object with correct premium values:")
    print(f"   pinned={limits.get('pinned')}, bio={limits.get('bio')}, links={limits.get('links')}")
    
    print("\n" + "=" * 80)
    print("✅ PART B: ALL ACCOUNT TIER LIMITS TESTS PASSED (12/12)")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("✅✅✅ ALL TESTS PASSED (18/18) ✅✅✅")
    print("=" * 80)
    print("\nSUMMARY:")
    print("  PART A - HANDLE HISTORY RESOLUTION: 6/6 tests passed")
    print("    ✅ Register adult A, capture original handle")
    print("    ✅ A changes handle to H1")
    print("    ✅ GET /api/users/{ORIGINAL_handle} resolves to H1 via handle_history")
    print("    ✅ GET /api/users/{H1} works")
    print("    ✅ GET /api/users/{ORIGINAL_handle}/posts works")
    print("    ✅ GET /api/users/{random-nonexistent} returns 404")
    print("\n  PART B - ACCOUNT TIER LIMITS: 12/12 tests passed")
    print("    ✅ C (free) bio 200-char → 400 (max 150)")
    print("    ✅ C (free) bio 140-char → 200")
    print("    ✅ C (free) 4 links → 400 (max 3)")
    print("    ✅ C (free) 3 links → 200")
    print("    ✅ Super admin upgrades C to premium")
    print("    ✅ C (premium) bio 250-char → 200 (max 300)")
    print("    ✅ C (premium) 8 links → 200 (max 8)")
    print("    ✅ C creates 7 public posts")
    print("    ✅ C pins 6 posts → all 200")
    print("    ✅ C pins 7th post → 400 (premium max 6)")
    print("    ✅ GET /api/me exposes 'limits' object")
    print("    ✅ limits.pinned=6, bio=300, links=8 (premium values)")
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
