#!/usr/bin/env python3
"""
Test script for POST /api/upload endpoint verification.
Tests: no-auth, image upload, video upload, audio upload, oversize, sticker send flow.
"""
import requests
import io
import secrets
from PIL import Image

BASE_URL = "http://localhost:8001/api"

def create_test_image(size_kb=10):
    """Create a small PNG image in memory."""
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def create_test_file(size_mb, filename):
    """Create a test file of specified size in memory."""
    size_bytes = size_mb * 1024 * 1024
    content = secrets.token_bytes(size_bytes)
    return io.BytesIO(content)

def register_user():
    """Register a throwaway user and return access_token and handle."""
    rand = secrets.token_hex(4)
    email = f"up+{rand}@example.com"
    payload = {
        "email": email,
        "password": "secret123",
        "name": "Up",
        "dob": "1990-01-01"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"[REGISTER] {resp.status_code} - {email}")
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        return None, None
    data = resp.json()
    return data.get('access_token'), data.get('user', {}).get('handle')

def test_no_auth():
    """Test 1: POST /api/upload with NO Authorization header -> expect 401 or 403."""
    print("\n=== TEST 1: NO AUTH ===")
    img_file = create_test_image()
    files = {'file': ('test.png', img_file, 'image/png')}
    resp = requests.post(f"{BASE_URL}/upload", files=files)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}")
    if resp.status_code in (401, 403):
        print("✅ PASS: No auth correctly rejected")
        return True
    else:
        print(f"❌ FAIL: Expected 401/403, got {resp.status_code}")
        return False

def test_image_upload(token):
    """Test 2: POST /api/upload with PNG + token -> expect 200, media_type='image', signed_url reachable."""
    print("\n=== TEST 2: IMAGE UPLOAD ===")
    img_file = create_test_image()
    files = {'file': ('test.png', img_file, 'image/png')}
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False, None
    
    data = resp.json()
    required_keys = ['path', 'signed_url', 'media_type', 'nsfw']
    missing = [k for k in required_keys if k not in data]
    if missing:
        print(f"❌ FAIL: Missing keys: {missing}")
        return False, None
    
    if data['media_type'] != 'image':
        print(f"❌ FAIL: Expected media_type='image', got '{data['media_type']}'")
        return False, None
    
    # Test if signed_url is reachable
    signed_url = data['signed_url']
    print(f"Testing signed_url: {signed_url[:80]}...")
    url_resp = requests.get(signed_url)
    print(f"Signed URL GET status: {url_resp.status_code}")
    
    if url_resp.status_code != 200:
        print(f"❌ FAIL: Signed URL not reachable, got {url_resp.status_code}")
        return False, None
    
    print(f"✅ PASS: Image upload successful, media_type='image', signed_url reachable")
    return True, signed_url

def test_video_upload(token):
    """Test 3: POST /api/upload with video.mp4 -> expect 200, media_type='video'."""
    print("\n=== TEST 3: VIDEO UPLOAD ===")
    # Create small video file (just bytes with video mime type)
    video_content = secrets.token_bytes(1024)  # 1KB
    files = {'file': ('video.mp4', io.BytesIO(video_content), 'video/mp4')}
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    if data.get('media_type') != 'video':
        print(f"❌ FAIL: Expected media_type='video', got '{data.get('media_type')}'")
        return False
    
    if 'signed_url' not in data:
        print(f"❌ FAIL: Missing signed_url")
        return False
    
    print(f"✅ PASS: Video upload successful, media_type='video', signed_url present")
    return True

def test_audio_upload(token):
    """Test 4: POST /api/upload with audio.mp3 -> expect 200, media_type='audio'."""
    print("\n=== TEST 4: AUDIO UPLOAD ===")
    audio_content = secrets.token_bytes(1024)  # 1KB
    files = {'file': ('audio.mp3', io.BytesIO(audio_content), 'audio/mpeg')}
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    if data.get('media_type') != 'audio':
        print(f"❌ FAIL: Expected media_type='audio', got '{data.get('media_type')}'")
        return False
    
    print(f"✅ PASS: Audio upload successful, media_type='audio'")
    return True

