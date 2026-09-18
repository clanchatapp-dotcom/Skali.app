#!/usr/bin/env python3
"""
Test NEW DM media behavior: allow_save and view_once features.
Tests 6 scenarios as specified in the review request.
"""
import requests
import uuid
from datetime import datetime, timedelta

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"

def register_adult_user(email_prefix):
    """Register an adult user (DOB 1990-01-01) and return token + handle."""
    email = f"{email_prefix}+{uuid.uuid4().hex[:8]}@example.com"
    password = "Test1234!"
    dob = "1990-01-01"  # Adult user
    
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "dob": dob
    })
    
    if resp.status_code != 200:
        print(f"❌ Failed to register {email_prefix}: {resp.status_code} {resp.text}")
        return None, None
    
    data = resp.json()
    token = data.get("access_token")
    user = data.get("user", {})
    handle = user.get("handle")
    
    print(f"✅ Registered {email_prefix}: handle={handle}, email={email}")
    return token, handle

def setup_inner_circle_dm(token_a, handle_a, token_b, handle_b):
    """Setup inner circle relationship so A and B can DM."""
    # A invites B to inner circle
    resp = requests.post(
        f"{BASE_URL}/inner/invite/{handle_b}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    if resp.status_code != 200:
        print(f"❌ A failed to invite B to inner circle: {resp.status_code} {resp.text}")
        return False
    print(f"✅ A invited B to inner circle")
    
    # B accepts A's inner circle invite
    resp = requests.post(
        f"{BASE_URL}/inner/accept/{handle_a}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    if resp.status_code != 200:
        print(f"❌ B failed to accept A's inner circle invite: {resp.status_code} {resp.text}")
        return False
    print(f"✅ B accepted A's inner circle invite")
    
    return True

def send_dm(token, handle, payload):
    """Send a DM to handle with given payload."""
    resp = requests.post(
        f"{BASE_URL}/dms/{handle}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    return resp

def get_dm_history(token, handle):
    """Get DM history with handle."""
    resp = requests.get(
        f"{BASE_URL}/dms/{handle}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp

def view_once_message(token, handle, message_id):
    """View a view-once message."""
    resp = requests.post(
        f"{BASE_URL}/dms/{handle}/{message_id}/view",
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp

def delete_dm(token, handle, message_id):
    """Delete a DM message."""
    resp = requests.delete(
        f"{BASE_URL}/dms/{handle}/{message_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp

def main():
    print("\n" + "="*80)
    print("TEST: NEW DM MEDIA BEHAVIOR - allow_save and view_once")
    print("="*80 + "\n")
    
    # Setup: Create two adult users A & B
    print("SETUP: Creating two adult users A & B...")
    token_a, handle_a = register_adult_user("dmmedia_a")
    token_b, handle_b = register_adult_user("dmmedia_b")
    
    if not token_a or not token_b:
        print("❌ SETUP FAILED: Could not create users")
        return
    
    # Setup: Make DMs allowed between A & B (inner circle)
    print("\nSETUP: Establishing inner circle relationship for DM access...")
    if not setup_inner_circle_dm(token_a, handle_a, token_b, handle_b):
        print("❌ SETUP FAILED: Could not establish inner circle")
        return
    
    print("\n" + "="*80)
    print("TEST 1: ALLOW_SAVE DEFAULT (should be true)")
    print("="*80)
    
    try:
        # A sends image with default allow_save (should be true)
        payload = {
            "media_url": "https://example.com/a.jpg",
            "media_type": "image"
        }
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 1 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            allow_save = data.get("allow_save")
            print(f"✅ A POST /api/dms/{handle_b} → 200")
            
            if allow_save == True:
                print(f"✅ Response has allow_save == true ✓")
            else:
                print(f"❌ Response has allow_save == {allow_save} (expected true)")
            
            # B gets history
            resp_b = get_dm_history(token_b, handle_a)
            if resp_b.status_code != 200:
                print(f"❌ B GET /api/dms/{handle_a} → {resp_b.status_code} (expected 200)")
            else:
                data_b = resp_b.json()
                messages = data_b.get("messages", [])
                # Find the message with media_url='https://example.com/a.jpg'
                msg = next((m for m in messages if m.get("media_url") == "https://example.com/a.jpg"), None)
                if msg:
                    if msg.get("allow_save") == True:
                        print(f"✅ B GET history → message has allow_save == true ✓")
                        print(f"   TEST 1: PASS ✅")
                    else:
                        print(f"❌ B GET history → message has allow_save == {msg.get('allow_save')} (expected true)")
                        print(f"   TEST 1: FAIL ❌")
                else:
                    print(f"❌ B GET history → message not found")
                    print(f"   TEST 1: FAIL ❌")
    except Exception as e:
        print(f"❌ TEST 1 EXCEPTION: {e}")
        print(f"   TEST 1: FAIL ❌")
    
    print("\n" + "="*80)
    print("TEST 2: NO-SAVE (allow_save:false)")
    print("="*80)
    
    try:
        # A sends image with allow_save:false
        payload = {
            "media_url": "https://example.com/b.jpg",
            "media_type": "image",
            "allow_save": False
        }
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 2 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            allow_save = data.get("allow_save")
            print(f"✅ A POST /api/dms/{handle_b} → 200")
            
            if allow_save == False:
                print(f"✅ Response has allow_save == false ✓")
            else:
                print(f"❌ Response has allow_save == {allow_save} (expected false)")
            
            # B gets history
            resp_b = get_dm_history(token_b, handle_a)
            if resp_b.status_code != 200:
                print(f"❌ B GET /api/dms/{handle_a} → {resp_b.status_code} (expected 200)")
            else:
                data_b = resp_b.json()
                messages = data_b.get("messages", [])
                # Find the message with media_url='https://example.com/b.jpg'
                msg = next((m for m in messages if m.get("media_url") == "https://example.com/b.jpg"), None)
                if msg:
                    if msg.get("allow_save") == False:
                        print(f"✅ B GET history → message has allow_save == false ✓")
                        print(f"   TEST 2: PASS ✅")
                    else:
                        print(f"❌ B GET history → message has allow_save == {msg.get('allow_save')} (expected false)")
                        print(f"   TEST 2: FAIL ❌")
                else:
                    print(f"❌ B GET history → message not found")
                    print(f"   TEST 2: FAIL ❌")
    except Exception as e:
        print(f"❌ TEST 2 EXCEPTION: {e}")
        print(f"   TEST 2: FAIL ❌")
    
    print("\n" + "="*80)
    print("TEST 3: VIEW-ONCE FORCES NO-SAVE (view_once:true, allow_save:true → allow_save should be false)")
    print("="*80)
    
    try:
        # A sends image with view_once:true and allow_save:true
        # Expected: allow_save should be forced to false
        payload = {
            "media_url": "https://example.com/c.jpg",
            "media_type": "image",
            "view_once": True,
            "allow_save": True
        }
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 3 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            allow_save = data.get("allow_save")
            view_once = data.get("view_once")
            print(f"✅ A POST /api/dms/{handle_b} → 200")
            
            if view_once == True:
                print(f"✅ Response has view_once == true ✓")
            else:
                print(f"❌ Response has view_once == {view_once} (expected true)")
            
            if allow_save == False:
                print(f"✅ Response has allow_save == false (view-once is never savable) ✓")
                print(f"   TEST 3: PASS ✅")
            else:
                print(f"❌ Response has allow_save == {allow_save} (expected false, view-once should force no-save)")
                print(f"   TEST 3: FAIL ❌")
    except Exception as e:
        print(f"❌ TEST 3 EXCEPTION: {e}")
        print(f"   TEST 3: FAIL ❌")
    
    print("\n" + "="*80)
    print("TEST 4: SILENT DELETE (deleted messages should be fully hidden, no placeholder)")
    print("="*80)
    
    try:
        # A sends a normal text DM
        payload = {"text": "This message will be deleted"}
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 4 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            message_id = data.get("id")
            print(f"✅ A sent text DM → 200, message_id={message_id}")
            
            # A deletes the message
            resp_del = delete_dm(token_a, handle_b, message_id)
            if resp_del.status_code != 200:
                print(f"❌ A DELETE /api/dms/{handle_b}/{message_id} → {resp_del.status_code} (expected 200)")
            else:
                print(f"✅ A deleted message → 200")
                
                # B gets history - deleted message should NOT be present at all
                resp_b = get_dm_history(token_b, handle_a)
                if resp_b.status_code != 200:
                    print(f"❌ B GET /api/dms/{handle_a} → {resp_b.status_code} (expected 200)")
                else:
                    data_b = resp_b.json()
                    messages = data_b.get("messages", [])
                    
                    # Check if deleted message is present
                    deleted_msg = next((m for m in messages if m.get("id") == message_id), None)
                    
                    if deleted_msg is None:
                        print(f"✅ B GET history → deleted message NOT present (silently hidden) ✓")
                    else:
                        print(f"❌ B GET history → deleted message IS present (should be fully hidden)")
                        print(f"   Message: {deleted_msg}")
                        print(f"   TEST 4: FAIL ❌")
                        return
                    
                    # Check no message has deleted==true or text 'This message was deleted'
                    has_deleted_flag = any(m.get("deleted") == True for m in messages)
                    has_deleted_text = any("This message was deleted" in str(m.get("text", "")) for m in messages)
                    
                    if has_deleted_flag:
                        print(f"❌ B GET history → found message with deleted==true (should not be present)")
                        print(f"   TEST 4: FAIL ❌")
                    elif has_deleted_text:
                        print(f"❌ B GET history → found message with text 'This message was deleted' (should not be present)")
                        print(f"   TEST 4: FAIL ❌")
                    else:
                        print(f"✅ B GET history → no messages with deleted==true or 'This message was deleted' text ✓")
                        print(f"   TEST 4: PASS ✅")
    except Exception as e:
        print(f"❌ TEST 4 EXCEPTION: {e}")
        print(f"   TEST 4: FAIL ❌")
    
    print("\n" + "="*80)
    print("TEST 5: VIEW-ONCE DISAPPEARS AFTER VIEWING")
    print("="*80)
    
    try:
        # A sends view_once image
        payload = {
            "media_url": "https://example.com/viewonce.jpg",
            "media_type": "image",
            "view_once": True
        }
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 5 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            message_id = data.get("id")
            print(f"✅ A sent view_once image → 200, message_id={message_id}")
            
            # B views the message
            resp_view = view_once_message(token_b, handle_a, message_id)
            if resp_view.status_code != 200:
                print(f"❌ B POST /api/dms/{handle_a}/{message_id}/view → {resp_view.status_code} (expected 200)")
                print(f"   Response: {resp_view.text}")
            else:
                print(f"✅ B viewed view_once message → 200")
                
                # B gets history - view-once message should NOT be present anymore
                resp_b = get_dm_history(token_b, handle_a)
                if resp_b.status_code != 200:
                    print(f"❌ B GET /api/dms/{handle_a} → {resp_b.status_code} (expected 200)")
                else:
                    data_b = resp_b.json()
                    messages = data_b.get("messages", [])
                    
                    # Check if view-once message is present
                    viewonce_msg = next((m for m in messages if m.get("id") == message_id), None)
                    
                    if viewonce_msg is None:
                        print(f"✅ B GET history → view-once message NOT present (silently gone after viewing) ✓")
                        print(f"   TEST 5: PASS ✅")
                    else:
                        print(f"❌ B GET history → view-once message IS present (should be silently gone after viewing)")
                        print(f"   Message: {viewonce_msg}")
                        print(f"   TEST 5: FAIL ❌")
    except Exception as e:
        print(f"❌ TEST 5 EXCEPTION: {e}")
        print(f"   TEST 5: FAIL ❌")
    
    print("\n" + "="*80)
    print("TEST 6: NORMAL IMAGE STILL RETURNS media_url IN HISTORY")
    print("="*80)
    
    try:
        # A sends normal (non-view-once, allow_save true) image
        payload = {
            "media_url": "https://example.com/normal.jpg",
            "media_type": "image",
            "allow_save": True
        }
        resp = send_dm(token_a, handle_b, payload)
        
        if resp.status_code != 200:
            print(f"❌ TEST 6 FAILED: A POST /api/dms/{handle_b} → {resp.status_code} (expected 200)")
            print(f"   Response: {resp.text}")
        else:
            data = resp.json()
            print(f"✅ A sent normal image → 200")
            
            # B gets history
            resp_b = get_dm_history(token_b, handle_a)
            if resp_b.status_code != 200:
                print(f"❌ B GET /api/dms/{handle_a} → {resp_b.status_code} (expected 200)")
            else:
                data_b = resp_b.json()
                messages = data_b.get("messages", [])
                
                # Find the message with media_url='https://example.com/normal.jpg'
                msg = next((m for m in messages if m.get("media_url") == "https://example.com/normal.jpg"), None)
                
                if msg:
                    media_url = msg.get("media_url")
                    view_once = msg.get("view_once")
                    allow_save = msg.get("allow_save")
                    
                    if media_url == "https://example.com/normal.jpg":
                        print(f"✅ B GET history → normal image has media_url='https://example.com/normal.jpg' ✓")
                    else:
                        print(f"❌ B GET history → normal image has media_url={media_url} (expected 'https://example.com/normal.jpg')")
                    
                    if view_once == False:
                        print(f"✅ B GET history → normal image has view_once=false ✓")
                    else:
                        print(f"❌ B GET history → normal image has view_once={view_once} (expected false)")
                    
                    if allow_save == True:
                        print(f"✅ B GET history → normal image has allow_save=true ✓")
                    else:
                        print(f"❌ B GET history → normal image has allow_save={allow_save} (expected true)")
                    
                    if media_url == "https://example.com/normal.jpg" and view_once == False and allow_save == True:
                        print(f"   TEST 6: PASS ✅")
                    else:
                        print(f"   TEST 6: FAIL ❌")
                else:
                    print(f"❌ B GET history → normal image message not found")
                    print(f"   TEST 6: FAIL ❌")
    except Exception as e:
        print(f"❌ TEST 6 EXCEPTION: {e}")
        print(f"   TEST 6: FAIL ❌")
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
