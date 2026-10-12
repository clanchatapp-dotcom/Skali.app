#!/usr/bin/env python3
"""
Test the self-healing Supabase bucket config fix for POST /api/upload.
The backend was restarted, and on startup ensure_bucket now UPDATES the bucket
to allowed_mime_types ['image/*','video/*','audio/*'] and 50MB limit.

Test scenarios:
1. PNG image (tiny, image/png) → 200, media_type 'image', signed_url reachable
2. MP4 video (small, video/mp4) → 200, media_type 'video' (was 500 before)
3. Audio (small, audio/mpeg) → 200, media_type 'audio'
4. LARGE image ~20MB (image/jpeg) → 200 (previously blocked by 15MB cap)
5. OVERSIZE ~60MB (image/jpeg) → 413 (max 50MB)
6. NO AUTH → 401/403
"""
import asyncio
import httpx
import os
from io import BytesIO

BASE_URL = os.environ.get('NEXT_PUBLIC_BASE_URL', 'https://gif-troubleshoot-1.preview.emergentagent.com')
API_URL = f'{BASE_URL}/api'

# Admin credentials for auth
ADMIN_EMAIL = 'admin@clanchat.app'
ADMIN_PASSWORD = 'ClanChatAdmin!2025'


def create_tiny_png() -> bytes:
    """Create a minimal valid PNG (1x1 pixel, transparent)."""
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])


def create_small_mp4() -> bytes:
    """Create a minimal valid MP4 video file."""
    # Minimal MP4 with ftyp and mdat boxes
    return bytes([
        # ftyp box
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,  # size=32, type='ftyp'
        0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,  # major_brand='isom', minor_version=512
        0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,  # compatible_brands
        0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31,
        # mdat box (minimal)
        0x00, 0x00, 0x00, 0x10, 0x6D, 0x64, 0x61, 0x74,  # size=16, type='mdat'
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00   # empty data
    ])


def create_small_mp3() -> bytes:
    """Create a minimal valid MP3 audio file."""
    # Minimal MP3 with ID3v2 header and one frame
    return bytes([
        # ID3v2 header
        0x49, 0x44, 0x33, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        # MP3 frame header (MPEG-1 Layer 3, 128kbps, 44.1kHz)
        0xFF, 0xFB, 0x90, 0x00,
        # Minimal frame data (padding)
        *([0x00] * 100)
    ])


