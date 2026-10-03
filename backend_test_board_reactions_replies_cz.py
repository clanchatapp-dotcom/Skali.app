#!/usr/bin/env python3
"""
Test script for Board reactions + threaded replies + Comfort-Zone feed filtering.
Tests PART A (Board reactions + replies) and PART B (Comfort-Zone feed filter).
"""
import requests
import uuid
import os
from datetime import datetime, timedelta

BASE_URL = os.getenv('NEXT_PUBLIC_BASE_URL', 'https://gif-troubleshoot-1.preview.emergentagent.com')
API_URL = f"{BASE_URL}/api"

# Adult DOB (1990-01-01)
ADULT_DOB = "1990-01-01"

def register_user(handle_prefix):
    """Register a new adult user and return (handle, token, user_id)."""
    rand = uuid.uuid4().hex[:8]
    handle = f"{handle_prefix}{rand}"
    email = f"{handle}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "handle": handle,
        "display_name": handle.capitalize(),
        "dob": ADULT_DOB
    }
    r = requests.post(f"{API_URL}/auth/register", json=payload)
    if r.status_code != 200:
        raise Exception(f"Register failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get('access_token') or data.get('token')
    user_id = data['user']['id']
    print(f"✓ Registered {handle} (id={user_id})")
    return handle, token, user_id

def follow_user(follower_token, target_handle):
    """Follower follows target (open mode auto-approves)."""
    r = requests.post(f"{API_URL}/follow/{target_handle}", 
                      headers={"Authorization": f"Bearer {follower_token}"})
    if r.status_code != 200:
        raise Exception(f"Follow failed: {r.status_code} {r.text}")
    data = r.json()
    print(f"✓ Follow {target_handle} → status={data.get('status')}")
    return data

def create_board(owner_token, title, tier='public'):
    """Owner creates a board."""
    r = requests.post(f"{API_URL}/boards", 
                      json={"title": title, "tier": tier},
                      headers={"Authorization": f"Bearer {owner_token}"})
    if r.status_code != 200:
        raise Exception(f"Create board failed: {r.status_code} {r.text}")
    data = r.json()
    board_id = data['id']
    print(f"✓ Created board '{title}' (tier={tier}, id={board_id})")
    return board_id

def create_board_post(token, board_id, text, parent_id=None):
    """Create a board post (or reply if parent_id is set)."""
    payload = {"text": text}
    if parent_id:
        payload["parent_id"] = parent_id
    r = requests.post(f"{API_URL}/board/{board_id}/posts",
                      json=payload,
                      headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Create board post failed: {r.status_code} {r.text}")
    data = r.json()
    post_id = data['id']
    verb = "reply" if parent_id else "post"
    print(f"✓ Created {verb} on board {board_id} (post_id={post_id})")
    return post_id, data

def get_board(token, board_id):
    """Get board details with posts."""
    r = requests.get(f"{API_URL}/board/{board_id}",
                     headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Get board failed: {r.status_code} {r.text}")
    return r.json()

def react_board_post(token, post_id, emoji):
    """React to a board post."""
    r = requests.post(f"{API_URL}/board-posts/{post_id}/react",
                      json={"emoji": emoji},
                      headers={"Authorization": f"Bearer {token}"})
    return r

def delete_board_post(token, post_id):
    """Delete a board post."""
    r = requests.delete(f"{API_URL}/board-posts/{post_id}",
                        headers={"Authorization": f"Bearer {token}"})
    return r

def create_post(token, text, tier='public', media_url=None, media_type=None, ai_label=None):
    """Create a regular post."""
    payload = {"text": text, "tier": tier}
    if media_url:
        payload["media_url"] = media_url
    if media_type:
        payload["media_type"] = media_type
    if ai_label:
        payload["ai_label"] = ai_label
    r = requests.post(f"{API_URL}/posts",
                      json=payload,
                      headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Create post failed: {r.status_code} {r.text}")
    data = r.json()
    print(f"✓ Created post (id={data['id']}, ai_label={data.get('ai_label', 'none')})")
    return data['id'], data

def update_profile(token, **kwargs):
    """Update profile (e.g., comfort_zone)."""
    r = requests.put(f"{API_URL}/profile",
                     json=kwargs,
                     headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Update profile failed: {r.status_code} {r.text}")
    print(f"✓ Updated profile: {kwargs}")
    return r.json()

def get_feed(token, scope='general'):
    """Get feed."""
    r = requests.get(f"{API_URL}/feed?scope={scope}",
                     headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise Exception(f"Get feed failed: {r.status_code} {r.text}")
    return r.json()

def invite_inner(owner_token, target_handle):
    """Owner invites target to inner circle."""
    r = requests.post(f"{API_URL}/inner/invite/{target_handle}",
                      headers={"Authorization": f"Bearer {owner_token}"})
    if r.status_code != 200:
        raise Exception(f"Inner invite failed: {r.status_code} {r.text}")
    print(f"✓ Invited {target_handle} to inner circle")
    return r.json()

def accept_inner(member_token, owner_handle):
    """Member accepts inner circle invite."""
    r = requests.post(f"{API_URL}/inner/accept/{owner_handle}",
                      headers={"Authorization": f"Bearer {member_token}"})
    if r.status_code != 200:
        raise Exception(f"Inner accept failed: {r.status_code} {r.text}")
    print(f"✓ Accepted inner circle invite from {owner_handle}")
    return r.json()

def main():
    print("=" * 80)
    print("BOARD REACTIONS + THREADED REPLIES + COMFORT-ZONE FEED FILTERING TEST")
    print("=" * 80)
    
    results = []
    
    # ========== PART A: BOARDS (reactions + replies) ==========
    print("\n" + "=" * 80)
    print("PART A: BOARDS (reactions + replies)")
    print("=" * 80)
    
    # Setup: OWNER, FOLLOWER, STRANGER
    print("\n--- SETUP ---")
    owner_handle, owner_token, owner_id = register_user("boardowner")
    follower_handle, follower_token, follower_id = register_user("boardfollower")
    stranger_handle, stranger_token, stranger_id = register_user("boardstranger")
    
    # FOLLOWER follows OWNER (open mode auto-approves)
    follow_user(follower_token, owner_handle)
    
    # Test 1: OWNER creates public board
    print("\n--- TEST 1: OWNER creates public board ---")
    try:
        board_id = create_board(owner_token, "QA Board", tier='public')
        results.append(("1. OWNER creates public board", "PASS", "200, board created"))
    except Exception as e:
        results.append(("1. OWNER creates public board", "FAIL", str(e)))
    
    # Test 2: OWNER posts on board
    print("\n--- TEST 2: OWNER posts on board ---")
    try:
        p1_id, p1_data = create_board_post(owner_token, board_id, "top post")
        if p1_data.get('parent_id') is None:
            results.append(("2. OWNER posts 'top post'", "PASS", f"200, post_id={p1_id}, parent_id=None"))
        else:
            results.append(("2. OWNER posts 'top post'", "FAIL", f"parent_id should be None, got {p1_data.get('parent_id')}"))
    except Exception as e:
        results.append(("2. OWNER posts 'top post'", "FAIL", str(e)))
    
    # Test 3: FOLLOWER replies to P1
    print("\n--- TEST 3: FOLLOWER replies to P1 ---")
    try:
        reply_id, reply_data = create_board_post(follower_token, board_id, "a reply", parent_id=p1_id)
        if reply_data.get('parent_id') == p1_id:
            results.append(("3. FOLLOWER replies to P1", "PASS", f"200, reply_id={reply_id}, parent_id={p1_id}"))
        else:
            results.append(("3. FOLLOWER replies to P1", "FAIL", f"parent_id mismatch: expected {p1_id}, got {reply_data.get('parent_id')}"))
    except Exception as e:
        results.append(("3. FOLLOWER replies to P1", "FAIL", str(e)))
    
    # Test 4: FOLLOWER tries to reply to nonexistent parent
    print("\n--- TEST 4: FOLLOWER replies to nonexistent parent ---")
    try:
        r = requests.post(f"{API_URL}/board/{board_id}/posts",
                          json={"text": "bad", "parent_id": "nonexistent"},
                          headers={"Authorization": f"Bearer {follower_token}"})
        if r.status_code == 404:
            results.append(("4. Reply to nonexistent parent", "PASS", "404 as expected"))
        else:
            results.append(("4. Reply to nonexistent parent", "FAIL", f"Expected 404, got {r.status_code}"))
    except Exception as e:
        results.append(("4. Reply to nonexistent parent", "FAIL", str(e)))
    
    # Test 5: GET board shows P1 as top-level with replies nested
    print("\n--- TEST 5: GET board shows P1 as top-level with replies nested ---")
    try:
        board_data = get_board(owner_token, board_id)
        posts = board_data.get('posts', [])
        # Find P1 in top-level posts
        p1_found = None
        for post in posts:
            if post['id'] == p1_id:
                p1_found = post
                break
        
        if not p1_found:
            results.append(("5. GET board structure", "FAIL", "P1 not found in top-level posts"))
        elif p1_found.get('parent_id') is not None:
            results.append(("5. GET board structure", "FAIL", f"P1 should have parent_id=None, got {p1_found.get('parent_id')}"))
        else:
            # Check if reply is nested under P1
            replies = p1_found.get('replies', [])
            reply_found = any(r['id'] == reply_id for r in replies)
            if reply_found:
                # Check that reply is NOT a separate top-level entry
                reply_in_top = any(p['id'] == reply_id for p in posts)
                if reply_in_top:
                    results.append(("5. GET board structure", "FAIL", "Reply found as separate top-level entry (should be nested only)"))
                else:
                    results.append(("5. GET board structure", "PASS", "P1 is top-level with reply nested in replies[]"))
            else:
                results.append(("5. GET board structure", "FAIL", f"Reply {reply_id} not found in P1.replies[]"))
    except Exception as e:
        results.append(("5. GET board structure", "FAIL", str(e)))
    
    # Test 6: FOLLOWER reacts 'like' to P1
    print("\n--- TEST 6: FOLLOWER reacts 'like' to P1 ---")
    try:
        r = react_board_post(follower_token, p1_id, 'like')
        if r.status_code == 200:
            data = r.json()
            counts = data.get('counts', {})
            mine = data.get('mine')
            if counts.get('like') == 1 and mine == 'like':
                results.append(("6. FOLLOWER reacts 'like'", "PASS", "200, counts.like=1, mine='like'"))
            else:
                results.append(("6. FOLLOWER reacts 'like'", "FAIL", f"Expected counts.like=1 and mine='like', got counts={counts}, mine={mine}"))
        else:
            results.append(("6. FOLLOWER reacts 'like'", "FAIL", f"Expected 200, got {r.status_code}"))
    except Exception as e:
        results.append(("6. FOLLOWER reacts 'like'", "FAIL", str(e)))
    
    # Test 7: FOLLOWER reacts 'like' again (toggle off)
    print("\n--- TEST 7: FOLLOWER reacts 'like' again (toggle off) ---")
    try:
        r = react_board_post(follower_token, p1_id, 'like')
        if r.status_code == 200:
            data = r.json()
            counts = data.get('counts', {})
            mine = data.get('mine')
            # After toggle off, 'like' should be removed
            if 'like' not in counts or counts.get('like') == 0:
                if mine is None:
                    results.append(("7. Toggle 'like' off", "PASS", "200, counts has no 'like', mine=None"))
                else:
                    results.append(("7. Toggle 'like' off", "FAIL", f"Expected mine=None, got mine={mine}"))
            else:
                results.append(("7. Toggle 'like' off", "FAIL", f"Expected 'like' removed from counts, got counts={counts}"))
        else:
            results.append(("7. Toggle 'like' off", "FAIL", f"Expected 200, got {r.status_code}"))
    except Exception as e:
        results.append(("7. Toggle 'like' off", "FAIL", str(e)))
    
    # Test 8: FOLLOWER reacts 'love'
    print("\n--- TEST 8: FOLLOWER reacts 'love' ---")
    try:
        r = react_board_post(follower_token, p1_id, 'love')
        if r.status_code == 200:
            data = r.json()
            counts = data.get('counts', {})
            mine = data.get('mine')
            if counts.get('love') == 1 and mine == 'love':
                results.append(("8. FOLLOWER reacts 'love'", "PASS", "200, counts.love=1, mine='love'"))
            else:
                results.append(("8. FOLLOWER reacts 'love'", "FAIL", f"Expected counts.love=1 and mine='love', got counts={counts}, mine={mine}"))
        else:
            results.append(("8. FOLLOWER reacts 'love'", "FAIL", f"Expected 200, got {r.status_code}"))
    except Exception as e:
        results.append(("8. FOLLOWER reacts 'love'", "FAIL", str(e)))
    
    # Test 9: Invalid emoji
    print("\n--- TEST 9: Invalid emoji 'foo' ---")
    try:
        r = react_board_post(follower_token, p1_id, 'foo')
        if r.status_code == 400:
            results.append(("9. Invalid emoji 'foo'", "PASS", "400 as expected"))
        else:
            results.append(("9. Invalid emoji 'foo'", "FAIL", f"Expected 400, got {r.status_code}"))
    except Exception as e:
        results.append(("9. Invalid emoji 'foo'", "FAIL", str(e)))
    
    # Test 10: Missing post
    print("\n--- TEST 10: React to nonexistent post ---")
    try:
        r = react_board_post(follower_token, "nonexistentid", 'like')
        if r.status_code == 404:
            results.append(("10. React to nonexistent post", "PASS", "404 as expected"))
        else:
            results.append(("10. React to nonexistent post", "FAIL", f"Expected 404, got {r.status_code}"))
    except Exception as e:
        results.append(("10. React to nonexistent post", "FAIL", str(e)))
    
    # Test 11: GET board shows P1 with reactions
    print("\n--- TEST 11: GET board shows P1 with reactions ---")
    try:
        board_data = get_board(follower_token, board_id)
        posts = board_data.get('posts', [])
        p1_found = None
        for post in posts:
            if post['id'] == p1_id:
                p1_found = post
                break
        
        if not p1_found:
            results.append(("11. GET board shows reactions", "FAIL", "P1 not found"))
        else:
            reactions = p1_found.get('reactions', {})
            counts = reactions.get('counts', {})
            mine = reactions.get('mine')
            # Should have love=1, mine='love' (from test 8)
            if counts.get('love') == 1 and mine == 'love':
                results.append(("11. GET board shows reactions", "PASS", f"P1 has reactions: counts.love=1, mine='love'"))
            else:
                results.append(("11. GET board shows reactions", "FAIL", f"Expected counts.love=1 and mine='love', got counts={counts}, mine={mine}"))
    except Exception as e:
        results.append(("11. GET board shows reactions", "FAIL", str(e)))
    
    # Test 12: ACCESS CONTROL on react (inner-tier board)
    print("\n--- TEST 12: ACCESS CONTROL on react (inner-tier board) ---")
    try:
        # OWNER creates inner-tier board
        inner_board_id = create_board(owner_token, "Inner Board", tier='inner')
        # OWNER posts P2 on inner board
        p2_id, p2_data = create_board_post(owner_token, inner_board_id, "inner post")
        
        # STRANGER (not follower, not inner) tries to react
        r_react = react_board_post(stranger_token, p2_id, 'like')
        # STRANGER also tries to GET the inner board
        r_get = requests.get(f"{API_URL}/board/{inner_board_id}",
                             headers={"Authorization": f"Bearer {stranger_token}"})
        
        if r_react.status_code == 403 and r_get.status_code == 403:
            results.append(("12. ACCESS CONTROL (inner board)", "PASS", "STRANGER gets 403 for react and GET"))
        else:
            results.append(("12. ACCESS CONTROL (inner board)", "FAIL", f"Expected 403 for both, got react={r_react.status_code}, get={r_get.status_code}"))
    except Exception as e:
        results.append(("12. ACCESS CONTROL (inner board)", "FAIL", str(e)))
    
    # Test 13: CASCADE DELETE
    print("\n--- TEST 13: CASCADE DELETE (delete P1 removes reply and reactions) ---")
    try:
        # Delete P1
        r = delete_board_post(owner_token, p1_id)
        if r.status_code != 200:
            results.append(("13. CASCADE DELETE", "FAIL", f"Delete P1 failed: {r.status_code}"))
        else:
            # GET board and verify P1 and its reply are gone
            board_data = get_board(owner_token, board_id)
            posts = board_data.get('posts', [])
            p1_found = any(p['id'] == p1_id for p in posts)
            reply_found = False
            for post in posts:
                if post['id'] == reply_id:
                    reply_found = True
                    break
                # Also check nested replies
                for r in post.get('replies', []):
                    if r['id'] == reply_id:
                        reply_found = True
                        break
            
            if not p1_found and not reply_found:
                results.append(("13. CASCADE DELETE", "PASS", "P1 and its reply are gone"))
            else:
                results.append(("13. CASCADE DELETE", "FAIL", f"P1 found={p1_found}, reply found={reply_found} (both should be False)"))
    except Exception as e:
        results.append(("13. CASCADE DELETE", "FAIL", str(e)))
    
    # ========== PART B: COMFORT-ZONE FEED FILTER ==========
    print("\n" + "=" * 80)
    print("PART B: COMFORT-ZONE FEED FILTER")
    print("=" * 80)
    
    # Setup: Author B and Viewer V (both adults)
    print("\n--- SETUP ---")
    author_b_handle, author_b_token, author_b_id = register_user("authorb")
    viewer_v_handle, viewer_v_token, viewer_v_id = register_user("viewerv")
    
    # Test 14: B creates AI-labelled public post
    print("\n--- TEST 14: B creates AI-labelled public post ---")
    try:
        ai_post_id, ai_post_data = create_post(
            author_b_token,
            text="ai art",
            tier='public',
            media_url="https://example.com/a.jpg",
            media_type='image',
            ai_label='generated'
        )
        if ai_post_data.get('ai_label') == 'generated':
            results.append(("14. B creates AI post", "PASS", f"200, post_id={ai_post_id}, ai_label='generated'"))
        else:
            results.append(("14. B creates AI post", "FAIL", f"Expected ai_label='generated', got {ai_post_data.get('ai_label')}"))
    except Exception as e:
        results.append(("14. B creates AI post", "FAIL", str(e)))
    
    # Test 15: V sets comfort_zone.ai=false, AI post NOT in feed
    print("\n--- TEST 15: V sets comfort_zone.ai=false, AI post NOT in feed ---")
    try:
        update_profile(viewer_v_token, comfort_zone={'ai': False})
        feed = get_feed(viewer_v_token, scope='general')
        ai_post_in_feed = any(p['id'] == ai_post_id for p in feed)
        if not ai_post_in_feed:
            results.append(("15. V comfort_zone.ai=false", "PASS", "B's AI post NOT in V's feed"))
        else:
            results.append(("15. V comfort_zone.ai=false", "FAIL", "B's AI post IS in V's feed (should be hidden)"))
    except Exception as e:
        results.append(("15. V comfort_zone.ai=false", "FAIL", str(e)))
    
    # Test 16: V sets comfort_zone.ai=true, AI post IS in feed
    print("\n--- TEST 16: V sets comfort_zone.ai=true, AI post IS in feed ---")
    try:
        update_profile(viewer_v_token, comfort_zone={'ai': True})
        feed = get_feed(viewer_v_token, scope='general')
        ai_post_in_feed = any(p['id'] == ai_post_id for p in feed)
        if ai_post_in_feed:
            results.append(("16. V comfort_zone.ai=true", "PASS", "B's AI post IS in V's feed"))
        else:
            results.append(("16. V comfort_zone.ai=true", "FAIL", "B's AI post NOT in V's feed (should be visible)"))
    except Exception as e:
        results.append(("16. V comfort_zone.ai=true", "FAIL", str(e)))
    
    # Test 17: OWN-POST EXEMPTION
    print("\n--- TEST 17: OWN-POST EXEMPTION (V's own AI post visible even with ai=false) ---")
    try:
        # V sets comfort_zone.ai=false
        update_profile(viewer_v_token, comfort_zone={'ai': False})
        # V creates their OWN AI post
        v_ai_post_id, v_ai_post_data = create_post(
            viewer_v_token,
            text="my ai art",
            tier='public',
            media_url="https://example.com/v_ai.jpg",
            media_type='image',
            ai_label='generated'
        )
        # V gets feed
        feed = get_feed(viewer_v_token, scope='general')
        v_ai_post_in_feed = any(p['id'] == v_ai_post_id for p in feed)
        if v_ai_post_in_feed:
            results.append(("17. OWN-POST EXEMPTION", "PASS", "V's own AI post IS visible to V (even with ai=false)"))
        else:
            results.append(("17. OWN-POST EXEMPTION", "FAIL", "V's own AI post NOT visible to V (should be exempt from filter)"))
    except Exception as e:
        results.append(("17. OWN-POST EXEMPTION", "FAIL", str(e)))
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    total = len(results)
    
    for test_name, status, detail in results:
        symbol = "✅" if status == "PASS" else "❌"
        print(f"{symbol} {test_name}: {status} - {detail}")
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {passed}/{total} PASSED, {failed}/{total} FAILED")
    print("=" * 80)
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
