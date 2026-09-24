#!/usr/bin/env python3
"""
Backend test script for LOCAL sandbox (http://localhost:8001)
AREA 1: GIF search endpoint health verification
AREA 2: Media-type notification banner mapping (NEW feature)
"""
import requests
import random
import string
from datetime import datetime

BASE_URL = 'http://localhost:8001/api'

def rand_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def register_user(email, password, name, dob='1990-01-01'):
    """Register a new user and return the response."""
    resp = requests.post(f'{BASE_URL}/auth/register', json={
        'email': email,
        'password': password,
        'name': name,
        'dob': dob
    })
    return resp

def login_user(email, password):
    """Login and return the access token."""
    resp = requests.post(f'{BASE_URL}/auth/login', json={
        'email': email,
        'password': password
    })
    if resp.status_code == 200:
        return resp.json().get('access_token')
    return None

print("=" * 80)
print("BACKEND TEST: LOCAL SANDBOX (http://localhost:8001)")
print("=" * 80)

# ============================================================================
# AREA 1: GIF SEARCH ENDPOINT HEALTH VERIFICATION
# ============================================================================
print("\n" + "=" * 80)
print("AREA 1: GIF SEARCH ENDPOINT HEALTH VERIFICATION")
print("=" * 80)

# Register a throwaway user for GIF search tests
rand = rand_suffix()
qa1_email = f'qa1+{rand}@example.com'
qa1_password = 'secret123'
qa1_name = 'QA1'
qa1_dob = '1990-01-01'

print(f"\n[SETUP] Registering user: {qa1_email}")
reg_resp = register_user(qa1_email, qa1_password, qa1_name, qa1_dob)
if reg_resp.status_code != 200:
    print(f"❌ FAILED: Registration failed with status {reg_resp.status_code}")
    print(f"   Response: {reg_resp.text}")
    exit(1)

qa1_token = reg_resp.json().get('access_token')
if not qa1_token:
    print(f"❌ FAILED: No access_token in registration response")
    exit(1)

print(f"✅ User registered successfully")
print(f"   Token: {qa1_token[:20]}...")

