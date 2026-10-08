#!/usr/bin/env python3
"""
Backend test for Admin Management: seeded super-admin + add/remove admins + DB allowlist
Tests the NEW admin management endpoints with seeded super-admin.
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

def register_user(email, password, name):
    """Register a user via email/password and return (token, user_data)"""
    resp = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "name": name})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not register user {email}: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    return data['access_token'], data['user']

def headers(token):
    """Return auth headers"""
    return {"Authorization": f"Bearer {token}"}

print("\n" + "="*80)
print("ADMIN MANAGEMENT: SEEDED SUPER-ADMIN + ADD/REMOVE ADMINS + DB ALLOWLIST TESTS")
print("="*80 + "\n")

# ============================================================================
# 1. SEEDED SUPER-ADMIN
# ============================================================================
print("="*80)
print("1. SEEDED SUPER-ADMIN")
print("="*80 + "\n")

print("TEST 1.1: POST /api/auth/login with admin@clanchat.app / ClanChatAdmin!2025")
print("-" * 80)

login_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": "admin@clanchat.app", "password": "ClanChatAdmin!2025"}
)
print_test(
    "POST /api/auth/login {email:'admin@clanchat.app', password:'ClanChatAdmin!2025'} → 200",
    login_resp.status_code == 200,
    f"Status: {login_resp.status_code}"
)

admin_data = login_resp.json()
admin_token = admin_data['access_token']
print(f"  → Admin token obtained: {admin_token[:50]}...")

print("\nTEST 1.2: GET /api/me with admin token -> is_admin=true")
print("-" * 80)

me_resp = requests.get(f"{BASE_URL}/me", headers=headers(admin_token))
print_test(
    "GET /api/me → 200",
    me_resp.status_code == 200,
    f"Status: {me_resp.status_code}"
)

me_data = me_resp.json()
print_test(
    "is_admin=true for seeded super-admin",
    me_data.get('is_admin') == True,
    f"is_admin: {me_data.get('is_admin')}"
)

print(f"  → Seeded admin handle: {me_data.get('handle')}")

# ============================================================================
# 2. LIST ADMINS
# ============================================================================
print("\n" + "="*80)
print("2. LIST ADMINS")
print("="*80 + "\n")

print("TEST 2.1: As seeded admin, GET /api/admin/admins -> 200")
print("-" * 80)

list_resp = requests.get(f"{BASE_URL}/admin/admins", headers=headers(admin_token))
print_test(
    "GET /api/admin/admins → 200",
    list_resp.status_code == 200,
    f"Status: {list_resp.status_code}"
)

admins_data = list_resp.json()
print_test(
    "Response has 'admins' array",
    'admins' in admins_data and isinstance(admins_data['admins'], list),
    f"admins: {type(admins_data.get('admins'))}"
)
print_test(
    "Response has 'pending' array",
    'pending' in admins_data and isinstance(admins_data['pending'], list),
    f"pending: {type(admins_data.get('pending'))}"
)

print(f"  → Current admins count: {len(admins_data['admins'])}")
print(f"  → Pending admins count: {len(admins_data['pending'])}")

# Check if seeded admin appears with super=true
seeded_admin = None
for admin in admins_data['admins']:
    if admin.get('email', '').lower() == 'admin@clanchat.app':
        seeded_admin = admin
        break

print_test(
    "Seeded admin admin@clanchat.app appears in admins list",
    seeded_admin is not None,
    f"Found: {seeded_admin.get('email') if seeded_admin else 'Not found'}"
)

if seeded_admin:
    print_test(
        "Seeded admin has super=true",
        seeded_admin.get('super') == True,
        f"super: {seeded_admin.get('super')}"
    )

print("\nTEST 2.2: As REGULAR user, GET /api/admin/admins -> 403")
print("-" * 80)

# Register a regular user
regular_suffix = secrets.token_hex(4)
regular_email = f"regular+{regular_suffix}@example.com"
regular_token, regular_user = register_user(regular_email, "secret123", "Regular User")
print(f"  → Registered regular user: {regular_user['handle']} (email: {regular_email})")

list_resp_regular = requests.get(f"{BASE_URL}/admin/admins", headers=headers(regular_token))
print_test(
    "Regular user GET /api/admin/admins → 403",
    list_resp_regular.status_code == 403,
    f"Status: {list_resp_regular.status_code}"
)

# ============================================================================
# 3. ADD ADMIN (existing account -> promote)
# ============================================================================
print("\n" + "="*80)
print("3. ADD ADMIN (existing account -> promote)")
print("="*80 + "\n")

print("TEST 3.1: Register throwaway user U1, confirm is_admin=false")
print("-" * 80)

u1_suffix = secrets.token_hex(4)
u1_email = f"u1+{u1_suffix}@example.com"
u1_token, u1_user = register_user(u1_email, "secret123", "User One")
print(f"  → Registered U1: {u1_user['handle']} (email: {u1_email})")

u1_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(u1_token))
u1_me_data = u1_me_resp.json()
print_test(
    "U1 GET /api/me -> is_admin=false initially",
    u1_me_data.get('is_admin') == False,
    f"is_admin: {u1_me_data.get('is_admin')}"
)

print("\nTEST 3.2: As admin, POST /api/admin/admins {email:U1_email} -> 200 {promoted:true}")
print("-" * 80)

add_resp = requests.post(
    f"{BASE_URL}/admin/admins",
    headers=headers(admin_token),
    json={"email": u1_email}
)
print_test(
    "POST /api/admin/admins {email:U1_email} → 200",
    add_resp.status_code == 200,
    f"Status: {add_resp.status_code}"
)

add_data = add_resp.json()
print_test(
    "Response has promoted=true (existing account)",
    add_data.get('promoted') == True,
    f"promoted: {add_data.get('promoted')}"
)

print("\nTEST 3.3: U1 GET /api/me -> is_admin=true after promotion")
print("-" * 80)

u1_me_resp2 = requests.get(f"{BASE_URL}/me", headers=headers(u1_token))
u1_me_data2 = u1_me_resp2.json()
print_test(
    "U1 GET /api/me -> is_admin=true after promotion",
    u1_me_data2.get('is_admin') == True,
    f"is_admin: {u1_me_data2.get('is_admin')}"
)

print("\nTEST 3.4: GET /api/admin/admins -> U1 appears in admins with super=false")
print("-" * 80)

list_resp2 = requests.get(f"{BASE_URL}/admin/admins", headers=headers(admin_token))
admins_data2 = list_resp2.json()

u1_admin = None
for admin in admins_data2['admins']:
    if admin.get('email', '').lower() == u1_email.lower():
        u1_admin = admin
        break

print_test(
    "U1 appears in admins list",
    u1_admin is not None,
    f"Found: {u1_admin.get('email') if u1_admin else 'Not found'}"
)

if u1_admin:
    print_test(
        "U1 has super=false (not env super-admin)",
        u1_admin.get('super') == False,
        f"super: {u1_admin.get('super')}"
    )

print("\nTEST 3.5: As REGULAR user, POST /api/admin/admins -> 403")
print("-" * 80)

add_resp_regular = requests.post(
    f"{BASE_URL}/admin/admins",
    headers=headers(regular_token),
    json={"email": "x@y.com"}
)
print_test(
    "Regular user POST /api/admin/admins -> 403",
    add_resp_regular.status_code == 403,
    f"Status: {add_resp_regular.status_code}"
)

print("\nTEST 3.6: Invalid email, POST /api/admin/admins {email:'notanemail'} -> 400")
print("-" * 80)

add_resp_invalid = requests.post(
    f"{BASE_URL}/admin/admins",
    headers=headers(admin_token),
    json={"email": "notanemail"}
)
print_test(
    "Invalid email POST /api/admin/admins -> 400",
    add_resp_invalid.status_code == 400,
    f"Status: {add_resp_invalid.status_code}"
)

# ============================================================================
# 4. ADD ADMIN (no account yet -> allowlist, then auto-grant on signup)
# ============================================================================
print("\n" + "="*80)
print("4. ADD ADMIN (no account yet -> allowlist, then auto-grant on signup)")
print("="*80 + "\n")

print("TEST 4.1: As admin, POST /api/admin/admins {email:'future+<rand>@example.com'} -> 200 {promoted:false}")
print("-" * 80)

future_suffix = secrets.token_hex(4)
future_email = f"future+{future_suffix}@example.com"

add_future_resp = requests.post(
    f"{BASE_URL}/admin/admins",
    headers=headers(admin_token),
    json={"email": future_email}
)
print_test(
    "POST /api/admin/admins {email:future_email} → 200",
    add_future_resp.status_code == 200,
    f"Status: {add_future_resp.status_code}"
)

add_future_data = add_future_resp.json()
print_test(
    "Response has promoted=false (no account yet)",
    add_future_data.get('promoted') == False,
    f"promoted: {add_future_data.get('promoted')}"
)

print("\nTEST 4.2: GET /api/admin/admins -> future email in 'pending'")
print("-" * 80)

list_resp3 = requests.get(f"{BASE_URL}/admin/admins", headers=headers(admin_token))
admins_data3 = list_resp3.json()

print_test(
    "Future email appears in pending list",
    future_email.lower() in [e.lower() for e in admins_data3['pending']],
    f"pending: {admins_data3['pending']}"
)

print("\nTEST 4.3: Register with that SAME email -> GET /api/me -> is_admin=true (auto-granted)")
print("-" * 80)

future_token, future_user = register_user(future_email, "secret123", "Future Admin")
print(f"  → Registered with allowlisted email: {future_user['handle']} (email: {future_email})")

future_me_resp = requests.get(f"{BASE_URL}/me", headers=headers(future_token))
future_me_data = future_me_resp.json()
print_test(
    "Future user GET /api/me -> is_admin=true (auto-granted on signup)",
    future_me_data.get('is_admin') == True,
    f"is_admin: {future_me_data.get('is_admin')}"
)

print("\nTEST 4.4: GET /api/admin/admins -> future email now in 'admins' (not pending)")
print("-" * 80)

list_resp4 = requests.get(f"{BASE_URL}/admin/admins", headers=headers(admin_token))
admins_data4 = list_resp4.json()

future_admin = None
for admin in admins_data4['admins']:
    if admin.get('email', '').lower() == future_email.lower():
        future_admin = admin
        break

print_test(
    "Future email now appears in admins list",
    future_admin is not None,
    f"Found: {future_admin.get('email') if future_admin else 'Not found'}"
)

print_test(
    "Future email NOT in pending list anymore",
    future_email.lower() not in [e.lower() for e in admins_data4['pending']],
    f"pending: {admins_data4['pending']}"
)

# ============================================================================
# 5. REMOVE ADMIN
# ============================================================================
print("\n" + "="*80)
print("5. REMOVE ADMIN")
print("="*80 + "\n")

print("TEST 5.1: As admin, POST /api/admin/admins/remove {email:U1_email} -> 200")
print("-" * 80)

remove_resp = requests.post(
    f"{BASE_URL}/admin/admins/remove",
    headers=headers(admin_token),
    json={"email": u1_email}
)
print_test(
    "POST /api/admin/admins/remove {email:U1_email} → 200",
    remove_resp.status_code == 200,
    f"Status: {remove_resp.status_code}"
)

print("\nTEST 5.2: U1 GET /api/me -> is_admin=false after removal")
print("-" * 80)

u1_me_resp3 = requests.get(f"{BASE_URL}/me", headers=headers(u1_token))
u1_me_data3 = u1_me_resp3.json()
print_test(
    "U1 GET /api/me -> is_admin=false after removal",
    u1_me_data3.get('is_admin') == False,
    f"is_admin: {u1_me_data3.get('is_admin')}"
)

print("\nTEST 5.3: Protected - cannot remove env super-admin (admin@clanchat.app) -> 400")
print("-" * 80)

remove_super_resp = requests.post(
    f"{BASE_URL}/admin/admins/remove",
    headers=headers(admin_token),
    json={"email": "admin@clanchat.app"}
)
print_test(
    "POST /api/admin/admins/remove {email:'admin@clanchat.app'} → 400",
    remove_super_resp.status_code == 400,
    f"Status: {remove_super_resp.status_code}"
)

print("\nTEST 5.4: Protected - cannot remove yourself -> 400")
print("-" * 80)

# Use future_user (who is now an admin) to try to remove themselves
remove_self_resp = requests.post(
    f"{BASE_URL}/admin/admins/remove",
    headers=headers(future_token),
    json={"email": future_email}
)
print_test(
    "Admin cannot remove their own email -> 400",
    remove_self_resp.status_code == 400,
    f"Status: {remove_self_resp.status_code}"
)

print("\nTEST 5.5: Regular user POST /api/admin/admins/remove -> 403")
print("-" * 80)

remove_resp_regular = requests.post(
    f"{BASE_URL}/admin/admins/remove",
    headers=headers(regular_token),
    json={"email": "someone@example.com"}
)
print_test(
    "Regular user POST /api/admin/admins/remove -> 403",
    remove_resp_regular.status_code == 403,
    f"Status: {remove_resp_regular.status_code}"
)

# ============================================================================
# 6. REGRESSION: GET /api/admin/stats
# ============================================================================
print("\n" + "="*80)
print("6. REGRESSION: GET /api/admin/stats")
print("="*80 + "\n")

print("TEST 6.1: Admin GET /api/admin/stats -> 200")
print("-" * 80)

stats_resp_admin = requests.get(f"{BASE_URL}/admin/stats", headers=headers(admin_token))
print_test(
    "Admin GET /api/admin/stats → 200",
    stats_resp_admin.status_code == 200,
    f"Status: {stats_resp_admin.status_code}"
)

if stats_resp_admin.status_code == 200:
    stats_data = stats_resp_admin.json()
    print(f"  → Stats: users={stats_data.get('users')}, posts={stats_data.get('posts')}, deleted={stats_data.get('deleted')}")

print("\nTEST 6.2: Regular user GET /api/admin/stats -> 403")
print("-" * 80)

stats_resp_regular = requests.get(f"{BASE_URL}/admin/stats", headers=headers(regular_token))
print_test(
    "Regular user GET /api/admin/stats → 403",
    stats_resp_regular.status_code == 403,
    f"Status: {stats_resp_regular.status_code}"
)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("✅ ALL ADMIN MANAGEMENT TESTS PASSED")
print("="*80)
print("\nSUMMARY:")
print("  ✅ Seeded super-admin login working (admin@clanchat.app)")
print("  ✅ List admins endpoint working (200 for admin, 403 for regular)")
print("  ✅ Add admin (existing account) working - promotes user")
print("  ✅ Add admin (no account) working - allowlists email, auto-grants on signup")
print("  ✅ Remove admin working - demotes user, protects super-admin and self-removal")
print("  ✅ Regression: GET /api/admin/stats still working")
print("\n")