def test_oversize_upload(token):
    """Test 5: POST /api/upload with ~51MB file -> expect 413."""
    print("\n=== TEST 5: OVERSIZE UPLOAD ===")
    print("Creating 51MB file (this may take a moment)...")
    large_file = create_test_file(51, 'large.bin')
    files = {'file': ('large.bin', large_file, 'application/octet-stream')}
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}")
    
    if resp.status_code == 413:
        print("✅ PASS: Oversize file correctly rejected with 413")
        return True
    else:
        print(f"❌ FAIL: Expected 413, got {resp.status_code}")
        return False

def test_sticker_send_flow(token, handle):
    """Test 6: Upload PNG, then POST /api/dms/{own_handle} with sticker -> expect 200."""
    print("\n=== TEST 6: STICKER SEND FLOW (END-TO-END) ===")
    
    # Step 1: Upload a tiny PNG to get signed_url
    print("Step 1: Uploading sticker image...")
    img_file = create_test_image(5)
    files = {'file': ('sticker.png', img_file, 'image/png')}
    headers = {'Authorization': f'Bearer {token}'}
    upload_resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Upload status: {upload_resp.status_code}")
    
    if upload_resp.status_code != 200:
        print(f"❌ FAIL: Upload failed with {upload_resp.status_code}")
        return False
    
    upload_data = upload_resp.json()
    signed_url = upload_data.get('signed_url')
    print(f"Got signed_url: {signed_url[:80]}...")
    
    # Step 2: Send sticker as self-DM
    print(f"Step 2: Sending sticker to self (handle={handle})...")
    dm_payload = {
        "media_url": signed_url,
        "media_type": "sticker",
        "allow_save": True
    }
    dm_resp = requests.post(f"{BASE_URL}/dms/{handle}", json=dm_payload, headers=headers)
    print(f"DM send status: {dm_resp.status_code}")
    print(f"DM response: {dm_resp.text[:500]}")
    
    if dm_resp.status_code != 200:
        print(f"❌ FAIL: DM send failed with {dm_resp.status_code}")
        return False
    
    dm_data = dm_resp.json()
    
    # Verify response includes media_url, media_type='sticker', and notify_preview
    if dm_data.get('media_url') != signed_url:
        print(f"❌ FAIL: media_url mismatch")
        return False
    
    if dm_data.get('media_type') != 'sticker':
        print(f"❌ FAIL: Expected media_type='sticker', got '{dm_data.get('media_type')}'")
        return False
    
    if 'notify_preview' not in dm_data:
        print(f"❌ FAIL: Missing notify_preview field")
        return False
    
    print(f"notify_preview: {dm_data.get('notify_preview')}")
    print(f"✅ PASS: Sticker send flow successful (upload -> self-DM with media_type='sticker')")
    return True

def main():
    print("=" * 80)
    print("MEDIA UPLOAD ENDPOINT VERIFICATION TEST")
    print("Testing POST /api/upload on LOCAL sandbox backend (http://localhost:8001)")
    print("=" * 80)
    
    results = {}
    
    # Test 1: No auth
    results['no_auth'] = test_no_auth()
    
    # Register user for authenticated tests
    print("\n=== REGISTERING TEST USER ===")
    token, handle = register_user()
    if not token or not handle:
        print("❌ FATAL: Failed to register user, cannot continue")
        return
    print(f"✅ Registered user with handle: {handle}")
    
    # Test 2: Image upload
    image_pass, signed_url = test_image_upload(token)
    results['image_upload'] = image_pass
    
    # Test 3: Video upload
    results['video_upload'] = test_video_upload(token)
    
    # Test 4: Audio upload
    results['audio_upload'] = test_audio_upload(token)
    
    # Test 5: Oversize upload
    results['oversize_upload'] = test_oversize_upload(token)
    
    # Test 6: Sticker send flow
    results['sticker_send_flow'] = test_sticker_send_flow(token, handle)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        print(f"{status}: {test_name}")
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)

if __name__ == '__main__':
    main()
