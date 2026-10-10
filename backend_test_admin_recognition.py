#!/usr/bin/env python3
"""
Test script for Admin Recognition Fix
Tests that built-in super-admins are always recognized as admins.
"""
import requests
import time
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def test_admin_recognition():
    """Test admin recognition for built-in super-admins and regular users."""
    print("=" * 80)
    print("ADMIN RECOGNITION FIX TEST")
    print("=" * 80)
    
    # Generate unique timestamp for test users
    ts = str(int(time.time()))[-8:]
    
    # Test data
    builtin_admin_email = "thomasgallacher92@gmail.com"
    builtin_admin_password = "Test1234!"
    builtin_admin_dob = "1990-01-01"
    
    seeded_admin_email = "admin@clanchat.app"
    seeded_admin_password = "ClanChatAdmin!2025"
    
    random_user_email = f"notadmin+{ts}@example.com"
    random_user_password = "Test1234!"
    random_user_dob = "1995-05-15"
    
    admin_endpoints = [
        "/admin/stats",
        "/admin/reports",
        "/admin/users"
    ]
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    def test_case(name, condition, details=""):
        """Helper to track test results."""
        results["total"] += 1
        if condition:
            results["passed"] += 1
            print(f"✅ TEST {results['total']}: {name} - PASSED")
            if details:
                print(f"   {details}")
        else:
            results["failed"] += 1
            print(f"❌ TEST {results['total']}: {name} - FAILED")
            if details:
                print(f"   {details}")
        print()
    
    # ========================================================================
    # TEST 1: BUILT-IN ADMIN (thomasgallacher92@gmail.com)
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 1: BUILT-IN ADMIN (thomasgallacher92@gmail.com)")
    print("=" * 80)
    
    # Try to register, if already exists, login instead
    print(f"Attempting to register built-in admin: {builtin_admin_email}")
    register_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": builtin_admin_email,
            "password": builtin_admin_password,
            "name": "Thomas Gallacher",
            "dob": builtin_admin_dob
        }
    )
    
    if register_resp.status_code == 200:
        print(f"✓ Registered new user: {builtin_admin_email}")
        builtin_admin_token = register_resp.json()["access_token"]
    elif register_resp.status_code == 400 and "already registered" in register_resp.text.lower():
        print(f"✓ User already exists, logging in: {builtin_admin_email}")
        login_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": builtin_admin_email,
                "password": builtin_admin_password
            }
        )
        if login_resp.status_code == 200:
            builtin_admin_token = login_resp.json()["access_token"]
            print(f"✓ Logged in successfully")
        else:
            print(f"❌ Login failed: {login_resp.status_code} - {login_resp.text}")
            test_case(
                "Built-in admin login",
                False,
                f"Login failed: {login_resp.status_code} - {login_resp.text}"
            )
            builtin_admin_token = None
    else:
        print(f"❌ Registration failed: {register_resp.status_code} - {register_resp.text}")
        test_case(
            "Built-in admin registration",
            False,
            f"Registration failed: {register_resp.status_code} - {register_resp.text}"
        )
        builtin_admin_token = None
    
    if builtin_admin_token:
        # Check if is_admin is true
        print(f"\nChecking GET /api/me for built-in admin...")
        me_resp = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {builtin_admin_token}"}
        )
        
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            is_admin = me_data.get("is_admin", False)
            test_case(
                "Built-in admin has is_admin=true",
                is_admin == True,
                f"is_admin={is_admin}, expected=True"
            )
        else:
            test_case(
                "Built-in admin GET /api/me",
                False,
                f"GET /api/me failed: {me_resp.status_code} - {me_resp.text}"
            )
        
        # Test admin endpoints
        print(f"\nTesting admin endpoints for built-in admin...")
        for endpoint in admin_endpoints:
            endpoint_resp = requests.get(
                f"{BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {builtin_admin_token}"}
            )
            test_case(
                f"Built-in admin can access {endpoint}",
                endpoint_resp.status_code == 200,
                f"Status: {endpoint_resp.status_code}, Expected: 200"
            )
    
    # ========================================================================
    # TEST 2: SEEDED ADMIN (admin@clanchat.app)
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 2: SEEDED ADMIN (admin@clanchat.app)")
    print("=" * 80)
    
    print(f"Logging in as seeded admin: {seeded_admin_email}")
    seeded_login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": seeded_admin_email,
            "password": seeded_admin_password
        }
    )
    
    if seeded_login_resp.status_code == 200:
        print(f"✓ Logged in successfully")
        seeded_admin_token = seeded_login_resp.json()["access_token"]
        
        # Check if is_admin is true
        print(f"\nChecking GET /api/me for seeded admin...")
        me_resp = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {seeded_admin_token}"}
        )
        
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            is_admin = me_data.get("is_admin", False)
            test_case(
                "Seeded admin has is_admin=true",
                is_admin == True,
                f"is_admin={is_admin}, expected=True"
            )
        else:
            test_case(
                "Seeded admin GET /api/me",
                False,
                f"GET /api/me failed: {me_resp.status_code} - {me_resp.text}"
            )
        
        # Test admin endpoints
        print(f"\nTesting admin endpoints for seeded admin...")
        for endpoint in admin_endpoints:
            endpoint_resp = requests.get(
                f"{BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {seeded_admin_token}"}
            )
            test_case(
                f"Seeded admin can access {endpoint}",
                endpoint_resp.status_code == 200,
                f"Status: {endpoint_resp.status_code}, Expected: 200"
            )
    else:
        print(f"❌ Login failed: {seeded_login_resp.status_code} - {seeded_login_resp.text}")
        test_case(
            "Seeded admin login",
            False,
            f"Login failed: {seeded_login_resp.status_code} - {seeded_login_resp.text}"
        )
    
    # ========================================================================
    # TEST 3: NON-ADMIN USER
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 3: NON-ADMIN USER")
    print("=" * 80)
    
    print(f"Registering random user: {random_user_email}")
    random_register_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": random_user_email,
            "password": random_user_password,
            "name": "Random User",
            "dob": random_user_dob
        }
    )
    
    if random_register_resp.status_code == 200:
        print(f"✓ Registered successfully")
        random_user_token = random_register_resp.json()["access_token"]
        
        # Check if is_admin is false
        print(f"\nChecking GET /api/me for random user...")
        me_resp = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {random_user_token}"}
        )
        
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            is_admin = me_data.get("is_admin", False)
            test_case(
                "Random user has is_admin=false",
                is_admin == False,
                f"is_admin={is_admin}, expected=False"
            )
        else:
            test_case(
                "Random user GET /api/me",
                False,
                f"GET /api/me failed: {me_resp.status_code} - {me_resp.text}"
            )
        
        # Test that admin endpoints return 403
        print(f"\nTesting admin endpoints for random user (should be 403)...")
        for endpoint in admin_endpoints:
            endpoint_resp = requests.get(
                f"{BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {random_user_token}"}
            )
            test_case(
                f"Random user gets 403 for {endpoint}",
                endpoint_resp.status_code == 403,
                f"Status: {endpoint_resp.status_code}, Expected: 403"
            )
    else:
        print(f"❌ Registration failed: {random_register_resp.status_code} - {random_register_resp.text}")
        test_case(
            "Random user registration",
            False,
            f"Registration failed: {random_register_resp.status_code} - {random_register_resp.text}"
        )
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results['total']}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Success Rate: {(results['passed'] / results['total'] * 100):.1f}%")
    print("=" * 80)
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED! Admin recognition fix is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {results['failed']} TEST(S) FAILED. Please review the failures above.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = test_admin_recognition()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
