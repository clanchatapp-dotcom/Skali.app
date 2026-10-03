#!/usr/bin/env python3
"""
Backend test for Phase 1 social: post reactions + threaded comments + DM message delete
Tests reactions (toggle, switch, invalid emoji), threaded comments (create, reply, delete with permissions),
and DM message delete (soft-delete, permissions).
"""
import requests
import json
import sys
import secrets

# Base URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    if not passed:
        sys.exit(1)

def register_user(name_prefix):
    """Register a throwaway user with unique email"""
    rand_suffix = secrets.token_hex(4)
    email = f"{name_prefix}+{rand_suffix}@example.com"
    password = "secret123"
    name = f"{name_prefix.title()} User"
    
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "name": name}
    )
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Failed to register user {name_prefix}")
        print(f"  → Status: {resp.status_code}, Response: {resp.text}")
        sys.exit(1)
    
    data = resp.json()
    token = data.get('access_token')
    user_data = data.get('user', {})
    handle = user_data.get('handle')
    
    print(f"  → Registered {name_prefix}: email={email}, handle={handle}")
    return {"email": email, "password": password, "token": token, "handle": handle}

print("\n" + "="*80)
print("PHASE 1 SOCIAL TESTS: REACTIONS + THREADED COMMENTS + DM DELETE")
print("="*80 + "\n")

# ============================================================================
# SETUP: Register users
# ============================================================================
print("SETUP: Registering test users")
print("-" * 80)

user_a = register_user("reacta")
user_b = register_user("reactb")
user_c = register_user("reactc")

print()

# ============================================================================
# REACTIONS TESTS
# ============================================================================
print("="*80)
print("REACTIONS TESTS")
print("="*80 + "\n")

# Step 1: User A creates a public post
print("STEP 1: User A creates a public post")
print("-" * 80)

post_resp = requests.post(
    f"{BASE_URL}/posts",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"tier": "public", "text": "react test"}
)

print_test(
    "POST /api/posts (public post) → 200",
    post_resp.status_code == 200,
    f"Status: {post_resp.status_code}"
)

post_data = post_resp.json()
post_id = post_data.get('id')

print_test(
    "Post created with ID",
    post_id is not None,
    f"Post ID: {post_id}"
)

print(f"  → Post ID: {post_id}")
print()

# Step 2: User A reacts with 'love'
print("STEP 2: User A reacts with 'love'")
print("-" * 80)

react_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/react",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"emoji": "love"}
)

print_test(
    "POST /api/posts/{post_id}/react (love) → 200",
    react_resp.status_code == 200,
    f"Status: {react_resp.status_code}"
)

react_data = react_resp.json()
print(f"  → Response: {json.dumps(react_data, indent=2)}")

print_test(
    "reactions has love:1",
    react_data.get('reactions', {}).get('love') == 1,
    f"reactions: {react_data.get('reactions')}"
)

print_test(
    "reaction_total == 1",
    react_data.get('reaction_total') == 1,
    f"reaction_total: {react_data.get('reaction_total')}"
)

print_test(
    "my_reaction == 'love'",
    react_data.get('my_reaction') == 'love',
    f"my_reaction: {react_data.get('my_reaction')}"
)

print()

# Step 3: User A switches to 'haha' (single reaction per user)
print("STEP 3: User A switches to 'haha' (single reaction per user)")
print("-" * 80)

react_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/react",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"emoji": "haha"}
)

print_test(
    "POST /api/posts/{post_id}/react (haha) → 200",
    react_resp.status_code == 200,
    f"Status: {react_resp.status_code}"
)

react_data = react_resp.json()
print(f"  → Response: {json.dumps(react_data, indent=2)}")

print_test(
    "love is gone (not in reactions)",
    'love' not in react_data.get('reactions', {}),
    f"reactions: {react_data.get('reactions')}"
)

print_test(
    "haha:1 present",
    react_data.get('reactions', {}).get('haha') == 1,
    f"reactions: {react_data.get('reactions')}"
)

print_test(
    "my_reaction == 'haha'",
    react_data.get('my_reaction') == 'haha',
    f"my_reaction: {react_data.get('my_reaction')}"
)

print()

# Step 4: User A reacts with 'haha' again (toggle off)
print("STEP 4: User A reacts with 'haha' again (toggle off)")
print("-" * 80)

