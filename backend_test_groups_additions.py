#!/usr/bin/env python3
"""
Backend test for ClanChat group chat additions:
1. GROUP MEDIA MESSAGES (media_url, media_type, duration)
2. READ RECEIPTS (reads object with member_id → last_read timestamp)
"""
import asyncio
import httpx
import uuid
import os

BASE_URL = os.getenv('NEXT_PUBLIC_BASE_URL', 'https://gif-troubleshoot-1.preview.emergentagent.com')
API_URL = f'{BASE_URL}/api'

async def register_user(email: str, password: str, name: str):
    """Register a new user and return token + handle + id"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{API_URL}/auth/register', json={
            'email': email,
            'password': password,
            'name': name
        })
        if resp.status_code != 200:
            raise Exception(f"Registration failed: {resp.status_code} {resp.text}")
        data = resp.json()
        token = data['access_token']
        user = data['user']
        return token, user['handle'], user['id']

async def inner_invite(token: str, target_handle: str):
    """Invite a user to inner circle"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{API_URL}/inner/invite/{target_handle}', 
                                headers={'Authorization': f'Bearer {token}'})
        if resp.status_code != 200:
            raise Exception(f"Inner invite failed: {resp.status_code} {resp.text}")
        return resp.json()

async def inner_accept(token: str, owner_handle: str):
    """Accept inner circle invite"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{API_URL}/inner/accept/{owner_handle}', 
                                headers={'Authorization': f'Bearer {token}'})
        if resp.status_code != 200:
            raise Exception(f"Inner accept failed: {resp.status_code} {resp.text}")
        return resp.json()

async def create_group(token: str, name: str, members: list):
    """Create a group"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{API_URL}/groups', 
                                headers={'Authorization': f'Bearer {token}'},
                                json={'name': name, 'members': members})
        if resp.status_code != 200:
            raise Exception(f"Create group failed: {resp.status_code} {resp.text}")
        return resp.json()

async def send_group_message(token: str, group_id: str, payload: dict):
    """Send a message to a group"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{API_URL}/groups/{group_id}/messages', 
                                headers={'Authorization': f'Bearer {token}'},
                                json=payload)
        return resp

async def get_group_detail(token: str, group_id: str):
    """Get group detail with messages and reads"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f'{API_URL}/groups/{group_id}', 
                               headers={'Authorization': f'Bearer {token}'})
        if resp.status_code != 200:
            raise Exception(f"Get group detail failed: {resp.status_code} {resp.text}")
        return resp.json()

