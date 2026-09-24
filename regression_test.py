#!/usr/bin/env python3
"""
DEPLOYMENT-FIX REGRESSION TEST
Verifies NO regression from deployment-fix changes:
1. requirements.txt now pins click/h11/anyio/starlette
2. server.py uses os.environ.get() with safe defaults
3. startup() seeding wrapped in try/except

Test scope:
- AUTH: POST /api/dev/token, GET /api/me (200 and 401 cases)
- THREE-TIER VISIBILITY: AlphaD/BetaD - public/followers/inner post visibility
- ENCRYPTED DM: Inner circle members can send/receive decrypted DMs
- LIKES: Public posts only (400 for non-public)
- ADMIN: Admin gating (regular=403, admin=200), reporting flow
"""
import requests
import json
import sys

# Base URL from .env
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    if not passed:
        sys.exit(1)

def create_user(name):
    """Create a dev user and return (token, user_data)"""
    resp = requests.post(f"{BASE_URL}/dev/token", json={"name": name})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create user {name}: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    return data['access_token'], data['user']

def headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

print("\n" + "="*80)
print("DEPLOYMENT-FIX REGRESSION TEST")
print("="*80 + "\n")

# ============================================================================
# TEST 1: AUTH
# ============================================================================
print("TEST 1: AUTH")
print("-" * 80 + "\n")

# Test 1a: POST /api/dev/token creates user with token
alpha_token, alpha_user = create_user("RegDep")
print_test(
    "POST /api/dev/token creates user 'RegDep' with access_token",
    alpha_token and alpha_user and 'handle' in alpha_user,
    f"Token length: {len(alpha_token)}, Handle: {alpha_user.get('handle')}"
)

# Test 1b: GET /api/me with valid token returns profile (200)
me_resp = requests.get(f"{BASE_URL}/me", headers=headers(alpha_token))
print_test(
    "GET /api/me with valid token → 200",
    me_resp.status_code == 200,
    f"Status: {me_resp.status_code}"
)

if me_resp.status_code == 200:
    me_data = me_resp.json()
    print_test(
        "GET /api/me returns profile with handle",
        'handle' in me_data and me_data['handle'] == alpha_user['handle'],
        f"Handle: {me_data.get('handle')}"
    )

# Test 1c: GET /api/me without token → 401
no_auth_resp = requests.get(f"{BASE_URL}/me")
print_test(
    "GET /api/me without token → 401",
    no_auth_resp.status_code == 401,
    f"Status: {no_auth_resp.status_code}"
)

# Test 1d: GET /api/me with malformed token → 401
bad_token_resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": "Bearer invalid_token_xyz"})
print_test(
    "GET /api/me with malformed token → 401",
    bad_token_resp.status_code == 401,
    f"Status: {bad_token_resp.status_code}"
)

# ============================================================================
# TEST 2: THREE-TIER VISIBILITY
# ============================================================================
print("\n" + "="*80)
print("TEST 2: THREE-TIER VISIBILITY")
print("-" * 80 + "\n")

# Create second user
beta_token, beta_user = create_user("BetaD")
print(f"Created users: AlphaD={alpha_user['handle']}, BetaD={beta_user['handle']}")

# AlphaD creates public post
public_post_resp = requests.post(
    f"{BASE_URL}/posts",
    headers=headers(alpha_token),
    json={"tier": "public", "text": "dep regression public", "tags": ["test"]}
)
print_test(
    "AlphaD creates public post",
    public_post_resp.status_code == 200,
    f"Status: {public_post_resp.status_code}"
)
public_post = public_post_resp.json() if public_post_resp.status_code == 200 else {}

# AlphaD creates followers post
followers_post_resp = requests.post(
    f"{BASE_URL}/posts",
    headers=headers(alpha_token),
    json={"tier": "followers", "text": "dep regression followers", "tags": ["test"]}
)
print_test(
    "AlphaD creates followers post",
    followers_post_resp.status_code == 200,
    f"Status: {followers_post_resp.status_code}"
)
followers_post = followers_post_resp.json() if followers_post_resp.status_code == 200 else {}

