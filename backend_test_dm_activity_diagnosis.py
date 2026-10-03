#!/usr/bin/env python3
"""
Diagnostic test for DMs, Activity feed, and Notifications.
Tests the exact flow requested:
1. Create two fresh adult users A and B (DOB 1990-01-01)
2. Make them able to DM (B follows A, check can_dm logic)
3. Test DM flow - send DM, check thread lists for both users
4. Test Activity flow - follow, like, check activity endpoint
5. Report exact statuses/bodies
"""

import asyncio
import httpx
import uuid
from datetime import datetime

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

async def main():
    print("=" * 80)
    print("DM + ACTIVITY + NOTIFICATIONS DIAGNOSTIC TEST")
    print("=" * 80)
    
    # Generate unique emails for fresh users
    unique_suffix = uuid.uuid4().hex[:8]
    email_a = f"usera+{unique_suffix}@example.com"
    email_b = f"userb+{unique_suffix}@example.com"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # ===== STEP 1: Create two fresh adult users A and B =====
        print("\n[STEP 1] Creating two fresh adult users A and B (DOB 1990-01-01)")
        print("-" * 80)
        
        # Register User A
        print(f"\n1.1) Registering User A: {email_a}")
        reg_a_payload = {
            "email": email_a,
            "password": "TestPass123!",
            "dob": "1990-01-01",
            "name": "User A"
        }
        print(f"REQUEST: POST {BASE_URL}/auth/register")
        print(f"BODY: {reg_a_payload}")
        
        resp_a = await client.post(f"{BASE_URL}/auth/register", json=reg_a_payload)
        print(f"STATUS: {resp_a.status_code}")
        print(f"RESPONSE: {resp_a.text}")
        
        if resp_a.status_code != 200:
            print(f"❌ FAILED to register User A: {resp_a.status_code} {resp_a.text}")
            return
        
        data_a = resp_a.json()
        token_a = data_a['access_token']
        handle_a = data_a['user']['handle']
        user_id_a = data_a['user']['id']
        print(f"✅ User A registered: handle={handle_a}, id={user_id_a}")
        
        # Register User B
        print(f"\n1.2) Registering User B: {email_b}")
        reg_b_payload = {
            "email": email_b,
            "password": "TestPass123!",
            "dob": "1990-01-01",
            "name": "User B"
        }
        print(f"REQUEST: POST {BASE_URL}/auth/register")
        print(f"BODY: {reg_b_payload}")
        
        resp_b = await client.post(f"{BASE_URL}/auth/register", json=reg_b_payload)
        print(f"STATUS: {resp_b.status_code}")
        print(f"RESPONSE: {resp_b.text}")
        
        if resp_b.status_code != 200:
            print(f"❌ FAILED to register User B: {resp_b.status_code} {resp_b.text}")
            return
        
        data_b = resp_b.json()
        token_b = data_b['access_token']
        handle_b = data_b['user']['handle']
        user_id_b = data_b['user']['id']
        print(f"✅ User B registered: handle={handle_b}, id={user_id_b}")
        
        # ===== STEP 2: Make A and B able to DM =====
        print("\n[STEP 2] Making A and B able to DM each other")
        print("-" * 80)
        print("Strategy: Use inner circle (bidirectional DM capability)")
        print("A invites B to inner circle, B accepts -> both can DM each other")
        
        # A invites B to inner circle
        print(f"\n2.1) A invites B to inner circle")
        print(f"REQUEST: POST {BASE_URL}/inner/invite/{handle_b}")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        
        resp_invite = await client.post(f"{BASE_URL}/inner/invite/{handle_b}", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_invite.status_code}")
        print(f"RESPONSE: {resp_invite.text}")
        
        if resp_invite.status_code != 200:
            print(f"❌ FAILED: A could not invite B to inner circle: {resp_invite.status_code} {resp_invite.text}")
            return
        
        print(f"✅ A invited B to inner circle")
        
        # B accepts inner circle invite
        print(f"\n2.2) B accepts A's inner circle invite")
        print(f"REQUEST: POST {BASE_URL}/inner/accept/{handle_a}")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_accept_inner = await client.post(f"{BASE_URL}/inner/accept/{handle_a}", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_accept_inner.status_code}")
        print(f"RESPONSE: {resp_accept_inner.text}")
        
        if resp_accept_inner.status_code != 200:
            print(f"❌ FAILED: B could not accept inner circle invite: {resp_accept_inner.status_code} {resp_accept_inner.text}")
            return
        
        print(f"✅ B accepted A's inner circle invite")
        
        # Verify both can DM each other
        print(f"\n2.3) Verifying A can DM B (checking B's profile from A's perspective)")
        print(f"REQUEST: GET {BASE_URL}/users/{handle_b}")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        
        resp_profile_b_from_a = await client.get(f"{BASE_URL}/users/{handle_b}", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_profile_b_from_a.status_code}")
        profile_b_from_a = resp_profile_b_from_a.json()
        print(f"RESPONSE: can_dm={profile_b_from_a.get('can_dm')}, inner_status={profile_b_from_a.get('inner_status')}")
        
        if not profile_b_from_a.get('can_dm'):
            print(f"❌ CRITICAL: A cannot DM B even after inner circle setup (can_dm=false)")
            print(f"This indicates a bug in the can_dm logic.")
            return
        
        print(f"\n2.4) Verifying B can DM A (checking A's profile from B's perspective)")
        print(f"REQUEST: GET {BASE_URL}/users/{handle_a}")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_profile_a_from_b = await client.get(f"{BASE_URL}/users/{handle_a}", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_profile_a_from_b.status_code}")
        profile_a_from_b = resp_profile_a_from_b.json()
        print(f"RESPONSE: can_dm={profile_a_from_b.get('can_dm')}, inner_status={profile_a_from_b.get('inner_status')}")
        
        if not profile_a_from_b.get('can_dm'):
            print(f"❌ CRITICAL: B cannot DM A even after inner circle setup (can_dm=false)")
            print(f"This indicates a bug in the can_dm logic.")
            return
        
        print(f"\n✅ DM setup complete: Both A and B can DM each other (can_dm=true for both)")
        
        # Also have B follow A for the activity feed test
        print(f"\n2.5) B follows A (for activity feed test)")
        print(f"REQUEST: POST {BASE_URL}/follow/{handle_a}")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_follow = await client.post(f"{BASE_URL}/follow/{handle_a}", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_follow.status_code}")
        print(f"RESPONSE: {resp_follow.text}")
        
        if resp_follow.status_code != 200:
            print(f"⚠️  WARNING: B could not follow A: {resp_follow.status_code} {resp_follow.text}")
        else:
            follow_data = resp_follow.json()
            print(f"✅ B followed A: status={follow_data.get('status')}")
        
        # ===== STEP 3: DM FLOW =====
        print("\n[STEP 3] Testing DM Flow")
        print("-" * 80)
        
        # 3.1) A sends DM to B
        print(f"\n3.1) A sends DM to B: 'hello B'")
        dm_payload = {"text": "hello B"}
        print(f"REQUEST: POST {BASE_URL}/dms/{handle_b}")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        print(f"BODY: {dm_payload}")
        
        resp_dm_send = await client.post(f"{BASE_URL}/dms/{handle_b}", json=dm_payload, headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_dm_send.status_code}")
        print(f"RESPONSE: {resp_dm_send.text}")
        
        if resp_dm_send.status_code != 200:
            print(f"❌ FAILED: A could not send DM to B: {resp_dm_send.status_code} {resp_dm_send.text}")
            return
        
        dm_data = resp_dm_send.json()
        print(f"✅ A sent DM to B: message_id={dm_data.get('id')}, text={dm_data.get('text')}")
        
        # 3.2) A gets thread list (should see thread with B)
        print(f"\n3.2) A gets DM thread list: GET /api/dms")
        print(f"REQUEST: GET {BASE_URL}/dms")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        
        resp_threads_a = await client.get(f"{BASE_URL}/dms", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_threads_a.status_code}")
        print(f"RESPONSE BODY (full):")
        print(resp_threads_a.text)
        
        if resp_threads_a.status_code != 200:
            print(f"❌ FAILED: A could not get thread list: {resp_threads_a.status_code}")
            return
        
        threads_a = resp_threads_a.json()
        print(f"\n📊 A's thread list analysis:")
        print(f"   - Type: {type(threads_a)}")
        print(f"   - Length: {len(threads_a) if isinstance(threads_a, list) else 'N/A'}")
        
        if isinstance(threads_a, list):
            if len(threads_a) == 0:
                print(f"   ❌ EMPTY ARRAY - No threads found for A")
            else:
                print(f"   ✅ Found {len(threads_a)} thread(s)")
                for i, thread in enumerate(threads_a):
                    print(f"   Thread {i+1}:")
                    print(f"      - user.handle: {thread.get('user', {}).get('handle')}")
                    print(f"      - last: {thread.get('last')}")
                    print(f"      - mine: {thread.get('mine')}")
                    print(f"      - unread: {thread.get('unread')}")
                    print(f"      - created_at: {thread.get('created_at')}")
                
                # Check if thread with B exists
                thread_with_b = next((t for t in threads_a if t.get('user', {}).get('handle') == handle_b), None)
                if thread_with_b:
                    print(f"   ✅ Thread with B found: last='{thread_with_b.get('last')}', mine={thread_with_b.get('mine')}")
                else:
                    print(f"   ❌ Thread with B NOT found in A's thread list")
        else:
            print(f"   ❌ UNEXPECTED TYPE - Expected array, got {type(threads_a)}")
        
        # 3.3) B gets thread list (should see thread with A, unread >= 1)
        print(f"\n3.3) B gets DM thread list: GET /api/dms")
        print(f"REQUEST: GET {BASE_URL}/dms")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_threads_b = await client.get(f"{BASE_URL}/dms", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_threads_b.status_code}")
        print(f"RESPONSE BODY (full):")
        print(resp_threads_b.text)
        
        if resp_threads_b.status_code != 200:
            print(f"❌ FAILED: B could not get thread list: {resp_threads_b.status_code}")
            return
        
        threads_b = resp_threads_b.json()
        print(f"\n📊 B's thread list analysis:")
        print(f"   - Type: {type(threads_b)}")
        print(f"   - Length: {len(threads_b) if isinstance(threads_b, list) else 'N/A'}")
        
        if isinstance(threads_b, list):
            if len(threads_b) == 0:
                print(f"   ❌ EMPTY ARRAY - No threads found for B")
            else:
                print(f"   ✅ Found {len(threads_b)} thread(s)")
                for i, thread in enumerate(threads_b):
                    print(f"   Thread {i+1}:")
                    print(f"      - user.handle: {thread.get('user', {}).get('handle')}")
                    print(f"      - last: {thread.get('last')}")
                    print(f"      - mine: {thread.get('mine')}")
                    print(f"      - unread: {thread.get('unread')}")
                    print(f"      - created_at: {thread.get('created_at')}")
                
                # Check if thread with A exists
                thread_with_a = next((t for t in threads_b if t.get('user', {}).get('handle') == handle_a), None)
                if thread_with_a:
                    print(f"   ✅ Thread with A found: last='{thread_with_a.get('last')}', mine={thread_with_a.get('mine')}, unread={thread_with_a.get('unread')}")
                    if thread_with_a.get('unread', 0) >= 1:
                        print(f"   ✅ Unread count is correct (>= 1)")
                    else:
                        print(f"   ⚠️  Unread count is 0 (expected >= 1)")
                else:
                    print(f"   ❌ Thread with A NOT found in B's thread list")
        else:
            print(f"   ❌ UNEXPECTED TYPE - Expected array, got {type(threads_b)}")
        
        # 3.4) B gets messages from A
        print(f"\n3.4) B gets messages from A: GET /api/dms/{handle_a}")
        print(f"REQUEST: GET {BASE_URL}/dms/{handle_a}")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_messages_b = await client.get(f"{BASE_URL}/dms/{handle_a}", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_messages_b.status_code}")
        print(f"RESPONSE BODY (full):")
        print(resp_messages_b.text)
        
        if resp_messages_b.status_code != 200:
            print(f"❌ FAILED: B could not get messages from A: {resp_messages_b.status_code}")
            return
        
        messages_b = resp_messages_b.json()
        print(f"\n📊 B's messages from A analysis:")
        print(f"   - peer.handle: {messages_b.get('peer', {}).get('handle')}")
        print(f"   - can_dm: {messages_b.get('can_dm')}")
        print(f"   - messages count: {len(messages_b.get('messages', []))}")
        
        messages_array = messages_b.get('messages', [])
        if len(messages_array) == 0:
            print(f"   ❌ EMPTY MESSAGES ARRAY - No messages found")
        else:
            print(f"   ✅ Found {len(messages_array)} message(s)")
            for i, msg in enumerate(messages_array):
                print(f"   Message {i+1}:")
                print(f"      - text: {msg.get('text')}")
                print(f"      - mine: {msg.get('mine')}")
                print(f"      - sender_id: {msg.get('sender_id')}")
            
            # Check if 'hello B' message exists
            hello_msg = next((m for m in messages_array if m.get('text') == 'hello B'), None)
            if hello_msg:
                print(f"   ✅ Message 'hello B' found in B's messages from A")
            else:
                print(f"   ❌ Message 'hello B' NOT found in B's messages from A")
        
        # ===== STEP 4: ACTIVITY / NOTIFICATIONS FLOW =====
        print("\n[STEP 4] Testing Activity / Notifications Flow")
        print("-" * 80)
        
        # 4.1) Check if B already followed A (we did this in step 2)
        print(f"\n4.1) B already followed A in step 2, checking A's activity feed")
        print(f"REQUEST: GET {BASE_URL}/activity")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        
        resp_activity_a_1 = await client.get(f"{BASE_URL}/activity", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_activity_a_1.status_code}")
        print(f"RESPONSE BODY (full):")
        print(resp_activity_a_1.text)
        
        if resp_activity_a_1.status_code != 200:
            print(f"❌ FAILED: A could not get activity feed: {resp_activity_a_1.status_code}")
            return
        
        activity_a_1 = resp_activity_a_1.json()
        print(f"\n📊 A's activity feed analysis (after B followed):")
        print(f"   - Type: {type(activity_a_1)}")
        print(f"   - Length: {len(activity_a_1) if isinstance(activity_a_1, list) else 'N/A'}")
        
        if isinstance(activity_a_1, list):
            if len(activity_a_1) == 0:
                print(f"   ❌ EMPTY ARRAY - No activity entries found for A")
            else:
                print(f"   ✅ Found {len(activity_a_1)} activity entry/entries")
                for i, entry in enumerate(activity_a_1):
                    print(f"   Entry {i+1}:")
                    print(f"      - type: {entry.get('type')}")
                    print(f"      - actor_handle: {entry.get('actor_handle')}")
                    print(f"      - text: {entry.get('text')}")
                    print(f"      - post_id: {entry.get('post_id')}")
                    print(f"      - created_at: {entry.get('created_at')}")
                
                # Check if follow entry from B exists
                follow_entry = next((e for e in activity_a_1 if e.get('type') in ['follow', 'follow_request'] and e.get('actor_handle') == handle_b), None)
                if follow_entry:
                    print(f"   ✅ Follow entry from B found: type={follow_entry.get('type')}")
                else:
                    print(f"   ⚠️  Follow entry from B NOT found in A's activity feed")
        else:
            print(f"   ❌ UNEXPECTED TYPE - Expected array, got {type(activity_a_1)}")
        
        # 4.2) A creates a public post
        print(f"\n4.2) A creates a public post")
        post_payload = {"tier": "public", "text": "Test post for likes"}
        print(f"REQUEST: POST {BASE_URL}/posts")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        print(f"BODY: {post_payload}")
        
        resp_post = await client.post(f"{BASE_URL}/posts", json=post_payload, headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_post.status_code}")
        print(f"RESPONSE: {resp_post.text}")
        
        if resp_post.status_code != 200:
            print(f"❌ FAILED: A could not create post: {resp_post.status_code} {resp_post.text}")
            return
        
        post_data = resp_post.json()
        post_id = post_data.get('id')
        print(f"✅ A created post: id={post_id}, text={post_data.get('text')}")
        
        # 4.3) B likes A's post
        print(f"\n4.3) B likes A's post")
        print(f"REQUEST: POST {BASE_URL}/posts/{post_id}/like")
        print(f"HEADERS: Authorization: Bearer {token_b}")
        
        resp_like = await client.post(f"{BASE_URL}/posts/{post_id}/like", headers={"Authorization": f"Bearer {token_b}"})
        print(f"STATUS: {resp_like.status_code}")
        print(f"RESPONSE: {resp_like.text}")
        
        if resp_like.status_code != 200:
            print(f"❌ FAILED: B could not like A's post: {resp_like.status_code} {resp_like.text}")
            return
        
        like_data = resp_like.json()
        print(f"✅ B liked A's post: liked={like_data.get('liked')}, like_count={like_data.get('like_count')}")
        
        # 4.4) A gets activity feed again (should see like entry)
        print(f"\n4.4) A gets activity feed again (should see like entry)")
        print(f"REQUEST: GET {BASE_URL}/activity")
        print(f"HEADERS: Authorization: Bearer {token_a}")
        
        resp_activity_a_2 = await client.get(f"{BASE_URL}/activity", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_activity_a_2.status_code}")
        print(f"RESPONSE BODY (full):")
        print(resp_activity_a_2.text)
        
        if resp_activity_a_2.status_code != 200:
            print(f"❌ FAILED: A could not get activity feed: {resp_activity_a_2.status_code}")
            return
        
        activity_a_2 = resp_activity_a_2.json()
        print(f"\n📊 A's activity feed analysis (after B liked post):")
        print(f"   - Type: {type(activity_a_2)}")
        print(f"   - Length: {len(activity_a_2) if isinstance(activity_a_2, list) else 'N/A'}")
        
        if isinstance(activity_a_2, list):
            if len(activity_a_2) == 0:
                print(f"   ❌ EMPTY ARRAY - No activity entries found for A")
            else:
                print(f"   ✅ Found {len(activity_a_2)} activity entry/entries")
                for i, entry in enumerate(activity_a_2):
                    print(f"   Entry {i+1}:")
                    print(f"      - type: {entry.get('type')}")
                    print(f"      - actor_handle: {entry.get('actor_handle')}")
                    print(f"      - text: {entry.get('text')}")
                    print(f"      - post_id: {entry.get('post_id')}")
                    print(f"      - created_at: {entry.get('created_at')}")
                
                # Check if like entry from B exists
                like_entry = next((e for e in activity_a_2 if e.get('type') == 'like' and e.get('actor_handle') == handle_b and e.get('post_id') == post_id), None)
                if like_entry:
                    print(f"   ✅ Like entry from B found: type={like_entry.get('type')}, post_id={like_entry.get('post_id')}")
                else:
                    print(f"   ⚠️  Like entry from B NOT found in A's activity feed")
        else:
            print(f"   ❌ UNEXPECTED TYPE - Expected array, got {type(activity_a_2)}")
        
        # 4.5) Check for notification count endpoint
        print(f"\n4.5) Checking for notification count endpoint")
        print(f"Trying: GET {BASE_URL}/notifications/count")
        
        resp_notif_count = await client.get(f"{BASE_URL}/notifications/count", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_notif_count.status_code}")
        print(f"RESPONSE: {resp_notif_count.text}")
        
        if resp_notif_count.status_code == 404:
            print(f"   ℹ️  No /notifications/count endpoint found (404)")
        elif resp_notif_count.status_code == 200:
            print(f"   ✅ /notifications/count endpoint exists")
            print(f"   RESPONSE: {resp_notif_count.json()}")
        else:
            print(f"   ⚠️  Unexpected status: {resp_notif_count.status_code}")
        
        # Try alternative endpoints
        print(f"\nTrying: GET {BASE_URL}/activity/unread")
        resp_activity_unread = await client.get(f"{BASE_URL}/activity/unread", headers={"Authorization": f"Bearer {token_a}"})
        print(f"STATUS: {resp_activity_unread.status_code}")
        if resp_activity_unread.status_code == 200:
            print(f"RESPONSE: {resp_activity_unread.text}")
        
        # ===== FINAL SUMMARY =====
        print("\n" + "=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        
        print("\n✅ DM THREAD LIST ENDPOINT (/api/dms):")
        if isinstance(threads_a, list) and isinstance(threads_b, list):
            print(f"   - A's thread list: {len(threads_a)} thread(s)")
            print(f"   - B's thread list: {len(threads_b)} thread(s)")
            
            thread_with_b_in_a = next((t for t in threads_a if t.get('user', {}).get('handle') == handle_b), None)
            thread_with_a_in_b = next((t for t in threads_b if t.get('user', {}).get('handle') == handle_a), None)
            
            if thread_with_b_in_a and thread_with_a_in_b:
                print(f"   ✅ WORKING: Both users see the DM thread correctly")
            elif not thread_with_b_in_a:
                print(f"   ❌ ISSUE: A does NOT see thread with B in thread list")
            elif not thread_with_a_in_b:
                print(f"   ❌ ISSUE: B does NOT see thread with A in thread list")
        else:
            print(f"   ❌ NOT WORKING: Thread list endpoint returned non-array response")
        
        print("\n✅ ACTIVITY ENDPOINT (/api/activity):")
        if isinstance(activity_a_2, list):
            print(f"   - A's activity feed: {len(activity_a_2)} entry/entries")
            
            follow_entry = next((e for e in activity_a_2 if e.get('type') in ['follow', 'follow_request'] and e.get('actor_handle') == handle_b), None)
            like_entry = next((e for e in activity_a_2 if e.get('type') == 'like' and e.get('actor_handle') == handle_b), None)
            
            if follow_entry and like_entry:
                print(f"   ✅ WORKING: Activity feed contains both follow and like entries")
            elif not follow_entry:
                print(f"   ⚠️  ISSUE: Activity feed does NOT contain follow entry from B")
            elif not like_entry:
                print(f"   ⚠️  ISSUE: Activity feed does NOT contain like entry from B")
        else:
            print(f"   ❌ NOT WORKING: Activity endpoint returned non-array response")
        
        print("\n✅ NOTIFICATION COUNT ENDPOINT:")
        if resp_notif_count.status_code == 404:
            print(f"   ℹ️  No dedicated /notifications/count endpoint found")
            print(f"   ℹ️  Unread notifications likely tracked via 'read' field in activity entries")
        elif resp_notif_count.status_code == 200:
            print(f"   ✅ /notifications/count endpoint exists and returns data")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