async def main():
    print("=" * 80)
    print("CLANCHAT GROUP CHAT ADDITIONS - BACKEND TEST")
    print("=" * 80)
    
    # Generate unique identifiers
    rand = str(uuid.uuid4())[:8]
    
    # Test counters
    total_tests = 0
    passed_tests = 0
    
    try:
        # ===== SETUP: Register Owner O and Member M1 =====
        print("\n[SETUP] Registering Owner O and Member M1...")
        total_tests += 1
        
        o_email = f'groupowner+{rand}@example.com'
        m1_email = f'groupmember1+{rand}@example.com'
        
        o_token, o_handle, o_id = await register_user(o_email, 'secret123', 'Owner O')
        m1_token, m1_handle, m1_id = await register_user(m1_email, 'secret123', 'Member One')
        
        print(f"✅ Owner O registered: handle={o_handle}, id={o_id}")
        print(f"✅ Member M1 registered: handle={m1_handle}, id={m1_id}")
        passed_tests += 1
        
        # ===== SETUP: Put M1 in O's Inner Circle =====
        print("\n[SETUP] Putting M1 in O's Inner Circle...")
        total_tests += 1
        
        invite_resp = await inner_invite(o_token, m1_handle)
        print(f"✅ O invited M1 to inner circle: status={invite_resp.get('status')}")
        
        accept_resp = await inner_accept(m1_token, o_handle)
        print(f"✅ M1 accepted O's inner circle invite: status={accept_resp.get('status')}")
        passed_tests += 1
        
        # ===== TEST 1: Create Group =====
        print("\n[TEST 1] O creates group 'MediaSquad' with M1...")
        total_tests += 1
        
        group = await create_group(o_token, 'MediaSquad', [m1_handle])
        group_id = group['id']
        
        if group['name'] != 'MediaSquad':
            raise Exception(f"Group name mismatch: expected 'MediaSquad', got '{group['name']}'")
        if group['member_count'] != 2:
            raise Exception(f"Member count mismatch: expected 2, got {group['member_count']}")
        
        print(f"✅ Group created: id={group_id}, name={group['name']}, member_count={group['member_count']}")
        passed_tests += 1
        
        # ===== TEST 2: Send Audio Message (media-only, NO text) =====
        print("\n[TEST 2] O sends audio message (media-only, NO text)...")
        total_tests += 1
        
        audio_payload = {
            'media_url': 'https://example.com/v.webm',
            'media_type': 'audio',
            'duration': 4
        }
        audio_resp = await send_group_message(o_token, group_id, audio_payload)
        
        if audio_resp.status_code != 200:
            raise Exception(f"Audio message failed: {audio_resp.status_code} {audio_resp.text}")
        
        audio_msg = audio_resp.json()
        
        # Verify response fields
        if audio_msg.get('media_url') != 'https://example.com/v.webm':
            raise Exception(f"Audio media_url mismatch: {audio_msg.get('media_url')}")
        if audio_msg.get('media_type') != 'audio':
            raise Exception(f"Audio media_type mismatch: {audio_msg.get('media_type')}")
        if audio_msg.get('duration') != 4:
            raise Exception(f"Audio duration mismatch: {audio_msg.get('duration')}")
        if audio_msg.get('mine') != True:
            raise Exception(f"Audio mine flag mismatch: {audio_msg.get('mine')}")
        
        audio_msg_id = audio_msg['id']
        print(f"✅ Audio message sent: id={audio_msg_id}, media_type={audio_msg['media_type']}, duration={audio_msg['duration']}, mine={audio_msg['mine']}")
        passed_tests += 1
        
        # ===== TEST 3: Send Image Message (media-only) =====
        print("\n[TEST 3] O sends image message (media-only)...")
        total_tests += 1
        
        image_payload = {
            'media_url': 'https://example.com/p.jpg',
            'media_type': 'image'
        }
        image_resp = await send_group_message(o_token, group_id, image_payload)
        
        if image_resp.status_code != 200:
            raise Exception(f"Image message failed: {image_resp.status_code} {image_resp.text}")
        
        image_msg = image_resp.json()
        
        # Verify response fields
        if image_msg.get('media_url') != 'https://example.com/p.jpg':
            raise Exception(f"Image media_url mismatch: {image_msg.get('media_url')}")
        if image_msg.get('media_type') != 'image':
            raise Exception(f"Image media_type mismatch: {image_msg.get('media_type')}")
        if image_msg.get('mine') != True:
            raise Exception(f"Image mine flag mismatch: {image_msg.get('mine')}")
        
        image_msg_id = image_msg['id']
        print(f"✅ Image message sent: id={image_msg_id}, media_type={image_msg['media_type']}, mine={image_msg['mine']}")
        passed_tests += 1
        
        # ===== TEST 4: Empty Message Validation =====
        print("\n[TEST 4] O sends empty message (should fail with 400)...")
        total_tests += 1
        
        empty_resp = await send_group_message(o_token, group_id, {})
        
        if empty_resp.status_code != 400:
            raise Exception(f"Empty message should return 400, got {empty_resp.status_code}")
        
        print(f"✅ Empty message correctly rejected with 400: {empty_resp.json().get('detail')}")
        passed_tests += 1
        
        # ===== TEST 5: M1 retrieves group messages =====
        print("\n[TEST 5] M1 retrieves group messages...")
        total_tests += 1
        
        group_detail = await get_group_detail(m1_token, group_id)
        messages = group_detail.get('messages', [])
        
        if len(messages) != 2:
            raise Exception(f"Expected 2 messages, got {len(messages)}")
        
        # Find audio message
        audio_found = False
        image_found = False
        
        for msg in messages:
            if msg.get('media_type') == 'audio':
                audio_found = True
                if msg.get('media_url') != 'https://example.com/v.webm':
                    raise Exception(f"Audio message media_url mismatch in history: {msg.get('media_url')}")
                if msg.get('duration') != 4:
                    raise Exception(f"Audio message duration mismatch in history: {msg.get('duration')}")
                if msg.get('sender_id') != o_id:
                    raise Exception(f"Audio message sender mismatch: expected {o_id}, got {msg.get('sender_id')}")
                print(f"✅ Audio message found in history: media_type={msg['media_type']}, duration={msg['duration']}, sender={msg['sender']['handle']}")
            
            elif msg.get('media_type') == 'image':
                image_found = True
                if msg.get('media_url') != 'https://example.com/p.jpg':
                    raise Exception(f"Image message media_url mismatch in history: {msg.get('media_url')}")
                if msg.get('sender_id') != o_id:
                    raise Exception(f"Image message sender mismatch: expected {o_id}, got {msg.get('sender_id')}")
                print(f"✅ Image message found in history: media_type={msg['media_type']}, sender={msg['sender']['handle']}")
        
        if not audio_found:
            raise Exception("Audio message not found in M1's message history")
        if not image_found:
            raise Exception("Image message not found in M1's message history")
        
        passed_tests += 1
        
        # ===== TEST 6: Read Receipts - Initial State =====
        print("\n[TEST 6] Checking read receipts after M1 opened the group...")
        total_tests += 1
        
        # M1 already opened the group in TEST 5, so M1's read marker should be set
        # Now O retrieves the group to check reads
        o_group_detail = await get_group_detail(o_token, group_id)
        reads = o_group_detail.get('reads', {})
        
        if not reads:
            raise Exception("'reads' object not found in group detail response")
        
        # Check that reads contains keys for ALL members (O and M1)
        if o_id not in reads:
            raise Exception(f"Owner O's id ({o_id}) not found in reads object")
        if m1_id not in reads:
            raise Exception(f"Member M1's id ({m1_id}) not found in reads object")
        
        print(f"✅ 'reads' object contains keys for all members: O={o_id}, M1={m1_id}")
        
        # Check M1's read timestamp (should be non-empty since M1 opened the group)
        m1_read_timestamp = reads.get(m1_id)
        if not m1_read_timestamp:
            raise Exception(f"M1's read timestamp is empty, but M1 opened the group in TEST 5")
        
        print(f"✅ M1's read timestamp is non-empty: {m1_read_timestamp}")
        
        # Check O's read timestamp (should be non-empty since O just opened the group)
        o_read_timestamp = reads.get(o_id)
        if not o_read_timestamp:
            print(f"⚠️  O's read timestamp is empty (O just opened the group, but timestamp might be from before)")
        else:
            print(f"✅ O's read timestamp: {o_read_timestamp}")
        
        passed_tests += 1
        
        # ===== TEST 7: Read Receipts - Verify Structure =====
        print("\n[TEST 7] Verifying read receipts structure...")
        total_tests += 1
        
        # Verify that reads is a dict mapping member_id → timestamp string
        if not isinstance(reads, dict):
            raise Exception(f"'reads' should be a dict, got {type(reads)}")
        
        for member_id, timestamp in reads.items():
            if not isinstance(member_id, str):
                raise Exception(f"Member id should be a string, got {type(member_id)}")
            if not isinstance(timestamp, str):
                raise Exception(f"Timestamp should be a string, got {type(timestamp)}")
        
        print(f"✅ Read receipts structure is correct: dict mapping member_id (str) → timestamp (str)")
        print(f"   Reads: {reads}")
        passed_tests += 1
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # ===== SUMMARY =====
    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("=" * 80)
    
    if passed_tests == total_tests:
        print("✅ ALL TESTS PASSED - Group chat additions are working correctly!")
        return 0
    else:
        print(f"❌ {total_tests - passed_tests} test(s) failed")
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
