#!/usr/bin/env python3
"""
Board Tier Access Control Fix Test
Re-test ONLY the board tier access-control fix (missing await is_admin_user_id bug).
"""
import requests
import sys
from datetime import datetime
import uuid

# External URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def register_user(email, password, name, dob="1990-01-01"):
    """Register a new user with adult DOB"""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "dob": dob
    }, timeout=30)
    if resp.status_code != 200:
        log(f"❌ Register failed: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    token = data.get('access_token')
    
    # Get handle
    me_resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if me_resp.status_code != 200:
        log(f"❌ Get /me failed: {me_resp.status_code}")
        return None, None
    handle = me_resp.json().get('handle')
    log(f"✅ Registered {handle} ({email})")
    return token, handle

def login_admin():
    """Login as seeded admin"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@clanchat.app",
        "password": "ClanChatAdmin!2025"
    }, timeout=30)
    if resp.status_code != 200:
        log(f"❌ Admin login failed: {resp.status_code}")
        return None
    token = resp.json().get('access_token')
    log(f"✅ Admin logged in")
    return token

def follow_user(follower_token, target_handle):
    """Follow a user (open mode auto-approve)"""
    resp = requests.post(f"{BASE_URL}/follow/{target_handle}", 
                        headers={"Authorization": f"Bearer {follower_token}"}, 
                        timeout=30)
    if resp.status_code != 200:
        log(f"❌ Follow failed: {resp.status_code} {resp.text}")
        return False
    log(f"✅ Followed {target_handle}")
    return True

def create_board(owner_token, title, tier):
    """Create a board with specified tier"""
    resp = requests.post(f"{BASE_URL}/boards", 
                        headers={"Authorization": f"Bearer {owner_token}"},
                        json={"title": title, "tier": tier},
                        timeout=30)
    if resp.status_code != 200:
        log(f"❌ Create board failed: {resp.status_code} {resp.text}")
        return None
    board_id = resp.json().get('id')
    log(f"✅ Created {tier} board '{title}' (id={board_id})")
    return board_id

def get_board(token, board_id, expect_status=200):
    """Get a board and check expected status"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{BASE_URL}/board/{board_id}", 
                       headers=headers,
                       timeout=30)
    return resp

