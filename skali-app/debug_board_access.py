#!/usr/bin/env python3
"""
Debug test to understand the tier-based board access issue
"""
import asyncio
import aiohttp
import uuid

BASE_URL = "https://gif-troubleshoot-1.preview.emergentagent.com/api"
ADULT_DOB = "1990-01-01"

async def register_user(session, name_suffix):
    email = f"debugboard{name_suffix}+{uuid.uuid4().hex[:8]}@example.com"
    name = f"DebugBoard{name_suffix}"
    
    async with session.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": "secret123",
        "name": name,
        "dob": ADULT_DOB
    }) as resp:
        data = await resp.json()
        return data['access_token'], data['user']['handle'], data['user']['id']

async def main():
    async with aiohttp.ClientSession() as session:
        # Register users
        owner_token, owner_handle, owner_id = await register_user(session, "Owner")
        stranger_token, stranger_handle, stranger_id = await register_user(session, "Stranger")
        
        print(f"OWNER: {owner_handle} (id={owner_id})")
        print(f"STRANGER: {stranger_handle} (id={stranger_id})")
        
        # Create followers-tier board
        async with session.post(f"{BASE_URL}/boards", 
                               headers={"Authorization": f"Bearer {owner_token}"},
                               json={"title": "Followers Only", "tier": "followers"}) as resp:
            board = await resp.json()
            board_id = board['id']
            print(f"\nCreated followers board: {board_id}")
            print(f"Board data: {board}")
        
        # Check if STRANGER is a follower
        async with session.get(f"{BASE_URL}/connections", 
                              headers={"Authorization": f"Bearer {owner_token}"}) as resp:
            connections = await resp.json()
            print(f"\nOWNER's connections:")
            print(f"  Followers: {[f['handle'] for f in connections.get('followers', [])]}")
        
        # STRANGER tries to read followers board
        print(f"\nSTRANGER trying to read followers board...")
        async with session.get(f"{BASE_URL}/board/{board_id}", 
                              headers={"Authorization": f"Bearer {stranger_token}"}) as resp:
            print(f"  Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"  Response: {data}")
            else:
                text = await resp.text()
                print(f"  Error: {text}")

if __name__ == "__main__":
    asyncio.run(main())
