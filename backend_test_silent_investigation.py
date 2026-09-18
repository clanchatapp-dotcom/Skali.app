#!/usr/bin/env python3
"""
Test script for Silent Investigation Admin Endpoint
Tests GET /api/admin/investigate/{handle} with all required scenarios
"""
import requests
import uuid
import json
from datetime import datetime

# Backend URL
BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def register_user(email, password, dob, handle_prefix):
    """Register a new user and return token + handle"""
    handle = f"{handle_prefix}{uuid.uuid4().hex[:8]}"
    payload = {
        "email": email,
        "password": password,
        "handle": handle,
        "display_name": f"Test {handle_prefix}",
        "dob": dob
    }
    r = requests.post(f"{BASE_URL}/auth/register", json=payload)
    if r.status_code != 200:
        log(f"❌ Failed to register {handle}: {r.status_code} {r.text}")
        return None, None
    data = r.json()
    token = data.get('access_token') or data.get('token')
    actual_handle = data.get('user', {}).get('handle') or handle
    log(f"✅ Registered user: {actual_handle}")
    return token, actual_handle

def login_admin():
    """Login as seeded admin"""
    payload = {
        "email": "admin@clanchat.app",
        "password": "ClanChatAdmin!2025"
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=payload)
    if r.status_code != 200:
        log(f"❌ Admin login failed: {r.status_code} {r.text}")
        return None
    data = r.json()
    log(f"✅ Admin logged in")
    return data.get('access_token') or data.get('token')

def create_post(token, text, tier='public'):
    """Create a post"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"text": text, "tier": tier}
    r = requests.post(f"{BASE_URL}/posts", json=payload, headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to create post: {r.status_code} {r.text}")
        return None
    data = r.json()
    log(f"✅ Created post: {data.get('id')}")
    return data.get('id')

def send_dm(token, handle, text):
    """Send a DM to a user"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"text": text}
    r = requests.post(f"{BASE_URL}/dms/{handle}", json=payload, headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to send DM: {r.status_code} {r.text}")
        return False
    log(f"✅ Sent DM to {handle}")
    return True

def invite_inner_circle(token, handle):
    """Invite user to inner circle"""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/inner/invite/{handle}", headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to invite to inner circle: {r.status_code} {r.text}")
        return False
    log(f"✅ Invited {handle} to inner circle")
    return True

def accept_inner_invite(token, handle):
    """Accept inner circle invite"""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/inner/accept/{handle}", headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to accept inner invite: {r.status_code} {r.text}")
        return False
    log(f"✅ Accepted inner circle invite from {handle}")
    return True

def watch_user(admin_token, handle, reason):
    """Watch a user"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"reason": reason}
    r = requests.post(f"{BASE_URL}/admin/users/{handle}/watch", json=payload, headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to watch user: {r.status_code} {r.text}")
        return False
    log(f"✅ Watched user {handle}")
    return True

def unwatch_user(admin_token, handle):
    """Unwatch a user"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.post(f"{BASE_URL}/admin/users/{handle}/unwatch", headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to unwatch user: {r.status_code} {r.text}")
        return False
    log(f"✅ Unwatched user {handle}")
    return True

def flag_user(admin_token, handle, reason):
    """Flag a user"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"reason": reason}
    r = requests.post(f"{BASE_URL}/admin/users/{handle}/flag", json=payload, headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to flag user: {r.status_code} {r.text}")
        return False
    log(f"✅ Flagged user {handle}")
    return True

def investigate(token, handle):
    """Call investigate endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/admin/investigate/{handle}", headers=headers)
    return r

