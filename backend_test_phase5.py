#!/usr/bin/env python3
"""
Phase 5 Backend Testing: Display prefs + notif_prefs, Block/Mute/Restrict, Connections manager
Tests all scenarios from the review request using external URL with /api prefix.
"""

import requests
import uuid
import time
from typing import Dict, Optional

# External URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def random_email():
    """Generate unique random email for testing"""
    return f"phase5test+{uuid.uuid4().hex[:8]}@example.com"

def register_user(name: str) -> Dict:
    """Register a new user and return {token, handle, email, user_id}"""
    email = random_email()
    password = "secret123"
    
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name
    })
    
    if resp.status_code != 200:
        raise Exception(f"Registration failed: {resp.status_code} {resp.text}")
    
    data = resp.json()
    return {
        "token": data["access_token"],
        "handle": data["user"]["handle"],
        "email": email,
        "password": password,
        "user_id": data["user"]["id"]
    }

def auth_headers(token: str) -> Dict:
    """Return authorization headers"""
    return {"Authorization": f"Bearer {token}"}

def get_me(token: str) -> Dict:
    """GET /api/me"""
    resp = requests.get(f"{BASE_URL}/me", headers=auth_headers(token))
    if resp.status_code != 200:
        raise Exception(f"GET /me failed: {resp.status_code} {resp.text}")
    return resp.json()

def update_profile(token: str, data: Dict) -> Dict:
    """PUT /api/profile"""
    resp = requests.put(f"{BASE_URL}/profile", json=data, headers=auth_headers(token))
    if resp.status_code != 200:
        raise Exception(f"PUT /profile failed: {resp.status_code} {resp.text}")
    return resp.json()

def follow_user(token: str, handle: str) -> Dict:
    """POST /api/follow/{handle}"""
    resp = requests.post(f"{BASE_URL}/follow/{handle}", headers=auth_headers(token))
    return resp

def invite_inner(token: str, handle: str) -> Dict:
    """POST /api/inner/invite/{handle}"""
    resp = requests.post(f"{BASE_URL}/inner/invite/{handle}", headers=auth_headers(token))
    return resp

def accept_inner(token: str, owner_handle: str) -> Dict:
    """POST /api/inner/accept/{owner_handle}"""
    resp = requests.post(f"{BASE_URL}/inner/accept/{owner_handle}", headers=auth_headers(token))
    return resp

def set_relation(token: str, handle: str, kind: str) -> requests.Response:
    """POST /api/relations/{handle}"""
    resp = requests.post(f"{BASE_URL}/relations/{handle}", 
                        json={"kind": kind}, 
                        headers=auth_headers(token))
    return resp

def clear_relation(token: str, handle: str) -> requests.Response:
    """DELETE /api/relations/{handle}"""
    resp = requests.delete(f"{BASE_URL}/relations/{handle}", headers=auth_headers(token))
    return resp

def get_relations(token: str) -> Dict:
    """GET /api/relations"""
    resp = requests.get(f"{BASE_URL}/relations", headers=auth_headers(token))
    if resp.status_code != 200:
        raise Exception(f"GET /relations failed: {resp.status_code} {resp.text}")
    return resp.json()

def get_user(token: str, handle: str) -> requests.Response:
    """GET /api/users/{handle}"""
    resp = requests.get(f"{BASE_URL}/users/{handle}", headers=auth_headers(token))
    return resp

def get_connections(token: str) -> Dict:
    """GET /api/connections"""
    resp = requests.get(f"{BASE_URL}/connections", headers=auth_headers(token))
    if resp.status_code != 200:
        raise Exception(f"GET /connections failed: {resp.status_code} {resp.text}")
    return resp.json()

def remove_follower(token: str, handle: str) -> requests.Response:
    """POST /api/followers/{handle}/remove"""
    resp = requests.post(f"{BASE_URL}/followers/{handle}/remove", headers=auth_headers(token))
    return resp

def remove_inner_member(token: str, handle: str) -> requests.Response:
    """DELETE /api/inner/{handle}"""
    resp = requests.delete(f"{BASE_URL}/inner/{handle}", headers=auth_headers(token))
    return resp

