#!/usr/bin/env python3
"""One-time rebrand migration: rename the seeded official account (and its
welcome posts) from ClanChat -> Skali on an EXISTING database.

The startup seed only creates the official account if it doesn't already
exist, so live databases keep the old 'ClanChat' record. Run this once
against production to rebrand it in place.

Usage (point at your production DB):
    MONGO_URL="<your-atlas-uri>" DB_NAME="clanchat" python scripts/rebrand_migration.py
"""
import os
from pymongo import MongoClient

url = os.environ["MONGO_URL"]
dbname = os.environ.get("DB_NAME", "clanchat")
db = MongoClient(url)[dbname]

SYS_ID = "system-clanchat"  # doc id is kept stable; only its labels change

res = db.profiles.update_one(
    {"id": SYS_ID},
    {"$set": {
        "handle": "skali",
        "display_name": "Skali",
        "bio": "Your place to gather. Your circle. Your rules. No bullshit.",
        "links": ["skali.app"],
    }},
)
print(f"official profile: matched={res.matched_count} modified={res.modified_count}")

posts = list(db.posts.find({"author_id": SYS_ID}))
for p in posts:
    text = (p.get("text") or "").replace("ClanChat", "Skali").replace("clubhouse", "gathering")
    tags = ["skali" if t == "clanchat" else t for t in (p.get("tags") or [])]
    db.posts.update_one({"id": p["id"]}, {"$set": {"text": text, "tags": tags}})
print(f"official posts updated: {len(posts)}")

print("Done. The official account is now 'Skali' (@skali).")