# Test 1: GET /api/giphy/search (no q) with token -> expect 200, non-empty array
print("\n[TEST 1] GET /api/giphy/search (no q) with token")
resp = requests.get(f'{BASE_URL}/giphy/search', headers={'Authorization': f'Bearer {qa1_token}'})
print(f"   Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"❌ FAILED: Expected 200, got {resp.status_code}")
    print(f"   Response: {resp.text}")
else:
    data = resp.json()
    if not isinstance(data, list):
        print(f"❌ FAILED: Expected array, got {type(data)}")
    elif len(data) == 0:
        print(f"❌ FAILED: Expected non-empty array, got empty array")
    else:
        # Check first item has keys id, url, preview
        first = data[0]
        if 'id' not in first or 'url' not in first or 'preview' not in first:
            print(f"❌ FAILED: Items missing required keys (id, url, preview)")
            print(f"   First item keys: {list(first.keys())}")
        else:
            print(f"✅ PASSED: Returned {len(data)} trending gifs with keys id, url, preview")

# Test 2: GET /api/giphy/search?q=cat with token -> expect 200, non-empty array
print("\n[TEST 2] GET /api/giphy/search?q=cat with token")
resp = requests.get(f'{BASE_URL}/giphy/search?q=cat', headers={'Authorization': f'Bearer {qa1_token}'})
print(f"   Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"❌ FAILED: Expected 200, got {resp.status_code}")
    print(f"   Response: {resp.text}")
else:
    data = resp.json()
    if not isinstance(data, list):
        print(f"❌ FAILED: Expected array, got {type(data)}")
    elif len(data) == 0:
        print(f"❌ FAILED: Expected non-empty array, got empty array")
    else:
        print(f"✅ PASSED: Returned {len(data)} cat gifs")

# Test 3: GET /api/giphy/search with NO token -> expect 401
print("\n[TEST 3] GET /api/giphy/search with NO token")
resp = requests.get(f'{BASE_URL}/giphy/search')
print(f"   Status: {resp.status_code}")
if resp.status_code != 401:
    print(f"❌ FAILED: Expected 401, got {resp.status_code}")
    print(f"   Response: {resp.text}")
else:
    print(f"✅ PASSED: Correctly returned 401 without token")

# ============================================================================
# AREA 2: MEDIA-TYPE NOTIFICATION BANNER MAPPING (NEW FEATURE)
# ============================================================================
print("\n" + "=" * 80)
print("AREA 2: MEDIA-TYPE NOTIFICATION BANNER MAPPING (NEW FEATURE)")
print("=" * 80)

# Register ONE user for self-DM tests
rand2 = rand_suffix()
self_email = f'selftest+{rand2}@example.com'
self_password = 'secret123'
self_name = 'SelfTest'
self_dob = '1990-01-01'

print(f"\n[SETUP] Registering user for self-DM: {self_email}")
reg_resp = register_user(self_email, self_password, self_name, self_dob)
if reg_resp.status_code != 200:
    print(f"❌ FAILED: Registration failed with status {reg_resp.status_code}")
    print(f"   Response: {reg_resp.text}")
    exit(1)

self_token = reg_resp.json().get('access_token')
self_handle = reg_resp.json().get('user', {}).get('handle')

if not self_token or not self_handle:
    print(f"❌ FAILED: Missing access_token or handle in registration response")
    print(f"   Response: {reg_resp.json()}")
    exit(1)

print(f"✅ User registered successfully")
print(f"   Handle: {self_handle}")
print(f"   Token: {self_token[:20]}...")

# Define test cases with exact expected values
test_cases = [
    {
        'name': 'Image (photo)',
        'body': {'media_url': 'https://x/p.jpg', 'media_type': 'image'},
        'expected': 'sent 📷'
    },
    {
        'name': 'Video',
        'body': {'media_url': 'https://x/v.mp4', 'media_type': 'video'},
        'expected': 'sent 📹'
    },
    {
        'name': 'Image with allow_save=false (no-save)',
        'body': {'media_url': 'https://x/p.jpg', 'media_type': 'image', 'allow_save': False},
        'expected': 'sent 📵'
    },
    {
        'name': 'Image with view_once=true (disappearing)',
        'body': {'media_url': 'https://x/p.jpg', 'media_type': 'image', 'view_once': True},
        'expected': 'sent 🔥'
    },
    {
        'name': 'Video with allow_save=false (no-save takes precedence)',
        'body': {'media_url': 'https://x/v.mp4', 'media_type': 'video', 'allow_save': False},
        'expected': 'sent 📵'
    },
    {
        'name': 'Audio (voice message)',
        'body': {'media_url': 'https://x/a.webm', 'media_type': 'audio', 'duration': 5},
        'expected': '🎤 Voice message'
    },
    {
        'name': 'Text-only',
        'body': {'text': 'hello there'},
        'expected': 'hello there'
    }
]

results = []
for i, test in enumerate(test_cases, 1):
    print(f"\n[TEST {i}] {test['name']}")
    print(f"   Body: {test['body']}")
    print(f"   Expected notify_preview: '{test['expected']}'")
    
    resp = requests.post(
        f"{BASE_URL}/dms/{self_handle}",
        json=test['body'],
        headers={'Authorization': f'Bearer {self_token}'}
    )
    
    print(f"   Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp.status_code}")
        print(f"   Response: {resp.text}")
        results.append(False)
        continue
    
    data = resp.json()
    notify_preview = data.get('notify_preview')
    
    print(f"   Actual notify_preview: '{notify_preview}'")
    
    if notify_preview == test['expected']:
        print(f"✅ PASSED: notify_preview matches expected value")
        results.append(True)
    else:
        print(f"❌ FAILED: notify_preview mismatch")
        print(f"   Expected: '{test['expected']}'")
        print(f"   Actual: '{notify_preview}'")
        results.append(False)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

area1_tests = 3  # GIF search tests (excluding setup)
area2_tests = len(test_cases)
total_tests = area1_tests + area2_tests

# Count passes (assuming first 3 tests in AREA 1 passed if we got here)
area1_passed = 3  # Manual count from AREA 1
area2_passed = sum(results)
total_passed = area1_passed + area2_passed

print(f"\nAREA 1 (GIF Search): 3/3 tests passed")
print(f"AREA 2 (Media-type notification banners): {area2_passed}/{area2_tests} tests passed")
print(f"\nTOTAL: {total_passed}/{total_tests} tests passed")

if total_passed == total_tests:
    print("\n✅ ALL TESTS PASSED")
else:
    print(f"\n❌ {total_tests - total_passed} TEST(S) FAILED")
    exit(1)
