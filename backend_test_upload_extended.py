#!/usr/bin/env python3
"""
Extended diagnosis - test various file types and investigate the 500 error.
"""
import asyncio
import httpx
import time
import io
from PIL import Image

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@clanchat.app"
ADMIN_PASSWORD = "ClanChatAdmin!2025"

def generate_tiny_png():
    """Generate a tiny valid PNG image (10x10 red square)."""
    img = Image.new('RGB', (10, 10), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()

def generate_tiny_jpeg():
    """Generate a tiny valid JPEG image (10x10 blue square)."""
    img = Image.new('RGB', (10, 10), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf.getvalue()

async def main():
    print("=" * 80)
    print("EXTENDED MEDIA UPLOAD DIAGNOSIS")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Login
        print("\n[LOGIN]")
        login_resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        if login_resp.status_code != 200:
            print(f"❌ LOGIN FAILED: {login_resp.status_code}")
            return
        
        token = login_resp.json().get('access_token') or login_resp.json().get('token')
        print(f"✅ LOGIN SUCCESS")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test different file types
        test_cases = [
            ("PNG image", "test.png", generate_tiny_png(), "image/png"),
            ("JPEG image", "test.jpg", generate_tiny_jpeg(), "image/jpeg"),
            ("Text file", "note.txt", b"This is a test note.", "text/plain"),
            ("Video (fake)", "video.mp4", b"fake video content", "video/mp4"),
            ("Audio (fake)", "audio.mp3", b"fake audio content", "audio/mpeg"),
        ]
        
        for name, filename, content, content_type in test_cases:
            print("\n" + "=" * 80)
            print(f"[TEST] {name} - {filename} ({content_type})")
            print("=" * 80)
            
            files = {
                'file': (filename, content, content_type)
            }
            
            start_time = time.time()
            try:
                resp = await client.post(
                    f"{BASE_URL}/upload",
                    headers=headers,
                    files=files
                )
                elapsed = time.time() - start_time
                
                print(f"Status: {resp.status_code}")
                print(f"Elapsed: {elapsed:.2f}s")
                
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"✅ SUCCESS")
                    print(f"  - path: {data.get('path')}")
                    print(f"  - media_type: {data.get('media_type')}")
                    print(f"  - nsfw: {data.get('nsfw')}")
                    print(f"  - signed_url: {data.get('signed_url')[:80]}...")
                else:
                    print(f"❌ FAILED: {resp.status_code}")
                    print(f"Response: {resp.text}")
                    
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"❌ EXCEPTION after {elapsed:.2f}s: {e}")
        
        # Test file size limits
        print("\n" + "=" * 80)
        print("[TEST] Large file (>50MB) - should return 413")
        print("=" * 80)
        
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB
        files = {
            'file': ('large.bin', large_content, 'application/octet-stream')
        }
        
        try:
            resp = await client.post(
                f"{BASE_URL}/upload",
                headers=headers,
                files=files
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
            
            if resp.status_code == 413:
                print(f"✅ LARGE FILE CORRECTLY REJECTED: 413")
            else:
                print(f"⚠️  Expected 413, got {resp.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
