#!/usr/bin/env python3
"""
Test script for Account tier admin set + Co-Admin DM access guard feature.
Tests:
(A) ACCOUNT TIER: POST /api/admin/users/{handle}/account-type endpoint
(B) CO-ADMIN DM GUARD: toggle + request/approve one-time grant flow
"""
import requests
import uuid
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def register_user(email, password, dob="1990-01-01"):
    """Register a new adult user."""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "dob": dob
    })
    if resp.status_code != 200:
        print(f"❌ Registration failed for {email}: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get('access_token')

def get_me(token):
    """Get current user profile."""
    resp = requests.get(f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ GET /api/me failed: {resp.status_code} {resp.text}")
        return None
    return resp.json()

def login(email, password):
    """Login and get access token."""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code != 200:
        print(f"❌ Login failed for {email}: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get('access_token')

def assign_role(token, handle, role):
    """Assign a role to a user."""
    resp = requests.post(f"{BASE_URL}/admin/roles/assign", 
                        headers={"Authorization": f"Bearer {token}"},
                        json={"handle": handle, "role": role})
    return resp

def set_account_type(token, handle, account_type):
    """Set account type for a user."""
    resp = requests.post(f"{BASE_URL}/admin/users/{handle}/account-type",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"account_type": account_type})
    return resp

def get_user_profile(token, handle):
    """Get user profile by handle."""
    resp = requests.get(f"{BASE_URL}/users/{handle}",
                       headers={"Authorization": f"Bearer {token}"})
    return resp

def set_coadmin_dms(token, enabled):
    """Toggle co-admin DM access setting."""
    resp = requests.post(f"{BASE_URL}/admin/settings/coadmin-dms",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"enabled": enabled})
    return resp

def request_dm_access(token, handle):
    """Request DM access to a super admin."""
    resp = requests.post(f"{BASE_URL}/admin/dm-access/request",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"handle": handle})
    return resp

def get_dm_access_list(token):
    """Get DM access requests."""
    resp = requests.get(f"{BASE_URL}/admin/dm-access",
                       headers={"Authorization": f"Bearer {token}"})
    return resp

def decide_dm_access(token, req_id, decision):
    """Approve or deny a DM access request."""
    resp = requests.post(f"{BASE_URL}/admin/dm-access/{req_id}/{decision}",
                        headers={"Authorization": f"Bearer {token}"})
    return resp

