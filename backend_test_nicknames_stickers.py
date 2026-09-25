#!/usr/bin/env python3
"""
Backend test for Inner-circle private nicknames + custom stickers (personal pack).
Tests NEW features:
(A) NICKNAMES (private, inner-circle only)
(B) CUSTOM STICKERS (personal pack)
"""
import requests
import uuid
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def register_adult(email_prefix):
    """Register an adult user (DOB 1990-01-01) and return token + handle."""
    email = f"{email_prefix}+{uuid.uuid4().hex[:8]}@example.com"
    password = "Test1234!"
    dob = "1990-01-01"
    
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "dob": dob
    })
    print(f"Register {email_prefix}: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        sys.exit(1)
    
    token = resp.json()["access_token"]
    
    # Get handle
    me_resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"})
    handle = me_resp.json()["handle"]
    print(f"  Handle: {handle}, Token: {token[:20]}...")
    
    return token, handle, email

def main():
    print("=" * 80)
    print("BACKEND TEST: Inner-circle private nicknames + custom stickers")
    print("=" * 80)
    
    # Register two adult users A and B
    print("\n[SETUP] Registering adult users A and B (DOB 1990-01-01)")
    token_a, handle_a, email_a = register_adult("nicknametest_a")
    token_b, handle_b, email_b = register_adult("nicknametest_b")
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # ========================================================================
    # (A) NICKNAMES TESTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("(A) NICKNAMES TESTS")
    print("=" * 80)
    
    # Test 1: A PUT /api/inner/{B_handle}/nickname BEFORE inner relationship → 403
    print("\n[TEST 1] A PUT nickname for B BEFORE inner relationship → 403")
    resp = requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                       json={"nickname": "Jinky"}, 
                       headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 403:
        print("  ✅ PASS: 403 (not in inner circle)")
    else:
        print(f"  ❌ FAIL: Expected 403, got {resp.status_code}")
        print(f"  Response: {resp.text}")
    
    # Test 2: Establish inner circle: A invites B, B accepts
    print("\n[TEST 2] Establish inner circle: A invites B, B accepts")
    
    # A invites B
    resp = requests.post(f"{BASE_URL}/inner/invite/{handle_b}", headers=headers_a)
    print(f"  A invites B: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        sys.exit(1)
    
    # B accepts A
    resp = requests.post(f"{BASE_URL}/inner/accept/{handle_a}", headers=headers_b)
    print(f"  B accepts A: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        sys.exit(1)
    print("  ✅ Inner circle established")
    
    # Test 3: A PUT /api/inner/{B_handle}/nickname {nickname:'Jinky'} → 200
    print("\n[TEST 3] A PUT nickname for B (now in inner circle) → 200")
    resp = requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                       json={"nickname": "Jinky"}, 
                       headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Response: {data}")
        if data.get("nickname") == "Jinky":
            print("  ✅ PASS: 200, nickname set to 'Jinky'")
        else:
            print(f"  ❌ FAIL: nickname not 'Jinky', got {data.get('nickname')}")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"  Response: {resp.text}")
    
    # Test 4: A GET /api/inner → B entry has nickname == 'Jinky'
    print("\n[TEST 4] A GET /api/inner → B entry has nickname == 'Jinky'")
    resp = requests.get(f"{BASE_URL}/inner", headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        inner_list = resp.json()
        print(f"  Inner list count: {len(inner_list)}")
        b_entry = next((item for item in inner_list if item["handle"] == handle_b), None)
        if b_entry:
            nickname = b_entry.get("nickname")
            print(f"  B's nickname: {nickname}")
            if nickname == "Jinky":
                print("  ✅ PASS: B entry has nickname 'Jinky'")
            else:
                print(f"  ❌ FAIL: Expected 'Jinky', got {nickname}")
        else:
            print(f"  ❌ FAIL: B not found in inner list")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 5: A GET /api/dms/{B_handle} → peer.nickname == 'Jinky' AND peer_is_inner == true
    print("\n[TEST 5] A GET /api/dms/{B_handle} → peer.nickname == 'Jinky' AND peer_is_inner == true")
    resp = requests.get(f"{BASE_URL}/dms/{handle_b}", headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        peer_nickname = data.get("peer", {}).get("nickname")
        peer_is_inner = data.get("peer_is_inner")
        print(f"  peer.nickname: {peer_nickname}")
        print(f"  peer_is_inner: {peer_is_inner}")
        if peer_nickname == "Jinky" and peer_is_inner == True:
            print("  ✅ PASS: peer.nickname == 'Jinky' AND peer_is_inner == true")
        else:
            print(f"  ❌ FAIL: Expected nickname='Jinky' and peer_is_inner=true")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 6: A PUT /api/inner/{B_handle}/nickname {nickname:''} → 200 (clears)
    print("\n[TEST 6] A PUT nickname for B with empty string → 200 (clears)")
    resp = requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                       json={"nickname": ""}, 
                       headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Response: {data}")
        # Re-check GET /api/inner to verify cleared
        resp2 = requests.get(f"{BASE_URL}/inner", headers=headers_a)
        if resp2.status_code == 200:
            inner_list = resp2.json()
            b_entry = next((item for item in inner_list if item["handle"] == handle_b), None)
            if b_entry:
                nickname = b_entry.get("nickname")
                print(f"  B's nickname after clear: {nickname}")
                if nickname == "" or nickname is None:
                    print("  ✅ PASS: 200, nickname cleared")
                    # Re-set to 'Jinky' for later tests
                    print("  Re-setting nickname to 'Jinky' for later tests...")
                    requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                               json={"nickname": "Jinky"}, 
                               headers=headers_a)
                else:
                    print(f"  ❌ FAIL: Expected empty/None, got {nickname}")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 7: A PUT /api/inner/{B_handle}/nickname with banned word → 400
    print("\n[TEST 7] A PUT nickname for B with banned word → 400")
    resp = requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                       json={"nickname": "nigger"}, 
                       headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 400:
        print(f"  Response: {resp.json()}")
        print("  ✅ PASS: 400 (banned word rejected)")
    else:
        print(f"  ❌ FAIL: Expected 400, got {resp.status_code}")
    
    # Test 8: PUT nickname with NO auth header → 401
    print("\n[TEST 8] PUT nickname with NO auth header → 401")
    resp = requests.put(f"{BASE_URL}/inner/{handle_b}/nickname", 
                       json={"nickname": "test"})
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 401:
        print("  ✅ PASS: 401 (no auth)")
    else:
        print(f"  ❌ FAIL: Expected 401, got {resp.status_code}")
    
    # ========================================================================
    # (B) CUSTOM STICKERS TESTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("(B) CUSTOM STICKERS TESTS")
    print("=" * 80)
    
    # Test 1: A GET /api/stickers → [] (empty)
    print("\n[TEST 1] A GET /api/stickers → [] (empty)")
    resp = requests.get(f"{BASE_URL}/stickers", headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        stickers = resp.json()
        print(f"  Stickers count: {len(stickers)}")
        if len(stickers) == 0:
            print("  ✅ PASS: Empty stickers list")
        else:
            print(f"  ❌ FAIL: Expected empty list, got {len(stickers)} items")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 2: A POST /api/stickers {url:'https://example.com/s1.png'} → 200 returns {id, url}
    print("\n[TEST 2] A POST /api/stickers {url:'https://example.com/s1.png'} → 200")
    resp = requests.post(f"{BASE_URL}/stickers", 
                        json={"url": "https://example.com/s1.png"}, 
                        headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        sticker_data = resp.json()
        sticker_id = sticker_data.get("id")
        sticker_url = sticker_data.get("url")
        print(f"  Sticker ID: {sticker_id}")
        print(f"  Sticker URL: {sticker_url}")
        if sticker_id and sticker_url == "https://example.com/s1.png":
            print("  ✅ PASS: 200, sticker created with id and url")
        else:
            print(f"  ❌ FAIL: Missing id or url mismatch")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"  Response: {resp.text}")
        sys.exit(1)
    
    # Test 3: A GET /api/stickers → 1 item
    print("\n[TEST 3] A GET /api/stickers → 1 item")
    resp = requests.get(f"{BASE_URL}/stickers", headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        stickers = resp.json()
        print(f"  Stickers count: {len(stickers)}")
        if len(stickers) == 1:
            print("  ✅ PASS: 1 sticker in list")
        else:
            print(f"  ❌ FAIL: Expected 1 item, got {len(stickers)}")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 4: A DELETE /api/stickers/{id} → 200; then DELETE same id again → 404
    print("\n[TEST 4] A DELETE /api/stickers/{id} → 200; then DELETE same id again → 404")
    resp = requests.delete(f"{BASE_URL}/stickers/{sticker_id}", headers=headers_a)
    print(f"  First DELETE status: {resp.status_code}")
    if resp.status_code == 200:
        print("  ✅ First DELETE: 200")
        # Try deleting same id again
        resp2 = requests.delete(f"{BASE_URL}/stickers/{sticker_id}", headers=headers_a)
        print(f"  Second DELETE status: {resp2.status_code}")
        if resp2.status_code == 404:
            print("  ✅ PASS: Second DELETE → 404 (already deleted)")
        else:
            print(f"  ❌ FAIL: Expected 404, got {resp2.status_code}")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
    
    # Test 5: A POST /api/stickers {url:''} → 400
    print("\n[TEST 5] A POST /api/stickers {url:''} → 400")
    resp = requests.post(f"{BASE_URL}/stickers", 
                        json={"url": ""}, 
                        headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 400:
        print(f"  Response: {resp.json()}")
        print("  ✅ PASS: 400 (empty url rejected)")
    else:
        print(f"  ❌ FAIL: Expected 400, got {resp.status_code}")
    
    # Test 6: Sticker send in DM: A POST /api/dms/{B_handle} {media_url:'https://example.com/s1.png', media_type:'sticker'} → 200
    print("\n[TEST 6] A POST /api/dms/{B_handle} with sticker → 200")
    resp = requests.post(f"{BASE_URL}/dms/{handle_b}", 
                        json={"media_url": "https://example.com/s1.png", "media_type": "sticker"}, 
                        headers=headers_a)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        dm_data = resp.json()
        print(f"  DM sent: {dm_data.get('id')}")
        print(f"  media_type: {dm_data.get('media_type')}")
        if dm_data.get("media_type") == "sticker":
            print("  ✅ PASS: 200, sticker sent in DM")
        else:
            print(f"  ❌ FAIL: media_type not 'sticker'")
    else:
        print(f"  ❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"  Response: {resp.text}")
    
    # Test 7: GET /api/stickers with NO auth header → 401
    print("\n[TEST 7] GET /api/stickers with NO auth header → 401")
    resp = requests.get(f"{BASE_URL}/stickers")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 401:
        print("  ✅ PASS: 401 (no auth)")
    else:
        print(f"  ❌ FAIL: Expected 401, got {resp.status_code}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    main()
