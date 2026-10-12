#!/usr/bin/env python3
"""
Comprehensive diagnosis of POST /api/upload endpoint.
Tests image upload, signed URL verification, auth enforcement, and post-with-media flow.
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

async def main():
    print("=" * 80)
    print("MEDIA UPLOAD DIAGNOSIS - POST /api/upload")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # ===== STEP 0: LOGIN AS ADMIN =====
        print("\n[STEP 0] LOGIN AS ADMIN")
        print(f"POST {BASE_URL}/auth/login")
        try:
            login_resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
            )
            print(f"Status: {login_resp.status_code}")
            print(f"Response: {login_resp.text[:500]}")
            
            if login_resp.status_code != 200:
                print(f"❌ LOGIN FAILED: {login_resp.status_code} - {login_resp.text}")
                return
            
            login_data = login_resp.json()
            token = login_data.get('access_token') or login_data.get('token')
            if not token:
                print(f"❌ NO TOKEN IN RESPONSE: {login_data}")
                return
            
            print(f"✅ LOGIN SUCCESS - Token: {token[:20]}...")
            headers = {"Authorization": f"Bearer {token}"}
        except Exception as e:
            print(f"❌ LOGIN EXCEPTION: {e}")
            return
        
        # ===== TEST 1: IMAGE UPLOAD =====
        print("\n" + "=" * 80)
        print("[TEST 1] IMAGE UPLOAD - POST /api/upload with PNG")
        print("=" * 80)
        
        png_bytes = generate_tiny_png()
        print(f"Generated PNG: {len(png_bytes)} bytes")
        
        files = {
            'file': ('test.png', png_bytes, 'image/png')
        }
        
        print(f"POST {BASE_URL}/upload")
        print(f"Headers: Authorization: Bearer {token[:20]}...")
        print(f"Files: test.png ({len(png_bytes)} bytes, image/png)")
        
        start_time = time.time()
        try:
            upload_resp = await client.post(
                f"{BASE_URL}/upload",
                headers=headers,
                files=files
            )
            elapsed = time.time() - start_time
            
            print(f"\nStatus: {upload_resp.status_code}")
            print(f"Elapsed time: {elapsed:.2f}s")
            print(f"Response headers: {dict(upload_resp.headers)}")
            print(f"Response body: {upload_resp.text}")
            
            if upload_resp.status_code == 200:
                upload_data = upload_resp.json()
                print(f"\n✅ UPLOAD SUCCESS")
                print(f"  - path: {upload_data.get('path')}")
                print(f"  - signed_url: {upload_data.get('signed_url')}")
                print(f"  - media_type: {upload_data.get('media_type')}")
                print(f"  - nsfw: {upload_data.get('nsfw')}")
                print(f"  - nsfw_reason: {upload_data.get('nsfw_reason')}")
                
                signed_url = upload_data.get('signed_url')
                
                # ===== TEST 2: VERIFY SIGNED URL =====
                print("\n" + "=" * 80)
                print("[TEST 2] VERIFY SIGNED URL - GET signed_url")
                print("=" * 80)
                
                if signed_url:
                    print(f"GET {signed_url[:100]}...")
                    try:
                        url_resp = await client.get(signed_url)
                        print(f"Status: {url_resp.status_code}")
                        print(f"Content-Type: {url_resp.headers.get('content-type')}")
                        print(f"Content-Length: {len(url_resp.content)} bytes")
                        
                        if url_resp.status_code == 200:
                            print(f"✅ SIGNED URL IS REACHABLE - Got {len(url_resp.content)} bytes")
                        else:
                            print(f"❌ SIGNED URL FAILED: {url_resp.status_code} - {url_resp.text[:200]}")
                    except Exception as e:
                        print(f"❌ SIGNED URL EXCEPTION: {e}")
                else:
                    print("❌ NO SIGNED URL IN RESPONSE")
                
                # ===== TEST 5: POST-WITH-MEDIA FLOW =====
                print("\n" + "=" * 80)
                print("[TEST 5] POST-WITH-MEDIA FLOW - Create post with uploaded media")
                print("=" * 80)
                
                print(f"POST {BASE_URL}/posts")
                post_data = {
                    "tier": "public",
                    "text": "upload test",
                    "media_url": signed_url,
                    "media_type": "image"
                }
                print(f"Body: {post_data}")
                
                try:
                    post_resp = await client.post(
                        f"{BASE_URL}/posts",
                        headers=headers,
                        json=post_data
                    )
                    print(f"Status: {post_resp.status_code}")
                    print(f"Response: {post_resp.text[:500]}")
                    
                    if post_resp.status_code == 200:
                        post_id = post_resp.json().get('id')
                        print(f"✅ POST CREATED: {post_id}")
                        
                        # Verify in feed
                        print(f"\nGET {BASE_URL}/feed?scope=general")
                        feed_resp = await client.get(
                            f"{BASE_URL}/feed?scope=general",
                            headers=headers
                        )
                        print(f"Status: {feed_resp.status_code}")
                        
                        if feed_resp.status_code == 200:
                            feed_data = feed_resp.json()
                            matching_posts = [p for p in feed_data if p.get('id') == post_id]
                            if matching_posts:
                                post = matching_posts[0]
                                print(f"✅ POST FOUND IN FEED")
                                print(f"  - id: {post.get('id')}")
                                print(f"  - text: {post.get('text')}")
                                print(f"  - media_url: {post.get('media_url')}")
                                print(f"  - media_type: {post.get('media_type')}")
                            else:
                                print(f"❌ POST NOT FOUND IN FEED (searched {len(feed_data)} posts)")
                        else:
                            print(f"❌ FEED REQUEST FAILED: {feed_resp.status_code} - {feed_resp.text[:200]}")
                    else:
                        print(f"❌ POST CREATION FAILED: {post_resp.status_code} - {post_resp.text}")
                except Exception as e:
                    print(f"❌ POST-WITH-MEDIA EXCEPTION: {e}")
                    
            else:
                print(f"❌ UPLOAD FAILED: {upload_resp.status_code}")
                print(f"Response: {upload_resp.text}")
                
        except Exception as e:
            print(f"❌ UPLOAD EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
        
        # ===== TEST 3: TEXT FILE UPLOAD =====
        print("\n" + "=" * 80)
        print("[TEST 3] TEXT FILE UPLOAD - POST /api/upload with text file")
        print("=" * 80)
        
        text_content = b"This is a test note file."
        files = {
            'file': ('note.txt', text_content, 'text/plain')
        }
        
        print(f"POST {BASE_URL}/upload")
        print(f"Files: note.txt ({len(text_content)} bytes, text/plain)")
        
        try:
            text_resp = await client.post(
                f"{BASE_URL}/upload",
                headers=headers,
                files=files
            )
            print(f"Status: {text_resp.status_code}")
            print(f"Response: {text_resp.text}")
            
            if text_resp.status_code == 200:
                text_data = text_resp.json()
                print(f"✅ TEXT FILE UPLOAD SUCCESS")
                print(f"  - media_type: {text_data.get('media_type')}")
                print(f"  - signed_url: {text_data.get('signed_url')}")
            else:
                print(f"❌ TEXT FILE UPLOAD FAILED: {text_resp.status_code}")
        except Exception as e:
            print(f"❌ TEXT FILE UPLOAD EXCEPTION: {e}")
        
        # ===== TEST 4: NO AUTH =====
        print("\n" + "=" * 80)
        print("[TEST 4] NO AUTH - POST /api/upload without Authorization header")
        print("=" * 80)
        
        png_bytes = generate_tiny_png()
        files = {
            'file': ('test.png', png_bytes, 'image/png')
        }
        
        print(f"POST {BASE_URL}/upload (NO Authorization header)")
        
        try:
            noauth_resp = await client.post(
                f"{BASE_URL}/upload",
                files=files
            )
            print(f"Status: {noauth_resp.status_code}")
            print(f"Response: {noauth_resp.text}")
            
            if noauth_resp.status_code in [401, 403]:
                print(f"✅ NO AUTH CORRECTLY BLOCKED: {noauth_resp.status_code}")
            else:
                print(f"❌ NO AUTH SHOULD RETURN 401/403, GOT: {noauth_resp.status_code}")
        except Exception as e:
            print(f"❌ NO AUTH TEST EXCEPTION: {e}")
        
        # ===== TEST 6: LATENCY MEASUREMENT =====
        print("\n" + "=" * 80)
        print("[TEST 6] LATENCY MEASUREMENT - Measure upload time")
        print("=" * 80)
        
        png_bytes = generate_tiny_png()
        files = {
            'file': ('latency_test.png', png_bytes, 'image/png')
        }
        
        print(f"POST {BASE_URL}/upload (measuring latency)")
        
        start_time = time.time()
        try:
            latency_resp = await client.post(
                f"{BASE_URL}/upload",
                headers=headers,
                files=files
            )
            elapsed = time.time() - start_time
            
            print(f"Status: {latency_resp.status_code}")
            print(f"⏱️  UPLOAD LATENCY: {elapsed:.2f}s")
            
            if elapsed > 10:
                print(f"⚠️  WARNING: Upload took {elapsed:.2f}s (>10s) - NSFW moderation may be adding latency")
            elif elapsed > 5:
                print(f"⚠️  NOTICE: Upload took {elapsed:.2f}s (>5s) - moderate latency")
            else:
                print(f"✅ Upload completed in {elapsed:.2f}s")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ LATENCY TEST EXCEPTION after {elapsed:.2f}s: {e}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
