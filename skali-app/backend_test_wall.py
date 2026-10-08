#!/usr/bin/env python3
"""
Phase 4 Backend Testing: Facebook-style Wall (GET/POST/DELETE /api/wall)
Tests tier-gated wall posting with authentication
"""

import requests
import uuid
import json
from datetime import datetime

# Backend URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def log(msg):
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def register_user(name_prefix):
    """Register a throwaway user for testing"""
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"{name_prefix}+{unique_suffix}@example.com"
    password = "secret123"
    name = f"{name_prefix.capitalize()} User"
    
    log(f"Registering user: {email}")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name
    }, timeout=30)
    
    if resp.status_code != 200:
        log(f"❌ Registration failed: {resp.status_code} - {resp.text}")
        return None, None
    
    data = resp.json()
    token = data.get("access_token")
    handle = data.get("user", {}).get("handle")
    log(f"✅ Registered user: {handle} (token: {len(token)} chars)")
    return token, handle

def test_scenario_1_register_users():
    """Scenario 1: Register OWNER and VIEWER users"""
    log("\n=== SCENARIO 1: Register OWNER and VIEWER ===")
    
    owner_token, owner_handle = register_user("wallowner")
    if not owner_token:
        log("❌ FAIL: Could not register OWNER")
        return False, None, None, None, None
    
    viewer_token, viewer_handle = register_user("wallviewer")
    if not viewer_token:
        log("❌ FAIL: Could not register VIEWER")
        return False, None, None, None, None
    
    log(f"✅ PASS: Registered OWNER ({owner_handle}) and VIEWER ({viewer_handle})")
    return True, owner_token, owner_handle, viewer_token, viewer_handle