# AlphaD creates inner post
inner_post_resp = requests.post(
    f"{BASE_URL}/posts",
    headers=headers(alpha_token),
    json={"tier": "inner", "text": "dep regression inner", "tags": ["test"]}
)
print_test(
    "AlphaD creates inner post",
    inner_post_resp.status_code == 200,
    f"Status: {inner_post_resp.status_code}"
)
inner_post = inner_post_resp.json() if inner_post_resp.status_code == 200 else {}

# BetaD (not following) sees ONLY public post via general feed
general_feed_resp = requests.get(f"{BASE_URL}/feed?scope=general", headers=headers(beta_token))
print_test(
    "BetaD GET /api/feed?scope=general → 200",
    general_feed_resp.status_code == 200,
    f"Status: {general_feed_resp.status_code}"
)

if general_feed_resp.status_code == 200:
    general_feed = general_feed_resp.json()
    alpha_posts = [p for p in general_feed if p.get('author', {}).get('handle') == alpha_user['handle']]
    alpha_tiers = [p['tier'] for p in alpha_posts]
    
    print_test(
        "BetaD (not following) sees ONLY AlphaD's public post in general feed",
        alpha_tiers == ['public'],
        f"AlphaD's visible tiers: {alpha_tiers}"
    )

# BetaD views AlphaD's profile posts - should see ONLY public
profile_posts_resp = requests.get(f"{BASE_URL}/users/{alpha_user['handle']}/posts", headers=headers(beta_token))
print_test(
    "BetaD GET /api/users/{alphaDHandle}/posts → 200",
    profile_posts_resp.status_code == 200,
    f"Status: {profile_posts_resp.status_code}"
)

if profile_posts_resp.status_code == 200:
    profile_posts = profile_posts_resp.json()
    profile_tiers = [p['tier'] for p in profile_posts]
    
    print_test(
        "BetaD sees ONLY AlphaD's public post on profile",
        profile_tiers == ['public'],
        f"Visible tiers: {profile_tiers}"
    )

# BetaD follows AlphaD (open mode -> auto-approved)
follow_resp = requests.post(f"{BASE_URL}/follow/{alpha_user['handle']}", headers=headers(beta_token))
print_test(
    "BetaD follows AlphaD",
    follow_resp.status_code == 200 and follow_resp.json().get('status') == 'approved',
    f"Status: {follow_resp.status_code}, Follow status: {follow_resp.json().get('status') if follow_resp.status_code == 200 else 'N/A'}"
)

# BetaD now sees public+followers (NOT inner)
general_feed_after_follow_resp = requests.get(f"{BASE_URL}/feed?scope=general", headers=headers(beta_token))
if general_feed_after_follow_resp.status_code == 200:
    general_feed_after = general_feed_after_follow_resp.json()
    alpha_posts_after = [p for p in general_feed_after if p.get('author', {}).get('handle') == alpha_user['handle']]
    alpha_tiers_after = sorted([p['tier'] for p in alpha_posts_after])
    
    print_test(
        "BetaD (following) sees AlphaD's public+followers posts (NOT inner)",
        alpha_tiers_after == ['followers', 'public'],
        f"AlphaD's visible tiers: {alpha_tiers_after}"
    )

# AlphaD invites BetaD to inner circle
invite_resp = requests.post(f"{BASE_URL}/inner/invite/{beta_user['handle']}", headers=headers(alpha_token))
print_test(
    "AlphaD invites BetaD to inner circle",
    invite_resp.status_code == 200,
    f"Status: {invite_resp.status_code}"
)

# BetaD accepts inner circle invite
accept_resp = requests.post(f"{BASE_URL}/inner/accept/{alpha_user['handle']}", headers=headers(beta_token))
print_test(
    "BetaD accepts AlphaD's inner circle invite",
    accept_resp.status_code == 200,
    f"Status: {accept_resp.status_code}"
)

