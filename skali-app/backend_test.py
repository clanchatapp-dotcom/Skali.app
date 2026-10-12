#!/usr/bin/env python3
"""
Backend API testing for Skali app - Stories API, Creator Hub v2, Finance Exports
Tests the LOCAL sandbox FastAPI backend at http://localhost:8001/api
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL
BASE_URL = "http://localhost:8001/api"

def register_adult_user(email_prefix):
    """Register a throwaway ADULT user (DOB 1990-01-01)"""
    email = f"{email_prefix}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "name": email_prefix,
        "dob": "1990-01-01"  # ADULT user
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('access_token')
            handle = data['user']['handle']
            print(f"✓ Registered adult user: {email} (handle: {handle})")
            return token, handle
        else:
            print(f"✗ Registration failed: {resp.status_code} - {resp.text}")
            return None, None
    except Exception as e:
        print(f"✗ Registration error: {e}")
        return None, None


def test_stories_api(token, handle):
    """Test all 7 Stories API endpoints"""
    print("\n" + "="*80)
    print("TESTING STORIES API (7 tests)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    results = {"passed": 0, "failed": 0}
    story_id = None
    
    # Test 1: POST /api/stories - Create story
    print("\n[1/7] POST /api/stories - Create story")
    try:
        payload = {
            "media_url": "https://example.com/photo.jpg",
            "media_type": "image",
            "caption": "Test story caption"
        }
        resp = requests.post(f"{BASE_URL}/stories", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'id' in data and 'expires_at' in data:
                story_id = data['id']
                print(f"✓ PASSED: Story created with id={story_id}, expires_at={data['expires_at']}")
                results["passed"] += 1
            else:
                print(f"✗ FAILED: Missing required fields in response: {data}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 2: GET /api/stories - Get stories feed (should contain own story)
    print("\n[2/7] GET /api/stories - Get stories feed")
    try:
        resp = requests.get(f"{BASE_URL}/stories", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                # Find own ring
                own_ring = next((ring for ring in data if ring.get('is_self')), None)
                if own_ring and len(own_ring.get('stories', [])) >= 1:
                    print(f"✓ PASSED: Stories feed returned, own ring found with {len(own_ring['stories'])} story(ies)")
                    results["passed"] += 1
                else:
                    print(f"✗ FAILED: Own ring not found or no stories in it. Data: {data}")
                    results["failed"] += 1
            else:
                print(f"✗ FAILED: Expected list, got: {type(data)}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 3: GET /api/stories/{handle} - Get own stories
    print(f"\n[3/7] GET /api/stories/{handle} - Get own stories")
    try:
        resp = requests.get(f"{BASE_URL}/stories/{handle}", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('is_self') and len(data.get('stories', [])) >= 1:
                print(f"✓ PASSED: Own stories returned, is_self=true, {len(data['stories'])} story(ies)")
                results["passed"] += 1
            else:
                print(f"✗ FAILED: is_self={data.get('is_self')}, stories count={len(data.get('stories', []))}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 4: POST /api/stories/{story_id}/view - View own story
    if story_id:
        print(f"\n[4/7] POST /api/stories/{story_id}/view - View story")
        try:
            resp = requests.post(f"{BASE_URL}/stories/{story_id}/view", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    print(f"✓ PASSED: View story returned ok=true (viewing own story is no-op but should not error)")
                    results["passed"] += 1
                else:
                    print(f"✗ FAILED: Expected ok=true, got: {data}")
                    results["failed"] += 1
            else:
                print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
                results["failed"] += 1
        except Exception as e:
            print(f"✗ FAILED: Exception - {e}")
            results["failed"] += 1
    else:
        print(f"\n[4/7] POST /api/stories/{story_id}/view - SKIPPED (no story_id)")
        results["failed"] += 1
    
    # Test 5: GET /api/stories/{story_id}/viewers - Get viewers (owner-only)
    if story_id:
        print(f"\n[5/7] GET /api/stories/{story_id}/viewers - Get viewers")
        try:
            resp = requests.get(f"{BASE_URL}/stories/{story_id}/viewers", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    print(f"✓ PASSED: Viewers list returned (array with {len(data)} viewer(s))")
                    results["passed"] += 1
                else:
                    print(f"✗ FAILED: Expected array, got: {type(data)}")
                    results["failed"] += 1
            else:
                print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
                results["failed"] += 1
        except Exception as e:
            print(f"✗ FAILED: Exception - {e}")
            results["failed"] += 1
    else:
        print(f"\n[5/7] GET /api/stories/{story_id}/viewers - SKIPPED (no story_id)")
        results["failed"] += 1
    
    # Test 6: DELETE /api/stories/{story_id} - Delete story
    if story_id:
        print(f"\n[6/7] DELETE /api/stories/{story_id} - Delete story")
        try:
            resp = requests.delete(f"{BASE_URL}/stories/{story_id}", headers=headers, timeout=10)
            if resp.status_code in [200, 204]:
                print(f"✓ PASSED: Story deleted (status {resp.status_code})")
                results["passed"] += 1
                
                # Verify deletion by checking GET /api/stories/{handle}
                verify_resp = requests.get(f"{BASE_URL}/stories/{handle}", headers=headers, timeout=10)
                if verify_resp.status_code == 200:
                    verify_data = verify_resp.json()
                    if len(verify_data.get('stories', [])) == 0:
                        print(f"  ✓ Verified: GET /api/stories/{handle} now shows 0 stories")
                    else:
                        print(f"  ⚠ Warning: GET /api/stories/{handle} still shows {len(verify_data['stories'])} story(ies)")
            else:
                print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
                results["failed"] += 1
        except Exception as e:
            print(f"✗ FAILED: Exception - {e}")
            results["failed"] += 1
    else:
        print(f"\n[6/7] DELETE /api/stories/{story_id} - SKIPPED (no story_id)")
        results["failed"] += 1
    
    # Test 7: GET /api/stories with NO auth - Should return 401
    print("\n[7/7] GET /api/stories with NO auth - Should return 401")
    try:
        resp = requests.get(f"{BASE_URL}/stories", timeout=10)
        if resp.status_code == 401:
            print(f"✓ PASSED: No auth returned 401 (authentication enforced)")
            results["passed"] += 1
        else:
            print(f"✗ FAILED: Expected 401, got {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    print(f"\n{'='*80}")
    print(f"STORIES API RESULTS: {results['passed']}/7 PASSED, {results['failed']}/7 FAILED")
    print(f"{'='*80}")
    
    return results


def test_creator_hub_v2(token, handle):
    """Test Creator Hub v2 endpoints (5 tests)"""
    print("\n" + "="*80)
    print("TESTING CREATOR HUB V2 (5 tests)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    results = {"passed": 0, "failed": 0}
    
    # Test 1: GET /api/creator/me - Get creator status
    print("\n[1/5] GET /api/creator/me - Get creator status")
    try:
        resp = requests.get(f"{BASE_URL}/creator/me", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ['is_creator', 'creator_type', 'creator_types', 'can_sell', 
                           'inner_circle_min', 'inner_circle_max', 'inner_circle_price', 'health']
            missing_keys = [k for k in required_keys if k not in data]
            
            if not missing_keys:
                # Verify expected values
                if data['inner_circle_min'] == 10.0 and data['inner_circle_max'] == 50.0:
                    health = data.get('health', {})
                    if 'collection_enabled' in health and 'hidden' in health:
                        print(f"✓ PASSED: All required keys present with correct values")
                        print(f"  - is_creator: {data['is_creator']}")
                        print(f"  - creator_type: {data['creator_type']}")
                        print(f"  - creator_types: {data['creator_types']}")
                        print(f"  - can_sell: {data['can_sell']}")
                        print(f"  - inner_circle_min: {data['inner_circle_min']}")
                        print(f"  - inner_circle_max: {data['inner_circle_max']}")
                        print(f"  - inner_circle_price: {data['inner_circle_price']}")
                        print(f"  - health: {health}")
                        results["passed"] += 1
                    else:
                        print(f"✗ FAILED: health object missing required keys: {health}")
                        results["failed"] += 1
                else:
                    print(f"✗ FAILED: inner_circle_min={data['inner_circle_min']} (expected 10.0), inner_circle_max={data['inner_circle_max']} (expected 50.0)")
                    results["failed"] += 1
            else:
                print(f"✗ FAILED: Missing required keys: {missing_keys}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 2: POST /api/creator/enable - Enable creator with gaming type
    print("\n[2/5] POST /api/creator/enable - Enable creator with gaming type")
    try:
        payload = {"enabled": True, "creator_type": "gaming"}
        resp = requests.post(f"{BASE_URL}/creator/enable", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('is_creator') and data.get('creator_type') == 'gaming':
                print(f"✓ PASSED: Creator enabled with is_creator=true, creator_type='gaming'")
                results["passed"] += 1
            else:
                print(f"✗ FAILED: is_creator={data.get('is_creator')}, creator_type={data.get('creator_type')}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 3: POST /api/creator/enable with 'adult' type on NON age-verified user - Should return 403
    print("\n[3/5] POST /api/creator/enable with 'adult' type (non age-verified) - Should return 403")
    try:
        payload = {"creator_type": "adult"}
        resp = requests.post(f"{BASE_URL}/creator/enable", json=payload, headers=headers, timeout=10)
        if resp.status_code == 403:
            print(f"✓ PASSED: Adult creator type blocked for non age-verified user (403)")
            results["passed"] += 1
        else:
            print(f"✗ FAILED: Expected 403, got {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 4: GET /api/creator/health - Should return 200 for creator, 403 for non-creator
    print("\n[4/5] GET /api/creator/health - Should return 200 for creator")
    try:
        resp = requests.get(f"{BASE_URL}/creator/health", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ['settings', 'collecting', 'metrics']
            missing_keys = [k for k in required_keys if k not in data]
            if not missing_keys:
                print(f"✓ PASSED: Creator health returned with settings, collecting, metrics")
                print(f"  - settings: {data['settings']}")
                print(f"  - collecting: {data['collecting']}")
                results["passed"] += 1
            else:
                print(f"✗ FAILED: Missing required keys: {missing_keys}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 5: PUT /api/creator/health/settings - Update health settings
    print("\n[5/5] PUT /api/creator/health/settings - Update health settings")
    try:
        payload = {"hidden": True}
        resp = requests.put(f"{BASE_URL}/creator/health/settings", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'collection_enabled' in data and data.get('hidden') == True:
                print(f"✓ PASSED: Health settings updated, hidden=true")
                print(f"  - collection_enabled: {data['collection_enabled']}")
                print(f"  - hidden: {data['hidden']}")
                results["passed"] += 1
            else:
                print(f"✗ FAILED: Expected hidden=true, got: {data}")
                results["failed"] += 1
        else:
            print(f"✗ FAILED: Status {resp.status_code} - {resp.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    print(f"\n{'='*80}")
    print(f"CREATOR HUB V2 RESULTS: {results['passed']}/5 PASSED, {results['failed']}/5 FAILED")
    print(f"{'='*80}")
    
    return results


def test_finance_exports(token, handle):
    """Test Finance Export endpoints (2 tests)"""
    print("\n" + "="*80)
    print("TESTING FINANCE EXPORTS (2 tests)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    results = {"passed": 0, "failed": 0}
    
    # Test 1: GET /api/creator/finance/export.pdf - Should return 403 for non-monetisation user
    print("\n[1/2] GET /api/creator/finance/export.pdf - Should return 403 (non-monetisation user)")
    try:
        resp = requests.get(f"{BASE_URL}/creator/finance/export.pdf", headers=headers, timeout=10)
        if resp.status_code == 403:
            print(f"✓ PASSED: PDF export correctly gated by monetisation (403 for unverified user)")
            print(f"  Note: This 403 is EXPECTED and CORRECT behavior (not a bug)")
            results["passed"] += 1
        elif resp.status_code == 200 and resp.headers.get('content-type') == 'application/pdf':
            print(f"⚠ WARNING: PDF export returned 200 (user may have monetisation unlocked)")
            print(f"  Note: If user has creator_override or is verified, 200 is correct")
            results["passed"] += 1
        else:
            print(f"✗ FAILED: Expected 403 or 200 with PDF, got {resp.status_code} - content-type: {resp.headers.get('content-type')}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    # Test 2: GET /api/creator/finance/export.csv - Should also return 403 for non-monetisation user
    print("\n[2/2] GET /api/creator/finance/export.csv - Should return 403 (non-monetisation user)")
    try:
        resp = requests.get(f"{BASE_URL}/creator/finance/export.csv", headers=headers, timeout=10)
        if resp.status_code == 403:
            print(f"✓ PASSED: CSV export correctly gated by monetisation (403 for unverified user)")
            print(f"  Note: This 403 is EXPECTED and CORRECT behavior (not a bug)")
            results["passed"] += 1
        elif resp.status_code == 200 and 'text/csv' in resp.headers.get('content-type', ''):
            print(f"⚠ WARNING: CSV export returned 200 (user may have monetisation unlocked)")
            print(f"  Note: If user has creator_override or is verified, 200 is correct")
            results["passed"] += 1
        else:
            print(f"✗ FAILED: Expected 403 or 200 with CSV, got {resp.status_code} - content-type: {resp.headers.get('content-type')}")
            results["failed"] += 1
    except Exception as e:
        print(f"✗ FAILED: Exception - {e}")
        results["failed"] += 1
    
    print(f"\n{'='*80}")
    print(f"FINANCE EXPORTS RESULTS: {results['passed']}/2 PASSED, {results['failed']}/2 FAILED")
    print(f"{'='*80}")
    
    return results


def main():
    print("="*80)
    print("SKALI BACKEND API TESTING")
    print("Testing LOCAL sandbox FastAPI backend at http://localhost:8001/api")
    print("="*80)
    
    # Generate unique email prefix with timestamp
    timestamp = datetime.now().strftime("%H%M%S")
    email_prefix = f"testuser_{timestamp}"
    
    # Register throwaway ADULT user
    print(f"\nRegistering throwaway ADULT user (DOB 1990-01-01)...")
    token, handle = register_adult_user(email_prefix)
    
    if not token or not handle:
        print("\n✗ FAILED: Could not register user. Aborting tests.")
        sys.exit(1)
    
    # Run all tests
    all_results = {"passed": 0, "failed": 0}
    
    # Test Stories API
    stories_results = test_stories_api(token, handle)
    all_results["passed"] += stories_results["passed"]
    all_results["failed"] += stories_results["failed"]
    
    # Test Creator Hub v2
    creator_results = test_creator_hub_v2(token, handle)
    all_results["passed"] += creator_results["passed"]
    all_results["failed"] += creator_results["failed"]
    
    # Test Finance Exports
    finance_results = test_finance_exports(token, handle)
    all_results["passed"] += finance_results["passed"]
    all_results["failed"] += finance_results["failed"]
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Total Tests: {all_results['passed'] + all_results['failed']}")
    print(f"✓ PASSED: {all_results['passed']}")
    print(f"✗ FAILED: {all_results['failed']}")
    print(f"Success Rate: {(all_results['passed'] / (all_results['passed'] + all_results['failed']) * 100):.1f}%")
    print("="*80)
    
    # Exit with appropriate code
    sys.exit(0 if all_results['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
