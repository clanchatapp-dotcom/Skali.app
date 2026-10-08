#!/usr/bin/env python3
"""
Smoke test to confirm backend is fully healthy after supervisor restructure.
Backend runs on 0.0.0.0:8001, frontend on 3000 proxies /api.
"""
import requests
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@clanchat.app"
ADMIN_PASSWORD = "ClanChatAdmin!2025"

def test_health():
    """Test 1: HEALTH endpoint GET /api/ → 200 with {ok:true}"""
    print("\n=== TEST 1: HEALTH ENDPOINT ===")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                print("✅ PASS: Health endpoint returned 200 with ok:true")
                return True
            else:
                print(f"❌ FAIL: Health endpoint returned 200 but data is {data}")
                return False
        else:
            print(f"❌ FAIL: Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Health endpoint error: {e}")
        return False

def test_auth():
    """Test 2: AUTH - login and verify admin status"""
    print("\n=== TEST 2: AUTH (LOGIN + /me) ===")
    try:
        # Login
        print(f"Logging in as {ADMIN_EMAIL}...")
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        print(f"Login status: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print(f"❌ FAIL: Login returned {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return False, None
        
        login_data = login_response.json()
        token = login_data.get("access_token") or login_data.get("token")
        
        if not token:
            print(f"❌ FAIL: Login response missing token/access_token: {login_data}")
            return False, None
        
        print(f"✅ Login successful, token received (length: {len(token)})")
        
        # Verify /me endpoint
        print("Verifying /me endpoint...")
        me_response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"/me status: {me_response.status_code}")
        
        if me_response.status_code != 200:
            print(f"❌ FAIL: /me returned {me_response.status_code}")
            print(f"Response: {me_response.text}")
            return False, token
        
        me_data = me_response.json()
        is_admin = me_data.get("is_admin")
        
        print(f"/me response: is_admin={is_admin}, email={me_data.get('email')}")
        
        if is_admin == True:
            print("✅ PASS: Auth working, admin status confirmed")
            return True, token
        else:
            print(f"❌ FAIL: is_admin is {is_admin}, expected True")
            return False, token
            
    except Exception as e:
        print(f"❌ FAIL: Auth error: {e}")
        return False, None

def test_data_endpoint(token):
    """Test 3: DATA ENDPOINT - GET /api/feed?scope=general"""
    print("\n=== TEST 3: DATA ENDPOINT (FEED) ===")
    if not token:
        print("❌ SKIP: No token available")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/feed?scope=general",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ FAIL: Feed returned {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        
        if isinstance(data, list):
            print(f"✅ PASS: Feed returned 200 with array (length: {len(data)})")
            return True
        else:
            print(f"❌ FAIL: Feed returned 200 but data is not an array: {type(data)}")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Feed error: {e}")
        return False

def test_admin_endpoint(token):
    """Test 4: ADMIN ENDPOINT - GET /api/admin/stats"""
    print("\n=== TEST 4: ADMIN ENDPOINT (STATS) ===")
    if not token:
        print("❌ SKIP: No token available")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ FAIL: Admin stats returned {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        print(f"Stats data keys: {list(data.keys())}")
        print(f"✅ PASS: Admin stats returned 200")
        return True
            
    except Exception as e:
        print(f"❌ FAIL: Admin stats error: {e}")
        return False

def main():
    print("=" * 60)
    print("BACKEND SMOKE TEST - Supervisor Restructure Verification")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    
    results = []
    
    # Test 1: Health
    results.append(("HEALTH", test_health()))
    
    # Test 2: Auth
    auth_pass, token = test_auth()
    results.append(("AUTH", auth_pass))
    
    # Test 3: Data endpoint
    results.append(("DATA (FEED)", test_data_endpoint(token)))
    
    # Test 4: Admin endpoint
    results.append(("ADMIN (STATS)", test_admin_endpoint(token)))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Backend is fully healthy!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