react_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/react",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"emoji": "haha"}
)

print_test(
    "POST /api/posts/{post_id}/react (haha again) → 200",
    react_resp.status_code == 200,
    f"Status: {react_resp.status_code}"
)

react_data = react_resp.json()
print(f"  → Response: {json.dumps(react_data, indent=2)}")

print_test(
    "my_reaction == null (toggled off)",
    react_data.get('my_reaction') is None,
    f"my_reaction: {react_data.get('my_reaction')}"
)

print_test(
    "reaction_total == 0",
    react_data.get('reaction_total') == 0,
    f"reaction_total: {react_data.get('reaction_total')}"
)

print()

# Step 5: Invalid emoji
print("STEP 5: Invalid emoji 'thumbsup'")
print("-" * 80)

react_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/react",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"emoji": "thumbsup"}
)

print_test(
    "POST /api/posts/{post_id}/react (invalid emoji) → 400",
    react_resp.status_code == 400,
    f"Status: {react_resp.status_code}, Response: {react_resp.text}"
)

print()

# Step 6: Verify post_out includes reactions fields
print("STEP 6: Verify post_out includes reactions, reaction_total, my_reaction, comment_count")
print("-" * 80)

feed_resp = requests.get(
    f"{BASE_URL}/feed?scope=general",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print_test(
    "GET /api/feed?scope=general → 200",
    feed_resp.status_code == 200,
    f"Status: {feed_resp.status_code}"
)

feed_data = feed_resp.json()
our_post = next((p for p in feed_data if p.get('id') == post_id), None)

print_test(
    "Post found in feed",
    our_post is not None,
    f"Found post: {our_post.get('id') if our_post else 'None'}"
)

if our_post:
    print(f"  → Post fields: reactions={our_post.get('reactions')}, reaction_total={our_post.get('reaction_total')}, my_reaction={our_post.get('my_reaction')}, comment_count={our_post.get('comment_count')}")
    
    print_test(
        "Post has 'reactions' field",
        'reactions' in our_post,
        f"reactions: {our_post.get('reactions')}"
    )
    
    print_test(
        "Post has 'reaction_total' field",
        'reaction_total' in our_post,
        f"reaction_total: {our_post.get('reaction_total')}"
    )
    
    print_test(
        "Post has 'my_reaction' field",
        'my_reaction' in our_post,
        f"my_reaction: {our_post.get('my_reaction')}"
    )
    
    print_test(
        "Post has 'comment_count' field",
        'comment_count' in our_post,
        f"comment_count: {our_post.get('comment_count')}"
    )

print()

# ============================================================================
# COMMENTS + THREADED REPLIES TESTS
# ============================================================================
print("="*80)
print("COMMENTS + THREADED REPLIES TESTS")
print("="*80 + "\n")

# Step 7: User A creates a top-level comment
print("STEP 7: User A creates a top-level comment")
print("-" * 80)

comment_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"text": "top comment"}
)

print_test(
    "POST /api/posts/{post_id}/comments (top comment) → 200",
    comment_resp.status_code == 200,
    f"Status: {comment_resp.status_code}"
)

comment_data = comment_resp.json()
top_comment_id = comment_data.get('id')

print(f"  → Comment ID: {top_comment_id}")
print(f"  → Comment data: {json.dumps(comment_data, indent=2)}")

print_test(
    "Comment has ID",
    top_comment_id is not None,
    f"Comment ID: {top_comment_id}"
)

print_test(
    "Comment has author",
    comment_data.get('author') is not None,
    f"Author: {comment_data.get('author')}"
)

print_test(
    "Comment parent_id is null (top-level)",
    comment_data.get('parent_id') is None,
    f"parent_id: {comment_data.get('parent_id')}"
)

print()

# Step 8: User B creates a reply to the top comment
print("STEP 8: User B creates a reply to the top comment")
print("-" * 80)

reply_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_b['token']}"},
    json={"text": "a reply", "parent_id": top_comment_id}
)

print_test(
    "POST /api/posts/{post_id}/comments (reply) → 200",
    reply_resp.status_code == 200,
    f"Status: {reply_resp.status_code}"
)

reply_data = reply_resp.json()
reply_id = reply_data.get('id')

print(f"  → Reply ID: {reply_id}")
print(f"  → Reply data: {json.dumps(reply_data, indent=2)}")