def send_dm(token: str, handle: str, text: str) -> requests.Response:
    """POST /api/dms/{handle}"""
    resp = requests.post(f"{BASE_URL}/dms/{handle}", 
                        json={"text": text}, 
                        headers=auth_headers(token))
    return resp

def create_post(token: str, tier: str, text: str) -> requests.Response:
    """POST /api/posts"""
    resp = requests.post(f"{BASE_URL}/posts", 
                        json={"tier": tier, "text": text}, 
                        headers=auth_headers(token))
    return resp

def get_feed(token: str, scope: str = "general") -> requests.Response:
    """GET /api/feed"""
    resp = requests.get(f"{BASE_URL}/feed", 
                       params={"scope": scope}, 
                       headers=auth_headers(token))
    return resp

def get_activity(token: str) -> requests.Response:
    """GET /api/activity"""
    resp = requests.get(f"{BASE_URL}/activity", headers=auth_headers(token))
    return resp

# ============================================================================
# (A) DISPLAY + NOTIFICATION PREFS TESTS
# ============================================================================

def test_display_notif_prefs():
    """Test Phase 5: Display prefs + notif_prefs"""
    print("\n" + "="*80)
    print("(A) DISPLAY + NOTIFICATION PREFS TESTS")
    print("="*80)
    
    passed = 0
    failed = 0
    
    try:
        # Test 1: Register user → GET /api/me returns defaults
        print("\n[TEST 1] Register user → GET /api/me returns theme='dark', accent='violet', font_size='normal', notif_prefs with 6 keys all true")
        user = register_user("Display Test User")
        print(f"✓ Registered user: {user['handle']} ({user['email']})")
        
        me = get_me(user['token'])
        
        # Check display defaults
        assert me.get('theme') == 'dark', f"Expected theme='dark', got {me.get('theme')}"
        assert me.get('accent') == 'violet', f"Expected accent='violet', got {me.get('accent')}"
        assert me.get('font_size') == 'normal', f"Expected font_size='normal', got {me.get('font_size')}"
        print(f"✓ Display defaults correct: theme={me['theme']}, accent={me['accent']}, font_size={me['font_size']}")
        
        # Check notif_prefs
        notif_prefs = me.get('notif_prefs', {})
        expected_keys = ['follows', 'wall', 'reactions', 'comments', 'dms', 'inner']
        assert set(notif_prefs.keys()) == set(expected_keys), f"Expected keys {expected_keys}, got {list(notif_prefs.keys())}"
        for key in expected_keys:
            assert notif_prefs[key] == True, f"Expected notif_prefs.{key}=true, got {notif_prefs[key]}"
        print(f"✓ notif_prefs has 6 keys all true: {notif_prefs}")
        passed += 1
        
        # Test 2: PUT /api/profile with valid display prefs
        print("\n[TEST 2] PUT /api/profile {theme:'light',accent:'blue',font_size:'large'} → GET /api/me reflects them")
        update_profile(user['token'], {
            'theme': 'light',
            'accent': 'blue',
            'font_size': 'large'
        })
        print("✓ Updated profile with theme='light', accent='blue', font_size='large'")
        
        me = get_me(user['token'])
        assert me.get('theme') == 'light', f"Expected theme='light', got {me.get('theme')}"
        assert me.get('accent') == 'blue', f"Expected accent='blue', got {me.get('accent')}"
        assert me.get('font_size') == 'large', f"Expected font_size='large', got {me.get('font_size')}"
        print(f"✓ GET /api/me reflects changes: theme={me['theme']}, accent={me['accent']}, font_size={me['font_size']}")
        passed += 1
        
        # Test 3: PUT /api/profile with invalid values (should be ignored)
        print("\n[TEST 3] PUT /api/profile {theme:'neon',accent:'gold'} → invalid values IGNORED (theme stays 'light', accent stays 'blue')")
        update_profile(user['token'], {
            'theme': 'neon',
            'accent': 'gold'
        })
        print("✓ Sent invalid values: theme='neon', accent='gold'")
        
        me = get_me(user['token'])
        assert me.get('theme') == 'light', f"Expected theme='light' (unchanged), got {me.get('theme')}"
        assert me.get('accent') == 'blue', f"Expected accent='blue' (unchanged), got {me.get('accent')}"
        print(f"✓ Invalid values ignored: theme={me['theme']} (unchanged), accent={me['accent']} (unchanged)")
        passed += 1
        
        # Test 4: PUT /api/profile with partial notif_prefs
        print("\n[TEST 4] PUT /api/profile {notif_prefs:{follows:false}} → GET /api/me notif_prefs.follows=false, other 5 keys true")
        update_profile(user['token'], {
            'notif_prefs': {'follows': False}
        })
        print("✓ Updated notif_prefs with follows=false")
        
        me = get_me(user['token'])
        notif_prefs = me.get('notif_prefs', {})
        assert notif_prefs.get('follows') == False, f"Expected notif_prefs.follows=false, got {notif_prefs.get('follows')}"
        for key in ['wall', 'reactions', 'comments', 'dms', 'inner']:
            assert notif_prefs.get(key) == True, f"Expected notif_prefs.{key}=true, got {notif_prefs.get(key)}"
        print(f"✓ notif_prefs.follows=false, other 5 keys true: {notif_prefs}")
        passed += 1
        
        # Test 5: Notification gating - follow activity excluded when follows=false
        print("\n[TEST 5] Notification gating: B follows A (open mode auto-approve → creates 'follow' activity). As A GET /api/activity includes B's follow. As A PUT {notif_prefs:{follows:false}}. As A GET /api/activity → follow entry EXCLUDED")
        
        # Register user A and B
        userA = register_user("User A Notif")
        userB = register_user("User B Notif")
        print(f"✓ Registered A: {userA['handle']}, B: {userB['handle']}")
        
        # B follows A (open mode auto-approve)
        follow_resp = follow_user(userB['token'], userA['handle'])
        assert follow_resp.status_code == 200, f"Expected 200, got {follow_resp.status_code}"
        follow_data = follow_resp.json()
        assert follow_data.get('status') == 'approved', f"Expected status='approved', got {follow_data.get('status')}"
        print(f"✓ B follows A → status='approved' (open mode auto-approve)")
        
        time.sleep(0.5)  # Give activity time to be created
        
        # As A, GET /api/activity should include B's follow
        activity_resp = get_activity(userA['token'])
        assert activity_resp.status_code == 200, f"Expected 200, got {activity_resp.status_code}"
        activities = activity_resp.json()
        
        # Find follow activity from B
        follow_activities = [a for a in activities if a.get('type') in ['follow', 'follow_accepted'] and a.get('actor_id') == userB['user_id']]
        assert len(follow_activities) > 0, f"Expected follow activity from B, got {len(follow_activities)} activities"
        print(f"✓ As A, GET /api/activity includes B's follow entry (found {len(follow_activities)} follow activities)")
        
        # As A, turn off follows notifications
        update_profile(userA['token'], {
            'notif_prefs': {'follows': False}
        })
        print("✓ As A, PUT /api/profile {notif_prefs:{follows:false}}")
        
        # As A, GET /api/activity should exclude follow entries
        activity_resp = get_activity(userA['token'])
        assert activity_resp.status_code == 200, f"Expected 200, got {activity_resp.status_code}"
        activities = activity_resp.json()
        
        follow_activities = [a for a in activities if a.get('type') in ['follow', 'follow_accepted', 'follow_request']]
        assert len(follow_activities) == 0, f"Expected 0 follow activities (filtered out), got {len(follow_activities)}"
        print(f"✓ As A, GET /api/activity → follow entries EXCLUDED (found {len(follow_activities)} follow activities)")
        passed += 1
        
    except AssertionError as e:
        print(f"✗ FAILED: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        failed += 1
    
    print(f"\n{'='*80}")
    print(f"(A) DISPLAY + NOTIFICATION PREFS: {passed} passed, {failed} failed")
    print(f"{'='*80}")
    
    return passed, failed

# ============================================================================
# (B) BLOCK / MUTE / RESTRICT TESTS
# ============================================================================

def test_block_mute_restrict():
    """Test Phase 5: Block / Mute / Restrict relations"""
    print("\n" + "="*80)
    print("(B) BLOCK / MUTE / RESTRICT TESTS")
    print("="*80)
    
    passed = 0
    failed = 0
    
    try:
        # Setup: Register A, B, C, D
        print("\n[SETUP] Register A, B, C, D")
        userA = register_user("User A Block")
        userB = register_user("User B Block")
        userC = register_user("User C Mute")
        userD = register_user("User D Restrict")
        print(f"✓ Registered A: {userA['handle']}, B: {userB['handle']}, C: {userC['handle']}, D: {userD['handle']}")
        
        # B follows A (approved)
        follow_resp = follow_user(userB['token'], userA['handle'])
        assert follow_resp.status_code == 200, f"Expected 200, got {follow_resp.status_code}"
        assert follow_resp.json().get('status') == 'approved', f"Expected status='approved'"
        print(f"✓ B follows A → status='approved'")
        
        # A invites B to inner + B accepts
        invite_resp = invite_inner(userA['token'], userB['handle'])
        assert invite_resp.status_code == 200, f"Expected 200, got {invite_resp.status_code}"
        print(f"✓ A invites B to inner → status='pending'")
        
        accept_resp = accept_inner(userB['token'], userA['handle'])
        assert accept_resp.status_code == 200, f"Expected 200, got {accept_resp.status_code}"
        print(f"✓ B accepts A's inner invite → status='accepted'")
        
        # Test 1: BLOCK - A blocks B
        print("\n[TEST 1] A POST /api/relations/{B_handle} {kind:'block'} → 200")
        block_resp = set_relation(userA['token'], userB['handle'], 'block')
        assert block_resp.status_code == 200, f"Expected 200, got {block_resp.status_code}"
        assert block_resp.json().get('ok') == True, f"Expected ok=true"
        assert block_resp.json().get('kind') == 'block', f"Expected kind='block'"
        print(f"✓ A blocks B → 200 {block_resp.json()}")
        passed += 1
        
        # Test 2: BLOCK - Mutual invisibility (A GET /api/users/{B_handle} → 404)
        print("\n[TEST 2] A GET /api/users/{B_handle} → 404 (mutual invisibility)")
        get_b_resp = get_user(userA['token'], userB['handle'])
        assert get_b_resp.status_code == 404, f"Expected 404, got {get_b_resp.status_code}"
        print(f"✓ A GET /api/users/{userB['handle']} → 404 (blocked)")
        passed += 1
        
        # Test 3: BLOCK - Mutual invisibility (B GET /api/users/{A_handle} → 404)
        print("\n[TEST 3] B GET /api/users/{A_handle} → 404 (mutual invisibility)")
        get_a_resp = get_user(userB['token'], userA['handle'])
        assert get_a_resp.status_code == 404, f"Expected 404, got {get_a_resp.status_code}"
        print(f"✓ B GET /api/users/{userA['handle']} → 404 (blocked)")
        passed += 1
        
        # Test 4: BLOCK - Follows removed (A GET /api/connections shows B not in followers)
        print("\n[TEST 4] A GET /api/connections shows B not in followers (follows removed)")
        conn_a = get_connections(userA['token'])
        follower_handles = [f['handle'] for f in conn_a.get('followers', [])]
        assert userB['handle'] not in follower_handles, f"Expected B not in followers, got {follower_handles}"
        print(f"✓ A's followers: {follower_handles} (B not present)")
        passed += 1
        
        # Test 5: BLOCK - Inner removed (A GET /api/connections shows B not in inner)
        print("\n[TEST 5] A GET /api/connections shows B not in inner (inner removed)")
        inner_handles = [m['handle'] for m in conn_a.get('inner', [])]
        assert userB['handle'] not in inner_handles, f"Expected B not in inner, got {inner_handles}"
        print(f"✓ A's inner: {inner_handles} (B not present)")
        passed += 1
        
        # Test 6: BLOCK - A cannot DM B (403)
        print("\n[TEST 6] A POST /api/dms/{B_handle} → 403 (blocked)")
        dm_resp = send_dm(userA['token'], userB['handle'], "test message")
        assert dm_resp.status_code == 403, f"Expected 403, got {dm_resp.status_code}"
        print(f"✓ A POST /api/dms/{userB['handle']} → 403 (blocked)")
        passed += 1
        
        # Test 7: BLOCK - B cannot DM A (403)
        print("\n[TEST 7] B POST /api/dms/{A_handle} → 403 (blocked)")
        dm_resp = send_dm(userB['token'], userA['handle'], "test message")
        assert dm_resp.status_code == 403, f"Expected 403, got {dm_resp.status_code}"
        print(f"✓ B POST /api/dms/{userA['handle']} → 403 (blocked)")
        passed += 1
        
        # Test 8: BLOCK - A cannot follow B (403)
        print("\n[TEST 8] A POST /api/follow/{B_handle} → 403 (blocked)")
        follow_resp = follow_user(userA['token'], userB['handle'])
        assert follow_resp.status_code == 403, f"Expected 403, got {follow_resp.status_code}"
        print(f"✓ A POST /api/follow/{userB['handle']} → 403 (blocked)")
        passed += 1
        
        # Test 9: UNBLOCK - A DELETE /api/relations/{B_handle} → A GET /api/users/{B_handle} → 200
        print("\n[TEST 9] A DELETE /api/relations/{B_handle} → A GET /api/users/{B_handle} → 200 (unblocked)")
        clear_resp = clear_relation(userA['token'], userB['handle'])
        assert clear_resp.status_code == 200, f"Expected 200, got {clear_resp.status_code}"
        print(f"✓ A unblocks B → 200")
        
        get_b_resp = get_user(userA['token'], userB['handle'])
        assert get_b_resp.status_code == 200, f"Expected 200, got {get_b_resp.status_code}"
        print(f"✓ A GET /api/users/{userB['handle']} → 200 (visible again)")
        passed += 1
        
        # Test 10: MUTE - A mutes C
        print("\n[TEST 10] A POST /api/relations/{C_handle} {kind:'mute'} → 200")
        mute_resp = set_relation(userA['token'], userC['handle'], 'mute')
        assert mute_resp.status_code == 200, f"Expected 200, got {mute_resp.status_code}"
        assert mute_resp.json().get('kind') == 'mute', f"Expected kind='mute'"
        print(f"✓ A mutes C → 200")
        passed += 1
        
        # Test 11: MUTE - C creates a public post
        print("\n[TEST 11] C creates a public post")
        post_resp = create_post(userC['token'], 'public', 'Test post from C')
        assert post_resp.status_code == 200, f"Expected 200, got {post_resp.status_code}"
        post_id = post_resp.json().get('id')
        print(f"✓ C creates public post: {post_id}")
        passed += 1
        
        # Test 12: MUTE - A GET /api/feed?scope=general → C's post NOT present
        print("\n[TEST 12] A GET /api/feed?scope=general → C's post NOT present (muted)")
        feed_resp = get_feed(userA['token'], 'general')
        assert feed_resp.status_code == 200, f"Expected 200, got {feed_resp.status_code}"
        feed_posts = feed_resp.json()
        c_posts = [p for p in feed_posts if p.get('author', {}).get('handle') == userC['handle']]
        assert len(c_posts) == 0, f"Expected 0 posts from C (muted), got {len(c_posts)}"
        print(f"✓ A's feed does not include C's post (muted)")
        passed += 1
        
        # Test 13: MUTE - A GET /api/users/{C_handle} → 200 (mute doesn't hide profile)
        print("\n[TEST 13] A GET /api/users/{C_handle} → 200 (mute doesn't hide profile)")
        get_c_resp = get_user(userA['token'], userC['handle'])
        assert get_c_resp.status_code == 200, f"Expected 200, got {get_c_resp.status_code}"
        print(f"✓ A GET /api/users/{userC['handle']} → 200 (profile still visible)")
        passed += 1
        
        # Test 14: RESTRICT - A restricts D
        print("\n[TEST 14] A POST /api/relations/{D_handle} {kind:'restrict'} → 200")
        restrict_resp = set_relation(userA['token'], userD['handle'], 'restrict')
        assert restrict_resp.status_code == 200, f"Expected 200, got {restrict_resp.status_code}"
        assert restrict_resp.json().get('kind') == 'restrict', f"Expected kind='restrict'"
        print(f"✓ A restricts D → 200")
        passed += 1
        
        # Test 15: RESTRICT - D POST /api/dms/{A_handle} → 403 (restricted can't DM)
        print("\n[TEST 15] D POST /api/dms/{A_handle} → 403 (restricted can't DM)")
        dm_resp = send_dm(userD['token'], userA['handle'], "test message")
        assert dm_resp.status_code == 403, f"Expected 403, got {dm_resp.status_code}"
        print(f"✓ D POST /api/dms/{userA['handle']} → 403 (restricted)")
        passed += 1
        
        # Test 16: INVALID - POST /api/relations/{B_handle} {kind:'foo'} → 400
        print("\n[TEST 16] POST /api/relations/{B_handle} {kind:'foo'} → 400 (invalid kind)")
        invalid_resp = set_relation(userA['token'], userB['handle'], 'foo')
        assert invalid_resp.status_code == 400, f"Expected 400, got {invalid_resp.status_code}"
        print(f"✓ POST /api/relations with kind='foo' → 400 (invalid)")
        passed += 1
        
        # Test 17: INVALID - POST /api/relations/{own_handle} → 400
        print("\n[TEST 17] POST /api/relations/{own_handle} → 400 (cannot set relation on self)")
        self_resp = set_relation(userA['token'], userA['handle'], 'block')
        assert self_resp.status_code == 400, f"Expected 400, got {self_resp.status_code}"
        print(f"✓ POST /api/relations/{userA['handle']} (self) → 400 (invalid)")
        passed += 1
        
        # Test 18: GET /api/relations → {block:[...], mute:[...], restrict:[...]}
        print("\n[TEST 18] GET /api/relations → {block:[...], mute:[...], restrict:[...]}")
        relations = get_relations(userA['token'])
        assert 'block' in relations, f"Expected 'block' key in relations"
        assert 'mute' in relations, f"Expected 'mute' key in relations"
        assert 'restrict' in relations, f"Expected 'restrict' key in relations"
        
        # Check mute list contains C
        mute_handles = [u['handle'] for u in relations['mute']]
        assert userC['handle'] in mute_handles, f"Expected C in mute list, got {mute_handles}"
        
        # Check restrict list contains D
        restrict_handles = [u['handle'] for u in relations['restrict']]
        assert userD['handle'] in restrict_handles, f"Expected D in restrict list, got {restrict_handles}"
        
        print(f"✓ GET /api/relations → block={len(relations['block'])}, mute={len(relations['mute'])}, restrict={len(relations['restrict'])}")
        print(f"  Muted: {mute_handles}")
        print(f"  Restricted: {restrict_handles}")
        passed += 1
        
    except AssertionError as e:
        print(f"✗ FAILED: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        failed += 1
    
    print(f"\n{'='*80}")
    print(f"(B) BLOCK / MUTE / RESTRICT: {passed} passed, {failed} failed")
    print(f"{'='*80}")
    
    return passed, failed

# ============================================================================
# (C) CONNECTIONS MANAGER TESTS
# ============================================================================

def test_connections_manager():
    """Test Phase 5: Connections manager"""
    print("\n" + "="*80)
    print("(C) CONNECTIONS MANAGER TESTS")
    print("="*80)
    
    passed = 0
    failed = 0
    
    try:
        # Setup: Register users and build graph
        print("\n[SETUP] Register users and build follow/inner graph")
        userA = register_user("User A Conn")
        userB = register_user("User B Conn")
        userC = register_user("User C Conn")
        print(f"✓ Registered A: {userA['handle']}, B: {userB['handle']}, C: {userC['handle']}")
        
        # B follows A (approved)
        follow_resp = follow_user(userB['token'], userA['handle'])
        assert follow_resp.status_code == 200, f"Expected 200, got {follow_resp.status_code}"
        print(f"✓ B follows A → approved")
        
        # A follows C (approved)
        follow_resp = follow_user(userA['token'], userC['handle'])
        assert follow_resp.status_code == 200, f"Expected 200, got {follow_resp.status_code}"
        print(f"✓ A follows C → approved")
        
        # A invites B to inner + B accepts
        invite_resp = invite_inner(userA['token'], userB['handle'])
        assert invite_resp.status_code == 200, f"Expected 200, got {invite_resp.status_code}"
        accept_resp = accept_inner(userB['token'], userA['handle'])
        assert accept_resp.status_code == 200, f"Expected 200, got {accept_resp.status_code}"
        print(f"✓ A invites B to inner + B accepts")
        
        # Test 1: GET /api/connections returns correct structure
        print("\n[TEST 1] GET /api/connections → {followers, following, inner, requests, relations, counts}")
        conn = get_connections(userA['token'])
        
        assert 'followers' in conn, f"Expected 'followers' key"
        assert 'following' in conn, f"Expected 'following' key"
        assert 'inner' in conn, f"Expected 'inner' key"
        assert 'requests' in conn, f"Expected 'requests' key"
        assert 'relations' in conn, f"Expected 'relations' key"
        assert 'counts' in conn, f"Expected 'counts' key"
        
        print(f"✓ GET /api/connections structure correct")
        print(f"  followers: {len(conn['followers'])}, following: {len(conn['following'])}, inner: {len(conn['inner'])}, requests: {len(conn['requests'])}")
        passed += 1
        
        # Test 2: Followers list correct (B follows A)
        print("\n[TEST 2] A's followers list includes B")
        follower_handles = [f['handle'] for f in conn['followers']]
        assert userB['handle'] in follower_handles, f"Expected B in followers, got {follower_handles}"
        
        # Check in_my_inner flag
        b_follower = next((f for f in conn['followers'] if f['handle'] == userB['handle']), None)
        assert b_follower is not None, f"Expected B in followers"
        assert b_follower.get('in_my_inner') == True, f"Expected B in_my_inner=true, got {b_follower.get('in_my_inner')}"
        
        print(f"✓ A's followers: {follower_handles}, B.in_my_inner=true")
        passed += 1
        
        # Test 3: Following list correct (A follows C)
        print("\n[TEST 3] A's following list includes C")
        following_handles = [f['handle'] for f in conn['following']]
        assert userC['handle'] in following_handles, f"Expected C in following, got {following_handles}"
        
        # Check status
        c_following = next((f for f in conn['following'] if f['handle'] == userC['handle']), None)
        assert c_following is not None, f"Expected C in following"
        assert c_following.get('status') == 'approved', f"Expected C status='approved', got {c_following.get('status')}"
        
        print(f"✓ A's following: {following_handles}, C.status='approved'")
        passed += 1
        
        # Test 4: Inner list correct (B in A's inner)
        print("\n[TEST 4] A's inner list includes B")
        inner_handles = [m['handle'] for m in conn['inner']]
        assert userB['handle'] in inner_handles, f"Expected B in inner, got {inner_handles}"
        
        print(f"✓ A's inner: {inner_handles}")
        passed += 1
        
        # Test 5: Counts correct
        print("\n[TEST 5] Counts match list lengths")
        counts = conn['counts']
        assert counts['followers'] == len(conn['followers']), f"Expected followers count={len(conn['followers'])}, got {counts['followers']}"
        assert counts['following'] == len(conn['following']), f"Expected following count={len(conn['following'])}, got {counts['following']}"
        assert counts['inner'] == len(conn['inner']), f"Expected inner count={len(conn['inner'])}, got {counts['inner']}"
        assert counts['requests'] == len(conn['requests']), f"Expected requests count={len(conn['requests'])}, got {counts['requests']}"
        
        print(f"✓ Counts correct: {counts}")
        passed += 1
        
        # Test 6: POST /api/followers/{handle}/remove removes a follower
        print("\n[TEST 6] A POST /api/followers/{B_handle}/remove → B removed from followers")
        remove_resp = remove_follower(userA['token'], userB['handle'])
        assert remove_resp.status_code == 200, f"Expected 200, got {remove_resp.status_code}"
        print(f"✓ A removes B from followers → 200")
        
        conn = get_connections(userA['token'])
        follower_handles = [f['handle'] for f in conn['followers']]
        assert userB['handle'] not in follower_handles, f"Expected B not in followers, got {follower_handles}"
        print(f"✓ A's followers: {follower_handles} (B removed)")
        passed += 1
        
        # Test 7: DELETE /api/inner/{handle} removes an inner member
        print("\n[TEST 7] A DELETE /api/inner/{B_handle} → B removed from inner")
        remove_resp = remove_inner_member(userA['token'], userB['handle'])
        assert remove_resp.status_code == 200, f"Expected 200, got {remove_resp.status_code}"
        print(f"✓ A removes B from inner → 200")
        
        conn = get_connections(userA['token'])
        inner_handles = [m['handle'] for m in conn['inner']]
        assert userB['handle'] not in inner_handles, f"Expected B not in inner, got {inner_handles}"
        print(f"✓ A's inner: {inner_handles} (B removed)")
        passed += 1
        
        # Test 8: Existing accept-follow still works
        print("\n[TEST 8] Existing follow flow still works (regression)")
        userD = register_user("User D Conn")
        
        # D follows A
        follow_resp = follow_user(userD['token'], userA['handle'])
        assert follow_resp.status_code == 200, f"Expected 200, got {follow_resp.status_code}"
        assert follow_resp.json().get('status') == 'approved', f"Expected status='approved'"
        print(f"✓ D follows A → status='approved'")
        
        # Check A's connections
        conn = get_connections(userA['token'])
        follower_handles = [f['handle'] for f in conn['followers']]
        assert userD['handle'] in follower_handles, f"Expected D in followers, got {follower_handles}"
        print(f"✓ A's followers now include D: {follower_handles}")
        passed += 1
        
        # Test 9: Existing invite-inner still works
        print("\n[TEST 9] Existing inner invite flow still works (regression)")
        
        # A invites D to inner
        invite_resp = invite_inner(userA['token'], userD['handle'])
        assert invite_resp.status_code == 200, f"Expected 200, got {invite_resp.status_code}"
        print(f"✓ A invites D to inner → 200")
        
        # D accepts
        accept_resp = accept_inner(userD['token'], userA['handle'])
        assert accept_resp.status_code == 200, f"Expected 200, got {accept_resp.status_code}"
        print(f"✓ D accepts A's inner invite → 200")
        
        # Check A's connections
        conn = get_connections(userA['token'])
        inner_handles = [m['handle'] for m in conn['inner']]
        assert userD['handle'] in inner_handles, f"Expected D in inner, got {inner_handles}"
        print(f"✓ A's inner now includes D: {inner_handles}")
        passed += 1
        
    except AssertionError as e:
        print(f"✗ FAILED: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        failed += 1
    
    print(f"\n{'='*80}")
    print(f"(C) CONNECTIONS MANAGER: {passed} passed, {failed} failed")
    print(f"{'='*80}")
    
    return passed, failed

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*80)
    print("PHASE 5 BACKEND TESTING")
    print("Testing: Display prefs + notif_prefs, Block/Mute/Restrict, Connections manager")
    print(f"Base URL: {BASE_URL}")
    print("="*80)
    
    total_passed = 0
    total_failed = 0
    
    # (A) Display + Notification Prefs
    passed, failed = test_display_notif_prefs()
    total_passed += passed
    total_failed += failed
    
    # (B) Block / Mute / Restrict
    passed, failed = test_block_mute_restrict()
    total_passed += passed
    total_failed += failed
    
    # (C) Connections Manager
    passed, failed = test_connections_manager()
    total_passed += passed
    total_failed += failed
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Total: {total_passed} passed, {total_failed} failed")
    
    if total_failed == 0:
        print("✅ ALL PHASE 5 TESTS PASSED")
    else:
        print(f"❌ {total_failed} TESTS FAILED")
    
    print("="*80)
    
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    exit(main())
