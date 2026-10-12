#!/usr/bin/env python3
"""
Test script for Upheld-report counter + Creator Support escalation ladder feature.
Tests the NEW backend feature in /app/backend/server.py.
"""
import requests
import uuid
import sys

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

# Super admin credentials
SUPER_EMAIL = "admin@clanchat.app"
SUPER_PASSWORD = "ClanChatAdmin!2025"

def register_adult(email, password, name):
    """Register an adult user (DOB 1990-01-01)"""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "dob": "1990-01-01"
    })
    return resp

def login(email, password):
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None

def create_report(token, target_handle, category="harassment", note="test report"):
    """Create a report"""
    resp = requests.post(f"{BASE_URL}/report", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_type": "user",
            "target_id": target_handle,
            "category": category,
            "note": note
        })
    return resp

def uphold_report(token, report_id, reason="test uphold", severe=False):
    """Uphold a report"""
    resp = requests.post(f"{BASE_URL}/admin/reports/{report_id}/action",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "uphold",
            "reason": reason,
            "severe": severe
        })
    return resp

def get_admin_users(token, query):
    """Get admin users list"""
    resp = requests.get(f"{BASE_URL}/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query})
    return resp

def get_user_profile(token, handle):
    """Get user profile"""
    resp = requests.get(f"{BASE_URL}/users/{handle}",
        headers={"Authorization": f"Bearer {token}"})
    return resp

def clear_strikes(token, handle):
    """Clear strikes for a user"""
    resp = requests.post(f"{BASE_URL}/admin/users/{handle}/clear-strikes",
        headers={"Authorization": f"Bearer {token}"})
    return resp

def assign_role(token, handle, role):
    """Assign a role to a user"""
    resp = requests.post(f"{BASE_URL}/admin/roles/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "handle": handle,
            "role": role
        })
    return resp