# BetaD now sees ALL three tiers (public+followers+inner)
general_feed_after_inner_resp = requests.get(f"{BASE_URL}/feed?scope=general", headers=headers(beta_token))
if general_feed_after_inner_resp.status_code == 200:
    general_feed_inner = general_feed_after_inner_resp.json()
    alpha_posts_inner = [p for p in general_feed_inner if p.get('author', {}).get('handle') == alpha_user['handle']]
    alpha_tiers_inner = sorted([p['tier'] for p in alpha_posts_inner])
    
    print_test(
        "BetaD (inner circle) sees ALL AlphaD's posts (public+followers+inner)",
        alpha_tiers_inner == ['followers', 'inner', 'public'],
        f"AlphaD's visible tiers: {alpha_tiers_inner}"
    )

# ============================================================================
# TEST 3: ENCRYPTED DM
# ============================================================================
print("\n" + "="*80)
print("TEST 3: ENCRYPTED DM")
print("-" * 80 + "\n")

# AlphaD and BetaD are now in inner circle, so DMs are allowed
# AlphaD sends DM to BetaD
dm_send_resp = requests.post(
    f"{BASE_URL}/dms/{beta_user['handle']}",
    headers=headers(alpha_token),
    json={"text": "dep regression"}
)
print_test(
    "AlphaD POST /api/dms/{betaDHandle} with text 'dep regression' → 200",
    dm_send_resp.status_code == 200,
    f"Status: {dm_send_resp.status_code}"
)

# BetaD retrieves DM - should see decrypted message
dm_get_resp = requests.get(f"{BASE_URL}/dms/{alpha_user['handle']}", headers=headers(beta_token))
print_test(
    "BetaD GET /api/dms/{alphaDHandle} → 200",
    dm_get_resp.status_code == 200,
    f"Status: {dm_get_resp.status_code}"
)

if dm_get_resp.status_code == 200:
    dm_data = dm_get_resp.json()
    
    print_test(
        "BetaD sees can_dm=true",
        dm_data.get('can_dm') == True,
        f"can_dm={dm_data.get('can_dm')}"
    )
    
    messages = dm_data.get('messages', [])
    message_texts = [msg.get('text', '') for msg in messages]
    
    print_test(
        "BetaD sees DECRYPTED message 'dep regression'",
        'dep regression' in message_texts,
        f"Messages: {message_texts}"
    )

# ============================================================================
# TEST 4: LIKES (PUBLIC ONLY)
# ============================================================================
print("\n" + "="*80)
print("TEST 4: LIKES (PUBLIC ONLY)")
print("-" * 80 + "\n")

# BetaD likes AlphaD's public post
like_public_resp = requests.post(
    f"{BASE_URL}/posts/{public_post['id']}/like",
    headers=headers(beta_token)
)
print_test(
    "BetaD likes AlphaD's public post → 200",
    like_public_resp.status_code == 200,
    f"Status: {like_public_resp.status_code}"
)

if like_public_resp.status_code == 200:
    like_data = like_public_resp.json()
    print_test(
        "Like response shows liked=true",
        like_data.get('liked') == True,
        f"liked={like_data.get('liked')}"
    )

# BetaD attempts to like AlphaD's followers post → 400
like_followers_resp = requests.post(
    f"{BASE_URL}/posts/{followers_post['id']}/like",
    headers=headers(beta_token)
)
print_test(
    "BetaD attempts to like AlphaD's followers post → 400",
    like_followers_resp.status_code == 400,
    f"Status: {like_followers_resp.status_code}"
)

# BetaD attempts to like AlphaD's inner post → 400
like_inner_resp = requests.post(
    f"{BASE_URL}/posts/{inner_post['id']}/like",
    headers=headers(beta_token)
)
print_test(
    "BetaD attempts to like AlphaD's inner post → 400",
    like_inner_resp.status_code == 400,
    f"Status: {like_inner_resp.status_code}"
)

# ============================================================================
# TEST 5: ADMIN GATING + REPORTING
# ============================================================================
print("\n" + "="*80)
print("TEST 5: ADMIN GATING + REPORTING")
print("-" * 80 + "\n")

# Create admin user
admin_token, admin_user = create_user("Admin")
print(f"Created admin user: {admin_user['handle']}")