def main():
    print("=" * 80)
    print("ACCOUNT TIER + CO-ADMIN DM ACCESS GUARD TEST")
    print("=" * 80)
    
    # SETUP: Login as super admin
    print("\n[SETUP] Logging in as super admin...")
    super_token = login("admin@clanchat.app", "ClanChatAdmin!2025")
    if not super_token:
        print("❌ SETUP FAILED: Could not login as super admin")
        sys.exit(1)
    print("✅ Super admin logged in")
    
    # Get super admin's handle
    super_profile = get_me(super_token)
    if not super_profile:
        print("❌ SETUP FAILED: Could not get super admin profile")
        sys.exit(1)
    super_handle = super_profile.get('handle')
    print(f"✅ Super admin handle: {super_handle}")
    
    # Register CO (co-admin) user
    uid = str(uuid.uuid4())[:8]
    co_email = f"co+{uid}@example.com"
    co_password = "CoAdmin123!"
    print(f"\n[SETUP] Registering CO user: {co_email}")
    co_token = register_user(co_email, co_password, "1990-01-01")
    if not co_token:
        print("❌ SETUP FAILED: Could not register CO user")
        sys.exit(1)
    co_profile = get_me(co_token)
    co_handle = co_profile.get('handle')
    print(f"✅ CO user registered with handle: {co_handle}")
    
    # Register NORMAL user
    normal_email = f"normal+{uid}@example.com"
    normal_password = "Normal123!"
    print(f"\n[SETUP] Registering NORMAL user: {normal_email}")
    normal_token = register_user(normal_email, normal_password, "1990-01-01")
    if not normal_token:
        print("❌ SETUP FAILED: Could not register NORMAL user")
        sys.exit(1)
    normal_profile = get_me(normal_token)
    normal_handle = normal_profile.get('handle')
    print(f"✅ NORMAL user registered with handle: {normal_handle}")
    
    # Make CO a co_admin
    print(f"\n[SETUP] Assigning co_admin role to {co_handle}...")
    resp = assign_role(super_token, co_handle, "co_admin")
    if resp.status_code != 200:
        print(f"❌ SETUP FAILED: Could not assign co_admin role: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"✅ {co_handle} is now a co_admin")
    
    # Verify CO is now a co_admin
    co_profile = get_me(co_token)
    if not co_profile.get('is_admin'):
        print(f"❌ SETUP FAILED: CO user is_admin should be true but got: {co_profile.get('is_admin')}")
        sys.exit(1)
    print(f"✅ CO user is_admin verified: {co_profile.get('is_admin')}")
    
    print("\n" + "=" * 80)
    print("PART A: ACCOUNT TIER TESTS")
    print("=" * 80)
    
    # Test 1: Set account type to premium
    print("\n[TEST 1] Super admin sets NORMAL user account_type to 'premium'")
    resp = set_account_type(super_token, normal_handle, "premium")
    if resp.status_code != 200:
        print(f"❌ TEST 1 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 1 PASSED: POST /api/admin/users/{normal_handle}/account-type → 200")
        data = resp.json()
        if data.get('account_type') != 'premium':
            print(f"❌ TEST 1 FAILED: Response account_type should be 'premium', got: {data.get('account_type')}")
        else:
            print(f"✅ Response account_type: {data.get('account_type')}")
    
    # Verify account_type in profile
    print(f"\n[TEST 1 VERIFY] GET /api/users/{normal_handle} to verify account_type")
    resp = get_user_profile(super_token, normal_handle)
    if resp.status_code != 200:
        print(f"❌ TEST 1 VERIFY FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        profile = resp.json()
        if profile.get('account_type') != 'premium':
            print(f"❌ TEST 1 VERIFY FAILED: account_type should be 'premium', got: {profile.get('account_type')}")
        else:
            print(f"✅ TEST 1 VERIFY PASSED: account_type == 'premium'")
    
    # Test 2: Invalid account type 'gold'
    print("\n[TEST 2] Super admin sets account_type to invalid 'gold'")
    resp = set_account_type(super_token, normal_handle, "gold")
    if resp.status_code != 400:
        print(f"❌ TEST 2 FAILED: Expected 400, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 2 PASSED: POST with invalid account_type 'gold' → 400")
        print(f"   Error detail: {resp.json().get('detail', resp.text)}")
    
    # Test 3: Nonexistent handle
    print("\n[TEST 3] Super admin sets account_type for nonexistent handle")
    resp = set_account_type(super_token, "nosuchhandle123", "free")
    if resp.status_code != 404:
        print(f"❌ TEST 3 FAILED: Expected 404, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 3 PASSED: POST with nonexistent handle → 404")
        print(f"   Error detail: {resp.json().get('detail', resp.text)}")
    
    print("\n" + "=" * 80)
    print("PART B: CO-ADMIN DM ACCESS GUARD TESTS")
    print("=" * 80)
    
    # Test 4: CO (co_admin) tries to toggle coadmin-dms setting
    print("\n[TEST 4] CO (co_admin) tries to POST /api/admin/settings/coadmin-dms")
    resp = set_coadmin_dms(co_token, True)
    if resp.status_code != 403:
        print(f"❌ TEST 4 FAILED: Expected 403, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 4 PASSED: CO POST /api/admin/settings/coadmin-dms → 403 (only super admin)")
        print(f"   Error detail: {resp.json().get('detail', resp.text)}")
    
    # Test 5: Super admin sets coadmin-dms to false
    print("\n[TEST 5] Super admin sets coadmin-dms to false")
    resp = set_coadmin_dms(super_token, False)
    if resp.status_code != 200:
        print(f"❌ TEST 5 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 5 PASSED: Super POST /api/admin/settings/coadmin-dms {{enabled:false}} → 200")
        data = resp.json()
        if data.get('allow_coadmin_dms') != False:
            print(f"❌ TEST 5 FAILED: Response allow_coadmin_dms should be false, got: {data.get('allow_coadmin_dms')}")
        else:
            print(f"✅ Response allow_coadmin_dms: {data.get('allow_coadmin_dms')}")
    
    # Test 6: CO requests DM access to super admin
    print(f"\n[TEST 6] CO requests DM access to super admin ({super_handle})")
    resp = request_dm_access(co_token, super_handle)
    if resp.status_code != 200:
        print(f"❌ TEST 6 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 6 PASSED: CO POST /api/admin/dm-access/request {{handle:{super_handle}}} → 200")
        data = resp.json()
        if data.get('status') != 'pending':
            print(f"❌ TEST 6 FAILED: Response status should be 'pending', got: {data.get('status')}")
        else:
            print(f"✅ Response status: {data.get('status')}")
    
    # Test 7: Super admin gets DM access requests
    print(f"\n[TEST 7] Super admin GET /api/admin/dm-access")
    resp = get_dm_access_list(super_token)
    if resp.status_code != 200:
        print(f"❌ TEST 7 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        data = resp.json()
        if data.get('as_super') != True:
            print(f"❌ TEST 7 FAILED: as_super should be true, got: {data.get('as_super')}")
        else:
            print(f"✅ TEST 7 PASSED: Super GET /api/admin/dm-access → as_super==true")
        
        requests_list = data.get('requests', [])
        # Find CO's pending request
        co_request = None
        for req in requests_list:
            if req.get('requester_handle') == co_handle and req.get('status') == 'pending':
                co_request = req
                break
        
        if not co_request:
            print(f"❌ TEST 7 FAILED: Could not find CO's pending request in requests list")
            print(f"   Requests: {requests_list}")
        else:
            print(f"✅ Found CO's pending request with id: {co_request.get('id')}")
            req_id = co_request.get('id')
            
            # Test 8: Super admin approves the request
            print(f"\n[TEST 8] Super admin approves CO's DM access request")
            resp = decide_dm_access(super_token, req_id, "approve")
            if resp.status_code != 200:
                print(f"❌ TEST 8 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
            else:
                data = resp.json()
                if data.get('status') != 'approved':
                    print(f"❌ TEST 8 FAILED: Response status should be 'approved', got: {data.get('status')}")
                else:
                    print(f"✅ TEST 8 PASSED: Super POST /api/admin/dm-access/{req_id}/approve → 200, status 'approved'")
    
    # Test 9: CO gets their own DM access requests
    print(f"\n[TEST 9] CO GET /api/admin/dm-access (own requests)")
    resp = get_dm_access_list(co_token)
    if resp.status_code != 200:
        print(f"❌ TEST 9 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        data = resp.json()
        if data.get('as_super') != False:
            print(f"❌ TEST 9 FAILED: as_super should be false for CO, got: {data.get('as_super')}")
        else:
            print(f"✅ TEST 9 PASSED: CO GET /api/admin/dm-access → as_super==false")
        
        requests_list = data.get('requests', [])
        # Find own approved request
        own_request = None
        for req in requests_list:
            if req.get('requester_handle') == co_handle and req.get('status') == 'approved':
                own_request = req
                break
        
        if not own_request:
            print(f"❌ TEST 9 FAILED: Could not find own approved request")
            print(f"   Requests: {requests_list}")
        else:
            print(f"✅ Found own request with status: {own_request.get('status')}, used: {own_request.get('used')}")
            if own_request.get('used') != False:
                print(f"❌ TEST 9 FAILED: used should be false, got: {own_request.get('used')}")
            else:
                print(f"✅ TEST 9 PASSED: Own request status 'approved', used==false")
    
    # Test 10: CO requests DM access to NORMAL user (not a super admin)
    print(f"\n[TEST 10] CO requests DM access to NORMAL user (not a super admin)")
    resp = request_dm_access(co_token, normal_handle)
    if resp.status_code != 400:
        print(f"❌ TEST 10 FAILED: Expected 400, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 10 PASSED: CO POST /api/admin/dm-access/request {{handle:NORMAL_handle}} → 400")
        print(f"   Error detail: {resp.json().get('detail', resp.text)}")
    
    # Test 11: Super admin sets coadmin-dms to true
    print("\n[TEST 11] Super admin sets coadmin-dms to true")
    resp = set_coadmin_dms(super_token, True)
    if resp.status_code != 200:
        print(f"❌ TEST 11 FAILED: Expected 200, got {resp.status_code}: {resp.text}")
    else:
        print(f"✅ TEST 11 PASSED: Super POST /api/admin/settings/coadmin-dms {{enabled:true}} → 200")
        data = resp.json()
        if data.get('allow_coadmin_dms') != True:
            print(f"❌ TEST 11 FAILED: Response allow_coadmin_dms should be true, got: {data.get('allow_coadmin_dms')}")
        else:
            print(f"✅ Response allow_coadmin_dms: {data.get('allow_coadmin_dms')}")
    
    # Verify in super admin's profile
    print(f"\n[TEST 11 VERIFY] Super admin GET /api/me to verify allow_coadmin_dms")
    super_profile = get_me(super_token)
    if super_profile.get('allow_coadmin_dms') != True:
        print(f"❌ TEST 11 VERIFY FAILED: allow_coadmin_dms should be true, got: {super_profile.get('allow_coadmin_dms')}")
    else:
        print(f"✅ TEST 11 VERIFY PASSED: Super GET /api/me → allow_coadmin_dms == true")
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✅ All 11 tests completed. Review results above for pass/fail status.")
    print("=" * 80)

if __name__ == "__main__":
    main()
