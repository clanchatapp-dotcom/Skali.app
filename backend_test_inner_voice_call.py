#!/usr/bin/env python3
"""
Test script for Inner-Circle Voice/Call enforcement feature.
Tests the NEW can_voice/can_call flags in GET /api/dms/{handle} and
peer permission checks in POST /api/livekit/token.
"""
import requests
import sys
import uuid
from datetime import datetime

# Backend URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def register_adult_user(prefix):
    """Register an adult user (DOB 1990-01-01) and return (handle, token)."""
    email = f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"
    handle = prefix.replace('+', '').replace('@', '')[:15]
    payload = {
        "email": email,
        "password": "secret123",
        "name": handle.capitalize(),
        "dob": "1990-01-01"  # Adult
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    if resp.status_code != 200:
        print(f"❌ FAILED to register {prefix}: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    token = data.get('access_token')
    # Get handle from /api/me
    me_resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"})
    if me_resp.status_code != 200:
        print(f"❌ FAILED to get /api/me for {prefix}: {me_resp.status_code}")
        sys.exit(1)
    handle = me_resp.json()['handle']
    print(f"✅ Registered {prefix} → handle={handle}, token={token[:20]}...")
    return handle, token

def inner_invite(owner_token, member_handle):
    """Owner invites member to inner circle."""
    resp = requests.post(f"{BASE_URL}/inner/invite/{member_handle}",
                        headers={"Authorization": f"Bearer {owner_token}"})
    if resp.status_code != 200:
        print(f"❌ FAILED inner invite: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ Owner invited {member_handle} to inner circle → status={resp.json()['status']}")
    return resp.json()

def inner_accept(member_token, owner_handle):
    """Member accepts owner's inner circle invite."""
    resp = requests.post(f"{BASE_URL}/inner/accept/{owner_handle}",
                        headers={"Authorization": f"Bearer {member_token}"})
    if resp.status_code != 200:
        print(f"❌ FAILED inner accept: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ Member accepted {owner_handle}'s inner invite → status={resp.json()['status']}")
    return resp.json()

def get_dm_flags(token, peer_handle):
    """GET /api/dms/{handle} and return (can_voice, can_call)."""
    resp = requests.get(f"{BASE_URL}/dms/{peer_handle}",
                       headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAILED GET /api/dms/{peer_handle}: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    return data.get('can_voice'), data.get('can_call')

def livekit_token(token, room, peer=None):
    """POST /api/livekit/token and return (status_code, response_json)."""
    payload = {"room": room}
    if peer:
        payload["peer"] = peer
    resp = requests.post(f"{BASE_URL}/livekit/token", json=payload,
                        headers={"Authorization": f"Bearer {token}"})
    return resp.status_code, resp.json() if resp.status_code in [200, 403, 500] else resp.text

def set_inner_perms(owner_token, member_handle, dm=None, voice=None, call=None):
    """Owner sets inner circle permissions for member."""
    payload = {}
    if dm is not None:
        payload['dm'] = dm
    if voice is not None:
        payload['voice'] = voice
    if call is not None:
        payload['call'] = call
    resp = requests.put(f"{BASE_URL}/inner/{member_handle}/perms", json=payload,
                       headers={"Authorization": f"Bearer {owner_token}"})
    if resp.status_code != 200:
        print(f"❌ FAILED set_inner_perms: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ Owner set perms for {member_handle}: {payload} → {resp.json()['perms']}")
    return resp.json()

def send_dm(token, peer_handle, text=None, media_url=None, media_type=None, duration=None):
    """POST /api/dms/{handle} to send a message."""
    payload = {}
    if text:
        payload['text'] = text
    if media_url:
        payload['media_url'] = media_url
    if media_type:
        payload['media_type'] = media_type
    if duration is not None:
        payload['duration'] = duration
    resp = requests.post(f"{BASE_URL}/dms/{peer_handle}", json=payload,
                        headers={"Authorization": f"Bearer {token}"})
    return resp.status_code, resp.json() if resp.status_code in [200, 403, 400] else resp.text

def block_user(token, target_handle):
    """POST /api/relations/{handle} {kind:'block'}."""
    resp = requests.post(f"{BASE_URL}/relations/{target_handle}", json={"kind": "block"},
                        headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAILED block: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ Blocked {target_handle}")
    return resp.json()

def main():
    print("=" * 80)
    print("INNER-CIRCLE VOICE/CALL ENFORCEMENT TEST")
    print("=" * 80)
    
    # Setup: Register OWNER and MEMBER (both adults)
    print("\n[SETUP] Registering OWNER and MEMBER (adults, DOB 1990-01-01)...")
    owner_handle, owner_token = register_adult_user("voiceowner")
    member_handle, member_token = register_adult_user("voicemember")
    
    # Put MEMBER into OWNER's Inner Circle
    print("\n[SETUP] Putting MEMBER into OWNER's Inner Circle...")
    inner_invite(owner_token, member_handle)
    inner_accept(member_token, owner_handle)
    
    # Test counters
    passed = 0
    failed = 0
    
    # ========== SCENARIO 1: BASELINE FLAGS ==========
    print("\n" + "=" * 80)
    print("SCENARIO 1: BASELINE FLAGS (can_voice=true, can_call=true)")
    print("=" * 80)
    
    # MEMBER GET /api/dms/{owner_handle}
    print(f"\n[TEST 1.1] MEMBER GET /api/dms/{owner_handle} → expect can_voice=true, can_call=true")
    can_voice, can_call = get_dm_flags(member_token, owner_handle)
    if can_voice is True and can_call is True:
        print(f"✅ PASSED: MEMBER sees can_voice={can_voice}, can_call={can_call}")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER sees can_voice={can_voice}, can_call={can_call} (expected both true)")
        failed += 1
    
    # OWNER GET /api/dms/{member_handle}
    print(f"\n[TEST 1.2] OWNER GET /api/dms/{member_handle} → expect can_voice=true, can_call=true")
    can_voice, can_call = get_dm_flags(owner_token, member_handle)
    if can_voice is True and can_call is True:
        print(f"✅ PASSED: OWNER sees can_voice={can_voice}, can_call={can_call}")
        passed += 1
    else:
        print(f"❌ FAILED: OWNER sees can_voice={can_voice}, can_call={can_call} (expected both true)")
        failed += 1
    
    # ========== SCENARIO 2: BASELINE TOKEN ==========
    print("\n" + "=" * 80)
    print("SCENARIO 2: BASELINE TOKEN (LiveKit token with peer)")
    print("=" * 80)
    
    print(f"\n[TEST 2.1] MEMBER POST /api/livekit/token {{room:'dm-test', peer:'{owner_handle}'}} → expect 200 or 500")
    status, resp = livekit_token(member_token, "dm-test", peer=owner_handle)
    if status == 200:
        print(f"✅ PASSED: MEMBER got token (200) with participant_token={resp.get('participant_token', '')[:30]}...")
        passed += 1
    elif status == 500 and 'LiveKit not configured' in str(resp):
        print(f"✅ PASSED: LiveKit not configured (500), but permission check passed (no 403)")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER got {status} {resp} (expected 200 or 500-not-configured)")
        failed += 1
    
    # ========== SCENARIO 3: CALL OFF ==========
    print("\n" + "=" * 80)
    print("SCENARIO 3: CALL OFF (owner turns off call permission)")
    print("=" * 80)
    
    print(f"\n[TEST 3.1] OWNER PUT /api/inner/{member_handle}/perms {{call:false}}")
    set_inner_perms(owner_token, member_handle, call=False)
    
    print(f"\n[TEST 3.2] MEMBER GET /api/dms/{owner_handle} → expect can_call=false, can_voice=true")
    can_voice, can_call = get_dm_flags(member_token, owner_handle)
    if can_voice is True and can_call is False:
        print(f"✅ PASSED: MEMBER sees can_voice={can_voice}, can_call={can_call}")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER sees can_voice={can_voice}, can_call={can_call} (expected can_call=false, can_voice=true)")
        failed += 1
    
    print(f"\n[TEST 3.3] MEMBER POST /api/livekit/token {{peer:'{owner_handle}'}} → expect 403 'turned off calls'")
    status, resp = livekit_token(member_token, "dm-test", peer=owner_handle)
    if status == 403 and 'turned off calls' in str(resp.get('detail', '')):
        print(f"✅ PASSED: MEMBER got 403 with detail='{resp.get('detail')}'")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER got {status} {resp} (expected 403 'turned off calls')")
        failed += 1
    
    print(f"\n[TEST 3.4] OWNER POST /api/livekit/token {{peer:'{member_handle}'}} → expect 200 or 500 (NOT 403)")
    status, resp = livekit_token(owner_token, "dm-test", peer=member_handle)
    if status in [200, 500]:
        print(f"✅ PASSED: OWNER got {status} (owner can call their member, not blocked by call perm)")
        passed += 1
    else:
        print(f"❌ FAILED: OWNER got {status} {resp} (expected 200 or 500, NOT 403)")
        failed += 1
    
    # ========== SCENARIO 4: VOICE OFF ==========
    print("\n" + "=" * 80)
    print("SCENARIO 4: VOICE OFF (owner turns off voice permission)")
    print("=" * 80)
    
    print(f"\n[TEST 4.1] OWNER PUT /api/inner/{member_handle}/perms {{voice:false, call:true}}")
    set_inner_perms(owner_token, member_handle, voice=False, call=True)
    
    print(f"\n[TEST 4.2] MEMBER GET /api/dms/{owner_handle} → expect can_voice=false, can_call=true")
    can_voice, can_call = get_dm_flags(member_token, owner_handle)
    if can_voice is False and can_call is True:
        print(f"✅ PASSED: MEMBER sees can_voice={can_voice}, can_call={can_call}")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER sees can_voice={can_voice}, can_call={can_call} (expected can_voice=false, can_call=true)")
        failed += 1
    
    print(f"\n[TEST 4.3] MEMBER POST /api/dms/{owner_handle} {{media_url:'https://example.com/v.webm', media_type:'audio', duration:3}} → expect 403 'turned off voice notes'")
    status, resp = send_dm(member_token, owner_handle, media_url='https://example.com/v.webm', media_type='audio', duration=3)
    if status == 403 and 'turned off voice notes' in str(resp.get('detail', '')):
        print(f"✅ PASSED: MEMBER got 403 with detail='{resp.get('detail')}'")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER got {status} {resp} (expected 403 'turned off voice notes')")
        failed += 1
    
    print(f"\n[TEST 4.4] MEMBER POST /api/dms/{owner_handle} {{text:'hi'}} → expect 200 (text still works)")
    status, resp = send_dm(member_token, owner_handle, text='hi')
    if status == 200:
        print(f"✅ PASSED: MEMBER sent text message (200)")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER got {status} {resp} (expected 200)")
        failed += 1
    
    # ========== SCENARIO 5: RESTORE ==========
    print("\n" + "=" * 80)
    print("SCENARIO 5: RESTORE (owner restores all permissions)")
    print("=" * 80)
    
    print(f"\n[TEST 5.1] OWNER PUT /api/inner/{member_handle}/perms {{voice:true, call:true}}")
    set_inner_perms(owner_token, member_handle, voice=True, call=True)
    
    print(f"\n[TEST 5.2] MEMBER GET /api/dms/{owner_handle} → expect can_voice=true, can_call=true")
    can_voice, can_call = get_dm_flags(member_token, owner_handle)
    if can_voice is True and can_call is True:
        print(f"✅ PASSED: MEMBER sees can_voice={can_voice}, can_call={can_call}")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER sees can_voice={can_voice}, can_call={can_call} (expected both true)")
        failed += 1
    
    # ========== SCENARIO 6: SELF CHAT ==========
    print("\n" + "=" * 80)
    print("SCENARIO 6: SELF CHAT (owner calling self)")
    print("=" * 80)
    
    print(f"\n[TEST 6.1] OWNER GET /api/dms/{owner_handle} (self) → expect can_voice=true, can_call=true")
    can_voice, can_call = get_dm_flags(owner_token, owner_handle)
    if can_voice is True and can_call is True:
        print(f"✅ PASSED: OWNER sees can_voice={can_voice}, can_call={can_call} (self chat)")
        passed += 1
    else:
        print(f"❌ FAILED: OWNER sees can_voice={can_voice}, can_call={can_call} (expected both true for self)")
        failed += 1
    
    # ========== SCENARIO 7: TOKEN NO PEER ==========
    print("\n" + "=" * 80)
    print("SCENARIO 7: TOKEN NO PEER (LiveKit token without peer)")
    print("=" * 80)
    
    print(f"\n[TEST 7.1] MEMBER POST /api/livekit/token {{room:'r'}} (no peer) → expect 200 or 500 (NOT 403)")
    status, resp = livekit_token(member_token, "r", peer=None)
    if status in [200, 500]:
        print(f"✅ PASSED: MEMBER got {status} (no peer check, not 403)")
        passed += 1
    else:
        print(f"❌ FAILED: MEMBER got {status} {resp} (expected 200 or 500, NOT 403)")
        failed += 1
    
    # ========== SCENARIO 8: BLOCK BARRIER ==========
    print("\n" + "=" * 80)
    print("SCENARIO 8: BLOCK BARRIER (blocked user cannot call)")
    print("=" * 80)
    
    print("\n[SETUP] Registering STRANGER (adult)...")
    stranger_handle, stranger_token = register_adult_user("voicestranger")
    
    print(f"\n[TEST 8.1] OWNER blocks STRANGER")
    block_user(owner_token, stranger_handle)
    
    print(f"\n[TEST 8.2] STRANGER POST /api/livekit/token {{peer:'{owner_handle}'}} → expect 403 'Call not available'")
    status, resp = livekit_token(stranger_token, "r", peer=owner_handle)
    if status == 403 and 'Call not available' in str(resp.get('detail', '')):
        print(f"✅ PASSED: STRANGER got 403 with detail='{resp.get('detail')}'")
        passed += 1
    else:
        print(f"❌ FAILED: STRANGER got {status} {resp} (expected 403 'Call not available')")
        failed += 1
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ PASSED: {passed}/15")
    print(f"❌ FAILED: {failed}/15")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Inner-Circle Voice/Call enforcement is working correctly.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the output above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