# Verify admin has is_admin=true
admin_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(admin_token))
if admin_me_resp.status_code == 200:
    admin_me_data = admin_me_resp.json()
    is_admin = admin_me_data.get('is_admin', False)
    print_test(
        "Admin user has is_admin=true",
        is_admin,
        f"is_admin={is_admin}"
    )

# Regular user (BetaD) tries to access admin stats → 403
regular_admin_resp = requests.get(f"{BASE_URL}/admin/stats", headers=headers(beta_token))
print_test(
    "Regular user GET /api/admin/stats → 403",
    regular_admin_resp.status_code == 403,
    f"Status: {regular_admin_resp.status_code}"
)

# No token tries to access admin stats → 401
no_token_admin_resp = requests.get(f"{BASE_URL}/admin/stats")
print_test(
    "No token GET /api/admin/stats → 401",
    no_token_admin_resp.status_code == 401,
    f"Status: {no_token_admin_resp.status_code}"
)

# Admin user accesses admin stats → 200
admin_stats_resp = requests.get(f"{BASE_URL}/admin/stats", headers=headers(admin_token))
print_test(
    "Admin user GET /api/admin/stats → 200",
    admin_stats_resp.status_code == 200,
    f"Status: {admin_stats_resp.status_code}"
)

if admin_stats_resp.status_code == 200:
    stats_data = admin_stats_resp.json()
    print_test(
        "Admin stats returns numeric counts",
        'users' in stats_data and 'posts' in stats_data,
        f"users={stats_data.get('users')}, posts={stats_data.get('posts')}"
    )

# BetaD reports AlphaD's public post
report_resp = requests.post(
    f"{BASE_URL}/report",
    headers=headers(beta_token),
    json={
        "target_type": "post",
        "target_id": public_post['id'],
        "category": "spam",
        "note": "regression test report"
    }
)
print_test(
    "BetaD reports AlphaD's public post (spam category) → 200",
    report_resp.status_code == 200,
    f"Status: {report_resp.status_code}"
)

report_id = None
if report_resp.status_code == 200:
    report_data = report_resp.json()
    report_id = report_data.get('id')
    print_test(
        "Report response contains ok=true and id",
        report_data.get('ok') == True and report_id,
        f"ok={report_data.get('ok')}, id={report_id}"
    )

# Admin views open reports
reports_resp = requests.get(f"{BASE_URL}/admin/reports?status=open", headers=headers(admin_token))
print_test(
    "Admin GET /api/admin/reports?status=open → 200",
    reports_resp.status_code == 200,
    f"Status: {reports_resp.status_code}"
)

if reports_resp.status_code == 200:
    reports_data = reports_resp.json()
    # Find the report we just created
    our_report = None
    for r in reports_data:
        if r.get('id') == report_id:
            our_report = r
            break
    
    print_test(
        "Admin sees BetaD's report in open reports",
        our_report is not None,
        f"Found: {our_report is not None}"
    )
    
    if our_report:
        print_test(
            "Report shows target_user.handle=regdep (AlphaD)",
            our_report.get('target_user', {}).get('handle') == alpha_user['handle'],
            f"target_user.handle={our_report.get('target_user', {}).get('handle')}"
        )

# Admin dismisses the report
if report_id:
    dismiss_resp = requests.post(
        f"{BASE_URL}/admin/reports/{report_id}/action",
        headers=headers(admin_token),
        json={"action": "dismiss", "reason": "regression test"}
    )
    print_test(
        "Admin dismisses report → 200",
        dismiss_resp.status_code == 200,
        f"Status: {dismiss_resp.status_code}"
    )
    
    if dismiss_resp.status_code == 200:
        dismiss_data = dismiss_resp.json()
        print_test(
            "Dismiss response contains ok=true and action=dismiss",
            dismiss_data.get('ok') == True and dismiss_data.get('action') == 'dismiss',
            f"ok={dismiss_data.get('ok')}, action={dismiss_data.get('action')}"
        )

print("\n" + "="*80)
print("ALL REGRESSION TESTS PASSED ✅")
print("NO REGRESSIONS DETECTED FROM DEPLOYMENT-FIX CHANGES")
print("="*80 + "\n")
