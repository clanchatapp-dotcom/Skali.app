#!/usr/bin/env python3
"""
Test script for Disappearing (view-once) DM media feature.
Tests all 10 scenarios + regression check for Inner-Circle Voice/Call flags.
"""
import requests
import uuid
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def register_user(email, password, handle, dob="1990-01-01"):
    """Register a new user and return token"""
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "handle": handle,
            "display_name": handle.upper(),
            "dob": dob
        }, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Failed to register {handle}: {resp.status_code} {resp.text}")
            return None
        data = resp.json()
        print(f"✅ Registered {handle} (email: {email})")
        return data.get('access_token') or data.get('token')
    except Exception as e:
        print(f"❌ Exception during registration of {handle}: {e}")
        return None

def login_user(email, password):
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code != 200:
        print(f"❌ Failed to login {email}: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get('access_token') or data.get('token')

def main():
    print("=" * 80)
    print("DISAPPEARING (VIEW-ONCE) DM MEDIA TEST")
    print("=" * 80)
    
    # Generate unique identifiers for this test run
    test_id = str(uuid.uuid4())[:8]
    
    # Register 3 adult users (DOB 1990-01-01)
    print("\n[SETUP] Registering 3 adult users (DOB 1990-01-01)...")
    
    user_a_email = f"viewoncea+{test_id}@example.com"
    user_a_handle = f"viewoncea{test_id}"
    user_a_token = register_user(user_a_email, "Password123!", user_a_handle, "1990-01-01")
    if not user_a_token:
        sys.exit(1)
    
    user_b_email = f"viewonceb+{test_id}@example.com"
    user_b_handle = f"viewonceb{test_id}"
    print(f"Attempting to register user B: {user_b_handle}")
    user_b_token = register_user(user_b_email, "Password123!", user_b_handle, "1990-01-01")
    if not user_b_token:
        print(f"Failed to get token for user B")
        sys.exit(1)
    
    user_c_email = f"viewoncec+{test_id}@example.com"
    user_c_handle = f"viewoncec{test_id}"
    user_c_token = register_user(user_c_email, "Password123!", user_c_handle, "1990-01-01")
    if not user_c_token:
        sys.exit(1)
    
    # Put B into A's Inner Circle (A invites B, B accepts)
    print(f"\n[SETUP] Putting {user_b_handle} into {user_a_handle}'s Inner Circle...")
    
    # A invites B to inner circle
    resp = requests.post(f"{BASE_URL}/inner/invite/{user_b_handle}", 
                         headers={"Authorization": f"Bearer {user_a_token}"})
    if resp.status_code != 200:
        print(f"❌ Failed to invite B to inner circle: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ A invited B to inner circle")
    
    # B accepts the invite
    resp = requests.post(f"{BASE_URL}/inner/accept/{user_a_handle}", 
                         headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ Failed to accept inner circle invite: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    if data.get('status') != 'accepted':
        print(f"❌ Inner circle status not 'accepted': {data}")
        sys.exit(1)
    print(f"✅ B accepted inner circle invite (status: {data.get('status')})")
    
    # Now run the 10 test scenarios
    print("\n" + "=" * 80)
    print("TEST SCENARIOS")
    print("=" * 80)
    
    # SCENARIO 1: A sends view-once image to B
    print("\n[TEST 1] A sends view-once image to B...")
    resp = requests.post(f"{BASE_URL}/dms/{user_b_handle}", 
                         headers={"Authorization": f"Bearer {user_a_token}"},
                         json={
                             "media_url": "https://example.com/p.jpg",
                             "media_type": "image",
                             "view_once": True
                         })
    if resp.status_code != 200:
        print(f"❌ TEST 1 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    msg1_id = data.get('id')
    if not data.get('view_once'):
        print(f"❌ TEST 1 FAILED: view_once should be true, got {data.get('view_once')}")
        sys.exit(1)
    if data.get('media_url') is not None:
        print(f"❌ TEST 1 FAILED: media_url should be null (withheld from wire), got {data.get('media_url')}")
        sys.exit(1)
    print(f"✅ TEST 1 PASSED: A sent view-once image (msg_id: {msg1_id}), response has view_once=true and media_url=null")
    
    # SCENARIO 2: A GET /api/dms/{B_handle} → msg1 present with view_once=true, media_url=null
    print("\n[TEST 2] A GET /api/dms/{B_handle} → msg1 present with view_once=true, media_url=null...")
    resp = requests.get(f"{BASE_URL}/dms/{user_b_handle}", 
                        headers={"Authorization": f"Bearer {user_a_token}"})
    if resp.status_code != 200:
        print(f"❌ TEST 2 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    messages = data.get('messages', [])
    msg1 = next((m for m in messages if m['id'] == msg1_id), None)
    if not msg1:
        print(f"❌ TEST 2 FAILED: msg1 not found in A's history")
        sys.exit(1)
    if not msg1.get('view_once'):
        print(f"❌ TEST 2 FAILED: msg1 view_once should be true, got {msg1.get('view_once')}")
        sys.exit(1)
    if msg1.get('media_url') is not None:
        print(f"❌ TEST 2 FAILED: msg1 media_url should be null in history, got {msg1.get('media_url')}")
        sys.exit(1)
    print(f"✅ TEST 2 PASSED: A's history shows msg1 with view_once=true, media_url=null")
    
    # SCENARIO 3: B GET /api/dms/{A_handle} → msg1 present with view_once=true, view_once_viewed=false, media_url=null
    print("\n[TEST 3] B GET /api/dms/{A_handle} → msg1 present with view_once=true, view_once_viewed=false, media_url=null...")
    resp = requests.get(f"{BASE_URL}/dms/{user_a_handle}", 
                        headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ TEST 3 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    messages = data.get('messages', [])
    msg1 = next((m for m in messages if m['id'] == msg1_id), None)
    if not msg1:
        print(f"❌ TEST 3 FAILED: msg1 not found in B's history")
        sys.exit(1)
    if not msg1.get('view_once'):
        print(f"❌ TEST 3 FAILED: msg1 view_once should be true, got {msg1.get('view_once')}")
        sys.exit(1)
    if msg1.get('view_once_viewed'):
        print(f"❌ TEST 3 FAILED: msg1 view_once_viewed should be false, got {msg1.get('view_once_viewed')}")
        sys.exit(1)
    if msg1.get('media_url') is not None:
        print(f"❌ TEST 3 FAILED: msg1 media_url should be null in history, got {msg1.get('media_url')}")
        sys.exit(1)
    print(f"✅ TEST 3 PASSED: B's history shows msg1 with view_once=true, view_once_viewed=false, media_url=null")
    
    # SCENARIO 4: B POST /api/dms/{A_handle}/{msg1}/view → 200 with media_url=='https://example.com/p.jpg'
    print("\n[TEST 4] B POST /api/dms/{A_handle}/{msg1}/view → 200 with media_url...")
    resp = requests.post(f"{BASE_URL}/dms/{user_a_handle}/{msg1_id}/view", 
                         headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ TEST 4 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    if data.get('media_url') != 'https://example.com/p.jpg':
        print(f"❌ TEST 4 FAILED: Expected media_url='https://example.com/p.jpg', got {data.get('media_url')}")
        sys.exit(1)
    print(f"✅ TEST 4 PASSED: B viewed msg1, got media_url='https://example.com/p.jpg' (returned exactly once)")
    
    # SCENARIO 5: B POST /api/dms/{A_handle}/{msg1}/view again → 410 (already viewed)
    print("\n[TEST 5] B POST /api/dms/{A_handle}/{msg1}/view again → 410 (already viewed)...")
    resp = requests.post(f"{BASE_URL}/dms/{user_a_handle}/{msg1_id}/view", 
                         headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 410:
        print(f"❌ TEST 5 FAILED: Expected 410, got {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ TEST 5 PASSED: B tried to view msg1 again, got 410 (already viewed)")
    
    # SCENARIO 6: B GET /api/dms/{A_handle} → msg1 now view_once_viewed=true, media_url still null
    print("\n[TEST 6] B GET /api/dms/{A_handle} → msg1 now view_once_viewed=true, media_url still null...")
    resp = requests.get(f"{BASE_URL}/dms/{user_a_handle}", 
                        headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ TEST 6 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    messages = data.get('messages', [])
    msg1 = next((m for m in messages if m['id'] == msg1_id), None)
    if not msg1:
        print(f"❌ TEST 6 FAILED: msg1 not found in B's history")
        sys.exit(1)
    if not msg1.get('view_once_viewed'):
        print(f"❌ TEST 6 FAILED: msg1 view_once_viewed should be true, got {msg1.get('view_once_viewed')}")
        sys.exit(1)
    if msg1.get('media_url') is not None:
        print(f"❌ TEST 6 FAILED: msg1 media_url should still be null in history, got {msg1.get('media_url')}")
        sys.exit(1)
    print(f"✅ TEST 6 PASSED: B's history shows msg1 with view_once_viewed=true, media_url still null")
    
    # SCENARIO 7: SENDER rule - A sends ANOTHER view-once image to B (msg2), A tries to view it → 403
    print("\n[TEST 7] SENDER rule: A sends ANOTHER view-once image to B (msg2), A tries to view it → 403...")
    resp = requests.post(f"{BASE_URL}/dms/{user_b_handle}", 
                         headers={"Authorization": f"Bearer {user_a_token}"},
                         json={
                             "media_url": "https://example.com/p2.jpg",
                             "media_type": "image",
                             "view_once": True
                         })
    if resp.status_code != 200:
        print(f"❌ TEST 7 FAILED: Failed to send msg2: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    msg2_id = data.get('id')
    print(f"  → A sent msg2 (id: {msg2_id})")
    
    # A tries to view their own view-once message
    resp = requests.post(f"{BASE_URL}/dms/{user_b_handle}/{msg2_id}/view", 
                         headers={"Authorization": f"Bearer {user_a_token}"})
    if resp.status_code != 403:
        print(f"❌ TEST 7 FAILED: Expected 403, got {resp.status_code} {resp.text}")
        sys.exit(1)
    error_detail = resp.json().get('detail', '')
    if "can't reopen" not in error_detail.lower():
        print(f"❌ TEST 7 FAILED: Expected error detail to contain 'can't reopen', got '{error_detail}'")
        sys.exit(1)
    print(f"✅ TEST 7 PASSED: A (sender) tried to view msg2, got 403 with detail containing 'can't reopen'")
    
    # SCENARIO 8: NON-PARTICIPANT - C tries to view msg2 → 403
    print("\n[TEST 8] NON-PARTICIPANT: C tries to view msg2 → 403...")
    resp = requests.post(f"{BASE_URL}/dms/{user_a_handle}/{msg2_id}/view", 
                         headers={"Authorization": f"Bearer {user_c_token}"})
    if resp.status_code != 403:
        print(f"❌ TEST 8 FAILED: Expected 403, got {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ TEST 8 PASSED: C (non-participant) tried to view msg2, got 403")
    
    # SCENARIO 9: ERROR PATHS
    print("\n[TEST 9] ERROR PATHS...")
    
    # 9a: B tries to view non-existent message → 404
    print("  [9a] B tries to view non-existent message → 404...")
    resp = requests.post(f"{BASE_URL}/dms/{user_a_handle}/nonexistentid/view", 
                         headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 404:
        print(f"❌ TEST 9a FAILED: Expected 404, got {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"  ✅ TEST 9a PASSED: B tried to view non-existent message, got 404")
    
    # 9b: A sends NORMAL text message to B (msg3), B tries to view it → 400
    print("  [9b] A sends NORMAL text message to B (msg3), B tries to view it → 400...")
    resp = requests.post(f"{BASE_URL}/dms/{user_b_handle}", 
                         headers={"Authorization": f"Bearer {user_a_token}"},
                         json={"text": "This is a normal text message"})
    if resp.status_code != 200:
        print(f"❌ TEST 9b FAILED: Failed to send normal text message: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    msg3_id = data.get('id')
    print(f"    → A sent normal text message (msg3_id: {msg3_id})")
    
    resp = requests.post(f"{BASE_URL}/dms/{user_a_handle}/{msg3_id}/view", 
                         headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 400:
        print(f"❌ TEST 9b FAILED: Expected 400, got {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"  ✅ TEST 9b PASSED: B tried to view normal text message, got 400 (not a view-once message)")
    
    print(f"✅ TEST 9 PASSED: All error paths working correctly")
    
    # SCENARIO 10: REGRESSION - A sends NORMAL image (view_once omitted) → B sees media_url in history
    print("\n[TEST 10] REGRESSION: A sends NORMAL image (view_once omitted) → B sees media_url in history...")
    resp = requests.post(f"{BASE_URL}/dms/{user_b_handle}", 
                         headers={"Authorization": f"Bearer {user_a_token}"},
                         json={
                             "media_url": "https://example.com/normal.jpg",
                             "media_type": "image"
                         })
    if resp.status_code != 200:
        print(f"❌ TEST 10 FAILED: Failed to send normal image: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    normal_msg_id = data.get('id')
    print(f"  → A sent normal image (id: {normal_msg_id})")
    
    # B gets history and checks the normal image message
    resp = requests.get(f"{BASE_URL}/dms/{user_a_handle}", 
                        headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ TEST 10 FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    messages = data.get('messages', [])
    normal_msg = next((m for m in messages if m['id'] == normal_msg_id), None)
    if not normal_msg:
        print(f"❌ TEST 10 FAILED: Normal image message not found in B's history")
        sys.exit(1)
    if normal_msg.get('media_url') != 'https://example.com/normal.jpg':
        print(f"❌ TEST 10 FAILED: Normal image media_url should be 'https://example.com/normal.jpg', got {normal_msg.get('media_url')}")
        sys.exit(1)
    if normal_msg.get('view_once'):
        print(f"❌ TEST 10 FAILED: Normal image view_once should be false, got {normal_msg.get('view_once')}")
        sys.exit(1)
    print(f"✅ TEST 10 PASSED: B's history shows normal image with media_url='https://example.com/normal.jpg' (NOT null), view_once=false")
    
    # REGRESSION CHECK: Inner-Circle Voice/Call enforcement flags
    print("\n[REGRESSION CHECK] B GET /api/dms/{A_handle} still returns can_voice and can_call booleans...")
    resp = requests.get(f"{BASE_URL}/dms/{user_a_handle}", 
                        headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code != 200:
        print(f"❌ REGRESSION CHECK FAILED: Expected 200, got {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    if 'can_voice' not in data:
        print(f"❌ REGRESSION CHECK FAILED: can_voice field missing from response")
        sys.exit(1)
    if 'can_call' not in data:
        print(f"❌ REGRESSION CHECK FAILED: can_call field missing from response")
        sys.exit(1)
    if not isinstance(data['can_voice'], bool):
        print(f"❌ REGRESSION CHECK FAILED: can_voice should be boolean, got {type(data['can_voice'])}")
        sys.exit(1)
    if not isinstance(data['can_call'], bool):
        print(f"❌ REGRESSION CHECK FAILED: can_call should be boolean, got {type(data['can_call'])}")
        sys.exit(1)
    print(f"✅ REGRESSION CHECK PASSED: can_voice={data['can_voice']}, can_call={data['can_call']} (both booleans present)")
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✅")
    print("=" * 80)
    print(f"\nSummary:")
    print(f"  ✅ TEST 1: A sends view-once image, response has view_once=true and media_url=null")
    print(f"  ✅ TEST 2: A's history shows msg1 with view_once=true, media_url=null")
    print(f"  ✅ TEST 3: B's history shows msg1 with view_once=true, view_once_viewed=false, media_url=null")
    print(f"  ✅ TEST 4: B views msg1, gets media_url (returned exactly once)")
    print(f"  ✅ TEST 5: B tries to view msg1 again, gets 410 (already viewed)")
    print(f"  ✅ TEST 6: B's history shows msg1 with view_once_viewed=true, media_url still null")
    print(f"  ✅ TEST 7: A (sender) tries to view msg2, gets 403 with 'can't reopen'")
    print(f"  ✅ TEST 8: C (non-participant) tries to view msg2, gets 403")
    print(f"  ✅ TEST 9: Error paths (404 for non-existent, 400 for non-view-once)")
    print(f"  ✅ TEST 10: Normal image shows media_url in history (NOT null), view_once=false")
    print(f"  ✅ REGRESSION: can_voice and can_call flags present in dm_history")
    print()

if __name__ == '__main__':
    main()
