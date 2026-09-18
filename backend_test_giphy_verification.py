#!/usr/bin/env python3
"""
GIPHY GIF Search Endpoint Verification Test
============================================
Tests the re-added GET /api/giphy/search endpoint on LOCAL sandbox backend.

Test Cases:
1. GET /api/giphy/search with NO Authorization header -> expect 401
2. GET /api/giphy/search (no q param) WITH Bearer token -> expect 200 and non-empty JSON array with id, url, preview (trending)
3. GET /api/giphy/search?q=cat WITH Bearer token -> expect 200, non-empty array with id, url, preview
4. Regression: GET /api/reels WITH Bearer token -> expect 200 (array)
"""

import requests
import random
import string

# LOCAL sandbox backend
BASE_URL = "http://localhost:8001/api"

def random_suffix():
    """Generate random suffix for unique email"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def register_user():
    """Register a throwaway user with pattern giphyqa+<random>@example.com"""
    suffix = random_suffix()
    email = f"giphyqa+{suffix}@example.com"
    password = "secret123"
    name = "GiphyQA"
    dob = "1990-01-01"
    
    print(f"\n📝 Registering throwaway user: {email}")
    
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": password,
            "name": name,
            "dob": dob
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Registration failed: {response.status_code} - {response.text}")
        return None
    
    data = response.json()
    token = data.get('access_token')
    
    if not token:
        print(f"❌ No access_token in response: {data}")
        return None
    
    print(f"✅ Registration successful. Token: {token[:20]}...")
    return token

def test_1_no_auth():
    """Test 1: GET /api/giphy/search with NO Authorization header -> expect 401"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/giphy/search with NO Authorization header")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/giphy/search")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code == 401:
        print("✅ TEST 1 PASSED: Got 401 as expected")
        return True
    else:
        print(f"❌ TEST 1 FAILED: Expected 401, got {response.status_code}")
        return False

def test_2_trending(token):
    """Test 2: GET /api/giphy/search (no q param) WITH Bearer token -> expect 200 and non-empty array"""
    print("\n" + "="*80)
    print("TEST 2: GET /api/giphy/search (no q param) WITH Bearer token (trending)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/giphy/search", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Response: {response.text[:500]}")
        print(f"❌ TEST 2 FAILED: Expected 200, got {response.status_code}")
        return False
    
    data = response.json()
    
    if not isinstance(data, list):
        print(f"❌ TEST 2 FAILED: Expected array, got {type(data)}")
        return False
    
    print(f"Array length: {len(data)}")
    
    if len(data) == 0:
        print(f"❌ TEST 2 FAILED: Expected non-empty array, got empty array")
        return False
    
    # Check first item has required keys
    first_item = data[0]
    required_keys = ['id', 'url', 'preview']
    missing_keys = [k for k in required_keys if k not in first_item]
    
    if missing_keys:
        print(f"❌ TEST 2 FAILED: First item missing keys: {missing_keys}")
        print(f"First item keys: {list(first_item.keys())}")
        return False
    
    print(f"✅ First item has all required keys: {required_keys}")
    print(f"Sample item: id={first_item['id'][:20]}..., url={first_item['url'][:50]}..., preview={first_item['preview'][:50]}...")
    print(f"✅ TEST 2 PASSED: Got 200, non-empty array with {len(data)} items, each with id/url/preview")
    return True

def test_3_search_cat(token):
    """Test 3: GET /api/giphy/search?q=cat WITH Bearer token -> expect 200, non-empty array"""
    print("\n" + "="*80)
    print("TEST 3: GET /api/giphy/search?q=cat WITH Bearer token")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/giphy/search?q=cat", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Response: {response.text[:500]}")
        print(f"❌ TEST 3 FAILED: Expected 200, got {response.status_code}")
        return False
    
    data = response.json()
    
    if not isinstance(data, list):
        print(f"❌ TEST 3 FAILED: Expected array, got {type(data)}")
        return False
    
    print(f"Array length: {len(data)}")
    
    if len(data) == 0:
        print(f"❌ TEST 3 FAILED: Expected non-empty array, got empty array")
        return False
    
    # Check first item has required keys
    first_item = data[0]
    required_keys = ['id', 'url', 'preview']
    missing_keys = [k for k in required_keys if k not in first_item]
    
    if missing_keys:
        print(f"❌ TEST 3 FAILED: First item missing keys: {missing_keys}")
        print(f"First item keys: {list(first_item.keys())}")
        return False
    
    print(f"✅ First item has all required keys: {required_keys}")
    print(f"Sample item: id={first_item['id'][:20]}..., url={first_item['url'][:50]}..., preview={first_item['preview'][:50]}...")
    print(f"✅ TEST 3 PASSED: Got 200, non-empty array with {len(data)} items, each with id/url/preview")
    return True

def test_4_reels_regression(token):
    """Test 4: Regression - GET /api/reels WITH Bearer token -> expect 200 (array)"""
    print("\n" + "="*80)
    print("TEST 4: Regression - GET /api/reels WITH Bearer token")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/reels", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Response: {response.text[:500]}")
        print(f"❌ TEST 4 FAILED: Expected 200, got {response.status_code}")
        return False
    
    data = response.json()
    
    if not isinstance(data, list):
        print(f"❌ TEST 4 FAILED: Expected array, got {type(data)}")
        return False
    
    print(f"Array length: {len(data)}")
    print(f"✅ TEST 4 PASSED: Got 200, array with {len(data)} items (reels endpoint working)")
    return True

def main():
    print("="*80)
    print("GIPHY GIF SEARCH ENDPOINT VERIFICATION TEST")
    print("Testing LOCAL sandbox backend: http://localhost:8001")
    print("="*80)
    
    results = {}
    
    # Test 1: No auth (401)
    results['test_1_no_auth'] = test_1_no_auth()
    
    # Register user for authenticated tests
    token = register_user()
    if not token:
        print("\n❌ FATAL: Could not register user. Aborting remaining tests.")
        return
    
    # Test 2: Trending (no q param)
    results['test_2_trending'] = test_2_trending(token)
    
    # Test 3: Search with q=cat
    results['test_3_search_cat'] = test_3_search_cat(token)
    
    # Test 4: Reels regression
    results['test_4_reels_regression'] = test_4_reels_regression(token)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! GIPHY endpoint is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. See details above.")

if __name__ == "__main__":
    main()