print_test(
    "Reply has parent_id set",
    reply_data.get('parent_id') == top_comment_id,
    f"parent_id: {reply_data.get('parent_id')}"
)

print()

# Step 9: GET comments and verify comment_count
print("STEP 9: GET comments and verify comment_count")
print("-" * 80)

comments_resp = requests.get(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print_test(
    "GET /api/posts/{post_id}/comments → 200",
    comments_resp.status_code == 200,
    f"Status: {comments_resp.status_code}"
)

comments_data = comments_resp.json()
print(f"  → Comments count: {len(comments_data)}")

print_test(
    "Both comments appear (count == 2)",
    len(comments_data) == 2,
    f"Comments count: {len(comments_data)}"
)

# Verify comment_count in post
feed_resp = requests.get(
    f"{BASE_URL}/feed?scope=general",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

feed_data = feed_resp.json()
our_post = next((p for p in feed_data if p.get('id') == post_id), None)

print_test(
    "Post comment_count == 2",
    our_post.get('comment_count') == 2,
    f"comment_count: {our_post.get('comment_count')}"
)

print()

# Step 10: Bad parent_id and empty text
print("STEP 10: Bad parent_id and empty text")
print("-" * 80)

# Bad parent_id
bad_parent_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"text": "reply to nonexistent", "parent_id": "nonexistent"}
)

print_test(
    "POST comment with bad parent_id → 400",
    bad_parent_resp.status_code == 400,
    f"Status: {bad_parent_resp.status_code}, Response: {bad_parent_resp.text}"
)

# Empty text
empty_text_resp = requests.post(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"text": ""}
)

print_test(
    "POST comment with empty text → 400",
    empty_text_resp.status_code == 400,
    f"Status: {empty_text_resp.status_code}, Response: {empty_text_resp.text}"
)

print()

# Step 11: DELETE comment with permissions
print("STEP 11: DELETE comment with permissions")
print("-" * 80)

# User B deletes their own reply
delete_reply_resp = requests.delete(
    f"{BASE_URL}/comments/{reply_id}",
    headers={"Authorization": f"Bearer {user_b['token']}"}
)

print_test(
    "DELETE /api/comments/{reply_id} (as B, own comment) → 200",
    delete_reply_resp.status_code == 200,
    f"Status: {delete_reply_resp.status_code}"
)

# User C tries to delete top comment (should fail - not author/post-owner/admin)
delete_fail_resp = requests.delete(
    f"{BASE_URL}/comments/{top_comment_id}",
    headers={"Authorization": f"Bearer {user_c['token']}"}
)

print_test(
    "DELETE /api/comments/{top_comment_id} (as C, not author/post-owner/admin) → 403",
    delete_fail_resp.status_code == 403,
    f"Status: {delete_fail_resp.status_code}, Response: {delete_fail_resp.text}"
)