def main():
    print("=" * 80)
    print("UPHELD-REPORT COUNTER + CREATOR SUPPORT ESCALATION LADDER TEST")
    print("=" * 80)
    
    # Generate unique identifiers for this test run
    test_id = str(uuid.uuid4())[:8]
    
    # Test users
    v_email = f"reporter_{test_id}@example.com"
    v_password = "Test1234!"
    v_name = f"Reporter{test_id}"
    
    t_email = f"target_{test_id}@example.com"
    t_password = "Test1234!"
    t_name = f"Target{test_id}"
    
    t2_email = f"target2_{test_id}@example.com"
    t2_password = "Test1234!"
    t2_name = f"Target2{test_id}"
    
    m_email = f"moderator_{test_id}@example.com"
    m_password = "Test1234!"
    m_name = f"Moderator{test_id}"
    
    print(f"\nTest ID: {test_id}")
    print(f"Reporter: {v_email}")
    print(f"Target: {t_email}")
    print(f"Target2: {t2_email}")
    print(f"Moderator: {m_email}")
    
    # Login super admin
    print("\n" + "=" * 80)
    print("SETUP: Login super admin")
    print("=" * 80)
    super_token = login(SUPER_EMAIL, SUPER_PASSWORD)
    if not super_token:
        print("❌ FAILED: Could not login super admin")
        return False
    print("✅ Super admin logged in")
    
    # Register users
    print("\n" + "=" * 80)
    print("SETUP: Register test users")
    print("=" * 80)
    
    # Register V (reporter)
    resp = register_adult(v_email, v_password, v_name)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not register reporter V: {resp.status_code} {resp.text}")
        return False
    v_token = resp.json()["access_token"]
    v_handle = resp.json()["user"]["handle"]
    print(f"✅ Registered reporter V: {v_handle}")
    
    # Register T (target)
    resp = register_adult(t_email, t_password, t_name)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not register target T: {resp.status_code} {resp.text}")
        return False
    t_token = resp.json()["access_token"]
    t_handle = resp.json()["user"]["handle"]
    print(f"✅ Registered target T: {t_handle}")
    
    # Register T2 (second target)
    resp = register_adult(t2_email, t2_password, t2_name)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not register target T2: {resp.status_code} {resp.text}")
        return False
    t2_token = resp.json()["access_token"]
    t2_handle = resp.json()["user"]["handle"]
    print(f"✅ Registered target T2: {t2_handle}")
    
    # Register M (moderator)
    resp = register_adult(m_email, m_password, m_name)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not register moderator M: {resp.status_code} {resp.text}")
        return False
    m_token = resp.json()["access_token"]
    m_handle = resp.json()["user"]["handle"]
    print(f"✅ Registered moderator M: {m_handle}")
    
    # Assign moderator role to M
    print("\n" + "=" * 80)
    print("SETUP: Assign moderator role to M")
    print("=" * 80)
    resp = assign_role(super_token, m_handle, "moderator")
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not assign moderator role: {resp.status_code} {resp.text}")
        return False
    print(f"✅ Assigned moderator role to {m_handle}")
    
    # TEST 1: Reach 5 upheld reports on T
    print("\n" + "=" * 80)
    print("TEST 1: Reach 5 upheld reports on T (escalation ladder)")
    print("=" * 80)
    
    test1_passed = True
    for i in range(1, 6):
        print(f"\n--- Uphold #{i} ---")
        
        # Create report
        resp = create_report(v_token, t_handle, "harassment", f"test report {i}")
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not create report {i}: {resp.status_code} {resp.text}")
            test1_passed = False
            break
        report_id = resp.json()["id"]
        print(f"✅ Created report {i}: {report_id}")
        
        # Uphold report
        resp = uphold_report(super_token, report_id, f"uphold reason {i}", severe=False)
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not uphold report {i}: {resp.status_code} {resp.text}")
            test1_passed = False
            break
        
        result = resp.json()
        upheld_count = result.get("upheld_reports", 0)
        stage = result.get("stage", "")
        
        print(f"✅ Upheld report {i}")
        print(f"   upheld_reports: {upheld_count}")
        print(f"   stage: {stage}")
        
        # Verify count
        if upheld_count != i:
            print(f"❌ FAILED: Expected upheld_reports={i}, got {upheld_count}")
            test1_passed = False
            break
        
        # Verify stage at count 3 (creator_safety_flag set in DB, stage is just "upheld_3")
        if i == 3:
            if stage != "upheld_3":
                print(f"❌ FAILED: Expected stage='upheld_3' at count 3, got {stage}")
                test1_passed = False
                break
            print("✅ Count 3: upheld_3 stage confirmed (creator_safety_flag set in DB)")
        
        # Verify stage at count 5 (7-day suspension)
        if i == 5:
            if stage != "upheld_5":
                print(f"❌ FAILED: Expected stage='upheld_5' at count 5, got {stage}")
                test1_passed = False
                break
            print("✅ Count 5: upheld_5 stage confirmed (7-day suspension)")
    
    if test1_passed:
        print("\n✅ TEST 1 PASSED: Escalation ladder working correctly (1-5 upheld reports)")
    else:
        print("\n❌ TEST 1 FAILED")
    
    # TEST 2: GET /api/admin/users?q=<T_handle> → T has upheld_reports=5, creator_safety_flag=true, suspended_until set
    print("\n" + "=" * 80)
    print("TEST 2: Verify T in admin users list")
    print("=" * 80)
    
    resp = get_admin_users(super_token, t_handle)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not get admin users: {resp.status_code} {resp.text}")
        test2_passed = False
    else:
        users = resp.json()
        t_user = next((u for u in users if u["handle"] == t_handle), None)
        if not t_user:
            print(f"❌ FAILED: Could not find T in admin users list")
            test2_passed = False
        else:
            print(f"✅ Found T in admin users list")
            print(f"   upheld_reports: {t_user.get('upheld_reports', 0)}")
            print(f"   creator_safety_flag: {t_user.get('creator_safety_flag', False)}")
            print(f"   suspended_until: {t_user.get('suspended_until', 'None')}")
            
            test2_passed = True
            if t_user.get("upheld_reports", 0) != 5:
                print(f"❌ FAILED: Expected upheld_reports=5, got {t_user.get('upheld_reports', 0)}")
                test2_passed = False
            if not t_user.get("creator_safety_flag", False):
                print(f"❌ FAILED: Expected creator_safety_flag=true, got {t_user.get('creator_safety_flag', False)}")
                test2_passed = False
            if not t_user.get("suspended_until"):
                print(f"❌ FAILED: Expected suspended_until to be set, got None")
                test2_passed = False
            
            if test2_passed:
                print("✅ TEST 2 PASSED: T has upheld_reports=5, creator_safety_flag=true, suspended_until set")
            else:
                print("❌ TEST 2 FAILED")
    
    # TEST 3: GET /api/users/{T_handle} → creator_safety_flag=true in the profile
    print("\n" + "=" * 80)
    print("TEST 3: Verify creator_safety_flag in public profile")
    print("=" * 80)
    
    resp = get_user_profile(v_token, t_handle)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not get user profile: {resp.status_code} {resp.text}")
        test3_passed = False
    else:
        profile = resp.json()
        creator_safety_flag = profile.get("creator_safety_flag", False)
        print(f"✅ Got user profile")
        print(f"   creator_safety_flag: {creator_safety_flag}")
        
        if creator_safety_flag:
            print("✅ TEST 3 PASSED: creator_safety_flag=true in public profile")
            test3_passed = True
        else:
            print("❌ TEST 3 FAILED: Expected creator_safety_flag=true, got false")
            test3_passed = False
    
    # TEST 4: Zero-tolerance: create a report against T2, uphold with severe=true
    print("\n" + "=" * 80)
    print("TEST 4: Zero-tolerance (severe=true)")
    print("=" * 80)
    
    # Create report against T2
    resp = create_report(v_token, t2_handle, "harassment", "zero tolerance test")
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not create report against T2: {resp.status_code} {resp.text}")
        test4_passed = False
    else:
        report_id = resp.json()["id"]
        print(f"✅ Created report against T2: {report_id}")
        
        # Uphold with severe=true
        resp = uphold_report(super_token, report_id, "zero tolerance", severe=True)
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not uphold report with severe=true: {resp.status_code} {resp.text}")
            test4_passed = False
        else:
            result = resp.json()
            stage = result.get("stage", "")
            banned = result.get("banned", False)
            
            print(f"✅ Upheld report with severe=true")
            print(f"   stage: {stage}")
            print(f"   banned: {banned}")
            
            test4_passed = True
            if stage != "terminated_no_appeal":
                print(f"❌ FAILED: Expected stage='terminated_no_appeal', got '{stage}'")
                test4_passed = False
            if not banned:
                print(f"❌ FAILED: Expected banned=true, got {banned}")
                test4_passed = False
            
            # Verify in admin users list
            resp = get_admin_users(super_token, t2_handle)
            if resp.status_code != 200:
                print(f"❌ FAILED: Could not get admin users: {resp.status_code} {resp.text}")
                test4_passed = False
            else:
                users = resp.json()
                t2_user = next((u for u in users if u["handle"] == t2_handle), None)
                if not t2_user:
                    print(f"❌ FAILED: Could not find T2 in admin users list")
                    test4_passed = False
                else:
                    print(f"✅ Found T2 in admin users list")
                    print(f"   banned: {t2_user.get('banned', False)}")
                    print(f"   no_appeal: {t2_user.get('no_appeal', False)}")
                    
                    if not t2_user.get("banned", False):
                        print(f"❌ FAILED: Expected banned=true, got {t2_user.get('banned', False)}")
                        test4_passed = False
                    if not t2_user.get("no_appeal", False):
                        print(f"❌ FAILED: Expected no_appeal=true, got {t2_user.get('no_appeal', False)}")
                        test4_passed = False
            
            if test4_passed:
                print("✅ TEST 4 PASSED: Zero-tolerance working correctly (banned=true, no_appeal=true)")
            else:
                print("❌ TEST 4 FAILED")
    
    # TEST 5: Rehab: super POST /api/admin/users/{T_handle}/clear-strikes → 200
    print("\n" + "=" * 80)
    print("TEST 5: Rehab clear-strikes for T (normal user)")
    print("=" * 80)
    
    resp = clear_strikes(super_token, t_handle)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not clear strikes for T: {resp.status_code} {resp.text}")
        test5_passed = False
    else:
        print(f"✅ Cleared strikes for T")
        
        # Verify in admin users list
        resp = get_admin_users(super_token, t_handle)
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not get admin users: {resp.status_code} {resp.text}")
            test5_passed = False
        else:
            users = resp.json()
            t_user = next((u for u in users if u["handle"] == t_handle), None)
            if not t_user:
                print(f"❌ FAILED: Could not find T in admin users list")
                test5_passed = False
            else:
                print(f"✅ Found T in admin users list")
                print(f"   upheld_reports: {t_user.get('upheld_reports', 0)}")
                print(f"   creator_safety_flag: {t_user.get('creator_safety_flag', False)}")
                
                test5_passed = True
                if t_user.get("upheld_reports", 0) != 0:
                    print(f"❌ FAILED: Expected upheld_reports=0, got {t_user.get('upheld_reports', 0)}")
                    test5_passed = False
                if t_user.get("creator_safety_flag", False):
                    print(f"❌ FAILED: Expected creator_safety_flag=false, got {t_user.get('creator_safety_flag', False)}")
                    test5_passed = False
                
                if test5_passed:
                    print("✅ TEST 5 PASSED: Clear-strikes working correctly (upheld_reports=0, creator_safety_flag=false)")
                else:
                    print("❌ TEST 5 FAILED")
    
    # TEST 6: super POST /api/admin/users/{T2_handle}/clear-strikes → 403 (zero-tolerance no_appeal cannot be cleared)
    print("\n" + "=" * 80)
    print("TEST 6: Rehab clear-strikes for T2 (zero-tolerance, should fail)")
    print("=" * 80)
    
    resp = clear_strikes(super_token, t2_handle)
    if resp.status_code == 403:
        print(f"✅ TEST 6 PASSED: Clear-strikes correctly blocked for zero-tolerance user (403)")
        test6_passed = True
    else:
        print(f"❌ FAILED: Expected 403, got {resp.status_code}")
        print(f"   Response: {resp.text}")
        test6_passed = False
    
    # TEST 7: Permissions - moderator can uphold but not clear-strikes
    print("\n" + "=" * 80)
    print("TEST 7: Permissions - moderator can uphold but not clear-strikes")
    print("=" * 80)
    
    # Create a new target for moderator test
    t3_email = f"target3_{test_id}@example.com"
    t3_password = "Test1234!"
    t3_name = f"Target3{test_id}"
    
    resp = register_adult(t3_email, t3_password, t3_name)
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not register target T3: {resp.status_code} {resp.text}")
        test7_passed = False
    else:
        t3_handle = resp.json()["user"]["handle"]
        print(f"✅ Registered target T3: {t3_handle}")
        
        # Create report against T3
        resp = create_report(v_token, t3_handle, "harassment", "moderator test")
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not create report against T3: {resp.status_code} {resp.text}")
            test7_passed = False
        else:
            report_id = resp.json()["id"]
            print(f"✅ Created report against T3: {report_id}")
            
            # Moderator uphold (should succeed)
            resp = uphold_report(m_token, report_id, "moderator uphold", severe=False)
            if resp.status_code != 200:
                print(f"❌ FAILED: Moderator could not uphold report: {resp.status_code} {resp.text}")
                test7_passed = False
            else:
                print(f"✅ Moderator successfully upheld report")
                
                # Moderator clear-strikes (should fail with 403)
                resp = clear_strikes(m_token, t3_handle)
                if resp.status_code == 403:
                    print(f"✅ TEST 7 PASSED: Moderator can uphold (200) but not clear-strikes (403)")
                    test7_passed = True
                else:
                    print(f"❌ FAILED: Expected 403 for moderator clear-strikes, got {resp.status_code}")
                    print(f"   Response: {resp.text}")
                    test7_passed = False
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    all_tests = [
        ("TEST 1: Escalation ladder (1-5 upheld reports)", test1_passed),
        ("TEST 2: Admin users list verification", test2_passed),
        ("TEST 3: Public profile creator_safety_flag", test3_passed),
        ("TEST 4: Zero-tolerance (severe=true)", test4_passed),
        ("TEST 5: Rehab clear-strikes (normal user)", test5_passed),
        ("TEST 6: Rehab clear-strikes blocked (zero-tolerance)", test6_passed),
        ("TEST 7: Moderator permissions", test7_passed),
    ]
    
    passed = sum(1 for _, p in all_tests if p)
    total = len(all_tests)
    
    for name, result in all_tests:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
