#!/usr/bin/env python3
"""
Backend test for Discussion Boards + AI labels + banned-word filter + report categories
Tests the NEW ClanChat backend features as per test_result.md
"""
import asyncio
import aiohttp
import uuid
from datetime import datetime

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

# Test data
ADULT_DOB = "1990-01-01"
test_results = []

def log_test(step, passed, message):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {step}: {message}")
    test_results.append({"step": step, "passed": passed, "message": message})

async def register_user(session, name_suffix, dob=ADULT_DOB):
    """Register a new user and return token + handle"""
    email = f"boardtest{name_suffix}+{uuid.uuid4().hex[:8]}@example.com"
    name = f"BoardTest{name_suffix}"
    
    async with session.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": "secret123",
        "name": name,
        "dob": dob
    }) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Registration failed: {resp.status} - {text}")
        data = await resp.json()
        return data['access_token'], data['user']['handle'], data['user']['id']

async def main():
    print("=" * 80)
    print("BACKEND TEST: Discussion Boards + AI labels + banned-word filter + report categories")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        try:
            # ========== SETUP: Register users ==========
            print("\n[SETUP] Registering test users...")
            
            owner_token, owner_handle, owner_id = await register_user(session, "Owner")
            log_test("SETUP-1", True, f"Registered OWNER: {owner_handle}")
            
            follower_token, follower_handle, follower_id = await register_user(session, "Follower")
            log_test("SETUP-2", True, f"Registered FOLLOWER: {follower_handle}")
            
            stranger_token, stranger_handle, stranger_id = await register_user(session, "Stranger")
            log_test("SETUP-3", True, f"Registered STRANGER: {stranger_handle}")
            
            # Make FOLLOWER follow OWNER (open mode auto-approve)
            async with session.post(f"{BASE_URL}/follow/{owner_handle}", 
                                   headers={"Authorization": f"Bearer {follower_token}"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    log_test("SETUP-4", data.get('status') == 'approved', 
                            f"FOLLOWER follows OWNER: status={data.get('status')}")
                else:
                    log_test("SETUP-4", False, f"Follow failed: {resp.status}")
            
            # ========== BOARDS TESTS ==========
            print("\n[BOARDS] Testing Discussion Boards...")
            
            # Test 1: OWNER creates public board
            print("\n--- Test 1: OWNER creates public board ---")
            async with session.post(f"{BASE_URL}/boards", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={"title": "General", "description": "chat", "tier": "public"}) as resp:
                if resp.status == 200:
                    board_data = await resp.json()
                    public_board_id = board_data['id']
                    log_test("BOARDS-1a", True, f"OWNER created public board: id={public_board_id}")
                    log_test("BOARDS-1b", board_data.get('is_owner') == True, 
                            f"is_owner={board_data.get('is_owner')}")
                    log_test("BOARDS-1c", board_data.get('can_post') == True, 
                            f"can_post={board_data.get('can_post')}")
                else:
                    text = await resp.text()
                    log_test("BOARDS-1", False, f"Failed to create board: {resp.status} - {text}")
                    return
            
            # Test 2: OWNER tries to create board with banned word in title
            print("\n--- Test 2: Banned word in board title ---")
            async with session.post(f"{BASE_URL}/boards", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={"title": "retards only"}) as resp:
                if resp.status == 400:
                    text = await resp.text()
                    log_test("BOARDS-2", True, f"Banned word rejected: {resp.status}")
                else:
                    log_test("BOARDS-2", False, f"Expected 400, got {resp.status}")
            
            # Test 3: STRANGER can read public board but can_post=false
            print("\n--- Test 3: STRANGER reads public board ---")
            async with session.get(f"{BASE_URL}/board/{public_board_id}", 
                                  headers={"Authorization": f"Bearer {stranger_token}"}) as resp:
                if resp.status == 200:
                    board_data = await resp.json()
                    log_test("BOARDS-3a", True, f"STRANGER can read public board")
                    log_test("BOARDS-3b", board_data.get('can_post') == False, 
                            f"can_post={board_data.get('can_post')} (should be False for non-followers)")
                else:
                    text = await resp.text()
                    log_test("BOARDS-3", False, f"Failed to read board: {resp.status} - {text}")
            
            # Test 4: STRANGER tries to post on public board (should fail - T1 read-only for non-followers)
            print("\n--- Test 4: STRANGER tries to post (should fail) ---")
            async with session.post(f"{BASE_URL}/board/{public_board_id}/posts", 
                                   headers={"Authorization": f"Bearer {stranger_token}"},
                                   json={"text": "hi"}) as resp:
                if resp.status == 403:
                    log_test("BOARDS-4", True, f"STRANGER blocked from posting: {resp.status}")
                else:
                    log_test("BOARDS-4", False, f"Expected 403, got {resp.status}")
            
            # Test 5: FOLLOWER can post on public board
            print("\n--- Test 5: FOLLOWER posts on public board ---")
            async with session.get(f"{BASE_URL}/board/{public_board_id}", 
                                  headers={"Authorization": f"Bearer {follower_token}"}) as resp:
                if resp.status == 200:
                    board_data = await resp.json()
                    log_test("BOARDS-5a", board_data.get('can_post') == True, 
                            f"FOLLOWER can_post={board_data.get('can_post')}")
                else:
                    log_test("BOARDS-5a", False, f"Failed to read board: {resp.status}")
            
            async with session.post(f"{BASE_URL}/board/{public_board_id}/posts", 
                                   headers={"Authorization": f"Bearer {follower_token}"},
                                   json={"text": "hello board"}) as resp:
                if resp.status == 200:
                    post_data = await resp.json()
                    follower_post_id = post_data['id']
                    log_test("BOARDS-5b", True, f"FOLLOWER posted: id={follower_post_id}")
                else:
                    text = await resp.text()
                    log_test("BOARDS-5b", False, f"Failed to post: {resp.status} - {text}")
            
            # Test 6: FOLLOWER tries to post with banned word
            print("\n--- Test 6: Banned word in post text ---")
            async with session.post(f"{BASE_URL}/board/{public_board_id}/posts", 
                                   headers={"Authorization": f"Bearer {follower_token}"},
                                   json={"text": "you retard"}) as resp:
                if resp.status == 400:
                    log_test("BOARDS-6", True, f"Banned word in post rejected: {resp.status}")
                else:
                    log_test("BOARDS-6", False, f"Expected 400, got {resp.status}")
            
            # Test 7: OWNER creates followers-tier board
            print("\n--- Test 7: Followers-tier board ---")
            async with session.post(f"{BASE_URL}/boards", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={"title": "Fans", "tier": "followers"}) as resp:
                if resp.status == 200:
                    followers_board = await resp.json()
                    followers_board_id = followers_board['id']
                    log_test("BOARDS-7a", True, f"OWNER created followers board: id={followers_board_id}")
                else:
                    text = await resp.text()
                    log_test("BOARDS-7a", False, f"Failed: {resp.status} - {text}")
                    return
            
            # STRANGER cannot read followers board
            async with session.get(f"{BASE_URL}/board/{followers_board_id}", 
                                  headers={"Authorization": f"Bearer {stranger_token}"}) as resp:
                if resp.status == 403:
                    log_test("BOARDS-7b", True, f"STRANGER blocked from followers board: {resp.status}")
                else:
                    log_test("BOARDS-7b", False, f"Expected 403, got {resp.status}")
            
            # FOLLOWER can read followers board
            async with session.get(f"{BASE_URL}/board/{followers_board_id}", 
                                  headers={"Authorization": f"Bearer {follower_token}"}) as resp:
                if resp.status == 200:
                    log_test("BOARDS-7c", True, f"FOLLOWER can read followers board")
                else:
                    log_test("BOARDS-7c", False, f"Expected 200, got {resp.status}")
            
            # Test 8: OWNER creates inner-tier board
            print("\n--- Test 8: Inner-tier board ---")
            async with session.post(f"{BASE_URL}/boards", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={"title": "Inner", "tier": "inner"}) as resp:
                if resp.status == 200:
                    inner_board = await resp.json()
                    inner_board_id = inner_board['id']
                    log_test("BOARDS-8a", True, f"OWNER created inner board: id={inner_board_id}")
                else:
                    text = await resp.text()
                    log_test("BOARDS-8a", False, f"Failed: {resp.status} - {text}")
                    return
            
            # FOLLOWER (not in inner) cannot read inner board
            async with session.get(f"{BASE_URL}/board/{inner_board_id}", 
                                  headers={"Authorization": f"Bearer {follower_token}"}) as resp:
                if resp.status == 403:
                    log_test("BOARDS-8b", True, f"FOLLOWER (not inner) blocked from inner board: {resp.status}")
                else:
                    log_test("BOARDS-8b", False, f"Expected 403, got {resp.status}")
            
            # Test 9: Moderation - OWNER deletes FOLLOWER's post
            print("\n--- Test 9: Moderation ---")
            async with session.delete(f"{BASE_URL}/board-posts/{follower_post_id}", 
                                     headers={"Authorization": f"Bearer {owner_token}"}) as resp:
                if resp.status == 200:
                    log_test("BOARDS-9a", True, f"OWNER deleted FOLLOWER's post")
                else:
                    log_test("BOARDS-9a", False, f"Expected 200, got {resp.status}")
            
            # STRANGER cannot delete posts
            # First, OWNER creates a post to test deletion
            async with session.post(f"{BASE_URL}/board/{public_board_id}/posts", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={"text": "test post for deletion"}) as resp:
                if resp.status == 200:
                    test_post = await resp.json()
                    test_post_id = test_post['id']
                else:
                    log_test("BOARDS-9b", False, f"Failed to create test post")
                    return
            
            async with session.delete(f"{BASE_URL}/board-posts/{test_post_id}", 
                                     headers={"Authorization": f"Bearer {stranger_token}"}) as resp:
                if resp.status == 403:
                    log_test("BOARDS-9b", True, f"STRANGER blocked from deleting: {resp.status}")
                else:
                    log_test("BOARDS-9b", False, f"Expected 403, got {resp.status}")
            
            # Test 10: OWNER deletes board
            print("\n--- Test 10: Delete board ---")
            async with session.delete(f"{BASE_URL}/boards/{public_board_id}", 
                                     headers={"Authorization": f"Bearer {owner_token}"}) as resp:
                if resp.status == 200:
                    log_test("BOARDS-10", True, f"OWNER deleted board")
                else:
                    log_test("BOARDS-10", False, f"Expected 200, got {resp.status}")
            
            # Test 11: GET /api/boards/{handle} lists boards viewer can read
            print("\n--- Test 11: List boards ---")
            async with session.get(f"{BASE_URL}/boards/{owner_handle}", 
                                  headers={"Authorization": f"Bearer {follower_token}"}) as resp:
                if resp.status == 200:
                    boards = await resp.json()
                    log_test("BOARDS-11", True, f"Listed {len(boards)} boards for {owner_handle}")
                else:
                    log_test("BOARDS-11", False, f"Expected 200, got {resp.status}")
            
            # ========== AI LABELS TESTS ==========
            print("\n[AI LABELS] Testing AI labels on posts...")
            
            # Test 12: Post with ai_label='generated'
            print("\n--- Test 12: Post with ai_label='generated' ---")
            async with session.post(f"{BASE_URL}/posts", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={
                                       "tier": "public",
                                       "text": "art",
                                       "media_url": "https://x/y.jpg",
                                       "media_type": "image",
                                       "ai_label": "generated"
                                   }) as resp:
                if resp.status == 200:
                    post_data = await resp.json()
                    ai_post_id = post_data['id']
                    log_test("AI-12a", True, f"Created post with ai_label='generated': id={ai_post_id}")
                    log_test("AI-12b", post_data.get('ai_label') == 'generated', 
                            f"ai_label={post_data.get('ai_label')}")
                else:
                    text = await resp.text()
                    log_test("AI-12", False, f"Failed: {resp.status} - {text}")
            
            # Verify in feed
            async with session.get(f"{BASE_URL}/feed?scope=general", 
                                  headers={"Authorization": f"Bearer {owner_token}"}) as resp:
                if resp.status == 200:
                    feed = await resp.json()
                    ai_post = next((p for p in feed if p['id'] == ai_post_id), None)
                    if ai_post:
                        log_test("AI-12c", ai_post.get('ai_label') == 'generated', 
                                f"Feed shows ai_label='generated'")
                    else:
                        log_test("AI-12c", False, "Post not found in feed")
                else:
                    log_test("AI-12c", False, f"Failed to get feed: {resp.status}")
            
            # Test 13: Invalid ai_label stored as 'none'
            print("\n--- Test 13: Invalid ai_label ---")
            async with session.post(f"{BASE_URL}/posts", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={
                                       "tier": "public",
                                       "text": "z",
                                       "ai_label": "foo"
                                   }) as resp:
                if resp.status == 200:
                    post_data = await resp.json()
                    log_test("AI-13", post_data.get('ai_label') == 'none', 
                            f"Invalid ai_label stored as 'none': {post_data.get('ai_label')}")
                else:
                    log_test("AI-13", False, f"Failed: {resp.status}")
            
            # Test 14: Post with no ai_label defaults to 'none'
            print("\n--- Test 14: No ai_label defaults to 'none' ---")
            async with session.post(f"{BASE_URL}/posts", 
                                   headers={"Authorization": f"Bearer {owner_token}"},
                                   json={
                                       "tier": "public",
                                       "text": "no label"
                                   }) as resp:
                if resp.status == 200:
                    post_data = await resp.json()
                    log_test("AI-14", post_data.get('ai_label') == 'none', 
                            f"No ai_label defaults to 'none': {post_data.get('ai_label')}")
                else:
                    log_test("AI-14", False, f"Failed: {resp.status}")
            
            # ========== BANNED NAMES TESTS ==========
            print("\n[BANNED NAMES] Testing banned words in names...")
            
            # Test 15: Register with banned word in name
            print("\n--- Test 15: Register with banned name ---")
            email = f"bannedname+{uuid.uuid4().hex[:8]}@example.com"
            async with session.post(f"{BASE_URL}/auth/register", json={
                "email": email,
                "password": "secret123",
                "name": "faggot",
                "dob": ADULT_DOB
            }) as resp:
                if resp.status == 400:
                    log_test("BANNED-15", True, f"Banned name rejected at registration: {resp.status}")
                else:
                    log_test("BANNED-15", False, f"Expected 400, got {resp.status}")
            
            # Test 16: Update profile with banned display_name
            print("\n--- Test 16: Update profile with banned name ---")
            async with session.put(f"{BASE_URL}/profile", 
                                  headers={"Authorization": f"Bearer {owner_token}"},
                                  json={"display_name": "retard"}) as resp:
                if resp.status == 400:
                    log_test("BANNED-16", True, f"Banned display_name rejected: {resp.status}")
                else:
                    log_test("BANNED-16", False, f"Expected 400, got {resp.status}")
            
            # ========== REPORT CATEGORIES TESTS ==========
            print("\n[REPORT CATEGORIES] Testing report categories...")
            
            # Test 17: Valid category 'harassment'
            print("\n--- Test 17: Valid report category 'harassment' ---")
            async with session.post(f"{BASE_URL}/report", 
                                   headers={"Authorization": f"Bearer {stranger_token}"},
                                   json={
                                       "target_type": "user",
                                       "target_id": owner_handle,
                                       "category": "harassment"
                                   }) as resp:
                if resp.status == 200:
                    log_test("REPORT-17", True, f"Valid category 'harassment' accepted")
                else:
                    log_test("REPORT-17", False, f"Expected 200, got {resp.status}")
            
            # Test 18: Valid category 'impersonation'
            print("\n--- Test 18: Valid report category 'impersonation' ---")
            async with session.post(f"{BASE_URL}/report", 
                                   headers={"Authorization": f"Bearer {stranger_token}"},
                                   json={
                                       "target_type": "user",
                                       "target_id": owner_handle,
                                       "category": "impersonation"
                                   }) as resp:
                if resp.status == 200:
                    log_test("REPORT-18", True, f"Valid category 'impersonation' accepted")
                else:
                    log_test("REPORT-18", False, f"Expected 200, got {resp.status}")
            
            # Test 19: Invalid category
            print("\n--- Test 19: Invalid report category ---")
            async with session.post(f"{BASE_URL}/report", 
                                   headers={"Authorization": f"Bearer {stranger_token}"},
                                   json={
                                       "target_type": "user",
                                       "target_id": owner_handle,
                                       "category": "notacat"
                                   }) as resp:
                if resp.status == 400:
                    log_test("REPORT-19", True, f"Invalid category rejected: {resp.status}")
                else:
                    log_test("REPORT-19", False, f"Expected 400, got {resp.status}")
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if r['passed'])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total}% success rate)")
    
    if passed < total:
        print("\nFailed tests:")
        for r in test_results:
            if not r['passed']:
                print(f"  ❌ {r['step']}: {r['message']}")
    
    print("\n" + "=" * 80)
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
