#!/usr/bin/env python3
"""
Test Delete activity: DELETE /api/activity/{id} (single) + DELETE /api/activity (clear all)
Tests the NEW delete activity endpoints (single delete + clear all).
"""
import asyncio
import httpx
import uuid
from datetime import datetime

# Backend URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def random_email():
    return f"delactivity+{uuid.uuid4().hex[:8]}@example.com"

async def register_user(email: str, handle: str, dob: str = "1990-01-01"):
    """Register a new user and return their auth token and actual handle."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "handle": handle,
            "display_name": handle,
            "dob": dob
        })
        print(f"Register {handle}: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  Error: {resp.text}")
            return None, None
        data = resp.json()
        token = data.get('access_token') or data.get('token')
        actual_handle = data.get('user', {}).get('handle', handle)
        return token, actual_handle

async def test_delete_activity():
    """Test delete activity endpoints (single delete + clear all)."""
    print("\n=== DELETE ACTIVITY TEST ===\n")
    
    # Setup: Register user A + B as adult users (DOB 1990-01-01)
    print("SETUP: Register user A + B as adult users (DOB 1990-01-01)")
    a_email = random_email()
    a_handle = f"usera{uuid.uuid4().hex[:6]}"
    a_token, a_handle = await register_user(a_email, a_handle, "1990-01-01")
    if not a_token:
        print("❌ SETUP FAILED: Could not register user A\n")
        return
    print(f"✅ User A registered (handle={a_handle})")
    
    b_email = random_email()
    b_handle = f"userb{uuid.uuid4().hex[:6]}"
    b_token, b_handle = await register_user(b_email, b_handle, "1990-01-01")
    if not b_token:
        print("❌ SETUP FAILED: Could not register user B\n")
        return
    print(f"✅ User B registered (handle={b_handle})\n")
    
    headers_a = {"Authorization": f"Bearer {a_token}"}
    headers_b = {"Authorization": f"Bearer {b_token}"}
    
    # Generate activity for A: B follows A (open-follow produces a 'follow' activity for A)
    print("SETUP: B follows A to generate 'follow' activity for A")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/follow/{a_handle}", headers=headers_b)
        print(f"  B follows A: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  Error: {resp.text}")
            print("❌ SETUP FAILED: Could not create follow activity\n")
            return
        print(f"✅ B followed A (should generate 'follow' activity for A)\n")
    
    # Also generate a 'like' activity: A creates a PUBLIC post and B likes it
    print("SETUP: A creates PUBLIC post and B likes it to generate 'like' activity for A")
    post_id = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/posts", 
                                 json={"tier": "public", "text": "Test post for like activity"},
                                 headers=headers_a)
        print(f"  A creates post: {resp.status_code}")
        if resp.status_code == 200:
            post_id = resp.json().get('id')
            print(f"  Post created with id={post_id}")
        else:
            print(f"  Error: {resp.text}")
    
    if post_id:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{BASE_URL}/posts/{post_id}/like", headers=headers_b)
            print(f"  B likes A's post: {resp.status_code}")
            if resp.status_code == 200:
                print(f"✅ B liked A's post (should generate 'like' activity for A)\n")
            else:
                print(f"  Error: {resp.text}\n")
    
    # Wait a moment for activity to be created
    await asyncio.sleep(1)
    
    # TEST 1: GET /api/activity as A → list has >=1 item; capture one item's id
    print("TEST 1: GET /api/activity as A → list has >=1 item; capture one item's id")
    activity_id = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/activity", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            activities = resp.json()
            print(f"  Activities count: {len(activities)}")
            if len(activities) >= 1:
                activity_id = activities[0].get('id')
                print(f"  Captured activity id: {activity_id}")
                print(f"  Activity type: {activities[0].get('type')}")
                print("✅ TEST 1 PASSED: Activity list has >=1 item\n")
            else:
                print("❌ TEST 1 FAILED: Activity list is empty\n")
                return
        else:
            print(f"❌ TEST 1 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
            return
    
    # TEST 2: A DELETE /api/activity/{id} → 200 {ok:true}
    print(f"TEST 2: A DELETE /api/activity/{activity_id} → 200 {{ok:true}}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity/{activity_id}", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {data}")
            if data.get('ok') == True:
                print("✅ TEST 2 PASSED: Activity deleted successfully\n")
            else:
                print(f"❌ TEST 2 FAILED: Expected {{ok:true}}, got {data}\n")
        else:
            print(f"❌ TEST 2 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # TEST 3: GET /api/activity as A again → that item is gone
    print("TEST 3: GET /api/activity as A again → that item is gone")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/activity", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            activities = resp.json()
            activity_ids = [a.get('id') for a in activities]
            if activity_id not in activity_ids:
                print(f"  Deleted activity id {activity_id} is NOT in the list")
                print("✅ TEST 3 PASSED: Deleted activity is gone from the list\n")
            else:
                print(f"❌ TEST 3 FAILED: Deleted activity id {activity_id} is still in the list\n")
        else:
            print(f"❌ TEST 3 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # TEST 4: A DELETE /api/activity/{same id again} → 404
    print(f"TEST 4: A DELETE /api/activity/{activity_id} (same id again) → 404")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity/{activity_id}", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 404:
            print(f"  Response: {resp.text}")
            print("✅ TEST 4 PASSED: Deleting same activity again returns 404\n")
        else:
            print(f"❌ TEST 4 FAILED: Expected 404, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    # TEST 5: A DELETE /api/activity/{random-uuid} → 404
    print("TEST 5: A DELETE /api/activity/{random-uuid} → 404")
    random_uuid = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity/{random_uuid}", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 404:
            print(f"  Response: {resp.text}")
            print("✅ TEST 5 PASSED: Deleting random UUID returns 404\n")
        else:
            print(f"❌ TEST 5 FAILED: Expected 404, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    # TEST 6: Ownership - Get an activity id that belongs to A (if any left)
    print("TEST 6: Ownership - B DELETE /api/activity/{an id that belongs to A} → 404")
    a_activity_id = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/activity", headers=headers_a)
        if resp.status_code == 200:
            activities = resp.json()
            if len(activities) > 0:
                a_activity_id = activities[0].get('id')
                print(f"  Found A's activity id: {a_activity_id}")
            else:
                print("  No activities left for A, skipping ownership test")
    
    if a_activity_id:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(f"{BASE_URL}/activity/{a_activity_id}", headers=headers_b)
            print(f"  B tries to delete A's activity: {resp.status_code}")
            if resp.status_code == 404:
                print(f"  Response: {resp.text}")
                print("✅ TEST 6 PASSED: B cannot delete A's activity (404 - ownership enforced)\n")
            else:
                print(f"❌ TEST 6 FAILED: Expected 404, got {resp.status_code}\n")
                print(f"  Response: {resp.text}\n")
    else:
        print("⚠️  TEST 6 SKIPPED: No activities left for A\n")
    
    # Generate a couple more activity items for A for the clear all test
    print("SETUP: Generate more activity items for A")
    # A creates another post and B likes it
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/posts", 
                                 json={"tier": "public", "text": "Another test post"},
                                 headers=headers_a)
        if resp.status_code == 200:
            post_id2 = resp.json().get('id')
            print(f"  A creates another post: {post_id2}")
            resp2 = await client.post(f"{BASE_URL}/posts/{post_id2}/like", headers=headers_b)
            print(f"  B likes A's post: {resp2.status_code}")
    
    # B unfollows and follows A again to generate another follow activity
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.delete(f"{BASE_URL}/follow/{a_handle}", headers=headers_b)
        await asyncio.sleep(0.5)
        resp = await client.post(f"{BASE_URL}/follow/{a_handle}", headers=headers_b)
        print(f"  B follows A again: {resp.status_code}")
    
    await asyncio.sleep(1)
    
    # Check how many activities A has now
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/activity", headers=headers_a)
        if resp.status_code == 200:
            activities = resp.json()
            print(f"  A now has {len(activities)} activity items\n")
    
    # TEST 7: A DELETE /api/activity (clear all) → 200 {ok:true, deleted:>=1}
    print("TEST 7: A DELETE /api/activity (clear all) → 200 {ok:true, deleted:>=1}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {data}")
            if data.get('ok') == True and data.get('deleted', 0) >= 1:
                print(f"✅ TEST 7 PASSED: Clear all deleted {data.get('deleted')} activities\n")
            else:
                print(f"❌ TEST 7 FAILED: Expected {{ok:true, deleted:>=1}}, got {data}\n")
        else:
            print(f"❌ TEST 7 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # TEST 8: GET /api/activity as A → [] (empty)
    print("TEST 8: GET /api/activity as A → [] (empty)")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/activity", headers=headers_a)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            activities = resp.json()
            print(f"  Activities count: {len(activities)}")
            if len(activities) == 0:
                print("✅ TEST 8 PASSED: Activity list is empty after clear all\n")
            else:
                print(f"❌ TEST 8 FAILED: Expected empty list, got {len(activities)} activities\n")
        else:
            print(f"❌ TEST 8 FAILED: Expected 200, got {resp.status_code}\n")
            print(f"  Error: {resp.text}\n")
    
    # TEST 9: No-auth DELETE /api/activity/{id} → 401/403
    print("TEST 9: No-auth DELETE /api/activity/{random-uuid} → 401/403")
    random_uuid2 = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity/{random_uuid2}")
        print(f"  Status: {resp.status_code}")
        if resp.status_code in [401, 403]:
            print(f"  Response: {resp.text}")
            print("✅ TEST 9 PASSED: No-auth DELETE single activity returns 401/403\n")
        else:
            print(f"❌ TEST 9 FAILED: Expected 401/403, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    # TEST 10: No-auth DELETE /api/activity → 401/403
    print("TEST 10: No-auth DELETE /api/activity (clear all) → 401/403")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/activity")
        print(f"  Status: {resp.status_code}")
        if resp.status_code in [401, 403]:
            print(f"  Response: {resp.text}")
            print("✅ TEST 10 PASSED: No-auth DELETE clear all returns 401/403\n")
        else:
            print(f"❌ TEST 10 FAILED: Expected 401/403, got {resp.status_code}\n")
            print(f"  Response: {resp.text}\n")
    
    print("=== DELETE ACTIVITY TEST COMPLETE ===\n")

if __name__ == "__main__":
    asyncio.run(test_delete_activity())