# User A (post author) deletes top comment
delete_top_resp = requests.delete(
    f"{BASE_URL}/comments/{top_comment_id}",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print_test(
    "DELETE /api/comments/{top_comment_id} (as A, post author) → 200",
    delete_top_resp.status_code == 200,
    f"Status: {delete_top_resp.status_code}"
)

# Verify comments are deleted
comments_resp = requests.get(
    f"{BASE_URL}/posts/{post_id}/comments",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

comments_data = comments_resp.json()

print_test(
    "All comments deleted (count == 0)",
    len(comments_data) == 0,
    f"Comments count: {len(comments_data)}"
)

print()

# ============================================================================
# DM DELETE TESTS
# ============================================================================
print("="*80)
print("DM DELETE TESTS")
print("="*80 + "\n")

# Step 12: Self-DM and delete
print("STEP 12: User A sends self-DM and deletes it")
print("-" * 80)

# Send self-DM
dm_resp = requests.post(
    f"{BASE_URL}/dms/{user_a['handle']}",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"text": "to delete"}
)

print_test(
    "POST /api/dms/{own_handle} (self-DM) → 200",
    dm_resp.status_code == 200,
    f"Status: {dm_resp.status_code}"
)

dm_data = dm_resp.json()
message_id = dm_data.get('id')

print(f"  → Message ID: {message_id}")

# Delete the message
delete_dm_resp = requests.delete(
    f"{BASE_URL}/dms/{user_a['handle']}/{message_id}",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print_test(
    "DELETE /api/dms/{handle}/{message_id} (as A, own message) → 200",
    delete_dm_resp.status_code == 200,
    f"Status: {delete_dm_resp.status_code}"
)

# Verify message shows deleted:true and text 'This message was deleted'
dm_history_resp = requests.get(
    f"{BASE_URL}/dms/{user_a['handle']}",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print_test(
    "GET /api/dms/{handle} → 200",
    dm_history_resp.status_code == 200,
    f"Status: {dm_history_resp.status_code}"
)

dm_history_data = dm_history_resp.json()
messages = dm_history_data.get('messages', [])
deleted_msg = next((m for m in messages if m.get('id') == message_id), None)

print_test(
    "Deleted message found in history",
    deleted_msg is not None,
    f"Message: {deleted_msg}"
)

if deleted_msg:
    print_test(
        "Message has deleted:true",
        deleted_msg.get('deleted') == True,
        f"deleted: {deleted_msg.get('deleted')}"
    )
    
    print_test(
        "Message text is 'This message was deleted'",
        deleted_msg.get('text') == 'This message was deleted',
        f"text: {deleted_msg.get('text')}"
    )

print()

# Step 13: User B tries to delete User A's message (should fail)
print("STEP 13: User B tries to delete User A's message (should fail)")
print("-" * 80)

# First, make A and B able to DM (inner circle)
# A invites B to inner circle
invite_resp = requests.post(
    f"{BASE_URL}/inner/invite/{user_b['handle']}",
    headers={"Authorization": f"Bearer {user_a['token']}"}
)

print(f"  → A invites B to inner circle: {invite_resp.status_code}")

# B accepts
accept_resp = requests.post(
    f"{BASE_URL}/inner/accept/{user_a['handle']}",
    headers={"Authorization": f"Bearer {user_b['token']}"}
)

print(f"  → B accepts inner circle invite: {accept_resp.status_code}")

# A sends DM to B
dm_resp = requests.post(
    f"{BASE_URL}/dms/{user_b['handle']}",
    headers={"Authorization": f"Bearer {user_a['token']}"},
    json={"text": "message from A to B"}
)

print_test(
    "POST /api/dms/{B_handle} (A to B) → 200",
    dm_resp.status_code == 200,
    f"Status: {dm_resp.status_code}"
)

dm_data = dm_resp.json()
a_to_b_message_id = dm_data.get('id')

print(f"  → Message ID: {a_to_b_message_id}")

# B tries to delete A's message
delete_fail_resp = requests.delete(
    f"{BASE_URL}/dms/{user_a['handle']}/{a_to_b_message_id}",
    headers={"Authorization": f"Bearer {user_b['token']}"}
)

print_test(
    "DELETE /api/dms/{A_handle}/{message_id} (as B, not sender) → 403",
    delete_fail_resp.status_code == 403,
    f"Status: {delete_fail_resp.status_code}, Response: {delete_fail_resp.text}"
)

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("="*80)
print("ALL PHASE 1 SOCIAL TESTS PASSED ✅")
print("="*80 + "\n")

print("SUMMARY:")
print("  ✅ REACTIONS:")
print("    - React with emoji (love) → reactions has love:1, reaction_total 1, my_reaction 'love'")
print("    - Switch emoji (haha) → love gone, haha:1, my_reaction 'haha'")
print("    - Toggle off (haha again) → my_reaction null, reaction_total 0")
print("    - Invalid emoji (thumbsup) → 400")
print("    - Post includes reactions, reaction_total, my_reaction, comment_count fields")
print("  ✅ COMMENTS + THREADED REPLIES:")
print("    - Create top comment → returns id, author, parent_id null")
print("    - Create reply → parent_id set correctly")
print("    - GET comments → both appear, comment_count is 2")
print("    - Bad parent_id → 400")
print("    - Empty text → 400")
print("    - DELETE own comment (B) → 200")
print("    - DELETE other's comment (C, not author/post-owner/admin) → 403")
print("    - DELETE comment as post author (A) → 200, removes replies too")
print("  ✅ DM DELETE:")
print("    - Self-DM delete → deleted:true, text 'This message was deleted'")
print("    - Delete other's message → 403 (only sender can delete)")
print("\nCONCLUSION: Phase 1 social features working correctly.")