def create_large_jpeg(size_mb: int) -> bytes:
    """Create a JPEG file of approximately the specified size in MB."""
    # Minimal JPEG header
    header = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,  # JPEG SOI + APP0
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,  # DQT
        *([0x00] * 64),  # Quantization table
        0xFF, 0xC0, 0x00, 0x11, 0x08, 0x00, 0x01, 0x00,  # SOF0 (1x1 image)
        0x01, 0x03, 0x01, 0x22, 0x00, 0x02, 0x11, 0x01,
        0x03, 0x11, 0x01, 0xFF, 0xDA, 0x00, 0x0C, 0x03,  # SOS
        0x01, 0x00, 0x02, 0x11, 0x03, 0x11, 0x00, 0x3F,
        0x00
    ])
    # Pad with data to reach target size
    target_bytes = size_mb * 1024 * 1024
    padding_size = target_bytes - len(header) - 2  # -2 for EOI marker
    padding = bytes([0xFF, 0x00] * (padding_size // 2))  # Stuffed bytes
    footer = bytes([0xFF, 0xD9])  # EOI
    return header + padding + footer


async def main():
    print("=" * 80)
    print("MEDIA UPLOAD FIX VERIFICATION - Self-healing Supabase bucket config")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Login as admin to get token
        print("\n[SETUP] Logging in as admin...")
        try:
            login_resp = await client.post(
                f'{API_URL}/auth/login',
                json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}
            )
            print(f"Login response: {login_resp.status_code}")
            if login_resp.status_code != 200:
                print(f"❌ Login failed: {login_resp.text}")
                return
            
            token = login_resp.json()['access_token']
            print(f"✅ Login successful, token length: {len(token)}")
            headers = {'Authorization': f'Bearer {token}'}
        except Exception as e:
            print(f"❌ Login error: {e}")
            return
        
        # Test counters
        total_tests = 0
        passed_tests = 0
        
        # Test 1: PNG image (tiny, image/png) → 200, media_type 'image', signed_url reachable
        print("\n" + "=" * 80)
        print("TEST 1: PNG image upload (tiny, image/png)")
        print("=" * 80)
        total_tests += 1
        try:
            png_data = create_tiny_png()
            print(f"Created PNG: {len(png_data)} bytes")
            
            files = {'file': ('test.png', BytesIO(png_data), 'image/png')}
            resp = await client.post(f'{API_URL}/upload', headers=headers, files=files)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"Response data: {data}")
                
                # Verify response structure
                assert 'path' in data, "Missing 'path' in response"
                assert 'signed_url' in data, "Missing 'signed_url' in response"
                assert 'media_type' in data, "Missing 'media_type' in response"
                assert data['media_type'] == 'image', f"Expected media_type='image', got '{data['media_type']}'"
                
                # Verify signed URL is reachable
                signed_url = data['signed_url']
                print(f"Signed URL: {signed_url[:80]}...")
                url_resp = await client.get(signed_url)
                print(f"Signed URL GET status: {url_resp.status_code}")
                assert url_resp.status_code == 200, f"Signed URL not reachable: {url_resp.status_code}"
                print(f"Signed URL returned {len(url_resp.content)} bytes")
                
                print("✅ TEST 1 PASSED: PNG upload → 200, media_type='image', signed_url reachable")
                passed_tests += 1
            else:
                print(f"❌ TEST 1 FAILED: Expected 200, got {resp.status_code}")
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"❌ TEST 1 FAILED with exception: {e}")
        
        # Test 2: MP4 video (small, video/mp4) → 200, media_type 'video'
        print("\n" + "=" * 80)
        print("TEST 2: MP4 video upload (small, video/mp4) - was 500 before fix")
        print("=" * 80)
        total_tests += 1
        try:
            mp4_data = create_small_mp4()
            print(f"Created MP4: {len(mp4_data)} bytes")
            
            files = {'file': ('clip.mp4', BytesIO(mp4_data), 'video/mp4')}
            resp = await client.post(f'{API_URL}/upload', headers=headers, files=files)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"Response data: {data}")
                
                assert 'media_type' in data, "Missing 'media_type' in response"
                assert data['media_type'] == 'video', f"Expected media_type='video', got '{data['media_type']}'"
                assert 'signed_url' in data, "Missing 'signed_url' in response"
                
                print("✅ TEST 2 PASSED: MP4 upload → 200, media_type='video' (previously 500)")
                passed_tests += 1
            else:
                print(f"❌ TEST 2 FAILED: Expected 200, got {resp.status_code}")
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"❌ TEST 2 FAILED with exception: {e}")
        
        # Test 3: Audio (small, audio/mpeg) → 200, media_type 'audio'
        print("\n" + "=" * 80)
        print("TEST 3: Audio upload (small, audio/mpeg)")
        print("=" * 80)
        total_tests += 1
        try:
            mp3_data = create_small_mp3()
            print(f"Created MP3: {len(mp3_data)} bytes")
            
            files = {'file': ('v.mp3', BytesIO(mp3_data), 'audio/mpeg')}
            resp = await client.post(f'{API_URL}/upload', headers=headers, files=files)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"Response data: {data}")
                
                assert 'media_type' in data, "Missing 'media_type' in response"
                assert data['media_type'] == 'audio', f"Expected media_type='audio', got '{data['media_type']}'"
                assert 'signed_url' in data, "Missing 'signed_url' in response"
                
                print("✅ TEST 3 PASSED: Audio upload → 200, media_type='audio'")
                passed_tests += 1
            else:
                print(f"❌ TEST 3 FAILED: Expected 200, got {resp.status_code}")
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"❌ TEST 3 FAILED with exception: {e}")
        
        # Test 4: LARGE image ~20MB (image/jpeg) → 200 (previously blocked by 15MB cap)
        print("\n" + "=" * 80)
        print("TEST 4: LARGE image ~20MB (image/jpeg) - previously blocked by 15MB cap")
        print("=" * 80)
        total_tests += 1
        try:
            print("Creating 20MB JPEG... (this may take a moment)")
            large_jpeg = create_large_jpeg(20)
            print(f"Created JPEG: {len(large_jpeg) / (1024*1024):.2f} MB")
            
            files = {'file': ('large.jpg', BytesIO(large_jpeg), 'image/jpeg')}
            print("Uploading 20MB file... (this may take 30-60 seconds)")
            resp = await client.post(f'{API_URL}/upload', headers=headers, files=files)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"Response keys: {list(data.keys())}")
                
                assert 'media_type' in data, "Missing 'media_type' in response"
                assert data['media_type'] == 'image', f"Expected media_type='image', got '{data['media_type']}'"
                assert 'signed_url' in data, "Missing 'signed_url' in response"
                
                print("✅ TEST 4 PASSED: 20MB image upload → 200 (previously blocked by 15MB cap)")
                passed_tests += 1
            else:
                print(f"❌ TEST 4 FAILED: Expected 200, got {resp.status_code}")
                print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"❌ TEST 4 FAILED with exception: {e}")
        
        # Test 5: OVERSIZE ~60MB (image/jpeg) → 413 (max 50MB)
        print("\n" + "=" * 80)
        print("TEST 5: OVERSIZE ~60MB (image/jpeg) → expect 413 (max 50MB)")
        print("=" * 80)
        total_tests += 1
        try:
            print("Creating 60MB JPEG... (this may take a moment)")
            oversize_jpeg = create_large_jpeg(60)
            print(f"Created JPEG: {len(oversize_jpeg) / (1024*1024):.2f} MB")
            
            files = {'file': ('oversize.jpg', BytesIO(oversize_jpeg), 'image/jpeg')}
            print("Uploading 60MB file... (this may take 60-90 seconds)")
            resp = await client.post(f'{API_URL}/upload', headers=headers, files=files)
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code == 413:
                print(f"Response: {resp.text[:200]}")
                print("✅ TEST 5 PASSED: 60MB upload → 413 (correctly rejected, max 50MB)")
                passed_tests += 1
            else:
                print(f"❌ TEST 5 FAILED: Expected 413, got {resp.status_code}")
                print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"❌ TEST 5 FAILED with exception: {e}")
        
        # Test 6: NO AUTH → 401/403
        print("\n" + "=" * 80)
        print("TEST 6: Upload without auth → expect 401/403")
        print("=" * 80)
        total_tests += 1
        try:
            png_data = create_tiny_png()
            files = {'file': ('test.png', BytesIO(png_data), 'image/png')}
            resp = await client.post(f'{API_URL}/upload', files=files)  # No headers
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code in (401, 403):
                print(f"Response: {resp.text[:200]}")
                print(f"✅ TEST 6 PASSED: No auth → {resp.status_code} (correctly rejected)")
                passed_tests += 1
            else:
                print(f"❌ TEST 6 FAILED: Expected 401/403, got {resp.status_code}")
                print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"❌ TEST 6 FAILED with exception: {e}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {(passed_tests / total_tests * 100):.1f}%")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED - Media upload fix verified successfully!")
            print("✅ Self-healing bucket config working correctly")
            print("✅ All media types (image, video, audio) now work")
            print("✅ Large files up to 50MB now supported")
            print("✅ Oversize files (>50MB) correctly rejected")
            print("✅ Auth enforcement working")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        
        print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
