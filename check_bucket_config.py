#!/usr/bin/env python3
"""
Check Supabase bucket configuration to diagnose why non-image uploads fail.
"""
import asyncio
import httpx
import os

import sys
sys.path.insert(0, '/app/backend')

# Load from .env file
from dotenv import load_dotenv
load_dotenv('/app/.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://fkhsijjwkrwbwjjaapbb.supabase.co')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
BUCKET = 'clanchat-media'

print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_SERVICE_ROLE_KEY: {SUPABASE_SERVICE_ROLE_KEY[:20] if SUPABASE_SERVICE_ROLE_KEY else 'NOT SET'}...")

def admin_headers():
    return {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}'
    }

async def main():
    print("=" * 80)
    print("SUPABASE BUCKET CONFIGURATION CHECK")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Get bucket details
        print(f"\n[1] GET BUCKET DETAILS: {BUCKET}")
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}",
                headers=admin_headers()
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            
            if resp.status_code == 200:
                bucket_info = resp.json()
                print(f"\n✅ BUCKET EXISTS")
                print(f"  - id: {bucket_info.get('id')}")
                print(f"  - name: {bucket_info.get('name')}")
                print(f"  - public: {bucket_info.get('public')}")
                print(f"  - file_size_limit: {bucket_info.get('file_size_limit')}")
                print(f"  - allowed_mime_types: {bucket_info.get('allowed_mime_types')}")
                
                allowed_mimes = bucket_info.get('allowed_mime_types', [])
                if not allowed_mimes:
                    print(f"\n⚠️  WARNING: No allowed_mime_types set (all types allowed)")
                elif 'video/*' not in allowed_mimes and 'video/mp4' not in allowed_mimes:
                    print(f"\n❌ PROBLEM: video/* not in allowed_mime_types!")
                elif 'audio/*' not in allowed_mimes and 'audio/mpeg' not in allowed_mimes:
                    print(f"\n❌ PROBLEM: audio/* not in allowed_mime_types!")
                else:
                    print(f"\n✅ allowed_mime_types includes video/* and audio/*")
            else:
                print(f"❌ BUCKET NOT FOUND or ERROR: {resp.status_code}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
        
        # List all buckets
        print(f"\n[2] LIST ALL BUCKETS")
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/storage/v1/bucket",
                headers=admin_headers()
            )
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                buckets = resp.json()
                print(f"Found {len(buckets)} buckets:")
                for b in buckets:
                    print(f"  - {b.get('id')} (public: {b.get('public')}, allowed_mime_types: {b.get('allowed_mime_types')})")
            else:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
        
        # Try to update bucket with correct settings
        print(f"\n[3] UPDATE BUCKET SETTINGS")
        try:
            resp = await client.put(
                f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}",
                headers={**admin_headers(), 'Content-Type': 'application/json'},
                json={
                    'public': False,
                    'file_size_limit': 50 * 1024 * 1024,
                    'allowed_mime_types': ['image/*', 'video/*', 'audio/*', 'text/*']
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            
            if resp.status_code == 200:
                print(f"✅ BUCKET UPDATED SUCCESSFULLY")
            else:
                print(f"❌ BUCKET UPDATE FAILED")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(main())