def main():
    log("=" * 80)
    log("BOARD TIER ACCESS CONTROL FIX TEST")
    log("Testing the await is_admin_user_id fix in can_read_board()")
    log("=" * 80)
    
    # Generate unique emails
    rand = str(uuid.uuid4())[:8]
    owner_email = f"boardowner+{rand}@example.com"
    follower_email = f"boardfollower+{rand}@example.com"
    stranger_email = f"boardstranger+{rand}@example.com"
    
    # Register users (all adults with DOB 1990-01-01)
    log("\n[SETUP] Registering users...")
    owner_token, owner_handle = register_user(owner_email, "secret123", "Board Owner", "1990-01-01")
    follower_token, follower_handle = register_user(follower_email, "secret123", "Board Follower", "1990-01-01")
    stranger_token, stranger_handle = register_user(stranger_email, "secret123", "Board Stranger", "1990-01-01")
    
    if not all([owner_token, follower_token, stranger_token]):
        log("❌ SETUP FAILED: Could not register users")
        sys.exit(1)
    
    # Make FOLLOWER an approved follower of OWNER
    log(f"\n[SETUP] Making {follower_handle} follow {owner_handle}...")
    if not follow_user(follower_token, owner_handle):
        log("❌ SETUP FAILED: Could not create follower relationship")
        sys.exit(1)
    
    # Login admin
    log("\n[SETUP] Logging in admin...")
    admin_token = login_admin()
    if not admin_token:
        log("❌ SETUP FAILED: Could not login admin")
        sys.exit(1)
    
    log("\n" + "=" * 80)
    log("TEST 1: FOLLOWERS-TIER BOARD ACCESS")
    log("=" * 80)
    
    # OWNER creates FOLLOWERS-tier board
    followers_board_id = create_board(owner_token, "Fans", "followers")
    if not followers_board_id:
        log("❌ TEST 1 FAILED: Could not create followers board")
        sys.exit(1)
    
    # Test 1a: STRANGER should get 403
    log("\n[TEST 1a] STRANGER GET followers board → expect 403")
    resp = get_board(stranger_token, followers_board_id)
    if resp.status_code == 403:
        log(f"✅ PASS: STRANGER got 403 (correctly blocked)")
    else:
        log(f"❌ FAIL: STRANGER got {resp.status_code} (expected 403)")
        log(f"   Response: {resp.text}")
    
    # Test 1b: FOLLOWER should get 200
    log("\n[TEST 1b] FOLLOWER GET followers board → expect 200")
    resp = get_board(follower_token, followers_board_id)
    if resp.status_code == 200:
        log(f"✅ PASS: FOLLOWER got 200 (correctly allowed)")
    else:
        log(f"❌ FAIL: FOLLOWER got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    # Test 1c: OWNER should get 200
    log("\n[TEST 1c] OWNER GET followers board → expect 200")
    resp = get_board(owner_token, followers_board_id)
    if resp.status_code == 200:
        log(f"✅ PASS: OWNER got 200 (correctly allowed)")
    else:
        log(f"❌ FAIL: OWNER got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    log("\n" + "=" * 80)
    log("TEST 2: INNER-TIER BOARD ACCESS")
    log("=" * 80)
    
    # OWNER creates INNER-tier board
    inner_board_id = create_board(owner_token, "Inner", "inner")
    if not inner_board_id:
        log("❌ TEST 2 FAILED: Could not create inner board")
        sys.exit(1)
    
    # Test 2a: FOLLOWER (not in inner) should get 403
    log("\n[TEST 2a] FOLLOWER (not in inner) GET inner board → expect 403")
    resp = get_board(follower_token, inner_board_id)
    if resp.status_code == 403:
        log(f"✅ PASS: FOLLOWER got 403 (correctly blocked, not in inner)")
    else:
        log(f"❌ FAIL: FOLLOWER got {resp.status_code} (expected 403)")
        log(f"   Response: {resp.text}")
    
    # Test 2b: STRANGER should get 403
    log("\n[TEST 2b] STRANGER GET inner board → expect 403")
    resp = get_board(stranger_token, inner_board_id)
    if resp.status_code == 403:
        log(f"✅ PASS: STRANGER got 403 (correctly blocked)")
    else:
        log(f"❌ FAIL: STRANGER got {resp.status_code} (expected 403)")
        log(f"   Response: {resp.text}")
    
    # Test 2c: OWNER should get 200
    log("\n[TEST 2c] OWNER GET inner board → expect 200")
    resp = get_board(owner_token, inner_board_id)
    if resp.status_code == 200:
        log(f"✅ PASS: OWNER got 200 (correctly allowed)")
    else:
        log(f"❌ FAIL: OWNER got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    log("\n" + "=" * 80)
    log("TEST 3: PUBLIC BOARD SANITY CHECK")
    log("=" * 80)
    
    # OWNER creates PUBLIC board
    public_board_id = create_board(owner_token, "Open", "public")
    if not public_board_id:
        log("❌ TEST 3 FAILED: Could not create public board")
        sys.exit(1)
    
    # Test 3a: STRANGER should get 200 with can_post=false
    log("\n[TEST 3a] STRANGER GET public board → expect 200 with can_post=false")
    resp = get_board(stranger_token, public_board_id)
    if resp.status_code == 200:
        data = resp.json()
        can_post = data.get('can_post', None)
        if can_post == False:
            log(f"✅ PASS: STRANGER got 200 with can_post=false")
        else:
            log(f"❌ FAIL: STRANGER got 200 but can_post={can_post} (expected false)")
    else:
        log(f"❌ FAIL: STRANGER got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    # Test 3b: FOLLOWER should get 200 with can_post=true
    log("\n[TEST 3b] FOLLOWER GET public board → expect 200 with can_post=true")
    resp = get_board(follower_token, public_board_id)
    if resp.status_code == 200:
        data = resp.json()
        can_post = data.get('can_post', None)
        if can_post == True:
            log(f"✅ PASS: FOLLOWER got 200 with can_post=true")
        else:
            log(f"❌ FAIL: FOLLOWER got 200 but can_post={can_post} (expected true)")
    else:
        log(f"❌ FAIL: FOLLOWER got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    log("\n" + "=" * 80)
    log("TEST 4: ADMIN ACCESS (admin override)")
    log("=" * 80)
    
    # Test 4a: Admin should get 200 on followers board
    log("\n[TEST 4a] ADMIN GET followers board → expect 200 (admin override)")
    resp = get_board(admin_token, followers_board_id)
    if resp.status_code == 200:
        log(f"✅ PASS: ADMIN got 200 on followers board (admin override works)")
    else:
        log(f"❌ FAIL: ADMIN got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    # Test 4b: Admin should get 200 on inner board
    log("\n[TEST 4b] ADMIN GET inner board → expect 200 (admin override)")
    resp = get_board(admin_token, inner_board_id)
    if resp.status_code == 200:
        log(f"✅ PASS: ADMIN got 200 on inner board (admin override works)")
    else:
        log(f"❌ FAIL: ADMIN got {resp.status_code} (expected 200)")
        log(f"   Response: {resp.text}")
    
    log("\n" + "=" * 80)
    log("BOARD TIER ACCESS CONTROL FIX TEST COMPLETE")
    log("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