def test_scenario_2_stranger_access(viewer_token, owner_handle):
    """Scenario 2: VIEWER (stranger) GET wall -> can_post=false, POST -> 403"""
    log("\n=== SCENARIO 2: Stranger access (no follow) ===")
    
    # GET wall as stranger
    log(f"GET /api/wall/{owner_handle} as VIEWER (stranger)")
    headers = {"Authorization": f"Bearer {viewer_token}"}
    resp = requests.get(f"{BASE_URL}/wall/{owner_handle}", headers=headers, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    
    # Check can_post is false
    if data.get("can_post") != False:
        log(f"❌ FAIL: Expected can_post=false, got {data.get('can_post')}")
        return False
    
    log(f"✅ can_post=false (correct)")
    
    # Check posts array exists
    if "posts" not in data:
        log(f"❌ FAIL: Missing 'posts' field")
        return False
    
    log(f"✅ posts array present ({len(data['posts'])} posts)")
    
    # Try to POST as stranger (should fail with 403)
    log(f"POST /api/wall/{owner_handle} as VIEWER (stranger) - expect 403")
    resp = requests.post(f"{BASE_URL}/wall/{owner_handle}", headers=headers, json={
        "text": "trying to post as stranger"
    }, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 403:
        log(f"❌ FAIL: Expected 403, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PASS: Stranger correctly blocked from posting (403)")
    return True

def test_scenario_3_follow_and_post(viewer_token, viewer_handle, owner_token, owner_handle):
    """Scenario 3: VIEWER follows OWNER, then can post on wall"""
    log("\n=== SCENARIO 3: Follow and post on wall ===")
    
    # VIEWER follows OWNER
    log(f"POST /api/follow/{owner_handle} as VIEWER")
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}
    resp = requests.post(f"{BASE_URL}/follow/{owner_handle}", headers=headers_viewer, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Follow failed: {resp.status_code} - {resp.text}")
        return False, None
    
    data = resp.json()
    status = data.get("status")
    log(f"Follow status: {status}")
    
    if status != "approved":
        log(f"❌ FAIL: Expected auto-approved (open mode), got {status}")
        return False, None
    
    log(f"✅ Follow approved (open mode)")
    
    # GET wall again as VIEWER (now follower)
    log(f"GET /api/wall/{owner_handle} as VIEWER (now follower)")
    resp = requests.get(f"{BASE_URL}/wall/{owner_handle}", headers=headers_viewer, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False, None
    
    data = resp.json()
    
    # Check can_post is now true
    if data.get("can_post") != True:
        log(f"❌ FAIL: Expected can_post=true after follow, got {data.get('can_post')}")
        return False, None
    
    log(f"✅ can_post=true (correct)")
    
    # POST on wall as VIEWER
    log(f"POST /api/wall/{owner_handle} as VIEWER with text 'nice profile!'")
    resp = requests.post(f"{BASE_URL}/wall/{owner_handle}", headers=headers_viewer, json={
        "text": "nice profile!"
    }, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False, None
    
    data = resp.json()
    
    # Verify response structure
    required_fields = ['id', 'text', 'created_at', 'author', 'can_delete']
    missing = [f for f in required_fields if f not in data]
    if missing:
        log(f"❌ FAIL: Missing fields in response: {missing}")
        return False, None
    
    # Verify author is VIEWER
    if data['author']['handle'] != viewer_handle:
        log(f"❌ FAIL: Expected author.handle={viewer_handle}, got {data['author']['handle']}")
        return False, None
    
    log(f"✅ author.handle={viewer_handle} (correct)")
    
    # Verify can_delete is true (author can delete own post)
    if data.get('can_delete') != True:
        log(f"❌ FAIL: Expected can_delete=true for author, got {data.get('can_delete')}")
        return False, None
    
    log(f"✅ can_delete=true (correct)")
    
    wall_post_id = data['id']
    log(f"✅ PASS: Wall post created with id={wall_post_id}")
    
    return True, wall_post_id

def test_scenario_4_owner_sees_post(owner_token, owner_handle, viewer_handle):
    """Scenario 4: OWNER GET wall sees VIEWER's post with can_delete=true"""
    log("\n=== SCENARIO 4: Owner sees viewer's post ===")
    
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    resp = requests.get(f"{BASE_URL}/wall/{owner_handle}", headers=headers_owner, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    # Find VIEWER's post
    viewer_post = None
    for post in data.get('posts', []):
        if post.get('author', {}).get('handle') == viewer_handle:
            viewer_post = post
            break
    
    if not viewer_post:
        log(f"❌ FAIL: VIEWER's post not found in OWNER's wall")
        return False
    
    log(f"✅ Found VIEWER's post: '{viewer_post['text']}'")
    
    # Verify OWNER can delete (owner of wall)
    if viewer_post.get('can_delete') != True:
        log(f"❌ FAIL: Expected can_delete=true for OWNER, got {viewer_post.get('can_delete')}")
        return False
    
    log(f"✅ can_delete=true for OWNER (correct)")
    log(f"✅ PASS: Owner sees viewer's post with correct permissions")
    
    return True

def test_scenario_5_validation(viewer_token, owner_handle):
    """Scenario 5: Empty text -> 400, Unknown handle -> 404"""
    log("\n=== SCENARIO 5: Validation tests ===")
    
    headers = {"Authorization": f"Bearer {viewer_token}"}
    
    # Test empty text
    log("POST /api/wall with empty text - expect 400")
    resp = requests.post(f"{BASE_URL}/wall/{owner_handle}", headers=headers, json={
        "text": ""
    }, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400 for empty text, got {resp.status_code}")
        return False
    
    log(f"✅ Empty text correctly rejected (400)")
    
    # Test unknown handle
    unknown_handle = f"nonexistent{uuid.uuid4().hex[:8]}"
    log(f"GET /api/wall/{unknown_handle} - expect 404")
    resp = requests.get(f"{BASE_URL}/wall/{unknown_handle}", headers=headers, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 404:
        log(f"❌ FAIL: Expected 404 for unknown handle, got {resp.status_code}")
        return False
    
    log(f"✅ Unknown handle correctly returns 404")
    log(f"✅ PASS: Validation working correctly")
    
    return True

def test_scenario_6_delete_permissions(viewer_token, owner_token, wall_post_id):
    """Scenario 6: DELETE permissions - author can delete, third party cannot"""
    log("\n=== SCENARIO 6: DELETE permissions ===")
    
    # Register THIRD user
    third_token, third_handle = register_user("wallthird")
    if not third_token:
        log("❌ FAIL: Could not register THIRD user")
        return False
    
    log(f"Registered THIRD user: {third_handle}")
    
    # THIRD tries to delete VIEWER's post (should fail with 403)
    log(f"DELETE /api/wall/{wall_post_id} as THIRD (not author/owner) - expect 403")
    headers_third = {"Authorization": f"Bearer {third_token}"}
    resp = requests.delete(f"{BASE_URL}/wall/{wall_post_id}", headers=headers_third, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 403:
        log(f"❌ FAIL: Expected 403, got {resp.status_code}")
        return False
    
    log(f"✅ THIRD user correctly blocked from deleting (403)")
    
    # VIEWER (author) deletes own post
    log(f"DELETE /api/wall/{wall_post_id} as VIEWER (author) - expect 200")
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}
    resp = requests.delete(f"{BASE_URL}/wall/{wall_post_id}", headers=headers_viewer, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    if data.get('ok') != True:
        log(f"❌ FAIL: Expected ok=true, got {data}")
        return False
    
    log(f"✅ Author successfully deleted own post")
    log(f"✅ PASS: DELETE permissions working correctly")
    
    return True

def test_scenario_7_self_wall(owner_token, owner_handle):
    """Scenario 7: Self wall - OWNER can_post=true and POST works on own wall"""
    log("\n=== SCENARIO 7: Self wall ===")
    
    headers = {"Authorization": f"Bearer {owner_token}"}
    
    # GET own wall
    log(f"GET /api/wall/{owner_handle} as OWNER (self)")
    resp = requests.get(f"{BASE_URL}/wall/{owner_handle}", headers=headers, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    # Check can_post is true for self
    if data.get("can_post") != True:
        log(f"❌ FAIL: Expected can_post=true for self, got {data.get('can_post')}")
        return False
    
    log(f"✅ can_post=true for self (correct)")
    
    # POST on own wall
    log(f"POST /api/wall/{owner_handle} as OWNER (self)")
    resp = requests.post(f"{BASE_URL}/wall/{owner_handle}", headers=headers, json={
        "text": "posting on my own wall"
    }, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    
    # Verify author is OWNER
    if data['author']['handle'] != owner_handle:
        log(f"❌ FAIL: Expected author.handle={owner_handle}, got {data['author']['handle']}")
        return False
    
    log(f"✅ Self post created successfully")
    log(f"✅ PASS: Self wall working correctly")
    
    return True

def test_scenario_8_auth_regression(owner_handle):
    """Scenario 8: Regression - no auth token on GET/POST/DELETE -> 401"""
    log("\n=== SCENARIO 8: Auth regression (no token) ===")
    
    # GET without token
    log(f"GET /api/wall/{owner_handle} without token - expect 401")
    resp = requests.get(f"{BASE_URL}/wall/{owner_handle}", timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    
    log(f"✅ GET without token correctly returns 401")
    
    # POST without token
    log(f"POST /api/wall/{owner_handle} without token - expect 401")
    resp = requests.post(f"{BASE_URL}/wall/{owner_handle}", json={
        "text": "no auth"
    }, timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    
    log(f"✅ POST without token correctly returns 401")
    
    # DELETE without token
    fake_wall_id = str(uuid.uuid4())
    log(f"DELETE /api/wall/{fake_wall_id} without token - expect 401")
    resp = requests.delete(f"{BASE_URL}/wall/{fake_wall_id}", timeout=30)
    
    log(f"Status: {resp.status_code}")
    
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    
    log(f"✅ DELETE without token correctly returns 401")
    log(f"✅ PASS: Auth regression tests passed")
    
    return True

def main():
    """Run all Phase 4 Wall tests"""
    log("=" * 70)
    log("PHASE 4 BACKEND TESTING: Facebook-style Wall")
    log("=" * 70)
    
    results = {}
    
    # Scenario 1: Register users
    success, owner_token, owner_handle, viewer_token, viewer_handle = test_scenario_1_register_users()
    results['scenario_1_register'] = success
    
    if not success:
        log("\n❌ CRITICAL: Failed to register users, cannot continue")
        return
    
    # Scenario 2: Stranger access
    results['scenario_2_stranger'] = test_scenario_2_stranger_access(viewer_token, owner_handle)
    
    # Scenario 3: Follow and post
    success, wall_post_id = test_scenario_3_follow_and_post(viewer_token, viewer_handle, owner_token, owner_handle)
    results['scenario_3_follow_post'] = success
    
    if not success:
        log("\n❌ CRITICAL: Failed to create wall post, skipping delete tests")
        wall_post_id = None
    
    # Scenario 4: Owner sees post
    results['scenario_4_owner_sees'] = test_scenario_4_owner_sees_post(owner_token, owner_handle, viewer_handle)
    
    # Scenario 5: Validation
    results['scenario_5_validation'] = test_scenario_5_validation(viewer_token, owner_handle)
    
    # Scenario 6: Delete permissions (only if we have a wall post)
    if wall_post_id:
        results['scenario_6_delete'] = test_scenario_6_delete_permissions(viewer_token, owner_token, wall_post_id)
    else:
        results['scenario_6_delete'] = False
        log("\n⚠️  Skipping scenario 6 (delete permissions) - no wall post available")
    
    # Scenario 7: Self wall
    results['scenario_7_self_wall'] = test_scenario_7_self_wall(owner_token, owner_handle)
    
    # Scenario 8: Auth regression
    results['scenario_8_auth'] = test_scenario_8_auth_regression(owner_handle)
    
    # Summary
    log("\n" + "=" * 70)
    log("TEST SUMMARY")
    log("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log(f"\nTotal: {passed}/{total} tests passed ({100*passed//total}% success rate)")
    
    if passed == total:
        log("\n🎉 ALL TESTS PASSED - Phase 4 Wall backend is working correctly!")
    else:
        log(f"\n⚠️  {total - passed} test(s) failed - see details above")

if __name__ == "__main__":
    main()