def get_audit_log(admin_token):
    """Get audit log"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE_URL}/admin/audit", headers=headers)
    if r.status_code != 200:
        log(f"❌ Failed to get audit log: {r.status_code} {r.text}")
        return []
    return r.json()

def main():
    log("=" * 80)
    log("SILENT INVESTIGATION ENDPOINT TEST")
    log("=" * 80)
    
    # Login as admin
    log("\n[SETUP] Logging in as admin...")
    admin_token = login_admin()
    if not admin_token:
        log("❌ CRITICAL: Cannot proceed without admin token")
        return
    
    # Register SUBJECT user (adult)
    log("\n[SETUP] Registering SUBJECT user (adult, DOB 1990-01-01)...")
    subject_email = f"subject+{uuid.uuid4().hex[:8]}@example.com"
    subject_token, subject_handle = register_user(subject_email, "Test1234!", "1990-01-01", "subject")
    if not subject_token:
        log("❌ CRITICAL: Cannot proceed without SUBJECT user")
        return
    
    # SUBJECT creates 2 posts
    log("\n[SETUP] SUBJECT creating 2 posts...")
    post1_id = create_post(subject_token, "inv post 1", "public")
    post2_id = create_post(subject_token, "inv post 2", "public")
    if not post1_id or not post2_id:
        log("❌ CRITICAL: Failed to create posts")
        return
    
    # Register OTHER user (adult)
    log("\n[SETUP] Registering OTHER user (adult, DOB 1990-01-01)...")
    other_email = f"other+{uuid.uuid4().hex[:8]}@example.com"
    other_token, other_handle = register_user(other_email, "Test1234!", "1990-01-01", "other")
    if not other_token:
        log("❌ CRITICAL: Cannot proceed without OTHER user")
        return
    
    # Establish DM between SUBJECT and OTHER (via inner circle)
    log("\n[SETUP] Establishing DM between SUBJECT and OTHER...")
    
    # Try direct DM first (might work if dm_open is true)
    log("  - Attempting direct DM from SUBJECT to OTHER...")
    if not send_dm(subject_token, other_handle, "secret dm"):
        # If direct DM fails, establish inner circle relationship
        log("  - Direct DM failed, establishing inner circle relationship...")
        log("  - SUBJECT invites OTHER to inner circle...")
        if not invite_inner_circle(subject_token, other_handle):
            # Try the other way - OTHER invites SUBJECT
            log("  - Failed. Trying OTHER invites SUBJECT to inner circle...")
            if not invite_inner_circle(other_token, subject_handle):
                log("❌ CRITICAL: Failed to establish inner circle relationship")
                return
            log("  - SUBJECT accepts inner circle invite...")
            if not accept_inner_invite(subject_token, other_handle):
                log("❌ CRITICAL: Failed to accept inner circle invite")
                return
        else:
            log("  - OTHER accepts inner circle invite...")
            if not accept_inner_invite(other_token, subject_handle):
                log("❌ CRITICAL: Failed to accept inner circle invite")
                return
        
        log("  - SUBJECT sends DM to OTHER (after inner circle setup)...")
        if not send_dm(subject_token, other_handle, "secret dm"):
            log("❌ CRITICAL: Failed to send DM even after inner circle setup")
            return
    
    # TEST 1: NOT-GATED - investigate non-flagged/non-watchlisted user
    log("\n" + "=" * 80)
    log("TEST 1: NOT-GATED - ADMIN investigates SUBJECT (not flagged/watchlisted)")
    log("=" * 80)
    r = investigate(admin_token, subject_handle)
    if r.status_code == 403 and 'Watchlisted or Flagged' in r.text:
        log(f"✅ TEST 1 PASSED: Got 403 with correct message")
        log(f"   Response: {r.status_code} - {r.text[:200]}")
    else:
        log(f"❌ TEST 1 FAILED: Expected 403 with 'Watchlisted or Flagged', got {r.status_code}")
        log(f"   Response: {r.text[:500]}")
    
    # TEST 2: GATE via watchlist - watch SUBJECT then investigate
    log("\n" + "=" * 80)
    log("TEST 2: GATE via watchlist - watch SUBJECT then investigate")
    log("=" * 80)
    if not watch_user(admin_token, subject_handle, "test warrant"):
        log("❌ TEST 2 SETUP FAILED: Could not watch user")
    else:
        r = investigate(admin_token, subject_handle)
        if r.status_code == 200:
            data = r.json()
            required_keys = ['subject', 'posts', 'dms', 'groups', 'legal_notice']
            missing_keys = [k for k in required_keys if k not in data]
            
            if not missing_keys:
                log(f"✅ TEST 2 PASSED: Got 200 with all required keys")
                log(f"   Top-level keys: {list(data.keys())}")
                log(f"   Subject: {data['subject'].get('handle')}")
                log(f"   Posts count: {len(data['posts'])}")
                log(f"   DMs count: {len(data['dms'])}")
                log(f"   Groups count: {len(data['groups'])}")
                
                # Check if posts are present
                if len(data['posts']) >= 2:
                    log(f"   ✅ Found {len(data['posts'])} posts (expected 2)")
                else:
                    log(f"   ⚠️  Found {len(data['posts'])} posts (expected 2)")
                
                # Check if DMs are present
                if len(data['dms']) >= 1:
                    log(f"   ✅ Found {len(data['dms'])} DM thread(s)")
                    dm_thread = data['dms'][0]
                    if 'messages' in dm_thread and len(dm_thread['messages']) > 0:
                        msg = dm_thread['messages'][0]
                        log(f"   ✅ DM message found with text: '{msg.get('text')}'")
                        log(f"   ✅ DM message has from_subject: {msg.get('from_subject')}")
                    else:
                        log(f"   ⚠️  DM thread has no messages")
                else:
                    log(f"   ⚠️  No DM threads found (expected 1)")
                
            else:
                log(f"❌ TEST 2 FAILED: Missing keys: {missing_keys}")
                log(f"   Response keys: {list(data.keys())}")
        else:
            log(f"❌ TEST 2 FAILED: Expected 200, got {r.status_code}")
            log(f"   Response: {r.text[:500]}")
    
    # TEST 3: AUDIT - check audit log for silent_investigation entry
    log("\n" + "=" * 80)
    log("TEST 3: AUDIT - check audit log for silent_investigation entry")
    log("=" * 80)
    audit_log = get_audit_log(admin_token)
    investigation_entries = [e for e in audit_log if e.get('action') == 'silent_investigation' and e.get('target') == subject_handle]
    if investigation_entries:
        log(f"✅ TEST 3 PASSED: Found {len(investigation_entries)} silent_investigation entry/entries for {subject_handle}")
        log(f"   Entry: action={investigation_entries[0].get('action')}, target={investigation_entries[0].get('target')}")
    else:
        log(f"❌ TEST 3 FAILED: No silent_investigation entry found for {subject_handle}")
        log(f"   Audit log entries: {len(audit_log)}")
        if audit_log:
            log(f"   Recent actions: {[e.get('action') for e in audit_log[:5]]}")
    
    # TEST 4: GATE via flag - unwatch, flag, then investigate
    log("\n" + "=" * 80)
    log("TEST 4: GATE via flag - unwatch SUBJECT, flag, then investigate")
    log("=" * 80)
    if not unwatch_user(admin_token, subject_handle):
        log("❌ TEST 4 SETUP FAILED: Could not unwatch user")
    elif not flag_user(admin_token, subject_handle, "test flag"):
        log("❌ TEST 4 SETUP FAILED: Could not flag user")
    else:
        r = investigate(admin_token, subject_handle)
        if r.status_code == 200:
            data = r.json()
            if 'subject' in data and 'posts' in data and 'dms' in data:
                log(f"✅ TEST 4 PASSED: Got 200 after flagging (flag also satisfies gate)")
                log(f"   Subject flagged: {data['subject'].get('flagged')}")
            else:
                log(f"❌ TEST 4 FAILED: Got 200 but missing keys")
        else:
            log(f"❌ TEST 4 FAILED: Expected 200, got {r.status_code}")
            log(f"   Response: {r.text[:500]}")
    
    # TEST 5: NON-ADMIN - normal user tries to investigate
    log("\n" + "=" * 80)
    log("TEST 5: NON-ADMIN - normal user tries to investigate")
    log("=" * 80)
    r = investigate(other_token, subject_handle)
    if r.status_code == 403:
        log(f"✅ TEST 5 PASSED: Normal user got 403")
        log(f"   Response: {r.status_code} - {r.text[:200]}")
    else:
        log(f"❌ TEST 5 FAILED: Expected 403, got {r.status_code}")
        log(f"   Response: {r.text[:500]}")
    
    # TEST 6: NOT FOUND - investigate nonexistent handle
    log("\n" + "=" * 80)
    log("TEST 6: NOT FOUND - investigate nonexistent handle")
    log("=" * 80)
    r = investigate(admin_token, "nonexistenthandle")
    if r.status_code == 404:
        log(f"✅ TEST 6 PASSED: Got 404 for nonexistent handle")
        log(f"   Response: {r.status_code} - {r.text[:200]}")
    else:
        log(f"❌ TEST 6 FAILED: Expected 404, got {r.status_code}")
        log(f"   Response: {r.text[:500]}")
    
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log("All 6 tests completed. Check results above.")
    log("=" * 80)

if __name__ == "__main__":
    main()
