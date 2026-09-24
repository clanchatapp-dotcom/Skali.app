#!/usr/bin/env python3
"""
Regression test for DM encryption + notification banner mapping after hardening DM_ENC_KEY parser.
Tests on LOCAL sandbox backend (http://localhost:8001).

Steps:
1) Register ONE throwaway user
2) DM encryption round-trip (self-DM using own handle + own token)
3) Notification banner mapping (self-DM) with EXACT notify_preview values
4) GIF endpoint health check
"""

import requests
import random
import string
import json

BASE_URL = "http://localhost:8001/api"

def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def test_dm_enc_regression():
    print("=" * 80)
    print("DM ENCRYPTION + NOTIFICATION BANNER REGRESSION TEST")
    print("=" * 80)
    
    # Step 1: Register ONE throwaway user
    print("\n[STEP 1] Register throwaway user")
    rand_id = rand_str()
    email = f"enc+{rand_id}@example.com"
    password = "secret123"
    name = "Enc"
    dob = "1990-01-01"
    
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "dob": dob
    })
    
    print(f"  POST /api/auth/register -> {reg_resp.status_code}")
    assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.status_code} {reg_resp.text}"
    
    reg_data = reg_resp.json()
    access_token = reg_data.get("access_token")
    user_handle = reg_data.get("user", {}).get("handle")
    
    print(f"  ✓ Registered user: {email}")
    print(f"  ✓ Handle: {user_handle}")
    print(f"  ✓ Access token: {access_token[:20]}...")
    
    assert access_token, "No access_token in response"
    assert user_handle, "No user.handle in response"
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Step 2: DM encryption round-trip (self-DM)
    print("\n[STEP 2] DM encryption round-trip (self-DM)")
    
    # Send self-DM with text
    dm_text = "secret hello"
    dm_send_resp = requests.post(f"{BASE_URL}/dms/{user_handle}", 
                                  headers=headers,
                                  json={"text": dm_text})
    
    print(f"  POST /api/dms/{user_handle} {{text:'{dm_text}'}} -> {dm_send_resp.status_code}")
    assert dm_send_resp.status_code == 200, f"DM send failed: {dm_send_resp.status_code} {dm_send_resp.text}"
    
    dm_send_data = dm_send_resp.json()
    response_text = dm_send_data.get("text")
    response_notify_preview = dm_send_data.get("notify_preview")
    
    print(f"  ✓ Response text: '{response_text}'")
    print(f"  ✓ Response notify_preview: '{response_notify_preview}'")
    
    assert response_text == dm_text, f"Expected text '{dm_text}', got '{response_text}'"
    assert response_notify_preview == dm_text, f"Expected notify_preview '{dm_text}', got '{response_notify_preview}'"
    
    # Get DM history to verify decryption
    dm_history_resp = requests.get(f"{BASE_URL}/dms/{user_handle}", headers=headers)
    
    print(f"  GET /api/dms/{user_handle} -> {dm_history_resp.status_code}")
    assert dm_history_resp.status_code == 200, f"DM history failed: {dm_history_resp.status_code} {dm_history_resp.text}"
    
    dm_history_data = dm_history_resp.json()
    messages = dm_history_data.get("messages", [])
    
    assert len(messages) > 0, "No messages in DM history"
    
    last_message = messages[-1]
    decrypted_text = last_message.get("text")
    
    print(f"  ✓ Last message text (decrypted): '{decrypted_text}'")
    assert decrypted_text == dm_text, f"Expected decrypted text '{dm_text}', got '{decrypted_text}'"
    
    print("  ✅ DM encryption + decryption working correctly")
    
    # Step 3: Notification banner mapping (self-DM) - verify EXACT notify_preview values
    print("\n[STEP 3] Notification banner mapping (self-DM)")
    
    test_cases = [
        {
            "name": "IMAGE",
            "payload": {"media_url": "https://x/p.jpg", "media_type": "image"},
            "expected_notify_preview": "sent 📷"
        },
        {
            "name": "VIDEO",
            "payload": {"media_url": "https://x/v.mp4", "media_type": "video"},
            "expected_notify_preview": "sent 📹"
        },
        {
            "name": "NO-SAVE IMAGE",
            "payload": {"media_url": "https://x/p.jpg", "media_type": "image", "allow_save": False},
            "expected_notify_preview": "sent 📵"
        },
        {
            "name": "VIEW-ONCE IMAGE",
            "payload": {"media_url": "https://x/p.jpg", "media_type": "image", "view_once": True},
            "expected_notify_preview": "sent 🔥"
        },
        {
            "name": "AUDIO",
            "payload": {"media_url": "https://x/a.webm", "media_type": "audio", "duration": 5},
            "expected_notify_preview": "🎤 Voice message"
        },
        {
            "name": "TEXT",
            "payload": {"text": "hi"},
            "expected_notify_preview": "hi"
        }
    ]
    
    results = []
    for tc in test_cases:
        print(f"\n  Testing {tc['name']}:")
        print(f"    Payload: {json.dumps(tc['payload'])}")
        
        resp = requests.post(f"{BASE_URL}/dms/{user_handle}", 
                            headers=headers,
                            json=tc['payload'])
        
        print(f"    POST /api/dms/{user_handle} -> {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"    ❌ FAILED: Expected 200, got {resp.status_code}")
            print(f"    Response: {resp.text}")
            results.append({"name": tc['name'], "passed": False, "reason": f"Status {resp.status_code}"})
            continue
        
        data = resp.json()
        actual_notify_preview = data.get("notify_preview")
        expected_notify_preview = tc['expected_notify_preview']
        
        print(f"    notify_preview: '{actual_notify_preview}'")
        print(f"    Expected: '{expected_notify_preview}'")
        
        if actual_notify_preview == expected_notify_preview:
            print(f"    ✅ PASSED: EXACT match")
            results.append({"name": tc['name'], "passed": True})
        else:
            print(f"    ❌ FAILED: Expected '{expected_notify_preview}', got '{actual_notify_preview}'")
            results.append({"name": tc['name'], "passed": False, "reason": f"Expected '{expected_notify_preview}', got '{actual_notify_preview}'"})
    
    # Step 4: GIF endpoint health check
    print("\n[STEP 4] GIF endpoint health check")
    
    # Test with token
    gif_with_token_resp = requests.get(f"{BASE_URL}/giphy/search?q=cat", headers=headers)
    print(f"  GET /api/giphy/search?q=cat (with token) -> {gif_with_token_resp.status_code}")
    
    if gif_with_token_resp.status_code == 200:
        gif_data = gif_with_token_resp.json()
        print(f"  ✓ Returned {len(gif_data)} gifs")
        
        if len(gif_data) > 0:
            first_gif = gif_data[0]
            has_id = "id" in first_gif
            has_url = "url" in first_gif
            has_preview = "preview" in first_gif
            
            print(f"  ✓ First gif has id: {has_id}")
            print(f"  ✓ First gif has url: {has_url}")
            print(f"  ✓ First gif has preview: {has_preview}")
            
            assert has_id and has_url and has_preview, "GIF response missing required fields"
            print("  ✅ GIF endpoint with token: PASSED")
        else:
            print("  ❌ GIF endpoint returned empty array")
    else:
        print(f"  ❌ GIF endpoint with token failed: {gif_with_token_resp.status_code} {gif_with_token_resp.text}")
    
    # Test without token
    gif_no_token_resp = requests.get(f"{BASE_URL}/giphy/search?q=cat")
    print(f"  GET /api/giphy/search?q=cat (without token) -> {gif_no_token_resp.status_code}")
    
    if gif_no_token_resp.status_code == 401:
        print("  ✅ GIF endpoint without token: PASSED (401 as expected)")
    else:
        print(f"  ❌ GIF endpoint without token: Expected 401, got {gif_no_token_resp.status_code}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print("\n[DM ENCRYPTION ROUND-TRIP]")
    print("  ✅ PASSED: Text encryption + decryption working correctly")
    
    print("\n[NOTIFICATION BANNER MAPPING]")
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    for r in results:
        status = "✅ PASSED" if r['passed'] else f"❌ FAILED: {r.get('reason', 'Unknown')}"
        print(f"  {r['name']}: {status}")
    
    print(f"\n  Total: {passed_count}/{total_count} tests passed")
    
    print("\n[GIF ENDPOINT HEALTH]")
    if gif_with_token_resp.status_code == 200 and gif_no_token_resp.status_code == 401:
        print("  ✅ PASSED: GIF endpoint healthy (200 with token, 401 without)")
    else:
        print(f"  ❌ FAILED: GIF endpoint issues (with token: {gif_with_token_resp.status_code}, without token: {gif_no_token_resp.status_code})")
    
    print("\n" + "=" * 80)
    
    # Overall result
    all_passed = (
        passed_count == total_count and
        gif_with_token_resp.status_code == 200 and
        gif_no_token_resp.status_code == 401
    )
    
    if all_passed:
        print("✅ ALL REGRESSION TESTS PASSED")
    else:
        print("❌ SOME REGRESSION TESTS FAILED")
    
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_dm_enc_regression()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
