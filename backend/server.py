import os
import re
import uuid
import time
import base64
import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
import httpx
from dotenv import load_dotenv
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File, Header, Request,
    WebSocket, WebSocketDisconnect,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from livekit import api as lk_api
from pathlib import Path

# Optional AI image moderation (Emergent LLM key -> Gemini vision). Import guarded
# so the server still boots if the package/key is missing (scanner just no-ops).
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    _HAS_EI = True
except Exception:
    _HAS_EI = False

# Load .env for local/sandbox; on Render (and other hosts) real env vars are already
# present in os.environ and load_dotenv does NOT override them.
for _p in ('/app/.env', str(Path(__file__).resolve().parent.parent / '.env'), '.env'):
    load_dotenv(_p)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('skali')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'skali')
JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
BUCKET = os.environ.get('SUPABASE_BUCKET', 'skali-media')
def _load_dm_key() -> bytes:
    """Parse DM_ENC_KEY safely. A bad/missing value must NOT crash startup
    (that would 502 the whole service on Render)."""
    raw = os.environ.get('DM_ENC_KEY', '')
    if not raw:
        return b''
    try:
        return base64.b64decode(raw)
    except Exception:
        logging.getLogger('skali').warning('DM_ENC_KEY is not valid base64 — DM encryption disabled until fixed')
        return b''

DM_KEY = _load_dm_key()
LIVEKIT_URL = os.environ.get('LIVEKIT_URL', '')
LIVEKIT_API_KEY = os.environ.get('LIVEKIT_API_KEY', '')
LIVEKIT_API_SECRET = os.environ.get('LIVEKIT_API_SECRET', '')
# Built-in super-admins are ALWAYS admins on every deploy (owner accounts), even if the
# ADMIN_EMAILS env var isn't set. Env-provided emails are added on top.
_BUILTIN_ADMIN_EMAILS = {'admin@skaliapp.com', 'thomasgallacher92@gmail.com', 'admin@sandbox.skali'}
ADMIN_EMAILS = _BUILTIN_ADMIN_EMAILS | {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# ----------------------------- Block 1: sensitive-access hardening -----------------------------
# Server-side step-up secret for CSAM / DM-review / silent-investigation areas.
# We store ONLY the SHA-256 hash (env-configured). The raw secret is never in code
# or in the frontend; owner + co-admins receive it out-of-band and pass it in the
# `X-Step-Up` header on each sensitive request. Fail-closed: if unset, the area is
# inaccessible.
CSAM_STEPUP_SECRET_HASH = os.environ.get('CSAM_STEPUP_SECRET_HASH', '').strip().lower()

# ----------------------------- Staff roles -----------------------------
# Coloured shield roles. All role-holders are treated as "verified" accounts.
#   super_admin (green)  — the owner(s); reserved for built-in admin emails, not assignable via API
#   co_admin    (pink)   — full admin access (same as super admin)
#   moderator   (red)    — content moderation only (reports/strikes/flags/watchlist/nsfw)
#   first_tester(blue)   — cosmetic verified badge only, no powers
ROLES_VALID = {'super_admin', 'co_admin', 'moderator', 'first_tester'}
# Roles that can be assigned/removed through the admin API (super_admin is reserved).
ROLES_ASSIGNABLE = {'co_admin', 'moderator', 'first_tester'}
# Roles that grant full admin access (require_admin).
FULL_ADMIN_ROLES = {'super_admin', 'co_admin'}
# Roles that can moderate content (require_mod).
MOD_ROLES = {'super_admin', 'co_admin', 'moderator'}


def effective_role(prof: dict) -> Optional[str]:
    """The canonical role for a profile. Built-in admin emails are always super_admin;
    legacy is_admin accounts map to co_admin; otherwise use the stored role field."""
    if not prof:
        return None
    if (prof.get('email') or '').lower() in ADMIN_EMAILS:
        return 'super_admin'
    r = prof.get('role')
    if r in ROLES_VALID:
        return r
    if prof.get('is_admin'):
        return 'co_admin'
    return None


# Account tiers. 'standard' is the legacy default and is treated as 'free'.
ACCOUNT_TYPES = {'free', 'premium', 'verified'}

def acct_type(prof: dict) -> str:
    t = (prof or {}).get('account_type') or 'free'
    return 'free' if t == 'standard' else t

MB = 1024 * 1024
# Per-tier perks from the product spec (§15). Upload caps are practical ceilings
# ("unlimited" tiers still bounded by storage limits at the infra layer).
TIER_LIMITS = {
    'free':     {'pinned': 3, 'bio': 150, 'links': 3,
                 'image': 50 * MB, 'video': 500 * MB, 'audio': 100 * MB, 'doc': 100 * MB},
    'premium':  {'pinned': 6, 'bio': 300, 'links': 8,
                 'image': 500 * MB, 'video': 2048 * MB, 'audio': 1024 * MB, 'doc': 2048 * MB},
    'verified': {'pinned': 6, 'bio': 300, 'links': 9999,
                 'image': 500 * MB, 'video': 4096 * MB, 'audio': 4096 * MB, 'doc': 2048 * MB},
}

def tier_limits(prof: dict) -> dict:
    return TIER_LIMITS.get(acct_type(prof), TIER_LIMITS['free'])

def media_kind(content_type: str) -> str:
    ct = (content_type or '').lower()
    if ct.startswith('image/'):
        return 'image'
    if ct.startswith('video/'):
        return 'video'
    if ct.startswith('audio/'):
        return 'audio'
    return 'doc'



# NSFW threshold: any label >= this (or safe=false) queues media for admin review.
NSFW_THRESHOLD = 0.70
_NSFW_SYS = (
    "You are a conservative image-safety classifier. Return ONLY one valid JSON object, no markdown: "
    '{"safe": boolean, "confidence": number, '
    '"labels": {"nudity": number, "sexual_content": number, "violence": number, '
    '"graphic": number, "self_harm": number, "drugs": number}, "reason": string}. '
    "Scores are 0..1. Use safe=false when clearly unsafe or any category >= 0.70. "
    "Keep reason under 160 characters."
)


async def moderate_image(data: bytes, content_type: str) -> Optional[dict]:
    """Scan image bytes with Gemini vision. Returns a verdict dict, or None if the
    scanner is unavailable/errored (fail-open for the UPLOAD, but never fabricates 'safe')."""
    if not (_HAS_EI and EMERGENT_LLM_KEY) or not (content_type or '').startswith('image/'):
        return None
    import json as _json
    try:
        b64 = base64.b64encode(data).decode('ascii')
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                       system_message=_NSFW_SYS).with_model('gemini', 'gemini-2.5-flash')
        msg = UserMessage(text='Moderate this image and return the required JSON object.',
                          file_contents=[ImageContent(image_base64=b64)])
        resp = await chat.send_message(msg)
        raw = resp if isinstance(resp, str) else getattr(resp, 'text', str(resp))
        raw = str(raw).strip().replace('```json', '').replace('```', '').strip()
        s, e = raw.find('{'), raw.rfind('}')
        v = _json.loads(raw[s:e + 1])
        labels = {k: float(v.get('labels', {}).get(k, 0) or 0) for k in
                  ('nudity', 'sexual_content', 'violence', 'graphic', 'self_harm', 'drugs')}
        top = max(labels.values()) if labels else 0.0
        unsafe = (v.get('safe') is False) or top >= NSFW_THRESHOLD
        return {'safe': not unsafe, 'confidence': float(v.get('confidence', 0) or 0),
                'labels': labels, 'reason': str(v.get('reason', ''))[:200], 'top_score': top}
    except Exception as ex:
        log.warning('moderate_image failed: %s', ex)
        return None

# Comfort Zone — per-user content preferences (True = show in feed, False = soften/hide).
COMFORT_ZONE_KEYS = ['nsfw', 'ai', 'language', 'violence', 'drugs']
COMFORT_ZONE_DEFAULTS = {'nsfw': False, 'ai': True, 'language': True, 'violence': False, 'drugs': False}

# Phase 5 — Display / theme preferences.
THEME_VALUES = ('dark', 'light')
ACCENT_VALUES = ('violet', 'blue', 'emerald', 'rose', 'amber', 'cyan')
FONT_SIZE_VALUES = ('small', 'normal', 'large')
DISPLAY_DEFAULTS = {'theme': 'dark', 'accent': 'violet', 'font_size': 'normal'}

# Phase 5 — Granular notification preferences (True = show in Activity).
NOTIF_KEYS = ['follows', 'wall', 'reactions', 'comments', 'dms', 'inner']
NOTIF_DEFAULTS = {k: True for k in NOTIF_KEYS}
# Maps an activity 'type' to the notification pref key that gates it.
ACTIVITY_TYPE_TO_NOTIF = {
    'follow': 'follows', 'follow_request': 'follows', 'follow_accepted': 'follows',
    'inner_invite': 'inner', 'inner_accepted': 'inner',
    'wall': 'wall', 'like': 'reactions', 'react': 'reactions',
    'comment': 'comments', 'dm': 'dms',
}

# Phase 5 — Block / Mute / Restrict.
RELATION_KINDS = ('block', 'mute', 'restrict')

REPORT_CATEGORIES = {'csam', 'underage', 'harassment', 'hate', 'self_harm',
                     'inappropriate', 'unlabelled_ai', 'impersonation', 'spam', 'other'}

# AI content labels — mandatory pick for AI media; permanent badge on the post.
AI_LABELS = {'none', 'generated', 'assisted', 'altered'}

# Hardcoded slur/handle blocklist (silent-fail on names, tags, wall & board titles).
# Kept deliberately small + leet-normalised; extend as needed.
BANNED_WORDS = {
    'nigger', 'nigga', 'faggot', 'fag', 'retard', 'retarded', 'kike', 'spic',
    'chink', 'coon', 'wetback', 'tranny', 'paki', 'gook', 'cunt', 'rapist',
    'pedophile', 'pedo', 'paedophile', 'childporn', 'cp',
}
_LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's'})


def contains_banned(text: Optional[str]) -> bool:
    if not text:
        return False
    norm = re.sub(r'[^a-z0-9]', '', str(text).lower().translate(_LEET))
    return any(w in norm for w in BANNED_WORDS)


def is_admin_user(prof: dict) -> bool:
    return bool(prof.get('is_admin')) or (prof.get('email') or '').lower() in ADMIN_EMAILS


async def email_is_allowlisted(email: Optional[str]) -> bool:
    """True if this email was added to the DB-backed admin allowlist (from the panel)."""
    if not email:
        return False
    return bool(await db.admin_allow.find_one({'email': email.strip().lower()}))

client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
db = client[DB_NAME]
if MONGO_URL.startswith('mongodb://localhost'):
    log.warning('MONGO_URL is not set — falling back to localhost. On Render this WILL fail; '
                'set MONGO_URL to your Atlas URI and allowlist 0.0.0.0/0 in Atlas Network Access.')

app = FastAPI(title='Skali API')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False,
                   allow_methods=['*'], allow_headers=['*'])
security = HTTPBearer(auto_error=False)

TIERS = {'public', 'followers', 'inner'}


# ----------------------------- Encryption -----------------------------

def enc(text: str) -> str:
    n = os.urandom(12)
    ct = AESGCM(DM_KEY).encrypt(n, text.encode(), None)
    return base64.b64encode(n + ct).decode()

def dec(blob: str) -> str:
    try:
        raw = base64.b64decode(blob)
        return AESGCM(DM_KEY).decrypt(raw[:12], raw[12:], None).decode()
    except Exception:
        return ''


# ----------------------------- Auth -----------------------------

_jwk_client = None

def _get_jwk_client():
    global _jwk_client
    if _jwk_client is None and SUPABASE_URL:
        # cache_jwk_set + lifespan keep this to ~1 network fetch per 5 min,
        # not one per authenticated request.
        _jwk_client = jwt.PyJWKClient(f'{SUPABASE_URL}/auth/v1/.well-known/jwks.json',
                                      cache_jwk_set=True, lifespan=300, timeout=5)
    return _jwk_client


_SYMMETRIC_ALGS = ['HS256', 'HS384', 'HS512']
_ASYMMETRIC_ALGS = ['ES256', 'RS256', 'EdDSA']


def decode_jwt(token: str) -> dict:
    """Verify a bearer token, dispatching on the token's own `alg` header.

    Do NOT 'try HS256 first and fall through on failure': verifying an ES256
    token with algorithms=['HS256'] raises InvalidAlgorithmError, which is NOT a
    subclass of InvalidSignatureError. Catching only InvalidSignatureError means
    the JWKS branch is never reached, so every Google/OAuth login 401s on
    Supabase projects migrated to asymmetric JWT signing keys.
    """
    try:
        alg = (jwt.get_unverified_header(token) or {}).get('alg', '')
    except jwt.PyJWTError as e:
        raise jwt.InvalidTokenError(f'Malformed token header: {e}')

    # 1) Symmetric HS* -- our own email/password + dev tokens, and Supabase
    #    projects still on the shared (legacy) JWT secret.
    if alg in _SYMMETRIC_ALGS:
        if not JWT_SECRET:
            raise jwt.InvalidTokenError('HS* token but SUPABASE_JWT_SECRET is not configured')
        return jwt.decode(token, JWT_SECRET, algorithms=_SYMMETRIC_ALGS,
                          audience='authenticated',
                          options={'verify_signature': True, 'verify_exp': True,
                                   'verify_aud': True, 'require': ['exp', 'sub']})

    # 2) Asymmetric via Supabase JWKS -- real Google/OAuth tokens on projects
    #    migrated to JWT signing keys.
    if alg in _ASYMMETRIC_ALGS:
        client = _get_jwk_client()
        if client is None:
            raise jwt.InvalidTokenError(f'{alg} token but SUPABASE_URL is not configured')
        try:
            signing_key = client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as e:
            # JWKS endpoint unreachable. This is OUR outage, not a bad token --
            # surface 503 so the client keeps the session instead of signing out.
            raise HTTPException(503, f'Unable to reach identity provider: {e}')
        except jwt.PyJWKClientError as e:
            raise jwt.InvalidTokenError(f'No matching JWKS key: {e}')
        return jwt.decode(token, signing_key.key, algorithms=_ASYMMETRIC_ALGS,
                          audience='authenticated',
                          options={'verify_signature': True, 'verify_exp': True,
                                   'verify_aud': True, 'require': ['exp', 'sub']})

    raise jwt.InvalidTokenError(f'Unsupported token algorithm: {alg or "<none>"}')

def slugify_handle(name: str) -> str:
    base = re.sub(r'[^a-z0-9]', '', (name or 'member').lower())[:20] or 'member'
    return base

def calc_age(dob_str: Optional[str]) -> Optional[int]:
    """Age in years from a YYYY-MM-DD string, or None if unparseable."""
    try:
        parts = [int(x) for x in str(dob_str).split('T')[0].split('-')[:3]]
        y, m, d = parts[0], parts[1], parts[2]
        today = datetime.now(timezone.utc).date()
        return today.year - y - ((today.month, today.day) < (m, d))
    except Exception:
        return None


async def is_minor_user(uid: str) -> bool:
    p = await db.profiles.find_one({'id': uid}, {'is_minor': 1})
    return bool(p and p.get('is_minor'))


async def adult_minor_barrier(a: str, b: str) -> bool:
    """Hardcoded child-safety wall: True when exactly one of the two users is a minor
    (i.e. an adult ↔ minor pairing). Used to block follows, DMs, invites & discovery
    across the age boundary. Two minors or two adults are fine."""
    if a == b:
        return False
    pa = await db.profiles.find_one({'id': a}, {'is_minor': 1})
    pb = await db.profiles.find_one({'id': b}, {'is_minor': 1})
    if not pa or not pb:
        return False
    return bool(pa.get('is_minor')) != bool(pb.get('is_minor'))


async def ensure_profile(sub: str, email: Optional[str], name: Optional[str],
                         avatar: Optional[str], dob: Optional[str] = None) -> dict:
    prof = await db.profiles.find_one({'id': sub}, {'_id': 0})
    if prof:
        return prof
    display = name or (email.split('@')[0] if email else 'Member')
    base = slugify_handle(display)
    handle = base
    i = 0
    while await db.profiles.find_one({'handle': handle}):
        i += 1
        handle = f'{base}{i}'
    email_l = (email or '').lower()
    grant_admin = email_l in ADMIN_EMAILS or await email_is_allowlisted(email_l)
    age = calc_age(dob) if dob else None
    prof = {
        'id': sub, 'handle': handle, 'display_name': display, 'real_name': None,
        'email': email, 'bio': '', 'links': [], 'avatar_url': avatar,
        'account_type': 'verified' if grant_admin else 'free', 'follow_mode': 'open', 'dm_open': True,
        'is_admin': grant_admin, 'role': 'admin' if grant_admin else 'user',
        'allow_coadmin_dms': False,
        'dob': dob, 'is_minor': (age is not None and age < 18),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.profiles.insert_one(dict(prof))
    return prof

async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if creds is None or (creds.scheme or '').lower() != 'bearer':
        raise HTTPException(401, 'Missing Bearer token')
    try:
        c = decode_jwt(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f'Invalid token: {e}')
    meta = c.get('user_metadata') or {}
    return await ensure_profile(c['sub'], c.get('email'),
                                c.get('name') or meta.get('name') or meta.get('full_name'),
                                c.get('avatar_url') or meta.get('avatar_url'))


# ----------------------------- Relationship helpers -----------------------------

async def is_follower(viewer: str, author: str) -> bool:
    return bool(await db.follows.find_one({'follower_id': viewer, 'target_id': author, 'status': 'approved'}))

async def in_inner(owner: str, member: str) -> bool:
    return bool(await db.inner.find_one({'owner_id': owner, 'member_id': member, 'status': 'accepted'}))


async def nickname_for(owner_id: str, target_id: str) -> Optional[str]:
    """The private nickname `owner` has set for `target` (Inner-Circle only). None if unset."""
    if not owner_id or not target_id or owner_id == target_id:
        return None
    doc = await db.inner.find_one({'owner_id': owner_id, 'member_id': target_id, 'status': 'accepted'})
    return ((doc or {}).get('nickname') or None)


async def inner_perm(owner: str, member: str, key: str) -> bool:
    """Whether `member` may do `key` (dm|voice|call) toward `owner`. Only applies when
    member is in owner's Inner Circle; otherwise defaults to allowed (other gates handle it)."""
    doc = await db.inner.find_one({'owner_id': owner, 'member_id': member, 'status': 'accepted'})
    if not doc:
        return True
    return (doc.get('perms') or {}).get(key, True) is not False


# --- Phase 5: block / mute / restrict relations ---

async def get_relation(user_id: str, target_id: str) -> Optional[str]:
    """Return the kind ('block'|'mute'|'restrict') user_id set toward target_id, else None."""
    r = await db.relations.find_one({'user_id': user_id, 'target_id': target_id})
    return r.get('kind') if r else None


async def is_blocked_between(a: str, b: str) -> bool:
    """True if either user has blocked the other (mutual invisibility)."""
    r = await db.relations.find_one({'kind': 'block', '$or': [
        {'user_id': a, 'target_id': b}, {'user_id': b, 'target_id': a}]})
    return bool(r)


async def hidden_author_ids(viewer: str) -> set:
    """Author ids the viewer should not see in their feed: anyone they muted OR
    anyone blocked in either direction."""
    ids = set()
    async for r in db.relations.find({'user_id': viewer, 'kind': {'$in': ['mute', 'block']}}):
        ids.add(r['target_id'])
    async for r in db.relations.find({'target_id': viewer, 'kind': 'block'}):
        ids.add(r['user_id'])
    return ids


async def relation_slim(prof: dict) -> dict:
    return {'id': prof['id'], 'handle': prof['handle'], 'display_name': prof['display_name'],
            'avatar_url': prof.get('avatar_url'), 'account_type': acct_type(prof),
            'verified': is_identity_verified(prof),
            'role': effective_role(prof)}

async def can_view(viewer: str, post: dict) -> bool:
    if post.get('quarantined'):
        return False
    if post['author_id'] == viewer:
        return True
    if await is_blocked_between(viewer, post['author_id']):
        return False  # block = mutual invisibility
    t = post['tier']
    if t == 'public':
        return True
    if t == 'followers':
        return await is_follower(viewer, post['author_id'])
    if t == 'inner':
        return await in_inner(post['author_id'], viewer)
    return False

async def can_dm(viewer: str, target: str) -> bool:
    if viewer == target:
        return True  # "Me, Myself & I" — you can always message yourself (Saved Messages)
    if await is_blocked_between(viewer, target):
        return False  # blocked either direction -> no DMs
    if await adult_minor_barrier(viewer, target):
        return False  # child-safety: no adult ↔ minor DMs
    if await get_relation(target, viewer) == 'restrict':
        return False  # target restricted the viewer -> viewer can't DM them
    # viewer is a MEMBER of target's inner circle -> target controls DM permission per member
    doc = await db.inner.find_one({'owner_id': target, 'member_id': viewer, 'status': 'accepted'})
    if doc and (doc.get('perms') or {}).get('dm', True):
        return True
    if await in_inner(viewer, target):
        return True  # viewer owns target as an inner member -> can always DM their member
    tp = await db.profiles.find_one({'id': target})
    if tp and tp.get('dm_open') and await is_follower(viewer, target):
        return True  # Tier 2 optional toggle
    return False

async def add_activity(user_id: str, typ: str, actor: dict, text: str, post_id=None):
    await db.activity.insert_one({
        'id': str(uuid.uuid4()), 'user_id': user_id, 'type': typ,
        'actor_handle': actor['handle'], 'actor_name': actor['display_name'],
        'actor_id': actor['id'], 'actor_role': effective_role(actor), 'actor_account_type': acct_type(actor), 'text': text, 'post_id': post_id,
        'created_at': datetime.now(timezone.utc).isoformat(), 'read': False,
    })


# ----------------------------- Serializers -----------------------------

async def public_profile(prof: dict, viewer_id: str) -> dict:
    is_self = prof['id'] == viewer_id
    following = await db.follows.find_one({'follower_id': viewer_id, 'target_id': prof['id']})
    inv = await db.inner.find_one({'owner_id': prof['id'], 'member_id': viewer_id})
    followers_count = await db.follows.count_documents({'target_id': prof['id'], 'status': 'approved'})
    following_count = await db.follows.count_documents({'follower_id': prof['id'], 'status': 'approved'})
    out = {
        'id': prof['id'], 'handle': prof['handle'], 'display_name': prof['display_name'],
        'bio': prof.get('bio', ''), 'links': prof.get('links', []),
        'avatar_url': prof.get('avatar_url'), 'account_type': acct_type(prof),
        'role': effective_role(prof),
        'verified': is_identity_verified(prof),
        'creator_safety_flag': bool(prof.get('creator_safety_flag')),
        'follow_mode': prof.get('follow_mode', 'open'), 'dm_open': prof.get('dm_open', True),
        'is_self': is_self,
        'follow_status': following['status'] if following else None,
        'inner_status': inv['status'] if inv else None,
        'in_inner': bool(inv and inv['status'] == 'accepted'),
        'can_dm': await can_dm(viewer_id, prof['id']) if not is_self else False,
    }
    if is_self:
        out['real_name'] = prof.get('real_name')
        out['real_name_visibility'] = prof.get('real_name_visibility', 'private')
        out['email'] = prof.get('email')
        out['has_password'] = bool(await db.auth.find_one({'user_id': prof['id']}))
        out['followers_count'] = followers_count  # private: owner only
        out['following_count'] = following_count  # private: owner only
        out['is_admin'] = is_admin_user(prof)
        out['can_moderate'] = effective_role(prof) in MOD_ROLES
        out['allow_coadmin_dms'] = bool(prof.get('allow_coadmin_dms'))
        # Username-change cooldown (once every 60 days)
        _hc = prof.get('handle_changed_at')
        out['handle_changed_at'] = _hc
        _next = None
        if _hc:
            try:
                _next_dt = datetime.fromisoformat(_hc) + timedelta(days=60)
                if datetime.now(timezone.utc) < _next_dt:
                    _next = _next_dt.isoformat()
            except Exception:
                _next = None
        out['handle_change_available_at'] = _next  # null = can change now
        out['limits'] = tier_limits(prof)
        out['strikes'] = prof.get('strikes', 0)
        _minor = bool(prof.get('is_minor'))
        _cz = {**COMFORT_ZONE_DEFAULTS, **(prof.get('comfort_zone') or {})}
        if _minor:
            _cz['nsfw'] = False  # hardcoded: minors can never enable adult content
        out['comfort_zone'] = _cz
        out['is_minor'] = _minor
        out['dob_set'] = bool(prof.get('dob'))
        out['nsfw_locked'] = _minor  # tells UI the NSFW toggle is locked off
        out['theme'] = prof.get('theme') or DISPLAY_DEFAULTS['theme']
        out['accent'] = prof.get('accent') or DISPLAY_DEFAULTS['accent']
        out['font_size'] = prof.get('font_size') or DISPLAY_DEFAULTS['font_size']
        out['notif_prefs'] = {**NOTIF_DEFAULTS, **(prof.get('notif_prefs') or {})}
        out['onboarded'] = bool(prof.get('onboarded'))
        out['interests'] = prof.get('interests', [])
        # Block 2 — verification spine + monetisation gate.
        out['verification'] = verification_view(prof)
        out['monetisation_enabled'] = monetisation_ok(prof)
        out['account_nsfw'] = bool(prof.get('account_nsfw'))
    else:
        # My relation (block/mute/restrict) toward this user, for the profile menu.
        out['my_relation'] = await get_relation(viewer_id, prof['id'])
        # Real name is shown to others only per the owner's chosen visibility.
        vis = prof.get('real_name_visibility', 'private')
        rn = prof.get('real_name')
        is_fol = bool(following and following.get('status') == 'approved')
        is_inner = bool(inv and inv.get('status') == 'accepted')
        show_rn = rn and (
            vis == 'public'
            or (vis == 'followers' and (is_fol or is_inner))
            or (vis == 'inner' and is_inner)
        )
        if show_rn:
            out['real_name'] = rn
    # Pinned posts ribbon (up to 3), respecting tier visibility for the viewer.
    pinned = []
    for pid in (prof.get('pinned_post_ids', []) or [])[:tier_limits(prof).get('pinned', 3)]:
        pp = await db.posts.find_one({'id': pid})
        if pp and await can_view(viewer_id, pp):
            po = await post_out(pp, viewer_id)
            po['pinned'] = True
            pinned.append(po)
    out['pinned_posts'] = pinned
    return out

async def post_out(p: dict, viewer_id: str) -> dict:
    author = await db.profiles.find_one({'id': p['author_id']}, {'_id': 0})
    liked = viewer_id in p.get('likes', [])
    reactions = p.get('reactions', {}) or {}
    counts = {k: len(v) for k, v in reactions.items() if v}
    my_reaction = next((k for k, v in reactions.items() if viewer_id in v), None)
    is_author = p['author_id'] == viewer_id
    all_people = p.get('people_tags', []) or []
    # Others see only approved tags; the author and the tagged person see full status.
    if is_author or any(pt['user_id'] == viewer_id for pt in all_people):
        people_tags = all_people
    else:
        people_tags = [pt for pt in all_people if pt.get('status') == 'approved']
    my_tag_status = next((pt.get('status') for pt in all_people if pt['user_id'] == viewer_id), None)
    return {
        'id': p['id'], 'tier': p['tier'], 'text': p.get('text', ''),
        'media_url': p.get('media_url'), 'media_type': p.get('media_type'),
        'tags': p.get('tags', []), 'ai_label': p.get('ai_label', 'none'), 'edited': bool(p.get('edited')), 'edited_count': len(p.get('edit_history', [])), 'pinned': bool(p.get('pinned')), 'can_edit': p['author_id'] == viewer_id, 'created_at': p['created_at'],
        'people_tags': people_tags, 'my_tag_status': my_tag_status,
        'like_count': len(p.get('likes', [])), 'liked': liked,
        'likeable': p['tier'] == 'public',
        'reactions': counts, 'reaction_total': sum(counts.values()), 'my_reaction': my_reaction,
        'comment_count': await db.comments.count_documents({'post_id': p['id']}),
        'author': {'id': author['id'], 'handle': author['handle'],
                   'display_name': author['display_name'], 'avatar_url': author.get('avatar_url'),
                   'account_type': acct_type(author),
                   'verified': is_identity_verified(author),
                   'role': effective_role(author)} if author else None,
        'is_mine': p['author_id'] == viewer_id,
    }


# ----------------------------- Models -----------------------------

class DevLogin(BaseModel):
    name: Optional[str] = 'Guest'
    email: Optional[str] = None

class EmailAuth(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    dob: Optional[str] = None  # YYYY-MM-DD

class DobBody(BaseModel):
    dob: str  # YYYY-MM-DD

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    links: Optional[list] = None
    follow_mode: Optional[str] = None
    dm_open: Optional[bool] = None
    avatar_url: Optional[str] = None
    comfort_zone: Optional[dict] = None
    real_name: Optional[str] = None
    real_name_visibility: Optional[str] = None  # private | inner | followers | public
    theme: Optional[str] = None                 # dark | light
    accent: Optional[str] = None                # violet | blue | emerald | rose | amber | cyan
    font_size: Optional[str] = None             # small | normal | large
    notif_prefs: Optional[dict] = None
    onboarded: Optional[bool] = None            # completed the "welcome to Skali" tour

class PostCreate(BaseModel):
    tier: str = 'public'
    text: Optional[str] = ''
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    tags: Optional[list] = None
    people_tags: Optional[list] = None  # handles to tag; each requires that person's approval
    ai_label: Optional[str] = 'none'  # none | generated | assisted | altered

class ReactBody(BaseModel):
    emoji: str  # like | love | haha | wow | sad | angry

class CommentCreate(BaseModel):
    text: str
    parent_id: Optional[str] = None

REACTIONS = ['like', 'love', 'haha', 'wow', 'sad', 'angry']

class DMSend(BaseModel):
    text: Optional[str] = ''
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # audio | image
    duration: Optional[float] = None
    view_once: Optional[bool] = False  # disappearing media: recipient may open it a single time
    allow_save: Optional[bool] = True   # if False, recipient can't save/download the media

class TokenReq(BaseModel):
    room: str
    peer: Optional[str] = None  # handle of the person being called (for permission enforcement)


# ----------------------------- WS manager -----------------------------

class Manager:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = {}
    async def connect(self, room: str, ws: WebSocket):
        await ws.accept(); self.rooms.setdefault(room, set()).add(ws)
    def disconnect(self, room: str, ws: WebSocket):
        self.rooms.get(room, set()).discard(ws)
    async def broadcast(self, room: str, data: dict):
        for ws in list(self.rooms.get(room, set())):
            try: await ws.send_json(data)
            except Exception: self.disconnect(room, ws)

manager = Manager()

def dm_room(a: str, b: str) -> str:
    return 'dm:' + ':'.join(sorted([a, b]))


# --- Phase 6-prep: unread tracking (DMs + groups) ---

async def mark_read(scope: str, key: str, uid: str):
    """Record that user `uid` has read `scope`:`key` up to now."""
    await db.reads.update_one(
        {'scope': scope, 'key': key, 'user_id': uid},
        {'$set': {'last_read_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True)


async def read_marker(scope: str, key: str, uid: str) -> str:
    r = await db.reads.find_one({'scope': scope, 'key': key, 'user_id': uid})
    return r.get('last_read_at', '') if r else ''


async def dm_unread_count(room: str, uid: str, since: str) -> int:
    q = {'room': room, 'sender_id': {'$ne': uid}}
    if since:
        q['created_at'] = {'$gt': since}
    return await db.dms.count_documents(q)


# ----------------------------- Storage -----------------------------

def admin_headers():
    return {'apikey': SERVICE_ROLE_KEY, 'Authorization': f'Bearer {SERVICE_ROLE_KEY}'}

async def ensure_bucket():
    body = {'id': BUCKET, 'name': BUCKET, 'public': False,
            'file_size_limit': 50 * 1024 * 1024,
            'allowed_mime_types': ['image/*', 'video/*', 'audio/*']}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f'{SUPABASE_URL}/storage/v1/bucket',
                         headers={**admin_headers(), 'Content-Type': 'application/json'},
                         json=body)
        log.info('ensure_bucket create %s', r.status_code)
        # If it already exists (400/409), UPDATE its config so mime-types/size limits are
        # correct (older buckets were image-only @15MB, which broke video/audio/large uploads).
        if r.status_code in (400, 409):
            upd = await c.put(f'{SUPABASE_URL}/storage/v1/bucket/{BUCKET}',
                              headers={**admin_headers(), 'Content-Type': 'application/json'},
                              json={'public': False, 'file_size_limit': 50 * 1024 * 1024,
                                    'allowed_mime_types': ['image/*', 'video/*', 'audio/*']})
            log.info('ensure_bucket update %s', upd.status_code)

async def upload_and_sign(path: str, content: bytes, content_type: str,
                          expires_in: int = 60 * 60 * 24 * 365 * 10) -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        up = await c.post(f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}',
                          headers={**admin_headers(), 'Content-Type': content_type, 'x-upsert': 'true'},
                          content=content)
        up.raise_for_status()
        s = await c.post(f'{SUPABASE_URL}/storage/v1/object/sign/{BUCKET}/{path}',
                         headers={**admin_headers(), 'Content-Type': 'application/json'},
                         json={'expiresIn': expires_in})
        s.raise_for_status()
        url = s.json()['signedURL']
    return url if url.startswith('http') else f'{SUPABASE_URL}/storage/v1{url}'


# ----------------------------- Startup seed -----------------------------

@app.on_event('startup')
async def startup():
    # Run one-time bootstrap (seeding, bucket, admin) in the BACKGROUND so the
    # server starts accepting requests immediately. This keeps cold-start
    # time-to-first-response fast — login no longer waits on Supabase/DB seeding.
    asyncio.create_task(_bootstrap())


async def _bootstrap():
    sys_id = 'system-skali'
    try:
        if not await db.profiles.find_one({'id': sys_id}):
            await db.profiles.insert_one({
                'id': sys_id, 'handle': 'skali', 'display_name': 'Skali',
                'real_name': None, 'email': None, 'bio': 'Your place to gather. Your circle. Your rules. No bullshit.',
                'links': ['skali.app'], 'avatar_url': None, 'account_type': 'verified',
                'follow_mode': 'open', 'dm_open': False,
                'created_at': datetime.now(timezone.utc).isoformat()})
            for txt, tags in [
                ('Welcome to Skali — the responsible adult social network. No algorithm. No ads in your feed. Just your people.', ['welcome', 'skali']),
                ('Three tiers, one gathering: Public, Followers, and your Inner Circle. You decide who sees what.', ['privacy', 'tiers']),
            ]:
                await db.posts.insert_one({
                    'id': str(uuid.uuid4()), 'author_id': sys_id, 'tier': 'public',
                    'text': txt, 'media_url': None, 'media_type': None, 'tags': tags,
                    'likes': [], 'created_at': datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        log.warning('seed skipped: %s', e)
    try:
        await ensure_bucket()
    except Exception as e:
        log.warning('bucket: %s', e)
    # Seed a bootstrap super-admin login (email+password) you fully control.
    # SECURITY: the password has NO hardcoded default — it must come from the
    # SEED_ADMIN_PASSWORD env var. If it's unset, seeding is skipped (fail-closed)
    # so a known default can never ship in the repo.
    try:
        seed_email = os.environ.get('SEED_ADMIN_EMAIL', 'admin@skaliapp.com').strip().lower()
        seed_pw = os.environ.get('SEED_ADMIN_PASSWORD', '')
        if not seed_pw:
            log.warning('admin seed skipped: SEED_ADMIN_PASSWORD is not set (no default in code)')
        elif seed_email and not await db.auth.find_one({'email': seed_email}):
            salt = secrets.token_hex(16)
            uid = str(uuid.uuid4())
            await db.auth.insert_one({'email': seed_email, 'salt': salt,
                                      'hash': _pw_hash(seed_pw, salt), 'user_id': uid})
            prof = await ensure_profile(uid, seed_email, 'Skali Admin', None)
            await db.profiles.update_one({'id': uid}, {'$set': {'is_admin': True, 'role': 'admin', 'account_type': 'verified'}})
            log.info('seeded super-admin account: %s', seed_email)
    except Exception as e:
        log.warning('admin seed skipped: %s', e)


# ----------------------------- Auth routes -----------------------------

@app.get('/api/')
async def root():
    return {'ok': True, 'service': 'skali', 'time': datetime.now(timezone.utc).isoformat()}

@app.get('/api/health/db')
async def health_db():
    """Quick DB connectivity probe — open this URL to see if the backend can reach Mongo.
    Never leaks the connection string; only reports reachability + which host type."""
    configured = not MONGO_URL.startswith('mongodb://localhost')
    try:
        await client.admin.command('ping')
        return {'db': 'ok', 'mongo_url_configured': configured, 'db_name': DB_NAME}
    except Exception as e:
        return JSONResponse(status_code=503, content={
            'db': 'unreachable', 'mongo_url_configured': configured, 'db_name': DB_NAME,
            'hint': ('MONGO_URL is not set on this service — set it to your Atlas URI.' if not configured
                     else 'MONGO_URL is set but the database is unreachable — check the Atlas IP allowlist (add 0.0.0.0/0) and the credentials.'),
            'error': str(e)[:200]})

def mint_token(uid: str, email: str, name: str) -> str:
    now = int(time.time())
    return jwt.encode({'sub': uid, 'email': email, 'aud': 'authenticated',
                       'role': 'authenticated', 'iss': 'skali', 'iat': now,
                       'exp': now + 60 * 60 * 24 * 30, 'user_metadata': {'name': name}},
                      JWT_SECRET, algorithm='HS256')

def _pw_hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 100_000).hex()


@app.post('/api/dev/token')
async def dev_token(body: DevLogin):
    name = (body.name or 'Guest').strip() or 'Guest'
    email = (body.email or f"{slugify_handle(name)}@sandbox.skali").strip()
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
    prof = await ensure_profile(uid, email, name, None)
    return {'access_token': mint_token(uid, email, name), 'token_type': 'bearer',
            'user': {'id': uid, 'handle': prof['handle'], 'display_name': prof['display_name'], 'email': email}}


@app.post('/api/auth/register')
async def auth_register(body: EmailAuth):
    email = (body.email or '').strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise HTTPException(400, 'Enter a valid email')
    if not body.password or len(body.password) < 6:
        raise HTTPException(400, 'Password must be at least 6 characters')
    if await db.auth.find_one({'email': email}):
        raise HTTPException(400, 'That email is already registered — try signing in')
    age = calc_age(body.dob)
    if age is None:
        raise HTTPException(400, 'Please enter your date of birth')
    if age < 13:
        raise HTTPException(400, 'You must be at least 13 years old to use Skali')
    salt = secrets.token_hex(16)
    uid = str(uuid.uuid4())
    await db.auth.insert_one({'email': email, 'salt': salt, 'hash': _pw_hash(body.password, salt), 'user_id': uid})
    name = (body.name or email.split('@')[0]).strip()
    if contains_banned(name):
        raise HTTPException(400, 'That display name isn’t allowed. Please choose another.')
    prof = await ensure_profile(uid, email, name, None, dob=body.dob)
    return {'access_token': mint_token(uid, email, name), 'token_type': 'bearer',
            'user': {'id': uid, 'handle': prof['handle'], 'display_name': prof['display_name'], 'email': email}}


@app.post('/api/auth/dob')
async def set_dob(body: DobBody, u: dict = Depends(get_current_user)):
    """Set date of birth for accounts created without one (e.g. Google sign-in).
    DOB is write-once — it can't be changed after it's set."""
    if u.get('dob'):
        raise HTTPException(400, 'Your date of birth is already set')
    age = calc_age(body.dob)
    if age is None:
        raise HTTPException(400, 'Enter a valid date of birth')
    if age < 13:
        raise HTTPException(400, 'You must be at least 13 years old to use Skali')
    await db.profiles.update_one({'id': u['id']}, {'$set': {'dob': body.dob, 'is_minor': age < 18}})
    return {'ok': True, 'is_minor': age < 18}


@app.post('/api/auth/login')
async def auth_login(body: EmailAuth):
    email = (body.email or '').strip().lower()
    rec = await db.auth.find_one({'email': email})
    if not rec or not hmac.compare_digest(rec['hash'], _pw_hash(body.password or '', rec['salt'])):
        raise HTTPException(401, 'Invalid email or password')
    prof = await db.profiles.find_one({'id': rec['user_id']}, {'_id': 0})
    if not prof:
        prof = await ensure_profile(rec['user_id'], email, email.split('@')[0], None)
    return {'access_token': mint_token(rec['user_id'], email, prof['display_name']), 'token_type': 'bearer',
            'user': {'id': prof['id'], 'handle': prof['handle'], 'display_name': prof['display_name'], 'email': email}}

@app.get('/api/me')
async def me(u: dict = Depends(get_current_user)):
    return await public_profile(u, u['id'])


# ----------------------------- Interests (followed topics) -----------------------------
# Interests are lightweight followed topics. They map 1:1 to public post #tags, so a
# post tagged "gaming" shows up on the @gaming interest page. Followed interests are
# stored on the profile so they sync across every device the member signs in on.
INTEREST_MAX = 100

def _norm_interest(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())[:30]

@app.get('/api/interests')
async def my_interests(u: dict = Depends(get_current_user)):
    return {'interests': u.get('interests', []) or []}

@app.post('/api/interests/{name}')
async def follow_interest(name: str, u: dict = Depends(get_current_user)):
    key = _norm_interest(name)
    if not key:
        raise HTTPException(400, 'Invalid interest')
    cur = list(u.get('interests', []) or [])
    if not any(_norm_interest(x) == key for x in cur):
        cur = (cur + [name.strip()[:30]])[:INTEREST_MAX]
        await db.profiles.update_one({'id': u['id']}, {'$set': {'interests': cur}})
    return {'interests': cur, 'following': True}

@app.delete('/api/interests/{name}')
async def unfollow_interest(name: str, u: dict = Depends(get_current_user)):
    key = _norm_interest(name)
    cur = [x for x in (u.get('interests', []) or []) if _norm_interest(x) != key]
    await db.profiles.update_one({'id': u['id']}, {'$set': {'interests': cur}})
    return {'interests': cur, 'following': False}

@app.get('/api/interests/feed')
async def interests_feed(u: dict = Depends(get_current_user)):
    """Fresh public posts aggregated from every interest the member follows (chronological)."""
    keys = list({_norm_interest(x) for x in (u.get('interests') or []) if _norm_interest(x)})
    if not keys:
        return []
    out = []
    async for p in db.posts.find({'tier': 'public', 'tags': {'$in': keys}}).sort('created_at', -1).limit(80):
        if p['author_id'] != u['id'] and await is_blocked_between(u['id'], p['author_id']):
            continue
        out.append(await post_out(p, u['id']))
        if len(out) >= 40:
            break
    return out

@app.get('/api/interests/{name}/people')
async def interest_people(name: str, u: dict = Depends(get_current_user)):
    """Members who follow this interest — so people can discover others into @gaming, @art, etc.
    Also returns community counts (followers + public posts) for the interest page."""
    key = _norm_interest(name)
    if not key:
        return {'people': [], 'follower_count': 0, 'post_count': 0}
    people = []
    async for p in db.profiles.find({'interests': {'$exists': True, '$ne': []}}).limit(300):
        if not any(_norm_interest(x) == key for x in (p.get('interests') or [])):
            continue
        if p['id'] != u['id']:
            if await is_blocked_between(u['id'], p['id']):
                continue
            if await adult_minor_barrier(u['id'], p['id']):
                continue
        people.append(await public_profile(await db.profiles.find_one({'id': p['id']}, {'_id': 0}), u['id']))
        if len(people) >= 30:
            break
    follower_count = await db.profiles.count_documents(
        {'interests': {'$elemMatch': {'$regex': f'^{re.escape(key)}$', '$options': 'i'}}})
    post_count = await db.posts.count_documents({'tier': 'public', 'tags': key})
    return {'people': people, 'follower_count': follower_count, 'post_count': post_count}


@app.post('/api/auth/change-password')
async def change_password(body: ChangePassword, u: dict = Depends(get_current_user)):
    """Change the password for an email/password account."""
    rec = await db.auth.find_one({'user_id': u['id']})
    if not rec:
        raise HTTPException(400, 'This account signs in with Google, so it has no password to change')
    if not hmac.compare_digest(rec['hash'], _pw_hash(body.current_password or '', rec['salt'])):
        raise HTTPException(400, 'Current password is incorrect')
    if not body.new_password or len(body.new_password) < 6:
        raise HTTPException(400, 'New password must be at least 6 characters')
    salt = secrets.token_hex(16)
    await db.auth.update_one({'user_id': u['id']}, {'$set': {'salt': salt, 'hash': _pw_hash(body.new_password, salt)}})
    return {'ok': True}

class HandleUpdate(BaseModel):
    handle: str

HANDLE_COOLDOWN_DAYS = 60

@app.post('/api/profile/handle')
async def change_handle(body: HandleUpdate, u: dict = Depends(get_current_user)):
    """Change your #username. Allowed once every 60 days."""
    new_h = slugify_handle(body.handle)
    if len(new_h) < 3:
        raise HTTPException(400, 'Username must be at least 3 letters/numbers (a–z, 0–9)')
    if contains_banned(new_h):
        raise HTTPException(400, 'That username isn’t allowed. Please choose another.')
    if new_h == u['handle']:
        raise HTTPException(400, 'That’s already your username.')
    # 60-day cooldown
    last = u.get('handle_changed_at')
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            nxt = last_dt + timedelta(days=HANDLE_COOLDOWN_DAYS)
            now = datetime.now(timezone.utc)
            if now < nxt:
                days = (nxt - now).days + 1
                raise HTTPException(400, f'You can change your username again in {days} day{"s" if days != 1 else ""}.')
        except HTTPException:
            raise
        except Exception:
            pass
    # uniqueness (case-insensitive via normalized slug — handles are already lowercase slugs)
    taken = await db.profiles.find_one({'handle': new_h, 'id': {'$ne': u['id']}})
    if taken:
        raise HTTPException(409, 'That username is taken. Please choose another.')
    now_iso = datetime.now(timezone.utc).isoformat()
    old_h = u['handle']
    await db.profiles.update_one({'id': u['id']},
                                 {'$set': {'handle': new_h, 'handle_changed_at': now_iso}})
    # Handle history: remember the old handle so old @mentions/links still resolve,
    # and free the new handle from any stale history entry.
    await db.handle_history.delete_many({'handle': new_h})
    await db.handle_history.update_one(
        {'handle': old_h},
        {'$set': {'handle': old_h, 'user_id': u['id'], 'changed_at': now_iso}},
        upsert=True)
    return {'ok': True, 'handle': new_h, 'handle_changed_at': now_iso}


@app.put('/api/profile')
async def update_profile(body: ProfileUpdate, u: dict = Depends(get_current_user)):
    upd = {k: v for k, v in body.dict().items() if v is not None}
    lim = tier_limits(u)
    if 'display_name' in upd and contains_banned(upd['display_name']):
        raise HTTPException(400, 'That display name isn’t allowed. Please choose another.')
    if 'bio' in upd:
        if len(upd['bio']) > lim['bio']:
            raise HTTPException(400, f'Bio is limited to {lim["bio"]} characters on your plan.')
    if 'links' in upd:
        links = [l for l in (upd['links'] or []) if isinstance(l, str) and l.strip()]
        if len(links) > lim['links']:
            n = lim['links']
            raise HTTPException(400, f'You can add up to {n} links on your plan.' if n < 9999 else 'Too many links.')
        upd['links'] = links
    if 'follow_mode' in upd and upd['follow_mode'] not in ('open', 'approval'):
        upd.pop('follow_mode')
    if 'real_name_visibility' in upd and upd['real_name_visibility'] not in ('private', 'inner', 'followers', 'public'):
        upd.pop('real_name_visibility')
    if 'comfort_zone' in upd:
        cz = upd['comfort_zone'] or {}
        upd['comfort_zone'] = {k: bool(cz.get(k, COMFORT_ZONE_DEFAULTS[k])) for k in COMFORT_ZONE_KEYS}
        if u.get('is_minor'):
            upd['comfort_zone']['nsfw'] = False  # hardcoded: minors can't enable adult content
    if 'theme' in upd and upd['theme'] not in THEME_VALUES:
        upd.pop('theme')
    if 'accent' in upd and upd['accent'] not in ACCENT_VALUES:
        upd.pop('accent')
    if 'font_size' in upd and upd['font_size'] not in FONT_SIZE_VALUES:
        upd.pop('font_size')
    if 'notif_prefs' in upd:
        npf = upd['notif_prefs'] or {}
        upd['notif_prefs'] = {k: bool(npf.get(k, NOTIF_DEFAULTS[k])) for k in NOTIF_KEYS}
    if upd:
        await db.profiles.update_one({'id': u['id']}, {'$set': upd})
    prof = await db.profiles.find_one({'id': u['id']}, {'_id': 0})
    return await public_profile(prof, u['id'])


@app.delete('/api/account')
async def delete_account(u: dict = Depends(get_current_user)):
    """Permanently delete the signed-in user's account and all their data."""
    uid = u['id']
    await _purge_user(uid)
    await incr_deleted(1)
    return {'ok': True, 'deleted': uid}


async def _purge_user(uid: str):
    """Delete a user and all of their data across collections."""
    await db.profiles.delete_one({'id': uid})
    await db.auth.delete_many({'user_id': uid})
    await db.posts.delete_many({'author_id': uid})
    await db.comments.delete_many({'author_id': uid})
    await db.wall.delete_many({'$or': [{'owner_id': uid}, {'author_id': uid}]})
    await db.follows.delete_many({'$or': [{'follower_id': uid}, {'target_id': uid}]})
    await db.inner.delete_many({'$or': [{'owner_id': uid}, {'member_id': uid}]})
    await db.dms.delete_many({'participants': uid})
    await db.activity.delete_many({'$or': [{'user_id': uid}, {'actor_id': uid}]})
    await db.reports.delete_many({'reporter_id': uid})
    await db.relations.delete_many({'$or': [{'user_id': uid}, {'target_id': uid}]})
    await db.reads.delete_many({'user_id': uid})
    await db.group_messages.delete_many({'sender_id': uid})
    await db.groups.delete_many({'owner_id': uid})
    await db.groups.update_many({'members': uid}, {'$pull': {'members': uid}})
    await db.nsfw_queue.delete_many({'user_id': uid})
    await db.admin_notes.delete_many({'user_id': uid})
    await db.boards.delete_many({'owner_id': uid})
    await db.board_posts.delete_many({'author_id': uid})
    await db.board_reactions.delete_many({'user_id': uid})
    await db.device_tokens.delete_many({'user_id': uid})


async def incr_deleted(n: int = 1):
    if n:
        await db.counters.update_one({'_id': 'deleted'}, {'$inc': {'n': n}}, upsert=True)


# ----------------------------- Profiles / social graph -----------------------------

async def resolve_profile(handle: str, projection=None):
    """Find a profile by current handle, falling back to a past handle (handle history)
    so old @mentions and profile links still resolve to the same person."""
    h = slugify_handle(handle)
    prof = await db.profiles.find_one({'handle': h}, projection) if projection else await db.profiles.find_one({'handle': h})
    if prof:
        return prof
    hist = await db.handle_history.find_one({'handle': h}, sort=[('changed_at', -1)])
    if hist:
        return await db.profiles.find_one({'id': hist['user_id']}, projection) if projection else await db.profiles.find_one({'id': hist['user_id']})
    return None


@app.get('/api/users/{handle}')
async def get_user(handle: str, u: dict = Depends(get_current_user)):
    prof = await resolve_profile(handle, {'_id': 0})
    if not prof:
        raise HTTPException(404, 'User not found')
    if prof['id'] != u['id'] and await is_blocked_between(u['id'], prof['id']):
        raise HTTPException(404, 'User not found')  # block = mutual invisibility
    return await public_profile(prof, u['id'])

@app.get('/api/users/{handle}/posts')
async def user_posts(handle: str, u: dict = Depends(get_current_user)):
    prof = await resolve_profile(handle)
    if not prof:
        raise HTTPException(404, 'User not found')
    out = []
    async for p in db.posts.find({'author_id': prof['id']}).sort('created_at', -1).limit(100):
        if await can_view(u['id'], p):
            out.append(await post_out(p, u['id']))
    return out

@app.post('/api/follow/{handle}')
async def follow(handle: str, u: dict = Depends(get_current_user)):
    target = await db.profiles.find_one({'handle': handle})
    if not target or target['id'] == u['id']:
        raise HTTPException(400, 'Cannot follow')
    if await is_blocked_between(u['id'], target['id']):
        raise HTTPException(403, 'Cannot follow this user')
    if await adult_minor_barrier(u['id'], target['id']):
        raise HTTPException(403, 'This account is not available to you')  # child-safety wall
    status = 'approved' if target.get('follow_mode', 'open') == 'open' else 'pending'
    await db.follows.update_one({'follower_id': u['id'], 'target_id': target['id']},
                                {'$set': {'status': status,
                                          'created_at': datetime.now(timezone.utc).isoformat()}},
                                upsert=True)
    await add_activity(target['id'], 'follow_request' if status == 'pending' else 'follow',
                       u, 'requested to follow you' if status == 'pending' else 'started following you')
    return {'status': status}

@app.delete('/api/follow/{handle}')
async def unfollow(handle: str, u: dict = Depends(get_current_user)):
    target = await db.profiles.find_one({'handle': handle})
    if target:
        await db.follows.delete_one({'follower_id': u['id'], 'target_id': target['id']})
    return {'status': 'none'}

@app.post('/api/follow-requests/{handle}/accept')
async def accept_follow(handle: str, u: dict = Depends(get_current_user)):
    fol = await db.profiles.find_one({'handle': handle})
    if not fol:
        raise HTTPException(404, 'Not found')
    await db.follows.update_one({'follower_id': fol['id'], 'target_id': u['id']},
                                {'$set': {'status': 'approved'}})
    await add_activity(fol['id'], 'follow_accepted', u, 'accepted your follow request')
    return {'status': 'approved'}

@app.post('/api/inner/invite/{handle}')
async def invite_inner(handle: str, u: dict = Depends(get_current_user)):
    member = await db.profiles.find_one({'handle': handle})
    if not member or member['id'] == u['id']:
        raise HTTPException(400, 'Cannot invite')
    if await is_blocked_between(u['id'], member['id']):
        raise HTTPException(403, 'Cannot invite this user')
    if await adult_minor_barrier(u['id'], member['id']):
        raise HTTPException(403, 'This account is not available to you')  # child-safety wall
    await db.inner.update_one({'owner_id': u['id'], 'member_id': member['id']},
                              {'$set': {'status': 'pending',
                                        'created_at': datetime.now(timezone.utc).isoformat()}},
                              upsert=True)
    await add_activity(member['id'], 'inner_invite', u, 'invited you to their Inner Circle')
    return {'status': 'pending'}

@app.post('/api/inner/accept/{handle}')
async def accept_inner(handle: str, u: dict = Depends(get_current_user)):
    owner = await db.profiles.find_one({'handle': handle})
    if not owner:
        raise HTTPException(404, 'Not found')
    await db.inner.update_one({'owner_id': owner['id'], 'member_id': u['id']},
                              {'$set': {'status': 'accepted'}})
    await add_activity(owner['id'], 'inner_accepted', u, 'joined your Inner Circle')
    return {'status': 'accepted'}

@app.get('/api/inner')
async def my_inner(u: dict = Depends(get_current_user)):
    out = []
    async for r in db.inner.find({'owner_id': u['id'], 'status': 'accepted'}):
        p = await db.profiles.find_one({'id': r['member_id']}, {'_id': 0})
        if p:
            pp = await public_profile(p, u['id'])
            pp['nickname'] = r.get('nickname') or None
            out.append(pp)
    return out


# ----------------------------- Phase 5: block / mute / restrict -----------------------------

class RelationBody(BaseModel):
    kind: str  # block | mute | restrict


@app.post('/api/relations/{handle}')
async def set_relation(handle: str, body: RelationBody, u: dict = Depends(get_current_user)):
    """Block, mute, or restrict a user. Blocking severs all follow + Inner Circle ties both ways."""
    kind = (body.kind or '').strip().lower()
    if kind not in RELATION_KINDS:
        raise HTTPException(400, 'Invalid relation kind')
    target = await db.profiles.find_one({'handle': handle})
    if not target or target['id'] == u['id']:
        raise HTTPException(400, 'Cannot set a relation on this user')
    tid = target['id']
    await db.relations.update_one(
        {'user_id': u['id'], 'target_id': tid},
        {'$set': {'id': str(uuid.uuid4()), 'kind': kind,
                  'created_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    if kind == 'block':
        # Sever all ties in both directions.
        await db.follows.delete_many({'$or': [
            {'follower_id': u['id'], 'target_id': tid},
            {'follower_id': tid, 'target_id': u['id']}]})
        await db.inner.delete_many({'$or': [
            {'owner_id': u['id'], 'member_id': tid},
            {'owner_id': tid, 'member_id': u['id']}]})
    return {'ok': True, 'kind': kind}


@app.delete('/api/relations/{handle}')
async def clear_relation(handle: str, u: dict = Depends(get_current_user)):
    target = await db.profiles.find_one({'handle': handle})
    if target:
        await db.relations.delete_one({'user_id': u['id'], 'target_id': target['id']})
    return {'ok': True}


@app.get('/api/relations')
async def list_relations(u: dict = Depends(get_current_user)):
    out = {'block': [], 'mute': [], 'restrict': []}
    async for r in db.relations.find({'user_id': u['id']}):
        p = await db.profiles.find_one({'id': r['target_id']}, {'_id': 0})
        if p and r.get('kind') in out:
            out[r['kind']].append(await relation_slim(p))
    return out


# ----------------------------- Phase 5: Connections manager -----------------------------

@app.get('/api/connections')
async def connections(u: dict = Depends(get_current_user)):
    """Everything for the Connections manager: followers, following (+pending), Inner Circle,
    incoming follow requests, and my block/mute/restrict lists."""
    uid = u['id']
    followers, following, inner, requests = [], [], [], []

    async for f in db.follows.find({'target_id': uid, 'status': 'approved'}):
        p = await db.profiles.find_one({'id': f['follower_id']}, {'_id': 0})
        if p:
            s = await relation_slim(p)
            s['in_my_inner'] = await in_inner(uid, p['id'])
            followers.append(s)

    async for f in db.follows.find({'follower_id': uid}):
        p = await db.profiles.find_one({'id': f['target_id']}, {'_id': 0})
        if p:
            s = await relation_slim(p)
            s['status'] = f.get('status', 'approved')
            s['in_my_inner'] = await in_inner(uid, p['id'])
            following.append(s)

    async for r in db.inner.find({'owner_id': uid, 'status': 'accepted'}):
        p = await db.profiles.find_one({'id': r['member_id']}, {'_id': 0})
        if p:
            s = await relation_slim(p)
            s['perms'] = {'dm': True, 'voice': True, 'call': True, **(r.get('perms') or {})}
            inner.append(s)

    async for f in db.follows.find({'target_id': uid, 'status': 'pending'}):
        p = await db.profiles.find_one({'id': f['follower_id']}, {'_id': 0})
        if p:
            requests.append(await relation_slim(p))

    rel = await list_relations(u)
    return {'followers': followers, 'following': following, 'inner': inner,
            'requests': requests, 'relations': rel,
            'counts': {'followers': len(followers), 'following': len(following),
                       'inner': len(inner), 'requests': len(requests)}}


@app.post('/api/followers/{handle}/remove')
async def remove_follower(handle: str, u: dict = Depends(get_current_user)):
    """Remove someone who follows you (they stop following you)."""
    fol = await db.profiles.find_one({'handle': handle})
    if fol:
        await db.follows.delete_one({'follower_id': fol['id'], 'target_id': u['id']})
    return {'ok': True}


@app.delete('/api/inner/{handle}')
async def remove_inner(handle: str, u: dict = Depends(get_current_user)):
    """Remove a member from your Inner Circle (owner action)."""
    member = await db.profiles.find_one({'handle': handle})
    if member:
        await db.inner.delete_one({'owner_id': u['id'], 'member_id': member['id']})
    return {'ok': True}


class InnerPerms(BaseModel):
    dm: Optional[bool] = None
    voice: Optional[bool] = None
    call: Optional[bool] = None

@app.put('/api/inner/{handle}/perms')
async def set_inner_perms(handle: str, body: InnerPerms, u: dict = Depends(get_current_user)):
    """Owner sets what a specific Inner-Circle member may do toward them (DM / voice note / call)."""
    member = await db.profiles.find_one({'handle': handle})
    if not member:
        raise HTTPException(404, 'User not found')
    doc = await db.inner.find_one({'owner_id': u['id'], 'member_id': member['id'], 'status': 'accepted'})
    if not doc:
        raise HTTPException(404, 'That user is not in your Inner Circle')
    perms = {'dm': True, 'voice': True, 'call': True, **(doc.get('perms') or {})}
    for k in ('dm', 'voice', 'call'):
        v = getattr(body, k)
        if v is not None:
            perms[k] = bool(v)
    await db.inner.update_one({'id': doc['id']} if doc.get('id') else {'owner_id': u['id'], 'member_id': member['id']},
                              {'$set': {'perms': perms}})
    return {'ok': True, 'perms': perms}


class NicknameBody(BaseModel):
    nickname: Optional[str] = ''


@app.put('/api/inner/{handle}/nickname')
async def set_inner_nickname(handle: str, body: NicknameBody, u: dict = Depends(get_current_user)):
    """Set a PRIVATE nickname for one of your Inner-Circle members (only you see it).
    Send an empty string to clear it."""
    member = await db.profiles.find_one({'handle': handle})
    if not member:
        raise HTTPException(404, 'User not found')
    doc = await db.inner.find_one({'owner_id': u['id'], 'member_id': member['id'], 'status': 'accepted'})
    if not doc:
        raise HTTPException(403, 'You can only nickname people in your Inner Circle')
    nick = (body.nickname or '').strip()[:40]
    if nick and contains_banned(nick):
        raise HTTPException(400, 'That nickname isn’t allowed. Please choose another.')
    await db.inner.update_one({'id': doc['id']} if doc.get('id') else {'owner_id': u['id'], 'member_id': member['id']},
                              {'$set': {'nickname': nick}})
    return {'ok': True, 'nickname': nick}


# ----------------------------- Custom stickers (personal pack) -----------------------------

class StickerBody(BaseModel):
    url: str

MAX_STICKERS = 100

@app.get('/api/stickers')
async def list_stickers(u: dict = Depends(get_current_user)):
    out = []
    async for s in db.stickers.find({'user_id': u['id']}, {'_id': 0}).sort('created_at', -1):
        out.append(s)
    return out

@app.post('/api/stickers')
async def add_sticker(body: StickerBody, u: dict = Depends(get_current_user)):
    """Register an uploaded image as a personal sticker (upload the file via /api/upload first)."""
    url = (body.url or '').strip()
    if not url:
        raise HTTPException(400, 'Missing sticker image')
    count = await db.stickers.count_documents({'user_id': u['id']})
    if count >= MAX_STICKERS:
        raise HTTPException(400, f'You can keep up to {MAX_STICKERS} stickers. Delete some first.')
    doc = {'id': str(uuid.uuid4()), 'user_id': u['id'], 'url': url,
           'created_at': datetime.now(timezone.utc).isoformat()}
    await db.stickers.insert_one(dict(doc))
    return doc

@app.delete('/api/stickers/{sticker_id}')
async def delete_sticker(sticker_id: str, u: dict = Depends(get_current_user)):
    res = await db.stickers.delete_one({'id': sticker_id, 'user_id': u['id']})
    if res.deleted_count == 0:
        raise HTTPException(404, 'Sticker not found')
    return {'ok': True}




# ----------------------------- Feed / posts -----------------------------

@app.get('/api/feed')
async def feed(scope: str = 'general', u: dict = Depends(get_current_user)):
    author_filter = None
    if scope == 'followers':
        ids = [f['target_id'] async for f in db.follows.find({'follower_id': u['id'], 'status': 'approved'})]
        ids.append(u['id'])
        author_filter = {'author_id': {'$in': ids}}
    q = author_filter or {}
    hidden = await hidden_author_ids(u['id'])
    vp = await db.profiles.find_one({'id': u['id']})
    _cz = {**COMFORT_ZONE_DEFAULTS, **((vp or {}).get('comfort_zone') or {})}
    hide_ai = _cz.get('ai') is False       # "AI generated content" toggle off -> hide AI-labelled posts
    # Fail-closed NSFW gate (Block 2): NSFW is hidden unless the viewer has the Comfort-Zone
    # NSFW toggle ON *and* is an age-verified adult. Unverified/minor => always hidden.
    hide_nsfw = (_cz.get('nsfw') is not True) or (not is_age_verified_adult(vp))
    out = []
    async for p in db.posts.find(q).sort('created_at', -1).limit(150):
        if p['author_id'] in hidden and p['author_id'] != u['id']:
            continue  # muted or blocked
        if p['author_id'] != u['id']:
            if hide_ai and p.get('ai_label', 'none') != 'none':
                continue  # comfort zone: AI content hidden
            if hide_nsfw and p.get('nsfw'):
                continue  # comfort zone / minor safety: NSFW hidden
        if await can_view(u['id'], p):
            out.append(await post_out(p, u['id']))
        if len(out) >= 60:
            break
    return out


@app.get('/api/reels')
async def reels(u: dict = Depends(get_current_user)):
    """TikTok-style feed: video posts the viewer can see, newest first."""
    out = []
    async for p in db.posts.find({'media_type': 'video', 'media_url': {'$ne': None}}).sort('created_at', -1).limit(150):
        if await can_view(u['id'], p):
            out.append(await post_out(p, u['id']))
        if len(out) >= 40:
            break
    return out


class WallPost(BaseModel):
    text: str


async def can_wall(viewer: str, owner: str) -> bool:
    return viewer == owner or await in_inner(owner, viewer) or await is_follower(viewer, owner)


@app.get('/api/wall/{handle}')
async def get_wall(handle: str, u: dict = Depends(get_current_user)):
    owner = await db.profiles.find_one({'handle': handle}, {'_id': 0})
    if not owner:
        raise HTTPException(404, 'Not found')
    can = await can_wall(u['id'], owner['id'])
    items = []
    if can or owner['id'] == u['id']:
        async for w in db.wall.find({'owner_id': owner['id']}).sort('created_at', -1).limit(100):
            a = await db.profiles.find_one({'id': w['author_id']}, {'_id': 0})
            items.append({'id': w['id'], 'text': w['text'], 'created_at': w['created_at'],
                          'edited': bool(w.get('edited')), 'edited_count': len(w.get('edit_history', [])),
                          'author': {'id': a['id'], 'handle': a['handle'], 'display_name': a['display_name'],
                                     'avatar_url': a.get('avatar_url')} if a else None,
                          'can_delete': w['author_id'] == u['id'] or owner['id'] == u['id'] or is_admin_user(u),
                          'can_edit': w['author_id'] == u['id']})
    return {'can_post': can, 'posts': items}


@app.post('/api/wall/{handle}')
async def post_wall(handle: str, body: WallPost, u: dict = Depends(get_current_user)):
    owner = await db.profiles.find_one({'handle': handle}, {'_id': 0})
    if not owner:
        raise HTTPException(404, 'Not found')
    if not await can_wall(u['id'], owner['id']):
        raise HTTPException(403, 'Only followers and Inner Circle can post on this wall')
    text = (body.text or '').strip()
    if not text:
        raise HTTPException(400, 'Empty post')
    if contains_banned(text):
        raise HTTPException(400, 'Your message contains a word that isn’t allowed here.')
    doc = {'id': str(uuid.uuid4()), 'owner_id': owner['id'], 'author_id': u['id'],
           'text': text[:2000], 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.wall.insert_one(dict(doc))
    if owner['id'] != u['id']:
        await add_activity(owner['id'], 'wall', u, 'posted on your wall', doc['id'])
    a = await db.profiles.find_one({'id': u['id']}, {'_id': 0})
    return {'id': doc['id'], 'text': doc['text'], 'created_at': doc['created_at'], 'can_delete': True,
            'author': {'id': a['id'], 'handle': a['handle'], 'display_name': a['display_name'], 'avatar_url': a.get('avatar_url')}}


@app.delete('/api/wall/{wall_id}')
async def delete_wall(wall_id: str, u: dict = Depends(get_current_user)):
    w = await db.wall.find_one({'id': wall_id})
    if not w:
        raise HTTPException(404, 'Not found')
    if not (w['author_id'] == u['id'] or w['owner_id'] == u['id'] or is_admin_user(u)):
        raise HTTPException(403, 'Not allowed')
    await db.wall.delete_one({'id': wall_id})
    return {'ok': True}


# ----------------------------- Discussion Boards (tiered, creator-moderated) -----------------------------

class BoardCreate(BaseModel):
    title: str
    description: Optional[str] = ''
    tier: str = 'public'  # public (T1 read) | followers (T2) | inner (T3)

class BoardPost(BaseModel):
    text: str
    parent_id: Optional[str] = None  # set to reply to another board post (threaded)

class BoardReact(BaseModel):
    emoji: str  # like | love | haha | wow | sad | angry


async def can_read_board(viewer: str, board: dict) -> bool:
    owner = board['owner_id']
    if viewer == owner or await is_admin_user_id(viewer):
        return True
    if await adult_minor_barrier(viewer, owner) or await is_blocked_between(viewer, owner):
        return False
    t = board.get('tier', 'public')
    if t == 'public':
        return True
    if t == 'followers':
        return await is_follower(viewer, owner)
    if t == 'inner':
        return await in_inner(owner, viewer)
    return False


async def can_post_board(viewer: str, board: dict) -> bool:
    """T1 public boards: only the owner's approved followers (or owner) may post — read is open.
    T2/T3: same audience as read (followers / inner)."""
    owner = board['owner_id']
    if viewer == owner:
        return True
    if not await can_read_board(viewer, board):
        return False
    t = board.get('tier', 'public')
    if t == 'public':
        return await is_follower(viewer, owner)  # read-only for strangers on T1
    return True


def is_admin_user_id_sync():
    pass


async def is_admin_user_id(uid: str) -> bool:
    p = await db.profiles.find_one({'id': uid}, {'is_admin': 1, 'email': 1})
    return bool(p and is_admin_user(p))

async def board_out(b: dict, viewer: str) -> dict:
    owner = await db.profiles.find_one({'id': b['owner_id']}, {'_id': 0})
    return {'id': b['id'], 'title': b['title'], 'description': b.get('description', ''),
            'tier': b.get('tier', 'public'), 'owner_id': b['owner_id'],
            'owner': {'id': owner['id'], 'handle': owner['handle'], 'display_name': owner['display_name'],
                      'avatar_url': owner.get('avatar_url')} if owner else None,
            'is_owner': b['owner_id'] == viewer,
            'post_count': await db.board_posts.count_documents({'board_id': b['id']}),
            'can_post': await can_post_board(viewer, b),
            'created_at': b['created_at']}


@app.post('/api/boards')
async def create_board(body: BoardCreate, u: dict = Depends(get_current_user)):
    title = (body.title or '').strip()
    if not title:
        raise HTTPException(400, 'Board needs a title')
    if contains_banned(title) or contains_banned(body.description):
        raise HTTPException(400, 'That title or description contains a word that isn’t allowed.')
    tier = body.tier if body.tier in TIERS else 'public'
    doc = {'id': str(uuid.uuid4()), 'owner_id': u['id'], 'title': title[:100],
           'description': (body.description or '')[:500], 'tier': tier,
           'created_at': datetime.now(timezone.utc).isoformat()}
    await db.boards.insert_one(dict(doc))
    return await board_out(doc, u['id'])


@app.get('/api/boards/{handle}')
async def list_boards(handle: str, u: dict = Depends(get_current_user)):
    owner = await db.profiles.find_one({'handle': handle}, {'_id': 0})
    if not owner:
        raise HTTPException(404, 'User not found')
    out = []
    async for b in db.boards.find({'owner_id': owner['id']}).sort('created_at', -1).limit(100):
        if await can_read_board(u['id'], b):
            out.append(await board_out(b, u['id']))
    return out


async def board_post_reactions(post_id: str, viewer: str) -> dict:
    """Return {counts:{emoji:n}, mine: emoji|None} for a board post."""
    counts: dict = {}
    mine = None
    async for r in db.board_reactions.find({'post_id': post_id}):
        counts[r['emoji']] = counts.get(r['emoji'], 0) + 1
        if r['user_id'] == viewer:
            mine = r['emoji']
    return {'counts': counts, 'mine': mine}


async def board_post_out(p: dict, b: dict, viewer: str) -> dict:
    a = await db.profiles.find_one({'id': p['author_id']}, {'_id': 0})
    return {'id': p['id'], 'text': p['text'], 'created_at': p['created_at'],
            'parent_id': p.get('parent_id'),
            'author': {'id': a['id'], 'handle': a['handle'], 'display_name': a['display_name'],
                       'avatar_url': a.get('avatar_url')} if a else None,
            'reactions': await board_post_reactions(p['id'], viewer),
            'can_delete': p['author_id'] == viewer or b['owner_id'] == viewer or await is_admin_user_id(viewer)}


@app.get('/api/board/{board_id}')
async def get_board(board_id: str, u: dict = Depends(get_current_user)):
    b = await db.boards.find_one({'id': board_id})
    if not b:
        raise HTTPException(404, 'Board not found')
    if not await can_read_board(u['id'], b):
        raise HTTPException(403, 'You don’t have access to this board')
    tops = []
    replies_by_parent: dict = {}
    async for p in db.board_posts.find({'board_id': board_id}).sort('created_at', 1).limit(1000):
        out = await board_post_out(p, b, u['id'])
        if p.get('parent_id'):
            replies_by_parent.setdefault(p['parent_id'], []).append(out)
        else:
            tops.append(out)
    for t in tops:
        t['replies'] = replies_by_parent.get(t['id'], [])
    base = await board_out(b, u['id'])
    base['posts'] = tops
    return base


@app.post('/api/board/{board_id}/posts')
async def create_board_post(board_id: str, body: BoardPost, u: dict = Depends(get_current_user)):
    b = await db.boards.find_one({'id': board_id})
    if not b:
        raise HTTPException(404, 'Board not found')
    if not await can_post_board(u['id'], b):
        raise HTTPException(403, 'You can’t post on this board')
    text = (body.text or '').strip()
    if not text:
        raise HTTPException(400, 'Empty message')
    if contains_banned(text):
        raise HTTPException(400, 'Your message contains a word that isn’t allowed here.')
    parent_id = None
    if body.parent_id:
        parent = await db.board_posts.find_one({'id': body.parent_id, 'board_id': board_id})
        if not parent:
            raise HTTPException(404, 'Reply target not found')
        parent_id = parent['id']
    doc = {'id': str(uuid.uuid4()), 'board_id': board_id, 'author_id': u['id'], 'parent_id': parent_id,
           'text': text[:4000], 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.board_posts.insert_one(dict(doc))
    if b['owner_id'] != u['id']:
        verb = 'replied in' if parent_id else 'posted in'
        await add_activity(b['owner_id'], 'board', u, f'{verb} “{b["title"]}”', board_id)
    out = await board_post_out(doc, b, u['id'])
    out['replies'] = []
    return out


@app.post('/api/board-posts/{post_id}/react')
async def react_board_post(post_id: str, body: BoardReact, u: dict = Depends(get_current_user)):
    if body.emoji not in REACTIONS:
        raise HTTPException(400, 'Invalid reaction')
    p = await db.board_posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Not found')
    b = await db.boards.find_one({'id': p['board_id']})
    if not b or not await can_read_board(u['id'], b):
        raise HTTPException(403, 'You don’t have access to this board')
    existing = await db.board_reactions.find_one({'post_id': post_id, 'user_id': u['id']})
    if existing and existing['emoji'] == body.emoji:
        await db.board_reactions.delete_one({'post_id': post_id, 'user_id': u['id']})  # toggle off
    else:
        await db.board_reactions.update_one(
            {'post_id': post_id, 'user_id': u['id']},
            {'$set': {'post_id': post_id, 'user_id': u['id'], 'emoji': body.emoji}}, upsert=True)
    return await board_post_reactions(post_id, u['id'])


@app.delete('/api/board-posts/{post_id}')
async def delete_board_post(post_id: str, u: dict = Depends(get_current_user)):
    p = await db.board_posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Not found')
    b = await db.boards.find_one({'id': p['board_id']})
    if not (p['author_id'] == u['id'] or (b and b['owner_id'] == u['id']) or is_admin_user(u)):
        raise HTTPException(403, 'Not allowed')
    await db.board_posts.delete_one({'id': post_id})
    await db.board_posts.delete_many({'parent_id': post_id})  # cascade replies
    await db.board_reactions.delete_many({'post_id': post_id})
    return {'ok': True}


@app.delete('/api/boards/{board_id}')
async def delete_board(board_id: str, u: dict = Depends(get_current_user)):
    b = await db.boards.find_one({'id': board_id})
    if not b:
        raise HTTPException(404, 'Board not found')
    if not (b['owner_id'] == u['id'] or is_admin_user(u)):
        raise HTTPException(403, 'Only the board owner can delete it')
    await db.boards.delete_one({'id': board_id})
    post_ids = [p['id'] async for p in db.board_posts.find({'board_id': board_id}, {'id': 1})]
    await db.board_posts.delete_many({'board_id': board_id})
    if post_ids:
        await db.board_reactions.delete_many({'post_id': {'$in': post_ids}})
    return {'ok': True}



@app.post('/api/posts')
async def create_post(body: PostCreate, u: dict = Depends(get_current_user)):
    tier = body.tier if body.tier in TIERS else 'public'
    text = (body.text or '').strip()
    if not text and not body.media_url:
        raise HTTPException(400, 'Empty post')
    tags = [re.sub(r'[^a-z0-9]', '', t.lower())[:20] for t in (body.tags or [])]
    tags = [t for t in tags if t][:10]
    if tier == 'inner':
        tags = []  # spec: no tag field on Tier 3
    ai_label = body.ai_label if body.ai_label in AI_LABELS else 'none'
    # People-tags: each tagged person must approve before the tag shows publicly.
    people = []
    seen_ids = set()
    for h in (body.people_tags or [])[:10]:
        handle = re.sub(r'[^a-z0-9_]', '', str(h).lower())[:30]
        if not handle:
            continue
        tp = await db.profiles.find_one({'handle': handle}, {'_id': 0})
        if not tp or tp['id'] == u['id'] or tp['id'] in seen_ids:
            continue
        if await is_blocked_between(u['id'], tp['id']) or await adult_minor_barrier(u['id'], tp['id']):
            continue  # safety: can't tag across block / adult-minor barrier
        seen_ids.add(tp['id'])
        people.append({'user_id': tp['id'], 'handle': tp['handle'],
                       'display_name': tp['display_name'], 'status': 'pending'})
    doc = {'id': str(uuid.uuid4()), 'author_id': u['id'], 'tier': tier, 'text': text,
           'media_url': body.media_url, 'media_type': body.media_type, 'tags': tags,
           'people_tags': people, 'ai_label': ai_label,
           'likes': [], 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.posts.insert_one(dict(doc))
    for pt in people:
        await add_activity(pt['user_id'], 'tag_request', u, 'tagged you in a post', doc['id'])
    return await post_out(doc, u['id'])


@app.post('/api/posts/{post_id}/tag/{decision}')
async def decide_tag(post_id: str, decision: str, u: dict = Depends(get_current_user)):
    """Tagged person approves or rejects being tagged. decision = approve | reject."""
    if decision not in ('approve', 'reject'):
        raise HTTPException(400, 'Invalid decision')
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    people = p.get('people_tags', []) or []
    mine = next((pt for pt in people if pt['user_id'] == u['id']), None)
    if not mine:
        raise HTTPException(403, 'You are not tagged in this post')
    if decision == 'reject':
        people = [pt for pt in people if pt['user_id'] != u['id']]  # remove the tag entirely
    else:
        for pt in people:
            if pt['user_id'] == u['id']:
                pt['status'] = 'approved'
    await db.posts.update_one({'id': post_id}, {'$set': {'people_tags': people}})
    return {'ok': True, 'decision': decision}

@app.delete('/api/posts/{post_id}')
async def delete_post(post_id: str, u: dict = Depends(get_current_user)):
    await db.posts.delete_one({'id': post_id, 'author_id': u['id']})
    await db.profiles.update_one({'id': u['id']}, {'$pull': {'pinned_post_ids': post_id}})
    return {'deleted': True}

class EditText(BaseModel):
    text: str

@app.put('/api/posts/{post_id}')
async def edit_post(post_id: str, body: EditText, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if p['author_id'] != u['id']:
        raise HTTPException(403, 'Not your post')
    text = (body.text or '').strip()
    if contains_banned(text):
        raise HTTPException(400, 'Your text contains a word that isn’t allowed here.')
    prev = {'text': p.get('text', ''), 'at': p.get('edited_at') or p.get('created_at')}
    await db.posts.update_one({'id': post_id}, {
        '$set': {'text': text, 'edited': True, 'edited_at': datetime.now(timezone.utc).isoformat()},
        '$push': {'edit_history': prev}})
    return await post_out(await db.posts.find_one({'id': post_id}), u['id'])


@app.get('/api/posts/{post_id}/history')
async def post_history(post_id: str, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if not await can_view(u['id'], p):
        raise HTTPException(403, 'No access')
    return {'current': {'text': p.get('text', ''), 'at': p.get('edited_at') or p.get('created_at')},
            'history': list(reversed(p.get('edit_history', [])))}


@app.post('/api/posts/{post_id}/pin')
async def pin_post(post_id: str, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if p['author_id'] != u['id']:
        raise HTTPException(403, 'You can only pin your own posts')
    prof = await db.profiles.find_one({'id': u['id']})
    pins = list((prof or {}).get('pinned_post_ids', []) or [])
    if post_id in pins:
        pins.remove(post_id)
        pinned = False
    else:
        max_pins = tier_limits(prof).get('pinned', 3)
        if len(pins) >= max_pins:
            raise HTTPException(400, f'You can pin up to {max_pins} posts on your plan — unpin one first.')
        pins.insert(0, post_id)
        pinned = True
    await db.profiles.update_one({'id': u['id']}, {'$set': {'pinned_post_ids': pins}})
    return {'ok': True, 'pinned': pinned, 'pinned_post_ids': pins}

@app.put('/api/wall/{wall_id}')
async def edit_wall(wall_id: str, body: EditText, u: dict = Depends(get_current_user)):
    w = await db.wall.find_one({'id': wall_id})
    if not w:
        raise HTTPException(404, 'Not found')
    if w['author_id'] != u['id']:
        raise HTTPException(403, 'Not your post')
    text = (body.text or '').strip()
    if not text:
        raise HTTPException(400, 'Empty')
    if contains_banned(text):
        raise HTTPException(400, 'Your message contains a word that isn’t allowed here.')
    prev = {'text': w.get('text', ''), 'at': w.get('edited_at') or w.get('created_at')}
    await db.wall.update_one({'id': wall_id}, {
        '$set': {'text': text, 'edited': True, 'edited_at': datetime.now(timezone.utc).isoformat()},
        '$push': {'edit_history': prev}})
    return {'ok': True, 'text': text, 'edited': True}


@app.get('/api/wall/{wall_id}/history')
async def wall_history(wall_id: str, u: dict = Depends(get_current_user)):
    w = await db.wall.find_one({'id': wall_id})
    if not w:
        raise HTTPException(404, 'Not found')
    return {'current': {'text': w.get('text', ''), 'at': w.get('edited_at') or w.get('created_at')},
            'history': list(reversed(w.get('edit_history', [])))}

@app.post('/api/posts/{post_id}/like')
async def like_post(post_id: str, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if p['tier'] != 'public':
        raise HTTPException(400, 'Only public posts can be liked')
    if not await can_view(u['id'], p):
        raise HTTPException(403, 'Cannot view')
    liked = u['id'] in p.get('likes', [])
    op = '$pull' if liked else '$addToSet'
    await db.posts.update_one({'id': post_id}, {op: {'likes': u['id']}})
    if not liked and p['author_id'] != u['id']:
        author = await db.profiles.find_one({'id': p['author_id']})
        await add_activity(p['author_id'], 'like', u, 'liked your post', post_id)
    p = await db.posts.find_one({'id': post_id})
    return {'liked': not liked, 'like_count': len(p.get('likes', []))}


@app.post('/api/posts/{post_id}/react')
async def react_post(post_id: str, body: ReactBody, u: dict = Depends(get_current_user)):
    if body.emoji not in REACTIONS:
        raise HTTPException(400, 'Invalid reaction')
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if not await can_view(u['id'], p):
        raise HTTPException(403, 'Cannot view')
    reactions = p.get('reactions', {}) or {}
    current = next((k for k, v in reactions.items() if u['id'] in v), None)
    # Clear any existing reaction from this user
    for k in list(reactions.keys()):
        if u['id'] in reactions[k]:
            reactions[k] = [x for x in reactions[k] if x != u['id']]
    toggled_off = current == body.emoji
    if not toggled_off:
        reactions.setdefault(body.emoji, [])
        reactions[body.emoji].append(u['id'])
        if p['author_id'] != u['id']:
            await add_activity(p['author_id'], 'react', u, f'reacted {body.emoji} to your post', post_id)
    await db.posts.update_one({'id': post_id}, {'$set': {'reactions': reactions}})
    counts = {k: len(v) for k, v in reactions.items() if v}
    return {'reactions': counts, 'reaction_total': sum(counts.values()),
            'my_reaction': None if toggled_off else body.emoji}


async def comment_out(c: dict, viewer_id: str) -> dict:
    a = await db.profiles.find_one({'id': c['author_id']}, {'_id': 0})
    return {'id': c['id'], 'post_id': c['post_id'], 'parent_id': c.get('parent_id'),
            'text': c['text'], 'created_at': c['created_at'],
            'is_mine': c['author_id'] == viewer_id,
            'author': {'id': a['id'], 'handle': a['handle'], 'display_name': a['display_name'],
                       'avatar_url': a.get('avatar_url')} if a else None}


@app.get('/api/posts/{post_id}/comments')
async def list_comments(post_id: str, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if not await can_view(u['id'], p):
        raise HTTPException(403, 'Cannot view')
    author_id = p['author_id']
    # Instagram-style Restrict: comments by users the post author restricted are
    # visible only to that commenter (and the post author, flagged as restricted).
    restricted_ids = set()
    async for r in db.relations.find({'user_id': author_id, 'kind': 'restrict'}):
        restricted_ids.add(r['target_id'])
    out = []
    async for c in db.comments.find({'post_id': post_id}).sort('created_at', 1).limit(500):
        cauthor = c['author_id']
        is_restricted = cauthor in restricted_ids
        if is_restricted and u['id'] != cauthor and u['id'] != author_id:
            continue  # hidden from everyone else
        co = await comment_out(c, u['id'])
        if is_restricted:
            co['restricted'] = True
        out.append(co)
    return out


@app.post('/api/posts/{post_id}/comments')
async def add_comment(post_id: str, body: CommentCreate, u: dict = Depends(get_current_user)):
    p = await db.posts.find_one({'id': post_id})
    if not p:
        raise HTTPException(404, 'Post not found')
    if not await can_view(u['id'], p):
        raise HTTPException(403, 'Cannot view')
    text = (body.text or '').strip()
    if not text:
        raise HTTPException(400, 'Empty comment')
    if body.parent_id and not await db.comments.find_one({'id': body.parent_id, 'post_id': post_id}):
        raise HTTPException(400, 'Parent comment not found')
    doc = {'id': str(uuid.uuid4()), 'post_id': post_id, 'author_id': u['id'],
           'text': text[:2000], 'parent_id': body.parent_id,
           'created_at': datetime.now(timezone.utc).isoformat()}
    await db.comments.insert_one(dict(doc))
    if p['author_id'] != u['id']:
        await add_activity(p['author_id'], 'comment', u, 'commented on your post', post_id)
    return await comment_out(doc, u['id'])


@app.delete('/api/comments/{comment_id}')
async def delete_comment(comment_id: str, u: dict = Depends(get_current_user)):
    c = await db.comments.find_one({'id': comment_id})
    if not c:
        raise HTTPException(404, 'Comment not found')
    p = await db.posts.find_one({'id': c['post_id']})
    is_owner = c['author_id'] == u['id'] or (p and p['author_id'] == u['id']) or is_admin_user(u)
    if not is_owner:
        raise HTTPException(403, 'Not allowed')
    # delete the comment and any direct replies
    await db.comments.delete_many({'$or': [{'id': comment_id}, {'parent_id': comment_id}]})
    return {'ok': True}


@app.delete('/api/dms/{handle}/{message_id}')
async def delete_dm(handle: str, message_id: str, u: dict = Depends(get_current_user)):
    m = await db.dms.find_one({'id': message_id})
    if not m:
        raise HTTPException(404, 'Message not found')
    if m['sender_id'] != u['id']:
        raise HTTPException(403, 'You can only delete your own messages')
    await db.dms.update_one({'id': message_id}, {'$set': {'deleted': True}})
    await manager.broadcast(m['room'], {'type': 'dm_deleted', 'id': message_id})
    return {'ok': True}

@app.get('/api/trending')
async def trending(u: dict = Depends(get_current_user)):
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    counts: dict[str, int] = {}
    async for p in db.posts.find({'tier': 'public', 'created_at': {'$gte': since}}):
        for t in p.get('tags', []):
            counts[t] = counts.get(t, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:10]
    return [{'tag': t, 'count': c} for t, c in top]

@app.get('/api/search')
async def search(q: str = '', u: dict = Depends(get_current_user)):
    q = q.strip().lstrip('#').lower()
    users, posts = [], []
    if q:
        async for p in db.profiles.find({'$or': [
            {'handle': {'$regex': q, '$options': 'i'}},
            {'display_name': {'$regex': q, '$options': 'i'}}]}).limit(20):
            if p['id'] != u['id'] and await is_blocked_between(u['id'], p['id']):
                continue  # hide blocked users from search
            if p['id'] != u['id'] and await adult_minor_barrier(u['id'], p['id']):
                continue  # child-safety: minors invisible to adults & vice-versa
            users.append(await public_profile(await db.profiles.find_one({'id': p['id']}, {'_id': 0}), u['id']))
            if len(users) >= 15:
                break
        async for p in db.posts.find({'tier': 'public', 'tags': q}).sort('created_at', -1).limit(40):
            if p['author_id'] != u['id'] and await is_blocked_between(u['id'], p['author_id']):
                continue
            posts.append(await post_out(p, u['id']))
            if len(posts) >= 30:
                break
    return {'users': users, 'posts': posts}


# ----------------------------- DMs (encrypted) -----------------------------

@app.get('/api/dms')
async def dm_threads(u: dict = Depends(get_current_user)):
    seen = {}
    async for m in db.dms.find({'participants': u['id']}).sort('created_at', -1).limit(400):
        other = [p for p in m['participants'] if p != u['id']]
        oid = other[0] if other else u['id']
        if oid in seen:
            continue
        prof = await db.profiles.find_one({'id': oid}, {'_id': 0})
        if not prof:
            continue
        room = dm_room(u['id'], oid)
        since = await read_marker('dm', room, u['id'])
        seen[oid] = {'user': {'id': prof['id'], 'handle': prof['handle'],
                              'display_name': prof['display_name'], 'avatar_url': prof.get('avatar_url'), 'role': effective_role(prof), 'account_type': acct_type(prof), 'nickname': await nickname_for(u['id'], prof['id'])},
                     'last': ('🎤 Voice message' if m.get('media_type') == 'audio' else '📷 Photo' if m.get('media_url') else dec(m['content_enc'])[:80]), 'created_at': m['created_at'],
                     'mine': m['sender_id'] == u['id'],
                     'unread': await dm_unread_count(room, u['id'], since)}
    return list(seen.values())

@app.get('/api/dms/{handle}')
async def dm_history(handle: str, u: dict = Depends(get_current_user)):
    other = await db.profiles.find_one({'handle': handle})
    if not other:
        raise HTTPException(404, 'User not found')
    room = dm_room(u['id'], other['id'])
    out = []
    async for m in db.dms.find({'room': room}).sort('created_at', 1).limit(300):
        # Silently hide messages that were deleted or one-time media that's already been viewed.
        if m.get('deleted') or (m.get('view_once') and m.get('view_once_viewed')):
            continue
        mine = m['sender_id'] == u['id']
        vo = bool(m.get('view_once'))
        media_url = None if vo else m.get('media_url')
        out.append({'id': m['id'], 'sender_id': m['sender_id'],
                    'text': dec(m['content_enc']),
                    'media_url': media_url,
                    'media_type': m.get('media_type'), 'duration': m.get('duration'),
                    'view_once': vo, 'view_once_viewed': False,
                    'allow_save': m.get('allow_save', True),
                    'pinned': bool(m.get('pinned')), 'deleted': False,
                    'created_at': m['created_at'], 'mine': mine})
    await mark_read('dm', room, u['id'])  # opening a thread marks it read
    is_self = other['id'] == u['id']
    return {'peer': {'id': other['id'], 'handle': other['handle'],
                     'display_name': other['display_name'], 'avatar_url': other.get('avatar_url'), 'role': effective_role(other), 'account_type': acct_type(other), 'nickname': await nickname_for(u['id'], other['id'])},
            'can_dm': await can_dm(u['id'], other['id']),
            'peer_is_inner': await in_inner(u['id'], other['id']),
            'can_voice': is_self or await inner_perm(other['id'], u['id'], 'voice'),
            'can_call': is_self or await inner_perm(other['id'], u['id'], 'call'),
            'messages': out}

@app.post('/api/dms/{handle}')
async def dm_send(handle: str, body: DMSend, u: dict = Depends(get_current_user)):
    other = await db.profiles.find_one({'handle': handle})
    if not other:
        raise HTTPException(404, 'User not found')
    if not await can_dm(u['id'], other['id']):
        raise HTTPException(403, 'DMs not allowed with this user (tier-gated)')
    if (body.media_type == 'audio') and not await inner_perm(other['id'], u['id'], 'voice'):
        raise HTTPException(403, 'This person has turned off voice notes from you')
    text = (body.text or '').strip()
    if not text and not body.media_url:
        raise HTTPException(400, 'Empty message')
    view_once = bool(body.view_once) and bool(body.media_url)  # only meaningful with media
    allow_save = bool(body.allow_save) and not view_once  # view-once media is never savable
    room = dm_room(u['id'], other['id'])
    doc = {'id': str(uuid.uuid4()), 'room': room, 'participants': [u['id'], other['id']],
           'sender_id': u['id'], 'content_enc': enc(text),
           'media_url': body.media_url, 'media_type': body.media_type, 'duration': body.duration,
           'view_once': view_once, 'view_once_viewed': False, 'allow_save': allow_save,
           'pinned': False, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.dms.insert_one(dict(doc))
    # In WS + response, disappearing media never carries the URL — the recipient fetches it once via /view.
    wire_media = None if view_once else body.media_url
    msg = {'id': doc['id'], 'sender_id': u['id'], 'text': text, 'media_url': wire_media,
           'media_type': body.media_type, 'duration': body.duration,
           'view_once': view_once, 'view_once_viewed': False, 'allow_save': allow_save, 'created_at': doc['created_at']}
    await manager.broadcast(room, {'type': 'dm', 'message': msg})
    if other['id'] != u['id']:
        preview = '🎤 Voice message' if body.media_type == 'audio' else ('📷 Photo' if body.media_url else (text or '')[:100])
        await push_to_user(other['id'], f"#{u['handle']}", preview, {'url': f"/messages/{u['handle']}"})
    return {**msg, 'mine': True, 'pinned': False}


@app.post('/api/dms/{handle}/{message_id}/view')
async def view_once_dm(handle: str, message_id: str, u: dict = Depends(get_current_user)):
    """Consume a disappearing (view-once) media message. Returns the media URL a single
    time to the RECIPIENT, then marks it viewed and wipes the stored URL so it can never
    be fetched again. The sender cannot re-open their own view-once media."""
    m = await db.dms.find_one({'id': message_id})
    if not m:
        raise HTTPException(404, 'Message not found')
    if u['id'] not in m.get('participants', []):
        raise HTTPException(403, 'Not allowed')
    if not m.get('view_once'):
        raise HTTPException(400, 'Not a view-once message')
    if m['sender_id'] == u['id']:
        raise HTTPException(403, "You can't reopen media you sent")
    if m.get('view_once_viewed') or not m.get('media_url'):
        raise HTTPException(410, 'This media has already been viewed')
    url = m['media_url']
    now = datetime.now(timezone.utc).isoformat()
    # Mark viewed and wipe the URL from storage (true disappearing).
    await db.dms.update_one({'id': message_id},
                            {'$set': {'view_once_viewed': True, 'view_once_viewed_at': now, 'media_url': None}})
    await manager.broadcast(m['room'], {'type': 'dm_viewed', 'id': message_id})
    return {'media_url': url, 'media_type': m.get('media_type')}


@app.post('/api/dms/{handle}/{message_id}/pin')
async def pin_dm(handle: str, message_id: str, u: dict = Depends(get_current_user)):
    m = await db.dms.find_one({'id': message_id})
    if not m:
        raise HTTPException(404, 'Message not found')
    if u['id'] not in m['participants']:
        raise HTTPException(403, 'Not allowed')
    newp = not m.get('pinned')
    await db.dms.update_one({'id': message_id}, {'$set': {'pinned': newp}})
    await manager.broadcast(m['room'], {'type': 'dm_pin', 'id': message_id, 'pinned': newp})
    return {'ok': True, 'pinned': newp}


# ----------------------------- Unread counts (DMs + groups) -----------------------------

@app.get('/api/unread')
async def unread(u: dict = Depends(get_current_user)):
    dm_total, seen = 0, set()
    async for m in db.dms.find({'participants': u['id']}).sort('created_at', -1).limit(400):
        other = [p for p in m['participants'] if p != u['id']]
        oid = other[0] if other else u['id']
        if oid in seen:
            continue
        seen.add(oid)
        room = dm_room(u['id'], oid)
        since = await read_marker('dm', room, u['id'])
        dm_total += await dm_unread_count(room, u['id'], since)
    grp_total = 0
    async for g in db.groups.find({'members': u['id']}):
        since = await read_marker('group', g['id'], u['id'])
        q = {'group_id': g['id'], 'sender_id': {'$ne': u['id']}}
        if since:
            q['created_at'] = {'$gt': since}
        grp_total += await db.group_messages.count_documents(q)
    return {'dms': dm_total, 'groups': grp_total, 'total': dm_total + grp_total}


# ----------------------------- Inner-Circle Groups (encrypted group chat) -----------------------------

GROUP_MAX = 15

class GroupCreate(BaseModel):
    name: str
    members: Optional[list] = None  # list of handles (must be in owner's Inner Circle)

class GroupRename(BaseModel):
    name: str

class GroupMembers(BaseModel):
    handles: list

class GroupMessage(BaseModel):
    text: Optional[str] = ''
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    duration: Optional[float] = None


async def _members_slim(ids: list) -> list:
    out = []
    for mid in ids:
        p = await db.profiles.find_one({'id': mid}, {'_id': 0})
        if p:
            out.append(await relation_slim(p))
    return out


async def group_out(g: dict, uid: str) -> dict:
    since = await read_marker('group', g['id'], uid)
    cq = {'group_id': g['id'], 'sender_id': {'$ne': uid}}
    if since:
        cq['created_at'] = {'$gt': since}
    unread = await db.group_messages.count_documents(cq)
    last_text, last_at = '', g['created_at']
    async for m in db.group_messages.find({'group_id': g['id']}).sort('created_at', -1).limit(1):
        last_at = m['created_at']
        last_text = ('🎤 Voice message' if m.get('media_type') == 'audio'
                     else '📷 Photo' if m.get('media_url') else dec(m['content_enc'])[:80])
    return {'id': g['id'], 'name': g['name'], 'owner_id': g['owner_id'],
            'is_owner': g['owner_id'] == uid, 'member_count': len(g['members']),
            'members': await _members_slim(g['members']),
            'last': last_text, 'last_at': last_at, 'unread': unread}


@app.post('/api/groups')
async def create_group(body: GroupCreate, u: dict = Depends(get_current_user)):
    name = (body.name or '').strip()[:60]
    if not name:
        raise HTTPException(400, 'Group needs a name')
    member_ids = [u['id']]
    for h in (body.members or []):
        p = await db.profiles.find_one({'handle': h})
        if not p or p['id'] == u['id']:
            continue
        if not await in_inner(u['id'], p['id']):
            raise HTTPException(400, f'#{h} must be in your Inner Circle to add to a group')
        if p['id'] not in member_ids:
            member_ids.append(p['id'])
    if len(member_ids) > GROUP_MAX:
        raise HTTPException(400, f'Groups are capped at {GROUP_MAX} members')
    doc = {'id': str(uuid.uuid4()), 'name': name, 'owner_id': u['id'],
           'members': member_ids, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.groups.insert_one(dict(doc))
    return await group_out(doc, u['id'])


@app.get('/api/groups')
async def my_groups(u: dict = Depends(get_current_user)):
    out = []
    async for g in db.groups.find({'members': u['id']}):
        out.append(await group_out(g, u['id']))
    out.sort(key=lambda x: x['last_at'], reverse=True)
    return out


@app.get('/api/groups/{gid}')
async def group_detail(gid: str, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    if u['id'] not in g['members']:
        raise HTTPException(403, 'You are not a member of this group')
    msgs = []
    async for m in db.group_messages.find({'group_id': gid}).sort('created_at', 1).limit(300):
        deleted = bool(m.get('deleted'))
        s = await db.profiles.find_one({'id': m['sender_id']}, {'_id': 0})
        msgs.append({'id': m['id'], 'sender_id': m['sender_id'],
                     'sender': {'id': s['id'], 'handle': s['handle'], 'display_name': s['display_name'],
                                'avatar_url': s.get('avatar_url')} if s else None,
                     'text': 'This message was deleted' if deleted else dec(m['content_enc']),
                     'media_url': None if deleted else m.get('media_url'),
                     'media_type': m.get('media_type'), 'duration': m.get('duration'),
                     'deleted': deleted, 'created_at': m['created_at'],
                     'mine': m['sender_id'] == u['id']})
    await mark_read('group', gid, u['id'])
    base = await group_out(g, u['id'])
    base['messages'] = msgs
    # Read receipts: last_read time per member (computed BEFORE this viewer's open is
    # persisted above only for others; the frontend uses this to show "Seen by…").
    reads = {}
    for mid in g['members']:
        reads[mid] = await read_marker('group', gid, mid)
    base['reads'] = reads
    return base


@app.post('/api/groups/{gid}/messages')
async def group_send(gid: str, body: GroupMessage, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    if u['id'] not in g['members']:
        raise HTTPException(403, 'You are not a member of this group')
    text = (body.text or '').strip()
    if not text and not body.media_url:
        raise HTTPException(400, 'Empty message')
    doc = {'id': str(uuid.uuid4()), 'group_id': gid, 'sender_id': u['id'],
           'content_enc': enc(text), 'media_url': body.media_url, 'media_type': body.media_type,
           'duration': body.duration, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.group_messages.insert_one(dict(doc))
    s = await db.profiles.find_one({'id': u['id']}, {'_id': 0})
    msg = {'id': doc['id'], 'sender_id': u['id'],
           'sender': {'id': s['id'], 'handle': s['handle'], 'display_name': s['display_name'],
                      'avatar_url': s.get('avatar_url')},
           'text': text, 'media_url': body.media_url, 'media_type': body.media_type,
           'duration': body.duration, 'created_at': doc['created_at']}
    await manager.broadcast('group:' + gid, {'type': 'group', 'message': msg})
    return {**msg, 'mine': True}


@app.put('/api/groups/{gid}')
async def rename_group(gid: str, body: GroupRename, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    if g['owner_id'] != u['id']:
        raise HTTPException(403, 'Only the group owner can rename it')
    name = (body.name or '').strip()[:60]
    if not name:
        raise HTTPException(400, 'Group needs a name')
    await db.groups.update_one({'id': gid}, {'$set': {'name': name}})
    return {'ok': True, 'name': name}


@app.post('/api/groups/{gid}/members')
async def add_group_members(gid: str, body: GroupMembers, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    if g['owner_id'] != u['id']:
        raise HTTPException(403, 'Only the group owner can add members')
    members = list(g['members'])
    for h in (body.handles or []):
        p = await db.profiles.find_one({'handle': h})
        if not p or p['id'] in members:
            continue
        if not await in_inner(u['id'], p['id']):
            raise HTTPException(400, f'#{h} must be in your Inner Circle to add')
        members.append(p['id'])
    if len(members) > GROUP_MAX:
        raise HTTPException(400, f'Groups are capped at {GROUP_MAX} members')
    await db.groups.update_one({'id': gid}, {'$set': {'members': members}})
    g['members'] = members
    return await group_out(g, u['id'])


@app.delete('/api/groups/{gid}/members/{handle}')
async def remove_group_member(gid: str, handle: str, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    target = await db.profiles.find_one({'handle': handle})
    if not target:
        raise HTTPException(404, 'User not found')
    tid = target['id']
    is_self_leave = tid == u['id']
    if not is_self_leave and g['owner_id'] != u['id']:
        raise HTTPException(403, 'Only the owner can remove other members')
    members = [m for m in g['members'] if m != tid]
    if not members:
        await db.groups.delete_one({'id': gid})
        await db.group_messages.delete_many({'group_id': gid})
        return {'ok': True, 'deleted': True}
    upd = {'members': members}
    if g['owner_id'] == tid:  # owner left -> hand ownership to first remaining member
        upd['owner_id'] = members[0]
    await db.groups.update_one({'id': gid}, {'$set': upd})
    return {'ok': True, 'deleted': False}


@app.delete('/api/groups/{gid}')
async def delete_group(gid: str, u: dict = Depends(get_current_user)):
    g = await db.groups.find_one({'id': gid})
    if not g:
        raise HTTPException(404, 'Group not found')
    if g['owner_id'] != u['id']:
        raise HTTPException(403, 'Only the group owner can delete it')
    await db.groups.delete_one({'id': gid})
    await db.group_messages.delete_many({'group_id': gid})
    return {'ok': True}


GIPHY_API_KEY = os.environ.get('GIPHY_API_KEY', '')


@app.get('/api/giphy/search')
async def giphy_search(q: str = '', limit: int = 24, u: dict = Depends(get_current_user)):
    if not GIPHY_API_KEY:
        raise HTTPException(503, 'GIF search is not configured')
    base = 'https://api.giphy.com/v1/gifs/'
    url = base + ('search' if q.strip() else 'trending')
    params = {'api_key': GIPHY_API_KEY, 'limit': min(int(limit), 50), 'rating': 'pg-13'}
    if q.strip():
        params['q'] = q.strip()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json().get('data', [])
    except Exception:
        raise HTTPException(502, 'GIF search failed')
    out = []
    for g in data:
        imgs = g.get('images', {})
        fh = imgs.get('fixed_height', {})
        if fh.get('url'):
            out.append({'id': g.get('id'), 'url': fh['url'],
                        'preview': imgs.get('fixed_height_small', {}).get('url', fh['url'])})
    return out


# ----------------------------- Activity -----------------------------

@app.get('/api/activity')
async def activity(u: dict = Depends(get_current_user)):
    prefs = {**NOTIF_DEFAULTS, **(u.get('notif_prefs') or {})}
    # Actors I've blocked (either direction) or restricted are silenced.
    silenced = set()
    async for r in db.relations.find({'user_id': u['id'], 'kind': {'$in': ['block', 'restrict']}}):
        silenced.add(r['target_id'])
    async for r in db.relations.find({'target_id': u['id'], 'kind': 'block'}):
        silenced.add(r['user_id'])
    out = []
    async for a in db.activity.find({'user_id': u['id']}, {'_id': 0}).sort('created_at', -1).limit(120):
        if a.get('actor_id') in silenced:
            continue
        key = ACTIVITY_TYPE_TO_NOTIF.get(a.get('type'))
        if key and not prefs.get(key, True):
            continue  # user turned this notification type off
        out.append(a)
        if len(out) >= 50:
            break
    return out

@app.delete('/api/activity/{activity_id}')
async def delete_activity(activity_id: str, u: dict = Depends(get_current_user)):
    """Delete a single activity/notification (only the owner's own item)."""
    res = await db.activity.delete_one({'id': activity_id, 'user_id': u['id']})
    if res.deleted_count == 0:
        raise HTTPException(404, 'Activity not found')
    return {'ok': True}

@app.delete('/api/activity')
async def clear_activity(u: dict = Depends(get_current_user)):
    """Clear all of the current user's activity/notifications."""
    res = await db.activity.delete_many({'user_id': u['id']})
    return {'ok': True, 'deleted': res.deleted_count}

@app.get('/api/follow-requests')
async def follow_requests(u: dict = Depends(get_current_user)):
    out = []
    async for f in db.follows.find({'target_id': u['id'], 'status': 'pending'}):
        p = await db.profiles.find_one({'id': f['follower_id']}, {'_id': 0})
        if p: out.append({'handle': p['handle'], 'display_name': p['display_name'], 'avatar_url': p.get('avatar_url')})
    return out


# ----------------------------- Storage -----------------------------

@app.post('/api/upload')
async def upload(u: dict = Depends(get_current_user), file: UploadFile = File(...)):
    data = await file.read()
    kind = media_kind(file.content_type or '')
    limit = tier_limits(u).get(kind, 50 * MB)
    if len(data) > limit:
        mb = limit // MB
        tier = acct_type(u)
        raise HTTPException(413, f'File too large for your {tier} plan ({kind} limit {mb}MB). Upgrade for larger uploads.')
    ext = (file.filename or 'file').split('.')[-1][:8]
    path = f"{u['id']}/{uuid.uuid4().hex}.{ext}"
    ctype = file.content_type or 'application/octet-stream'
    url = await upload_and_sign(path, data, ctype)
    # NSFW scan (images only). If flagged, queue for admin review; report to uploader.
    verdict = await moderate_image(data, ctype)
    if verdict and not verdict['safe']:
        await db.nsfw_queue.insert_one({
            'id': str(uuid.uuid4()), 'user_id': u['id'], 'handle': u['handle'],
            'path': path, 'signed_url': url, 'verdict': verdict, 'status': 'open',
            'created_at': datetime.now(timezone.utc).isoformat()})
    return {'path': path, 'signed_url': url,
            'media_type': ctype.split('/')[0],
            'nsfw': (verdict and not verdict['safe']) or False,
            'nsfw_reason': verdict['reason'] if (verdict and not verdict['safe']) else None}


# ----------------------------- LiveKit -----------------------------

@app.post('/api/livekit/token')
async def livekit_token(body: TokenReq, u: dict = Depends(get_current_user)):
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(500, 'LiveKit not configured')
    # Enforce call permission / safety barriers when a specific peer is being called.
    if body.peer:
        other = await db.profiles.find_one({'handle': body.peer})
        if other and other['id'] != u['id']:
            if await is_blocked_between(u['id'], other['id']):
                raise HTTPException(403, 'Call not available with this user')
            if await adult_minor_barrier(u['id'], other['id']):
                raise HTTPException(403, 'Call not available with this user')
            if not await inner_perm(other['id'], u['id'], 'call'):
                raise HTTPException(403, 'This person has turned off calls from you')
    room = re.sub(r'[^A-Za-z0-9_:-]', '', body.room)[:128] or f"room-{u['id']}"
    token = (lk_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
             .with_identity(u['id']).with_name(f"#{u['handle']}")
             .with_ttl(timedelta(minutes=15))
             .with_grants(lk_api.VideoGrants(room_join=True, room=room,
                                             can_publish=True, can_subscribe=True)))
    return {'server_url': LIVEKIT_URL, 'participant_token': token.to_jwt(), 'room': room}


# ----------------------------- Call signaling (ringing) -----------------------------

class CallSignal(BaseModel):
    peer: str                       # handle of the other party
    room: str                       # shared LiveKit room name
    media: Optional[str] = 'video'  # 'audio' | 'video'


@app.post('/api/call/ring')
async def call_ring(body: CallSignal, u: dict = Depends(get_current_user)):
    """Ring a peer: notify their personal channel (and push) that a call is incoming.
    Enforces the same safety/permission barriers as the LiveKit token endpoint."""
    other = await db.profiles.find_one({'handle': body.peer})
    if not other:
        raise HTTPException(404, 'User not found')
    if other['id'] == u['id']:
        raise HTTPException(400, "You can't call yourself")
    if await is_blocked_between(u['id'], other['id']):
        raise HTTPException(403, 'Call not available with this user')
    if await adult_minor_barrier(u['id'], other['id']):
        raise HTTPException(403, 'Call not available with this user')
    if not await inner_perm(other['id'], u['id'], 'call'):
        raise HTTPException(403, 'This person has turned off calls from you')

    caller = await db.profiles.find_one({'id': u['id']}) or u
    media  = body.media or 'video'

    payload = {
        'type': 'incoming_call',
        'room': body.room,
        'media': media,
        'from': {
            'handle':       u['handle'],
            'display_name': caller.get('display_name') or u['handle'],
            'avatar_url':   caller.get('avatar_url'),
        },
    }
    await manager.broadcast('user:' + other['id'], payload)

    # Data-only, high-priority ring push so the native full-screen call
    # banner appears even when the app is force-killed.
    call_id = await push_call_ring_to_user(
        user_id       = other['id'],
        room          = body.room,
        media         = media,
        caller_handle = u['handle'],
        caller_name   = caller.get('display_name') or u['handle'],
        caller_avatar = caller.get('avatar_url'),
    )
    return {'ok': True, 'call_id': call_id}



@app.post('/api/call/cancel')
async def call_cancel(body: CallSignal, u: dict = Depends(get_current_user)):
    """Caller hangs up before the peer answers — stop the ring on their side."""
    other = await db.profiles.find_one({'handle': body.peer})
    if not other:
        raise HTTPException(404, 'User not found')
    await manager.broadcast('user:' + other['id'],
                            {'type': 'call_cancelled', 'room': body.room, 'from': u['handle']})
    return {'ok': True}


@app.post('/api/call/decline')
async def call_decline(body: CallSignal, u: dict = Depends(get_current_user)):
    """Peer declines — tell the caller so they can stop waiting."""
    other = await db.profiles.find_one({'handle': body.peer})
    if not other:
        raise HTTPException(404, 'User not found')
    evt = {'type': 'call_declined', 'room': body.room, 'from': u['handle']}
    await manager.broadcast('user:' + other['id'], evt)
    # Also hit the shared DM room so a caller with the chat open reacts immediately.
    await manager.broadcast(dm_room(u['id'], other['id']), evt)
    return {'ok': True}


@app.post('/api/call/accept')
async def call_accept(body: CallSignal, u: dict = Depends(get_current_user)):
    """Peer accepts — tell the caller so their UI can transition into the room."""
    other = await db.profiles.find_one({'handle': body.peer})
    if not other:
        raise HTTPException(404, 'User not found')
    await manager.broadcast('user:' + other['id'],
                            {'type': 'call_accepted', 'room': body.room, 'from': u['handle']})
    return {'ok': True}


# ----------------------------- Push notifications (FCM) -----------------------------

class PushRegister(BaseModel):
    token: str
    platform: Optional[str] = 'android'

_fcm_app = None
_fcm_ready = None  # None=unknown, True/False after first init attempt


def _init_fcm():
    """Lazily initialise firebase-admin from env. Returns True if send is available.
    Reads FIREBASE_CREDENTIALS_JSON (inline JSON) or GOOGLE_APPLICATION_CREDENTIALS (path).
    Fails open (returns False) if the package or credentials are missing."""
    global _fcm_app, _fcm_ready
    if _fcm_ready is not None:
        return _fcm_ready
    try:
        import json as _json
        import firebase_admin
        from firebase_admin import credentials as _creds
        inline = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if inline:
            cred = _creds.Certificate(_json.loads(inline))
        elif path and os.path.exists(path):
            cred = _creds.Certificate(path)
        else:
            _fcm_ready = False
            return False
        _fcm_app = firebase_admin.initialize_app(cred) if not firebase_admin._apps else firebase_admin.get_app()
        _fcm_ready = True
    except Exception as e:
        log.info(f'FCM not configured/available: {e}')
        _fcm_ready = False
    return _fcm_ready


async def push_to_user(user_id: str, title: str, body: str, data: Optional[dict] = None):
    """Best-effort push to all of a user's registered devices. No-op if FCM not configured."""
    if not _init_fcm():
        return
    try:
        from firebase_admin import messaging
        tokens = [d['token'] async for d in db.device_tokens.find({'user_id': user_id})]
        for tk in tokens:
            try:
                messaging.send(messaging.Message(
                    token=tk,
                    notification=messaging.Notification(title=title, body=body),
                    data={k: str(v) for k, v in (data or {}).items()},
                    android=messaging.AndroidConfig(priority='high')))
            except Exception as se:
                # Drop tokens FCM reports as unregistered so the table stays clean.
                if 'Unregistered' in type(se).__name__ or 'NotRegistered' in str(se):
                    await db.device_tokens.delete_one({'user_id': user_id, 'token': tk})
    except Exception as e:
        log.info(f'push_to_user failed: {e}')



async def push_call_ring_to_user(user_id: str,
                                 room: str,
                                 media: str,
                                 caller_handle: str,
                                 caller_name: str,
                                 caller_avatar: Optional[str]) -> Optional[str]:
    """Best-effort data-only high-priority ring push.

    Data-only messages are what let our own CallMessagingService run and
    render a phone-style, over-the-lockscreen full-screen incoming call
    notification even when the app has been force-killed. Notification
    messages (with a `notification` block) would just become a system-tray
    notification instead.
    """
    import uuid as _uuid_for_calls
    call_id = _uuid_for_calls.uuid4().hex
    if not _init_fcm():
        return call_id
    try:
        from firebase_admin import messaging
        tokens = [d['token'] async for d in db.device_tokens.find({'user_id': user_id})]
        data = {
            'type':        'incoming_call',
            'room':        room,
            'media':       media or 'video',
            'from_handle': caller_handle or '',
            'from_name':   caller_name or caller_handle or '',
            'from_avatar': caller_avatar or '',
            'call_id':     call_id,
        }
        for tk in tokens:
            try:
                messaging.send(messaging.Message(
                    token=tk,
                    data={k: str(v) for k, v in data.items()},
                    android=messaging.AndroidConfig(
                        priority='high',
                        ttl=45,
                        direct_boot_ok=True,
                    ),
                ))
            except Exception as se:
                if 'Unregistered' in type(se).__name__ or 'NotRegistered' in str(se):
                    await db.device_tokens.delete_one({'user_id': user_id, 'token': tk})
    except Exception as e:
        log.info(f'push_call_ring_to_user failed: {e}')
    return call_id


@app.post('/api/push/register')
async def push_register(body: PushRegister, u: dict = Depends(get_current_user)):
    tok = (body.token or '').strip()
    if not tok:
        raise HTTPException(400, 'Missing token')
    now = datetime.now(timezone.utc).isoformat()
    await db.device_tokens.update_one(
        {'user_id': u['id'], 'token': tok},
        {'$set': {'user_id': u['id'], 'token': tok, 'platform': body.platform or 'android', 'updated_at': now}},
        upsert=True)
    return {'ok': True}


@app.delete('/api/push/register/{token}')
async def push_unregister(token: str, u: dict = Depends(get_current_user)):
    await db.device_tokens.delete_one({'user_id': u['id'], 'token': token})
    return {'ok': True}



# ----------------------------- WebSocket (DM realtime) -----------------------------

@app.websocket('/api/ws/dm/{handle}')
async def ws_dm(ws: WebSocket, handle: str):
    token = ws.query_params.get('token')
    try:
        claims = decode_jwt(token) if token else None
        me_id = claims['sub']
    except Exception:
        await ws.close(code=1008); return
    other = await db.profiles.find_one({'handle': handle})
    if not other:
        await ws.close(code=1008); return
    room = dm_room(me_id, other['id'])
    await manager.connect(room, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(room, ws)
    except Exception:
        manager.disconnect(room, ws)


@app.websocket('/api/ws/group/{gid}')
async def ws_group(ws: WebSocket, gid: str):
    token = ws.query_params.get('token')
    try:
        claims = decode_jwt(token) if token else None
        me_id = claims['sub']
    except Exception:
        await ws.close(code=1008); return
    g = await db.groups.find_one({'id': gid})
    if not g or me_id not in g['members']:
        await ws.close(code=1008); return
    room = 'group:' + gid
    await manager.connect(room, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(room, ws)
    except Exception:
        manager.disconnect(room, ws)


@app.websocket('/api/ws/user')
async def ws_user(ws: WebSocket):
    """Personal per-user channel, connected app-wide while signed in.
    Used to deliver incoming-call rings and other user-scoped events."""
    token = ws.query_params.get('token')
    try:
        claims = decode_jwt(token) if token else None
        me_id = claims['sub']
    except Exception:
        await ws.close(code=1008); return
    room = 'user:' + me_id
    await manager.connect(room, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(room, ws)
    except Exception:
        manager.disconnect(room, ws)


# ----------------------------- Reporting & Admin -----------------------------

class ReportIn(BaseModel):
    target_type: str  # post | user | message
    target_id: str
    category: str
    note: Optional[str] = ''

class ActionIn(BaseModel):
    action: str  # dismiss | remove_content | warn_user | strike_user | uphold
    reason: Optional[str] = ''
    severe: Optional[bool] = False  # zero-tolerance (threats/violence/targeted harassment)

class StrikeIn(BaseModel):
    reason: str
    stage: Optional[str] = None  # soft | strike (auto-increments if 'strike')


async def require_admin(u: dict = Depends(get_current_user)) -> dict:
    if not is_admin_user(u):
        raise HTTPException(403, 'Admin access required')
    return u

async def require_mod(u: dict = Depends(get_current_user)) -> dict:
    """Content-moderation access: super_admin, co_admin OR moderator."""
    if is_admin_user(u) or effective_role(u) in MOD_ROLES:
        return u
    raise HTTPException(403, 'Moderator access required')


async def require_full_admin(u: dict = Depends(get_current_user)) -> dict:
    """Owner (super_admin) or Co-Admin only. Legacy is_admin accounts map to co_admin.
    Moderators and first_testers are explicitly excluded from this tier."""
    if effective_role(u) in FULL_ADMIN_ROLES:
        return u
    raise HTTPException(403, 'Owner or Co-Admin access required')


# --- In-memory fixed-window rate limiter (per key) ---
_RL_BUCKETS: dict[str, list] = {}

def _rate_limit(key: str, max_calls: int, window_s: int):
    now = time.time()
    q = _RL_BUCKETS.setdefault(key, [])
    cutoff = now - window_s
    while q and q[0] < cutoff:
        q.pop(0)
    if len(q) >= max_calls:
        raise HTTPException(429, 'Too many sensitive-access attempts. Please wait before trying again.')
    q.append(now)


def _verify_step_up(x_step_up: Optional[str]):
    """Validate the server-side step-up secret. Fail-closed: no configured hash => locked."""
    if not CSAM_STEPUP_SECRET_HASH:
        raise HTTPException(503, 'Sensitive-access step-up is not configured on this server.')
    provided = hashlib.sha256((x_step_up or '').encode()).hexdigest()
    if not x_step_up or not hmac.compare_digest(provided, CSAM_STEPUP_SECRET_HASH):
        raise HTTPException(403, 'Step-up verification failed. Provide the sensitive-access secret.')


async def sensitive_access_guard(u: dict = Depends(require_full_admin),
                                 x_step_up: Optional[str] = Header(None)) -> dict:
    """Gate for CSAM / DM-review / silent-investigation areas:
    owner+co-admin ONLY  +  server-side step-up secret  +  per-admin rate limit.
    Every downstream endpoint additionally writes an immutable audit entry."""
    _rate_limit(f'sensitive:{u["id"]}', max_calls=10, window_s=300)
    _verify_step_up(x_step_up)
    return u


async def audit(admin: dict, action: str, target: str, detail: str = ''):
    await db.audit.insert_one({
        'id': str(uuid.uuid4()), 'admin_handle': admin['handle'], 'admin_id': admin['id'],
        'action': action, 'target': target, 'detail': detail,
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

async def _resolve_target_user(target_type: str, target_id: str) -> Optional[dict]:
    if target_type == 'user':
        return await db.profiles.find_one({'$or': [{'id': target_id}, {'handle': target_id}]}, {'_id': 0})
    if target_type == 'post':
        p = await db.posts.find_one({'id': target_id})
        if p:
            return await db.profiles.find_one({'id': p['author_id']}, {'_id': 0})
    return None

async def apply_upheld(prof: dict, category: str, admin: dict, reason: str = '', severe: bool = False):
    """Increment a user's upheld-report count and auto-apply the Creator Support ladder:
       1 reminder · 3 Creator-Safety flag · 5 = 7-day suspension + rules re-accept ·
       7 = 30-day suspension + final warning · 10 = permanent ban.
       Threats/violence/recurring targeted harassment (severe) OR csam/underage =
       automatic termination, no appeal."""
    now = datetime.now(timezone.utc)
    zero_tolerance = bool(severe) or category in ('csam', 'underage')
    count = prof.get('upheld_reports', 0) + 1
    upd = {'upheld_reports': count, 'last_upheld_at': now.isoformat(), 'last_reason': reason or category}

    if zero_tolerance:
        upd.update({'banned': True, 'no_appeal': True, 'termination_reason': reason or category})
        await db.profiles.update_one({'id': prof['id']}, {'$set': upd})
        await add_activity(prof['id'], 'strike', admin, 'Account terminated (zero-tolerance) — no appeal.')
        await audit(admin, 'terminate_no_appeal', prof['handle'], reason or category)
        return {'upheld_reports': count, 'stage': 'terminated_no_appeal', 'banned': True}

    stage = f'upheld_{count}'
    msg = None
    if count == 1:
        msg = 'Please be mindful of your conduct. Continued violations may result in restrictions.'
    elif count == 3:
        upd['creator_safety_flag'] = True
        msg = 'A Creator Safety flag has been added to your account due to a history of upheld reports.'
    elif count == 5:
        upd['suspended_until'] = (now + timedelta(days=7)).isoformat()
        upd['rules_reaccept_required'] = True
        msg = '7-day suspension. You must re-accept the rules to continue. Further violations carry harsher penalties.'
    elif count == 7:
        upd['suspended_until'] = (now + timedelta(days=30)).isoformat()
        upd['final_warning'] = True
        msg = '30-day suspension. This is your final warning.'
    elif count >= 10:
        upd['banned'] = True
        stage = 'upheld_permanent_ban'
        msg = 'Your account has been permanently banned after repeated upheld reports.'

    await db.profiles.update_one({'id': prof['id']}, {'$set': upd})
    await add_activity(prof['id'], 'strike', admin, msg or f'Upheld report #{count} recorded.')
    await audit(admin, stage, prof['handle'], reason or category)
    return {'upheld_reports': count, 'stage': stage, 'message': msg}


async def apply_strike(prof: dict, reason: str, admin: dict, soft: bool = False):
    now = datetime.now(timezone.utc)
    if soft:
        await add_activity(prof['id'], 'soft_warning', admin, f'Soft warning: {reason}')
        await audit(admin, 'soft_warning', prof['handle'], reason)
        return {'strikes': prof.get('strikes', 0), 'stage': 'soft_warning'}
    strikes = prof.get('strikes', 0) + 1
    upd = {'strikes': strikes, 'last_reason': reason}
    if strikes == 1:
        upd['suspended_until'] = (now + timedelta(hours=48)).isoformat(); stage = 'strike_1_48h'
    elif strikes == 2:
        upd['suspended_until'] = (now + timedelta(days=7)).isoformat(); stage = 'strike_2_7d'
    else:
        upd['banned'] = True; stage = 'strike_3_permanent'
    await db.profiles.update_one({'id': prof['id']}, {'$set': upd})
    await add_activity(prof['id'], 'strike', admin, f'{stage}: {reason}')
    await audit(admin, stage, prof['handle'], reason)
    return {'strikes': strikes, 'stage': stage}


@app.post('/api/report')
async def create_report(body: ReportIn, u: dict = Depends(get_current_user)):
    if body.category not in REPORT_CATEGORIES:
        raise HTTPException(400, 'Invalid category')
    doc = {
        'id': str(uuid.uuid4()), 'target_type': body.target_type, 'target_id': body.target_id,
        'category': body.category, 'note': (body.note or '')[:500],
        'reporter_id': u['id'], 'reporter_handle': u['handle'],
        'status': 'open', 'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.reports.insert_one(dict(doc))
    # CSAM / underage -> auto-quarantine content + separate queue (law-enforcement matter)
    if body.category in ('csam', 'underage'):
        await db.csam_reports.insert_one({**doc})
        if body.target_type == 'post':
            await db.posts.update_one({'id': body.target_id}, {'$set': {'quarantined': True}})
    return {'ok': True, 'id': doc['id']}


@app.get('/api/admin/stats')
async def admin_stats(a: dict = Depends(require_mod)):
    deleted = (await db.counters.find_one({'_id': 'deleted'}) or {}).get('n', 0)
    return {
        'users': await db.profiles.count_documents({}),
        'posts': await db.posts.count_documents({}),
        'open_reports': await db.reports.count_documents({'status': 'open'}),
        'csam_reports': await db.csam_reports.count_documents({}),
        'suspended': await db.profiles.count_documents({'suspended_until': {'$exists': True}}),
        'banned': await db.profiles.count_documents({'banned': True}),
        'flagged': await db.profiles.count_documents({'flagged': True}),
        'watchlisted': await db.profiles.count_documents({'watchlisted': True}),
        'nsfw_open': await db.nsfw_queue.count_documents({'status': 'open'}),
        'deleted': deleted,
    }


class PromoteBody(BaseModel):
    email: str


class PurgeBody(BaseModel):
    include_admin: bool = False


@app.post('/api/admin/promote')
async def admin_promote(body: PromoteBody, a: dict = Depends(require_admin)):
    """Promote a user (by email) to admin."""
    email = (body.email or '').strip().lower()
    if not email:
        raise HTTPException(400, 'Email required')
    prof = await db.profiles.find_one({'email': {'$regex': f'^{re.escape(email)}$', '$options': 'i'}}, {'_id': 0})
    if not prof:
        raise HTTPException(404, 'No account with that email')
    await db.profiles.update_one({'id': prof['id']}, {'$set': {'is_admin': True, 'role': 'admin'}})
    await audit(a, 'promote_admin', prof['handle'], email)
    return {'ok': True, 'promoted': prof['handle']}


@app.post('/api/admin/purge-demo')
async def admin_purge_demo(body: PurgeBody, a: dict = Depends(require_admin)):
    """Purge seeded demo accounts. Optionally include the seeded admin.
    Never deletes the admin performing the action."""
    targets = list(await db.profiles.find(
        {'handle': {'$in': ['alice', 'bob', 'teen']}}, {'_id': 0, 'id': 1, 'handle': 1}
    ).to_list(50))
    if body.include_admin:
        seeded = await db.profiles.find_one(
            {'$or': [{'handle': 'admin'}, {'email': 'admin@sandbox.skali'}]}, {'_id': 0, 'id': 1, 'handle': 1})
        if seeded:
            targets.append(seeded)
    purged = []
    for t in targets:
        if t['id'] == a['id']:
            continue  # never delete yourself
        await _purge_user(t['id'])
        purged.append(t['handle'])
    await incr_deleted(len(purged))
    await audit(a, 'purge_demo', ','.join(purged) or 'none', f'include_admin={body.include_admin}')
    return {'ok': True, 'purged': purged, 'count': len(purged)}


class AdminEmailBody(BaseModel):
    email: str


@app.get('/api/admin/admins')
async def admin_list_admins(a: dict = Depends(require_admin)):
    """List current admins + any allowlisted emails that don't yet have an account."""
    admins = await db.profiles.find(
        {'is_admin': True},
        {'_id': 0, 'id': 1, 'handle': 1, 'display_name': 1, 'email': 1, 'avatar_url': 1}
    ).to_list(500)
    for x in admins:
        x['super'] = (x.get('email') or '').lower() in ADMIN_EMAILS
    have = {(x.get('email') or '').lower() for x in admins}
    allow = [d['email'] async for d in db.admin_allow.find({}, {'_id': 0, 'email': 1})]
    pending = sorted(e for e in allow if e not in have)
    return {'admins': admins, 'pending': pending}


@app.post('/api/admin/admins')
async def admin_add_admin(body: AdminEmailBody, a: dict = Depends(require_admin)):
    """Add an email as admin. Promotes the account if it exists, otherwise
    allowlists the email so it becomes admin the moment they sign up."""
    email = (body.email or '').strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise HTTPException(400, 'Enter a valid email')
    await db.admin_allow.update_one({'email': email}, {'$set': {'email': email}}, upsert=True)
    prof = await db.profiles.find_one({'email': {'$regex': f'^{re.escape(email)}$', '$options': 'i'}}, {'_id': 0})
    promoted = False
    if prof:
        await db.profiles.update_one({'id': prof['id']}, {'$set': {'is_admin': True, 'role': 'admin'}})
        promoted = True
    await audit(a, 'add_admin', email, 'promoted existing account' if promoted else 'allowlisted (no account yet)')
    return {'ok': True, 'email': email, 'promoted': promoted}


@app.post('/api/admin/admins/remove')
async def admin_remove_admin(body: AdminEmailBody, a: dict = Depends(require_admin)):
    """Revoke admin from an email. Cannot remove env super-admins or yourself."""
    email = (body.email or '').strip().lower()
    if email in ADMIN_EMAILS:
        raise HTTPException(400, 'That is a protected super-admin and cannot be removed here')
    await db.admin_allow.delete_one({'email': email})
    prof = await db.profiles.find_one({'email': {'$regex': f'^{re.escape(email)}$', '$options': 'i'}}, {'_id': 0})
    if prof:
        if prof['id'] == a['id']:
            raise HTTPException(400, 'You cannot remove your own admin access')
        await db.profiles.update_one({'id': prof['id']}, {'$set': {'is_admin': False, 'role': 'user'}})
    await audit(a, 'remove_admin', email, '')
    return {'ok': True, 'email': email}


# ----------------------------- Staff role assignment -----------------------------

class RoleAssignBody(BaseModel):
    handle: str
    role: str

class RoleRemoveBody(BaseModel):
    handle: str


@app.get('/api/admin/roles')
async def admin_list_roles(a: dict = Depends(require_admin)):
    """List everyone who holds a staff role (super_admin / co_admin / moderator / first_tester)."""
    out = []
    async for p in db.profiles.find({}, {'_id': 0}):
        r = effective_role(p)
        if r:
            out.append({'id': p['id'], 'handle': p['handle'], 'display_name': p['display_name'],
                        'avatar_url': p.get('avatar_url'), 'email': p.get('email'), 'role': r,
                        'account_type': acct_type(p),
                        'protected': (p.get('email') or '').lower() in ADMIN_EMAILS})
    order = {'super_admin': 0, 'co_admin': 1, 'moderator': 2, 'first_tester': 3}
    out.sort(key=lambda x: order.get(x['role'], 9))
    return out


@app.post('/api/admin/roles/assign')
async def admin_assign_role(body: RoleAssignBody, a: dict = Depends(require_admin)):
    """Assign a staff role by @handle. Only super_admin may assign the co_admin role.
    super_admin itself is reserved for built-in owner emails and cannot be assigned here."""
    role = (body.role or '').strip()
    if role not in ROLES_ASSIGNABLE:
        raise HTTPException(400, 'Invalid role. Choose co_admin, moderator or first_tester')
    actor_role = effective_role(a)
    if role == 'co_admin' and actor_role != 'super_admin':
        raise HTTPException(403, 'Only a Super Admin can assign Co-Admins')
    handle = body.handle.strip().lstrip('#@')
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    if (prof.get('email') or '').lower() in ADMIN_EMAILS:
        raise HTTPException(400, 'That account is a protected Super Admin and cannot be changed')
    upd = {'role': role, 'account_type': 'verified', 'is_admin': role in FULL_ADMIN_ROLES}
    await db.profiles.update_one({'id': prof['id']}, {'$set': upd})
    await audit(a, 'assign_role', handle, f'role={role}')
    return {'ok': True, 'handle': handle, 'role': role}


@app.post('/api/admin/roles/remove')
async def admin_remove_role(body: RoleRemoveBody, a: dict = Depends(require_admin)):
    """Remove a staff role by @handle. Only super_admin may remove a Co-Admin.
    Protected built-in Super Admins cannot be demoted."""
    handle = body.handle.strip().lstrip('#@')
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    if (prof.get('email') or '').lower() in ADMIN_EMAILS:
        raise HTTPException(400, 'That account is a protected Super Admin and cannot be demoted')
    current = effective_role(prof)
    if current == 'co_admin' and effective_role(a) != 'super_admin':
        raise HTTPException(403, 'Only a Super Admin can remove a Co-Admin')
    if prof['id'] == a['id']:
        raise HTTPException(400, 'You cannot remove your own role')
    await db.profiles.update_one({'id': prof['id']},
                                 {'$set': {'role': 'user', 'is_admin': False, 'account_type': 'free'}})
    await audit(a, 'remove_role', handle, f'was={current}')
    return {'ok': True, 'handle': handle}


# ----------------------------- Account tier (free / premium / verified) -----------------------------

class AccountTypeBody(BaseModel):
    account_type: str


@app.post('/api/admin/users/{handle}/account-type')
async def admin_set_account_type(handle: str, body: AccountTypeBody, a: dict = Depends(require_admin)):
    """Manually set a user's account tier. Billing isn't wired yet, so the owner sets
    premium/verified by hand. Valid values: free, premium, verified."""
    t = (body.account_type or '').strip().lower()
    if t not in ACCOUNT_TYPES:
        raise HTTPException(400, 'Invalid account type (free, premium or verified)')
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']}, {'$set': {'account_type': t}})
    await audit(a, 'set_account_type', handle, f'account_type={t}')
    return {'ok': True, 'handle': handle, 'account_type': t}


# ----------------------------- Co-Admin DM access guard -----------------------------
# Co-Admins have full admin access EXCEPT viewing a Super Admin's DMs, which requires
# either the Super Admin's global toggle to be ON, or a one-time approved request.

class CoDmToggle(BaseModel):
    enabled: bool

class DmAccessRequest(BaseModel):
    handle: str  # the Super Admin whose DMs the Co-Admin wants to view


async def super_dm_access_ok(actor: dict, target: dict) -> bool:
    """Whether `actor` may view `target`'s DMs. Only relevant when target is a Super Admin
    and actor is a different, non-super staff member (i.e. a Co-Admin)."""
    if effective_role(target) != 'super_admin':
        return True                      # target isn't a super admin -> normal rules
    if target['id'] == actor['id']:
        return True                      # viewing your own
    if effective_role(actor) == 'super_admin':
        return True                      # super admins can view each other
    if target.get('allow_coadmin_dms'):
        return True                      # global toggle ON
    grant = await db.dm_access.find_one({
        'requester_id': actor['id'], 'target_id': target['id'],
        'status': 'approved', 'used': False})
    if grant:
        # one-time consume
        await db.dm_access.update_one({'id': grant['id']},
                                      {'$set': {'used': True, 'used_at': datetime.now(timezone.utc).isoformat()}})
        return True
    return False


@app.post('/api/admin/settings/coadmin-dms')
async def set_coadmin_dms(body: CoDmToggle, a: dict = Depends(require_admin)):
    """Super Admin toggles whether Co-Admins may view their DMs without asking each time."""
    if effective_role(a) != 'super_admin':
        raise HTTPException(403, 'Only a Super Admin can change this setting')
    await db.profiles.update_one({'id': a['id']}, {'$set': {'allow_coadmin_dms': bool(body.enabled)}})
    return {'ok': True, 'allow_coadmin_dms': bool(body.enabled)}


@app.post('/api/admin/dm-access/request')
async def dm_access_request(body: DmAccessRequest, a: dict = Depends(require_admin)):
    """A Co-Admin requests one-time permission to view a specific Super Admin's DMs."""
    if effective_role(a) == 'super_admin':
        raise HTTPException(400, 'Super Admins already have access')
    handle = body.handle.strip().lstrip('#@')
    target = await db.profiles.find_one({'handle': handle})
    if not target:
        raise HTTPException(404, 'User not found')
    if effective_role(target) != 'super_admin':
        raise HTTPException(400, 'DM-access requests are only needed for Super Admins')
    existing = await db.dm_access.find_one({'requester_id': a['id'], 'target_id': target['id'], 'status': 'pending'})
    if existing:
        return {'ok': True, 'status': 'pending', 'id': existing['id']}
    doc = {'id': str(uuid.uuid4()), 'requester_id': a['id'], 'requester_handle': a['handle'],
           'requester_name': a['display_name'], 'target_id': target['id'], 'target_handle': target['handle'],
           'status': 'pending', 'used': False, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.dm_access.insert_one(dict(doc))
    await add_activity(target['id'], 'dm_access_request', a, 'requested permission to view your DMs')
    await audit(a, 'dm_access_request', target['handle'], '')
    return {'ok': True, 'status': 'pending', 'id': doc['id']}


@app.get('/api/admin/dm-access')
async def dm_access_list(a: dict = Depends(require_admin)):
    """Super Admin: requests targeting me. Co-Admin: my own requests."""
    is_super = effective_role(a) == 'super_admin'
    q = {'target_id': a['id']} if is_super else {'requester_id': a['id']}
    out = []
    async for r in db.dm_access.find(q, {'_id': 0}).sort('created_at', -1).limit(100):
        out.append(r)
    return {'as_super': is_super, 'allow_coadmin_dms': bool(a.get('allow_coadmin_dms')), 'requests': out}


@app.post('/api/admin/dm-access/{req_id}/{decision}')
async def dm_access_decide(req_id: str, decision: str, a: dict = Depends(require_admin)):
    """Super Admin approves or denies a Co-Admin's DM-access request targeting them."""
    if decision not in ('approve', 'deny'):
        raise HTTPException(400, 'Invalid decision')
    r = await db.dm_access.find_one({'id': req_id})
    if not r:
        raise HTTPException(404, 'Request not found')
    if r['target_id'] != a['id']:
        raise HTTPException(403, 'Only the Super Admin who was asked can decide this request')
    new_status = 'approved' if decision == 'approve' else 'denied'
    await db.dm_access.update_one({'id': req_id}, {'$set': {'status': new_status, 'used': False,
                                                            'decided_at': datetime.now(timezone.utc).isoformat()}})
    requester = await db.profiles.find_one({'id': r['requester_id']})
    if requester:
        await add_activity(requester['id'], 'dm_access_decision', a,
                           f'{"approved" if decision == "approve" else "denied"} your DM-access request')
    await audit(a, f'dm_access_{new_status}', r.get('requester_handle', ''), '')
    return {'ok': True, 'status': new_status}



@app.get('/api/admin/reports')
async def admin_reports(status: str = 'open', a: dict = Depends(require_mod)):
    q = {} if status == 'all' else {'status': status}
    out = []
    async for r in db.reports.find(q, {'_id': 0}).sort('created_at', -1).limit(100):
        target_user = await _resolve_target_user(r['target_type'], r['target_id'])
        preview = None
        if r['target_type'] == 'post':
            p = await db.posts.find_one({'id': r['target_id']}, {'_id': 0})
            preview = {'text': (p.get('text') if p else '(deleted)'), 'media_url': p.get('media_url') if p else None,
                       'tier': p.get('tier') if p else None, 'quarantined': p.get('quarantined') if p else None}
        out.append({**r, 'target_user': {'handle': target_user['handle'], 'display_name': target_user['display_name']} if target_user else None,
                    'preview': preview})
    return out

@app.post('/api/admin/reports/{report_id}/action')
async def admin_action(report_id: str, body: ActionIn, a: dict = Depends(require_mod)):
    r = await db.reports.find_one({'id': report_id})
    if not r:
        raise HTTPException(404, 'Report not found')
    result = {'action': body.action}
    if body.action == 'dismiss':
        await db.reports.update_one({'id': report_id}, {'$set': {'status': 'dismissed'}})
        await audit(a, 'dismiss_report', report_id, body.reason or '')
    elif body.action == 'remove_content':
        if r['target_type'] == 'post':
            await db.posts.update_one({'id': r['target_id']}, {'$set': {'quarantined': True}})
        await db.reports.update_one({'id': report_id}, {'$set': {'status': 'actioned'}})
        await audit(a, 'remove_content', r['target_id'], body.reason or '')
    elif body.action in ('warn_user', 'strike_user'):
        prof = await _resolve_target_user(r['target_type'], r['target_id'])
        if not prof:
            raise HTTPException(404, 'Target user not found')
        result.update(await apply_strike(prof, body.reason or r['category'], a, soft=(body.action == 'warn_user')))
        await db.reports.update_one({'id': report_id}, {'$set': {'status': 'actioned'}})
    elif body.action == 'uphold':
        prof = await _resolve_target_user(r['target_type'], r['target_id'])
        if not prof:
            raise HTTPException(404, 'Target user not found')
        result.update(await apply_upheld(prof, r['category'], a, body.reason or r['category'], severe=bool(body.severe)))
        await db.reports.update_one({'id': report_id}, {'$set': {'status': 'upheld'}})
    else:
        raise HTTPException(400, 'Unknown action')
    return {'ok': True, **result}

@app.get('/api/admin/csam')
async def admin_csam(a: dict = Depends(sensitive_access_guard)):
    out = []
    async for r in db.csam_reports.find({}, {'_id': 0}).sort('created_at', -1).limit(100):
        out.append(r)
    await audit(a, 'csam_list_view', 'csam_queue', f'viewed {len(out)} report(s)')
    return out

@app.get('/api/admin/users')
async def admin_users(q: str = '', a: dict = Depends(require_mod)):
    query = {}
    if q:
        query = {'$or': [{'handle': {'$regex': q, '$options': 'i'}}, {'display_name': {'$regex': q, '$options': 'i'}}]}
    out = []
    async for p in db.profiles.find(query, {'_id': 0}).sort('created_at', -1).limit(100):
        out.append({'id': p['id'], 'handle': p['handle'], 'display_name': p['display_name'],
                    'email': p.get('email'), 'account_type': acct_type(p),
                    'strikes': p.get('strikes', 0), 'suspended_until': p.get('suspended_until'),
                    'upheld_reports': p.get('upheld_reports', 0), 'creator_safety_flag': p.get('creator_safety_flag', False),
                    'no_appeal': p.get('no_appeal', False), 'final_warning': p.get('final_warning', False),
                    'banned': p.get('banned', False), 'is_admin': is_admin_user(p),
                    'flagged': p.get('flagged', False), 'flag_reason': p.get('flag_reason'),
                    'watchlisted': p.get('watchlisted', False), 'watch_reason': p.get('watch_reason'),
                    'created_at': p.get('created_at')})
    return out

@app.post('/api/admin/users/{handle}/strike')
async def admin_strike(handle: str, body: StrikeIn, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle}, {'_id': 0})
    if not prof:
        raise HTTPException(404, 'User not found')
    return {'ok': True, **await apply_strike(prof, body.reason, a, soft=(body.stage == 'soft'))}

@app.post('/api/admin/users/{handle}/unsuspend')
async def admin_unsuspend(handle: str, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']}, {'$set': {'strikes': 0, 'banned': False},
                                                       '$unset': {'suspended_until': '', 'last_reason': ''}})
    await audit(a, 'unsuspend', handle, '')
    return {'ok': True}

@app.post('/api/admin/users/{handle}/clear-strikes')
async def admin_clear_strikes(handle: str, a: dict = Depends(require_admin)):
    """Rehabilitation / successful appeal: wipe strikes, upheld reports and safety flags.
    Intended for the '12 months of good behaviour' appeal. Super/Co-Admin only.
    Does NOT lift a zero-tolerance (no_appeal) termination."""
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    if prof.get('no_appeal'):
        raise HTTPException(403, 'This account was terminated under zero-tolerance and cannot be appealed.')
    await db.profiles.update_one({'id': prof['id']}, {
        '$set': {'strikes': 0, 'upheld_reports': 0, 'creator_safety_flag': False,
                 'final_warning': False, 'rules_reaccept_required': False, 'banned': False},
        '$unset': {'suspended_until': '', 'last_reason': ''}})
    await add_activity(prof['id'], 'strike', a, 'Your record has been cleared following review of good behaviour.')
    await audit(a, 'clear_strikes', handle, '')
    return {'ok': True}

@app.get('/api/admin/audit')
async def admin_audit(a: dict = Depends(require_admin)):
    out = []
    async for r in db.audit.find({}, {'_id': 0}).sort('created_at', -1).limit(100):
        out.append(r)
    return out


# ----------------------------- Admin: flag accounts & discreet DM review -----------------------------

class FlagIn(BaseModel):
    reason: Optional[str] = ''


@app.post('/api/admin/users/{handle}/flag')
async def admin_flag(handle: str, body: FlagIn, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']}, {'$set': {
        'flagged': True, 'flag_reason': (body.reason or 'suspicious activity')[:300],
        'flagged_by': a['handle'], 'flagged_at': datetime.now(timezone.utc).isoformat()}})
    await audit(a, 'flag_user', handle, body.reason or 'suspicious activity')
    return {'ok': True, 'flagged': True}


@app.post('/api/admin/users/{handle}/unflag')
async def admin_unflag(handle: str, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']},
                                 {'$set': {'flagged': False}, '$unset': {'flag_reason': '', 'flagged_by': '', 'flagged_at': ''}})
    await audit(a, 'unflag_user', handle, '')
    return {'ok': True, 'flagged': False}


@app.get('/api/admin/dms/{handle}')
async def admin_view_dms(handle: str, legal_basis: str = '', a: dict = Depends(sensitive_access_guard)):
    """Discreet DM review for accounts flagged as suspicious. Server holds the DM
    encryption key so messages are decrypted here for moderation. The reviewed user
    is NOT notified; every access is written to the admin audit log for accountability.
    Requires a stated legal basis + step-up secret (owner/co-admin only, rate-limited)."""
    legal_basis = (legal_basis or '').strip()
    if len(legal_basis) < 8:
        raise HTTPException(400, 'A legal basis (min 8 chars) is required to open this account\'s DMs.')
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    if not await super_dm_access_ok(a, prof):
        raise HTTPException(403, "This is a Super Admin's account. You need their permission to view these DMs — send a request from the DM Access tab.")
    if not prof.get('flagged'):
        raise HTTPException(403, 'Account must be flagged for suspicious activity before DMs can be reviewed')

    threads: dict[str, list] = {}
    async for m in db.dms.find({'participants': prof['id']}).sort('created_at', 1):
        peer = next((pid for pid in m['participants'] if pid != prof['id']), prof['id'])
        threads.setdefault(peer, []).append({
            'sender_id': m['sender_id'], 'text': dec(m['content_enc']),
            'created_at': m['created_at'], 'from_flagged': m['sender_id'] == prof['id']})

    out = []
    for peer_id, msgs in threads.items():
        peer = await db.profiles.find_one({'id': peer_id}, {'_id': 0})
        out.append({'peer': {'handle': peer['handle'], 'display_name': peer['display_name']} if peer else {'handle': 'unknown', 'display_name': 'Unknown'},
                    'messages': msgs})
    out.sort(key=lambda t: t['messages'][-1]['created_at'] if t['messages'] else '', reverse=True)

    await audit(a, 'view_dms', handle, f'legal_basis="{legal_basis[:200]}"; reviewed {len(out)} thread(s)')
    return {'user': {'handle': prof['handle'], 'display_name': prof['display_name'],
                     'flag_reason': prof.get('flag_reason'), 'flagged_by': prof.get('flagged_by')},
            'threads': out}


@app.get('/api/admin/investigate/{handle}')
async def admin_investigate(handle: str, legal_basis: str = '', a: dict = Depends(sensitive_access_guard)):
    """SILENT INVESTIGATION — lawful, warrant-based inspection of an account (UK IPA / court order).
    Returns the subject's posts (all tiers), private DMs (decrypted, incl. media) and group
    memberships WITHOUT notifying them. Permitted only when the account is on the Watchlist or
    Flagged (i.e. a documented basis exists). Requires a stated legal basis + step-up secret
    (owner/co-admin only, rate-limited). EVERY access is written to the immutable admin audit log."""
    legal_basis = (legal_basis or '').strip()
    if len(legal_basis) < 8:
        raise HTTPException(400, 'A legal basis (min 8 chars) is required to run a silent investigation.')
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    if not await super_dm_access_ok(a, prof):
        raise HTTPException(403, "This is a Super Admin's account. You need their permission to investigate — send a request from the DM Access tab.")
    if not (prof.get('flagged') or prof.get('watchlisted')):
        raise HTTPException(403, 'Subject must be Watchlisted or Flagged (documented basis) before a silent investigation can run')
    uid = prof['id']

    posts = []
    async for p in db.posts.find({'author_id': uid}).sort('created_at', -1).limit(500):
        posts.append({'id': p['id'], 'tier': p.get('tier'), 'text': p.get('text', ''),
                      'media_url': p.get('media_url'), 'media_type': p.get('media_type'),
                      'ai_label': p.get('ai_label', 'none'), 'created_at': p.get('created_at')})

    threads: dict[str, list] = {}
    async for m in db.dms.find({'participants': uid}).sort('created_at', 1):
        peer = next((pid for pid in m['participants'] if pid != uid), uid)
        threads.setdefault(peer, []).append({
            'sender_id': m['sender_id'], 'from_subject': m['sender_id'] == uid,
            'text': dec(m['content_enc']),
            'media_url': m.get('media_url'), 'media_type': m.get('media_type'),
            'view_once': bool(m.get('view_once')), 'deleted': bool(m.get('deleted')),
            'created_at': m['created_at']})
    dms = []
    for peer_id, msgs in threads.items():
        peer = await db.profiles.find_one({'id': peer_id}, {'_id': 0})
        dms.append({'peer': {'handle': peer['handle'], 'display_name': peer['display_name']} if peer else {'handle': 'unknown', 'display_name': 'Unknown'},
                    'messages': msgs})
    dms.sort(key=lambda t: t['messages'][-1]['created_at'] if t['messages'] else '', reverse=True)

    groups = []
    async for g in db.groups.find({'members': uid}):
        groups.append({'id': g.get('id'), 'name': g.get('name'),
                       'member_count': len(g.get('members', [])),
                       'is_owner': g.get('owner_id') == uid, 'created_at': g.get('created_at')})

    await audit(a, 'silent_investigation', handle,
                f'legal_basis="{legal_basis[:200]}"; inspected {len(posts)} posts, {len(dms)} DM thread(s), {len(groups)} group(s)')
    return {'subject': {'handle': prof['handle'], 'display_name': prof['display_name'],
                        'email': prof.get('email'), 'is_minor': bool(prof.get('is_minor')),
                        'flagged': bool(prof.get('flagged')), 'flag_reason': prof.get('flag_reason'),
                        'watchlisted': bool(prof.get('watchlisted')), 'watch_reason': prof.get('watch_reason')},
            'posts': posts, 'dms': dms, 'groups': groups,
            'legal_notice': 'Accessed under lawful basis. This access is recorded in the admin audit log.'}




# ----------------------------- Phase 6: Admin+ & Safety -----------------------------

class NoteIn(BaseModel):
    note: str

class WatchIn(BaseModel):
    reason: Optional[str] = ''

class NsfwResolve(BaseModel):
    action: str  # dismiss | remove


@app.get('/api/admin/nsfw')
async def admin_nsfw_queue(status: str = 'open', a: dict = Depends(require_mod)):
    """AI-flagged media awaiting review."""
    q = {} if status == 'all' else {'status': status}
    out = []
    async for r in db.nsfw_queue.find(q, {'_id': 0}).sort('created_at', -1).limit(200):
        out.append(r)
    return out


@app.post('/api/admin/nsfw/{item_id}/resolve')
async def admin_nsfw_resolve(item_id: str, body: NsfwResolve, a: dict = Depends(require_mod)):
    item = await db.nsfw_queue.find_one({'id': item_id})
    if not item:
        raise HTTPException(404, 'Item not found')
    action = (body.action or '').lower()
    if action not in ('dismiss', 'remove'):
        raise HTTPException(400, 'Invalid action')
    if action == 'remove':
        # Quarantine any posts that used this media URL.
        await db.posts.update_many({'media_url': item.get('signed_url')}, {'$set': {'quarantined': True}})
    await db.nsfw_queue.update_one({'id': item_id}, {'$set': {
        'status': 'removed' if action == 'remove' else 'dismissed',
        'resolved_by': a['handle'], 'resolved_at': datetime.now(timezone.utc).isoformat()}})
    await audit(a, f'nsfw_{action}', item.get('handle', ''), item.get('reason', ''))
    return {'ok': True, 'status': 'removed' if action == 'remove' else 'dismissed'}


@app.get('/api/admin/watchlist')
async def admin_watchlist(a: dict = Depends(require_mod)):
    out = []
    async for p in db.profiles.find({'watchlisted': True}, {'_id': 0}).sort('watched_at', -1).limit(200):
        out.append({'id': p['id'], 'handle': p['handle'], 'display_name': p['display_name'],
                    'avatar_url': p.get('avatar_url'), 'email': p.get('email'),
                    'watch_reason': p.get('watch_reason'), 'watched_by': p.get('watched_by'),
                    'watched_at': p.get('watched_at'), 'strikes': p.get('strikes', 0),
                    'flagged': p.get('flagged', False)})
    return out


@app.post('/api/admin/users/{handle}/watch')
async def admin_watch(handle: str, body: WatchIn, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']}, {'$set': {
        'watchlisted': True, 'watch_reason': (body.reason or 'under review')[:300],
        'watched_by': a['handle'], 'watched_at': datetime.now(timezone.utc).isoformat()}})
    await audit(a, 'watch_user', handle, body.reason or '')
    return {'ok': True, 'watchlisted': True}


@app.post('/api/admin/users/{handle}/unwatch')
async def admin_unwatch(handle: str, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    await db.profiles.update_one({'id': prof['id']},
                                 {'$set': {'watchlisted': False}, '$unset': {'watch_reason': '', 'watched_by': '', 'watched_at': ''}})
    await audit(a, 'unwatch_user', handle, '')
    return {'ok': True, 'watchlisted': False}


@app.get('/api/admin/users/{handle}/notes')
async def admin_get_notes(handle: str, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    out = []
    async for n in db.admin_notes.find({'user_id': prof['id']}, {'_id': 0}).sort('created_at', -1).limit(200):
        out.append(n)
    return out


@app.post('/api/admin/users/{handle}/note')
async def admin_add_note(handle: str, body: NoteIn, a: dict = Depends(require_mod)):
    prof = await db.profiles.find_one({'handle': handle})
    if not prof:
        raise HTTPException(404, 'User not found')
    note = (body.note or '').strip()
    if not note:
        raise HTTPException(400, 'Empty note')
    doc = {'id': str(uuid.uuid4()), 'user_id': prof['id'], 'handle': handle,
           'note': note[:2000], 'admin_handle': a['handle'],
           'created_at': datetime.now(timezone.utc).isoformat()}
    await db.admin_notes.insert_one(dict(doc))
    return {'id': doc['id'], 'note': doc['note'], 'admin_handle': doc['admin_handle'], 'created_at': doc['created_at']}


@app.post('/api/admin/csam/{report_id}/escalate')
async def admin_csam_escalate(report_id: str, a: dict = Depends(sensitive_access_guard)):
    """CEOP-style escalation: mark a CSAM report as escalated to authorities."""
    r = await db.csam_reports.find_one({'id': report_id})
    if not r:
        raise HTTPException(404, 'Report not found')
    await db.csam_reports.update_one({'id': report_id}, {'$set': {
        'escalated': True, 'ceop_ref': f"CEOP-{report_id[:8].upper()}",
        'escalated_by': a['handle'], 'escalated_at': datetime.now(timezone.utc).isoformat()}})
    await audit(a, 'csam_escalate_ceop', r.get('target_id', ''), report_id)
    return {'ok': True, 'escalated': True, 'ceop_ref': f"CEOP-{report_id[:8].upper()}"}


@app.post('/api/admin/csam/{report_id}/resolve')
async def admin_csam_resolve(report_id: str, a: dict = Depends(sensitive_access_guard)):
    r = await db.csam_reports.find_one({'id': report_id})
    if not r:
        raise HTTPException(404, 'Report not found')
    await db.csam_reports.update_one({'id': report_id}, {'$set': {
        'status': 'resolved', 'resolved_by': a['handle'],
        'resolved_at': datetime.now(timezone.utc).isoformat()}})
    await audit(a, 'csam_resolve', r.get('target_id', ''), report_id)
    return {'ok': True, 'status': 'resolved'}


# ═══════════════════════════════════════════════════════════════════════════
# BLOCK 2 — Verification spine (identity + age)  ·  gates ALL monetisation
# ═══════════════════════════════════════════════════════════════════════════
# We store STATUS ONLY, never raw identity documents. Providers (Yoti / OneID)
# run server-side and confirm results via SIGNED webhooks. Fail-closed: an
# unset provider secret means that provider's webhook is rejected, and an
# unverified user has monetisation_enabled = False and cannot see adult content.

YOTI_WEBHOOK_SECRET = os.environ.get('YOTI_WEBHOOK_SECRET', '')
ONEID_WEBHOOK_SECRET = os.environ.get('ONEID_WEBHOOK_SECRET', '')

VERIFY_TYPES = {'identity', 'age'}
VERIFY_PROVIDERS = {'yoti', 'oneid'}
VERIFY_STATUSES = {'unverified', 'pending', 'verified', 'failed'}


def _blank_verification() -> dict:
    return {
        'identity': {'status': 'unverified', 'provider': None, 'at': None},
        'age': {'status': 'unverified', 'provider': None, 'region': None, 'at': None},
    }


def verification_view(prof: dict) -> dict:
    """Normalised verification block for API responses (status only — no documents)."""
    v = (prof or {}).get('verification') or {}
    base = _blank_verification()
    ident = {**base['identity'], **(v.get('identity') or {})}
    age = {**base['age'], **(v.get('age') or {})}
    return {'identity': ident, 'age': age}


def is_identity_verified(prof: dict) -> bool:
    return (((prof or {}).get('verification') or {}).get('identity') or {}).get('status') == 'verified'


def is_age_verified_adult(prof: dict) -> bool:
    """True only when the account is an age-verified ADULT. Minors are always False.
    Used as the fail-closed gate for all NSFW viewing / selection / discovery."""
    if not prof or prof.get('is_minor'):
        return False
    return (((prof.get('verification') or {}).get('age')) or {}).get('status') == 'verified'


def monetisation_ok(prof: dict) -> bool:
    """Creator tools unlock only when BOTH identity AND age are verified (adult)."""
    return bool(prof) and is_identity_verified(prof) and is_age_verified_adult(prof)


async def require_monetisation(u: dict = Depends(get_current_user)) -> dict:
    """Dependency for creator/monetisation endpoints. Fail-closed."""
    if not monetisation_ok(u):
        raise HTTPException(403, 'Monetisation is locked. Verify your identity and age to unlock creator tools.')
    return u


class VerificationStart(BaseModel):
    type: str       # identity | age
    provider: str   # yoti | oneid


@app.post('/api/verification/start')
async def verification_start(body: VerificationStart, u: dict = Depends(get_current_user)):
    """Begin an identity or age verification. Creates a provider session and marks the
    relevant status 'pending'. The real provider redirect/SDK handshake happens client-side;
    the authoritative result arrives later via the provider's SIGNED webhook.
    NOTE: minors can never age-verify as adults — the hardcoded minor block stays on top."""
    vtype = (body.type or '').strip().lower()
    provider = (body.provider or '').strip().lower()
    if vtype not in VERIFY_TYPES:
        raise HTTPException(400, 'Invalid verification type (identity | age)')
    if provider not in VERIFY_PROVIDERS:
        raise HTTPException(400, 'Invalid provider (yoti | oneid)')
    session_id = str(uuid.uuid4())
    await db.verification_sessions.insert_one({
        'id': session_id, 'user_id': u['id'], 'type': vtype, 'provider': provider,
        'status': 'pending', 'created_at': datetime.now(timezone.utc).isoformat()})
    v = verification_view(u)
    v[vtype]['status'] = 'pending'
    v[vtype]['provider'] = provider
    await db.profiles.update_one({'id': u['id']}, {'$set': {'verification': v}})
    # In production this returns the provider's hosted-flow URL / SDK token. Stubbed here.
    return {'session_id': session_id, 'type': vtype, 'provider': provider, 'status': 'pending',
            'redirect_url': f'https://verify.skaliapp.com/{provider}/{vtype}?session={session_id}'}


@app.get('/api/verification/status')
async def verification_status(u: dict = Depends(get_current_user)):
    prof = await db.profiles.find_one({'id': u['id']}, {'_id': 0})
    return {'verification': verification_view(prof),
            'monetisation_enabled': monetisation_ok(prof),
            'is_minor': bool(prof.get('is_minor'))}


def _verify_hmac(secret: str, raw: bytes, signature: Optional[str]) -> bool:
    """Constant-time HMAC-SHA256 check. Fail-closed: no secret or no signature => reject."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    sig = signature.strip().lower()
    if sig.startswith('sha256='):
        sig = sig[7:]
    return hmac.compare_digest(expected, sig)


async def _apply_verification_result(user_id: str, vtype: str, status: str,
                                     provider: str, region: Optional[str] = None):
    """Write STATUS ONLY to the profile. Never stores identity documents.
    Respects the hardcoded minor block: a minor can never become age-verified adult."""
    prof = await db.profiles.find_one({'id': user_id})
    if not prof:
        raise HTTPException(404, 'Unknown subject')
    v = verification_view(prof)
    now = datetime.now(timezone.utc).isoformat()
    if vtype == 'age':
        if prof.get('is_minor') and status == 'verified':
            status = 'failed'  # hardcoded child-safety wall stays on top
        v['age'] = {'status': status, 'provider': provider, 'region': region, 'at': now}
    else:
        v['identity'] = {'status': status, 'provider': provider, 'at': now}
    upd = {'verification': v}
    # Recompute the monetisation gate from the fresh verification block.
    merged = {**prof, 'verification': v}
    upd['monetisation_enabled'] = monetisation_ok(merged)
    await db.profiles.update_one({'id': user_id}, {'$set': upd})
    await db.verification_sessions.update_many(
        {'user_id': user_id, 'type': vtype, 'status': 'pending'},
        {'$set': {'status': status, 'resolved_at': now}})


async def _handle_verification_webhook(request_body: bytes, payload: dict, provider: str):
    """Shared webhook logic for Yoti/OneID. Expected JSON (status only):
    {user_id, type: 'identity'|'age', status: 'verified'|'failed'|'pending', region?}."""
    user_id = payload.get('user_id') or payload.get('subject_id')
    vtype = (payload.get('type') or '').strip().lower()
    status = (payload.get('status') or '').strip().lower()
    region = payload.get('region')
    if vtype not in VERIFY_TYPES or status not in VERIFY_STATUSES or not user_id:
        raise HTTPException(400, 'Malformed verification payload')
    await _apply_verification_result(user_id, vtype, status, provider, region)
    return {'ok': True, 'user_id': user_id, 'type': vtype, 'status': status}


@app.post('/api/webhooks/yoti')
async def yoti_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('X-Yoti-Signature') or request.headers.get('x-yoti-signature')
    if not _verify_hmac(YOTI_WEBHOOK_SECRET, raw, sig):
        raise HTTPException(401, 'Invalid or missing webhook signature')
    import json as _json
    try:
        payload = _json.loads(raw.decode() or '{}')
    except Exception:
        raise HTTPException(400, 'Invalid JSON')
    return await _handle_verification_webhook(raw, payload, 'yoti')


@app.post('/api/webhooks/oneid')
async def oneid_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('X-OneID-Signature') or request.headers.get('x-oneid-signature')
    if not _verify_hmac(ONEID_WEBHOOK_SECRET, raw, sig):
        raise HTTPException(401, 'Invalid or missing webhook signature')
    import json as _json
    try:
        payload = _json.loads(raw.decode() or '{}')
    except Exception:
        raise HTTPException(400, 'Invalid JSON')
    return await _handle_verification_webhook(raw, payload, 'oneid')



# ═══════════════════════════════════════════════════════════════════════════
# BLOCK 3 — Payments + entitlements (multi-PSP, account-level routing)
# ═══════════════════════════════════════════════════════════════════════════
# Skali is Merchant-of-Record. All purchases happen off-app on skaliapp.com; the
# app only READS entitlements. Account-level PSP routing: any NSFW anywhere on an
# account routes 100% of that account's money through CCBill (fallback Segpay/
# Paxum); fully-SFW accounts use Stripe/Xsolla. Never per-transaction splitting.
#
# Money waterfall (exact): prices are VAT-INCLUSIVE.
#   1) VAT carved out first        -> net_ex_vat = gross / (1 + vat_rate)
#   2) Skali fee on NET ex-VAT     -> 10% subs/inner-circle, 7.5% tips
#   3) PSP fee borne by CREATOR    -> psp_fee = psp_rate * gross
#   creator_net = net_ex_vat - skali_fee - psp_fee   (Premium sub = 100% Skali)
# Advertise "90% of net, less processing." Skali is positive-margin on every tier.

STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
XSOLLA_WEBHOOK_SECRET = os.environ.get('XSOLLA_WEBHOOK_SECRET', '')
CCBILL_WEBHOOK_SECRET = os.environ.get('CCBILL_WEBHOOK_SECRET', '')

# Skali platform fee rates (charged on NET ex-VAT).
SKALI_FEE_RATES = {'premium': 1.0, 'inner_circle': 0.10, 'tip': 0.075, 'shop': 0.10}
# Approximate PSP processing rates (fraction of gross, borne by the creator).
PSP_RATES = {'stripe': 0.029, 'xsolla': 0.05, 'ccbill': 0.109, 'segpay': 0.109, 'paxum': 0.05}
# Paid Inner Circle price caps (monthly, GBP, VAT-inclusive).
INNER_CIRCLE_TIERS = {1: 15.0, 2: 30.0, 3: 50.0}
CHARGEBACK_FLAG_THRESHOLD = 3  # repeat offenders auto-flagged for review


def account_is_nsfw(prof: dict) -> bool:
    return bool((prof or {}).get('account_nsfw'))


def route_psp(prof: dict) -> str:
    """Resolve the single processor for this creator's account by NSFW flag.
    NSFW anywhere on the account -> CCBill (adult-friendly). Otherwise Stripe."""
    return 'ccbill' if account_is_nsfw(prof) else 'stripe'


def compute_waterfall(gross: float, vat_rate: float, product: str, psp: str) -> dict:
    """Exact money waterfall. gross is VAT-INCLUSIVE. Returns a rounded breakdown."""
    gross = round(float(gross), 2)
    vat_rate = max(0.0, float(vat_rate))
    net_ex_vat = gross / (1 + vat_rate)
    vat = gross - net_ex_vat
    skali_fee = SKALI_FEE_RATES.get(product, 0.10) * net_ex_vat
    psp_fee = PSP_RATES.get(psp, 0.03) * gross
    if product == 'premium':
        # Premium is Skali's own product (100% Skali). No creator payout.
        skali_fee = net_ex_vat
        creator_net = 0.0
    else:
        creator_net = net_ex_vat - skali_fee - psp_fee
    r = lambda x: round(x + 1e-9, 2)
    return {'gross': r(gross), 'vat': r(vat), 'vat_rate': vat_rate,
            'net_ex_vat': r(net_ex_vat), 'skali_fee': r(skali_fee),
            'psp_fee': r(psp_fee), 'creator_net': r(max(0.0, creator_net)),
            'skali_margin': r(skali_fee)}


async def _record_transaction(**kw) -> dict:
    doc = {'id': str(uuid.uuid4()), 'status': 'settled',
           'created_at': datetime.now(timezone.utc).isoformat(), **kw}
    await db.transactions.insert_one(dict(doc))
    return doc


async def _grant_entitlement(user_id: str, etype: str, tier, psp: str,
                             creator_id: Optional[str], period_days: int = 30) -> dict:
    """Idempotent-ish upsert of an active entitlement the app reads."""
    now = datetime.now(timezone.utc)
    period_end = (now + timedelta(days=period_days)).isoformat() if period_days else None
    key = {'user_id': user_id, 'type': etype, 'creator_id': creator_id}
    doc = {**key, 'tier': tier, 'source_psp': psp, 'status': 'active',
           'period_end': period_end, 'updated_at': now.isoformat()}
    await db.entitlements.update_one(key, {'$set': doc,
        '$setOnInsert': {'id': str(uuid.uuid4()), 'created_at': now.isoformat()}}, upsert=True)
    return await db.entitlements.find_one(key, {'_id': 0})


async def _revoke_entitlement(user_id: str, etype: str, creator_id: Optional[str], reason: str):
    await db.entitlements.update_one(
        {'user_id': user_id, 'type': etype, 'creator_id': creator_id},
        {'$set': {'status': 'revoked' if reason == 'chargeback' else 'canceled',
                  'revoke_reason': reason, 'updated_at': datetime.now(timezone.utc).isoformat()}})


async def _adjust_creator_balance(creator_id: Optional[str], delta: float):
    if not creator_id:
        return
    await db.payout_balances.update_one({'creator_id': creator_id},
        {'$inc': {'pending': round(delta, 2)},
         '$set': {'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)


@app.get('/api/entitlements')
async def my_entitlements(u: dict = Depends(get_current_user)):
    """The app reads this to know what the user has unlocked. Read-only on every platform
    (iOS build shows status only — no price/buy/subscribe UI for digital goods)."""
    out = []
    now = datetime.now(timezone.utc).isoformat()
    async for e in db.entitlements.find({'user_id': u['id']}, {'_id': 0}):
        if e.get('status') == 'active' and e.get('period_end') and e['period_end'] < now:
            e['status'] = 'expired'
            await db.entitlements.update_one({'id': e['id']}, {'$set': {'status': 'expired'}})
        out.append(e)
    return {'entitlements': out,
            'premium': any(e['type'] == 'premium' and e['status'] == 'active' for e in out)}


class CheckoutStart(BaseModel):
    product: str                       # premium | inner_circle | tip
    creator_handle: Optional[str] = None
    tier: Optional[int] = None         # inner_circle: 1|2|3
    amount: Optional[float] = None     # tip amount (VAT-inclusive)
    vat_rate: Optional[float] = 0.20   # customer-country VAT rate


@app.post('/api/checkout/session')
async def checkout_session(body: CheckoutStart, u: dict = Depends(get_current_user)):
    """Create a WEB checkout session (fulfilled on skaliapp.com). Returns the hosted
    checkout URL and the resolved PSP. The PSP is chosen by the SELLER account's NSFW flag
    (Skali itself for Premium). No money moves here — the PSP webhook grants entitlements."""
    product = (body.product or '').strip().lower()
    if product not in SKALI_FEE_RATES:
        raise HTTPException(400, 'Unknown product')
    creator = None
    if product in ('inner_circle', 'tip'):
        if not body.creator_handle:
            raise HTTPException(400, 'creator_handle is required')
        creator = await resolve_profile(body.creator_handle, {'_id': 0})
        if not creator:
            raise HTTPException(404, 'Creator not found')
        if not monetisation_ok(creator):
            raise HTTPException(403, 'This creator is not set up to receive payments yet')
    # Price + PSP resolution
    if product == 'inner_circle':
        tier = int(body.tier or 1)
        if tier not in INNER_CIRCLE_TIERS:
            raise HTTPException(400, 'Invalid Inner Circle tier (1, 2 or 3)')
        gross = INNER_CIRCLE_TIERS[tier]
    elif product == 'tip':
        gross = round(float(body.amount or 0), 2)
        if gross <= 0:
            raise HTTPException(400, 'Tip amount must be greater than zero')
        tier = None
    else:  # premium
        gross = round(float(body.amount or 5.0), 2)
        tier = 'premium'
    # PSP: Premium is billed by Skali (Stripe/Xsolla, SFW); creator products follow the
    # creator account's NSFW flag.
    psp = route_psp(creator) if creator else 'stripe'
    session_id = str(uuid.uuid4())
    quote = compute_waterfall(gross, float(body.vat_rate or 0.20), product, psp)
    await db.checkout_sessions.insert_one({
        'id': session_id, 'buyer_id': u['id'],
        'creator_id': creator['id'] if creator else None,
        'product': product, 'tier': tier, 'gross': gross, 'psp': psp,
        'content_class': 'nsfw' if (creator and account_is_nsfw(creator)) else 'sfw',
        'vat_rate': float(body.vat_rate or 0.20), 'quote': quote,
        'status': 'created', 'created_at': datetime.now(timezone.utc).isoformat()})
    return {'session_id': session_id, 'psp': psp, 'gross': gross, 'currency': 'GBP',
            'quote': quote,
            'checkout_url': f'https://skaliapp.com/checkout?session={session_id}&psp={psp}'}


async def _fulfil_checkout(session_id: str, psp: str) -> dict:
    """Grant the entitlement + write the ledger transaction for a completed checkout."""
    s = await db.checkout_sessions.find_one({'id': session_id})
    if not s:
        raise HTTPException(404, 'Unknown checkout session')
    if s.get('status') == 'fulfilled':
        return {'ok': True, 'already': True}
    product, buyer, creator = s['product'], s['buyer_id'], s.get('creator_id')
    wf = s.get('quote') or compute_waterfall(s['gross'], s.get('vat_rate', 0.20), product, psp)
    if product == 'shop':
        # Digital download unlocks an entitlement; physical creates a Printful order.
        kind = s.get('shop_kind', 'digital')
        prod = await db.shop_products.find_one({'id': s.get('shop_product_id')}, {'_id': 0})
        if kind == 'digital':
            await _grant_entitlement(buyer, 'download', s.get('shop_product_id'), psp, creator, period_days=0)
        await db.shop_orders.insert_one({
            'id': str(uuid.uuid4()), 'creator_id': creator, 'buyer_id': buyer,
            'product_id': s.get('shop_product_id'), 'title': (prod or {}).get('title'),
            'kind': kind, 'gross': s['gross'], 'psp': psp,
            'download_url': (prod or {}).get('download_url') if kind == 'digital' else None,
            'fulfilment_status': 'delivered' if kind == 'digital' else 'printful_submitted',
            'created_at': datetime.now(timezone.utc).isoformat()})
    elif product != 'tip':
        etype = 'premium' if product == 'premium' else 'inner_circle'
        await _grant_entitlement(buyer, etype, s.get('tier'), psp, creator, period_days=30)
        if product == 'inner_circle':
            await db.subscriptions.update_one(
                {'buyer_id': buyer, 'creator_id': creator, 'type': 'inner_circle'},
                {'$set': {'id': str(uuid.uuid4()), 'buyer_id': buyer, 'creator_id': creator,
                          'type': 'inner_circle', 'tier': s.get('tier'), 'price': s['gross'],
                          'psp': psp, 'status': 'active',
                          'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
    txn = await _record_transaction(
        session_id=session_id, buyer_id=buyer, creator_id=creator, product=product,
        currency='GBP', psp=psp, content_class=s.get('content_class', 'sfw'), **wf)
    await _adjust_creator_balance(creator, wf['creator_net'])
    await db.checkout_sessions.update_one({'id': session_id},
        {'$set': {'status': 'fulfilled', 'psp': psp,
                  'fulfilled_at': datetime.now(timezone.utc).isoformat()}})
    return {'ok': True, 'transaction_id': txn['id'], 'creator_net': wf['creator_net']}


async def _handle_chargeback(session_id: str):
    """Proportional clawback from the creator's payout + repeat-offender flag."""
    txn = await db.transactions.find_one({'session_id': session_id})
    if not txn:
        return {'ok': False, 'reason': 'no transaction'}
    await db.transactions.update_one({'id': txn['id']},
        {'$set': {'status': 'chargeback', 'updated_at': datetime.now(timezone.utc).isoformat()}})
    creator = txn.get('creator_id')
    if creator:
        await _adjust_creator_balance(creator, -abs(txn.get('creator_net', 0)))  # proportional clawback
        cnt = await db.transactions.count_documents({'creator_id': creator, 'status': 'chargeback'})
        if cnt >= CHARGEBACK_FLAG_THRESHOLD:
            await db.payout_balances.update_one({'creator_id': creator},
                {'$set': {'payout_review_flag': True}}, upsert=True)
    # Revoke the buyer's entitlement for this purchase.
    etype = 'premium' if txn['product'] == 'premium' else ('inner_circle' if txn['product'] == 'inner_circle' else 'tip')
    if txn['product'] != 'tip':
        await _revoke_entitlement(txn['buyer_id'], etype, creator, 'chargeback')
    return {'ok': True, 'clawed_back': txn.get('creator_net', 0)}


async def _process_psp_event(psp: str, payload: dict):
    """Normalised PSP event handler. Expected: {event, session_id?, subscription_ref?}."""
    event = (payload.get('event') or payload.get('type') or '').lower()
    session_id = payload.get('session_id') or payload.get('client_reference_id')
    if event in ('checkout.completed', 'checkout.session.completed', 'invoice.paid',
                 'payment.success', 'newsalesuccess', 'renewalsuccess'):
        if not session_id:
            raise HTTPException(400, 'Missing session_id')
        return await _fulfil_checkout(session_id, psp)
    if event in ('subscription.canceled', 'customer.subscription.deleted', 'cancellation', 'expiration'):
        s = await db.checkout_sessions.find_one({'id': session_id}) if session_id else None
        if s:
            etype = 'premium' if s['product'] == 'premium' else 'inner_circle'
            await _revoke_entitlement(s['buyer_id'], etype, s.get('creator_id'), 'canceled')
            await db.subscriptions.update_many(
                {'buyer_id': s['buyer_id'], 'creator_id': s.get('creator_id')},
                {'$set': {'status': 'canceled'}})
        return {'ok': True, 'revoked': True}
    if event in ('charge.dispute.created', 'chargeback', 'dispute'):
        return await _handle_chargeback(session_id)
    return {'ok': True, 'ignored': event}


@app.post('/api/webhooks/stripe')
async def stripe_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('Stripe-Signature') or request.headers.get('stripe-signature')
    if not _verify_hmac(STRIPE_WEBHOOK_SECRET, raw, sig):
        raise HTTPException(401, 'Invalid or missing webhook signature')
    import json as _json
    return await _process_psp_event('stripe', _json.loads(raw.decode() or '{}'))


@app.post('/api/webhooks/ccbill')
async def ccbill_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('X-CCBill-Signature') or request.headers.get('x-ccbill-signature')
    if not _verify_hmac(CCBILL_WEBHOOK_SECRET, raw, sig):
        raise HTTPException(401, 'Invalid or missing webhook signature')
    import json as _json
    return await _process_psp_event('ccbill', _json.loads(raw.decode() or '{}'))


@app.post('/api/webhooks/xsolla')
async def xsolla_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('X-Xsolla-Signature') or request.headers.get('authorization')
    if not _verify_hmac(XSOLLA_WEBHOOK_SECRET, raw, sig):
        raise HTTPException(401, 'Invalid or missing webhook signature')
    import json as _json
    return await _process_psp_event('xsolla', _json.loads(raw.decode() or '{}'))


@app.post('/api/account/nsfw-flip')
async def account_nsfw_flip(u: dict = Depends(get_current_user)):
    """Flip a fully-SFW account to NSFW. Existing Stripe/Xsolla subscriptions run to
    period end, then cancel and must re-subscribe on CCBill (adult money NEVER runs
    through Stripe retroactively). Fans get a re-consent prompt. Sets account_nsfw=True
    so all FUTURE checkout routing goes through CCBill."""
    if account_is_nsfw(u):
        return {'ok': True, 'account_nsfw': True, 'already': True}
    await db.profiles.update_one({'id': u['id']}, {'$set': {'account_nsfw': True,
        'nsfw_flipped_at': datetime.now(timezone.utc).isoformat()}})
    # Mark existing non-CCBill subs to run to period end, then re-subscribe on CCBill.
    flip_count = 0
    async for sub in db.subscriptions.find({'creator_id': u['id'], 'status': 'active',
                                            'psp': {'$in': ['stripe', 'xsolla']}}):
        await db.subscriptions.update_one({'id': sub['id']},
            {'$set': {'flip_pending': True, 'resubscribe_psp': 'ccbill', 'cancel_at_period_end': True}})
        # Fan re-consent prompt for the buyer.
        await db.reconsent_prompts.update_one(
            {'buyer_id': sub['buyer_id'], 'creator_id': u['id']},
            {'$set': {'id': str(uuid.uuid4()), 'buyer_id': sub['buyer_id'], 'creator_id': u['id'],
                      'reason': 'creator_switched_to_nsfw', 'status': 'pending',
                      'created_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
        flip_count += 1
    return {'ok': True, 'account_nsfw': True, 'subscriptions_flipped': flip_count,
            'future_psp': 'ccbill'}


@app.get('/api/creator/finance')
async def creator_finance(u: dict = Depends(require_monetisation)):
    """Consolidated earnings across ALL PSPs into one ledger (Block 4 Finance foundation).
    Every line carries gross / VAT / PSP fee / Skali cut / creator net."""
    txns, totals = [], {'gross': 0.0, 'vat': 0.0, 'psp_fee': 0.0, 'skali_fee': 0.0, 'creator_net': 0.0}
    async for t in db.transactions.find({'creator_id': u['id']}, {'_id': 0}).sort('created_at', -1).limit(500):
        txns.append(t)
        if t.get('status') != 'chargeback':
            for k in totals:
                totals[k] = round(totals[k] + float(t.get(k, 0) or 0), 2)
    bal = await db.payout_balances.find_one({'creator_id': u['id']}, {'_id': 0}) or {}
    return {'transactions': txns, 'totals': totals,
            'pending_payout': round(float(bal.get('pending', 0) or 0), 2),
            'payout_review_flag': bool(bal.get('payout_review_flag')),
            'note': 'Skali is Merchant-of-Record; VAT is remitted by Skali. You keep 90% of net, less processing.'}



# ═══════════════════════════════════════════════════════════════════════════
# BLOCK 4 — Creator Hub (Overview · Subscribers · Shop · Finance · Payouts)
# ═══════════════════════════════════════════════════════════════════════════
# Built on the Block 3 ledger. Every money line carries gross / VAT / PSP fee /
# Skali cut / creator net. Earnings are consolidated across ALL PSPs into one
# ledger. Tax docs are issued by Skali (Merchant-of-Record). Creator Health is
# DEFERRED (needs an event pipeline) and must never touch strike enforcement.

PAYOUT_SCHEDULES = {'weekly', 'monthly', 'threshold'}
SHOP_PRODUCT_KINDS = {'digital', 'physical'}  # physical = Printful POD


def _month_starts():
    """(this_month_start_iso, last_month_start_iso) in UTC ISO — for chronological string compares."""
    now = datetime.now(timezone.utc)
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_end = this_start - timedelta(seconds=1)
    last_start = prev_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return this_start.isoformat(), last_start.isoformat()


async def _payout_doc(creator_id: str) -> dict:
    return await db.payout_balances.find_one({'creator_id': creator_id}, {'_id': 0}) or {}


@app.get('/api/creator/overview')
async def creator_overview(u: dict = Depends(require_monetisation)):
    """Overview tab: monthly revenue, new subs, tips, pending payouts, growth vs last month."""
    this_start, last_start = _month_starts()
    rev_this = rev_last = tips_this = 0.0
    new_subs = 0
    async for t in db.transactions.find({'creator_id': u['id'], 'status': {'$ne': 'chargeback'}}):
        c = float(t.get('creator_net', 0) or 0)
        created = t.get('created_at', '')
        if created >= this_start:
            rev_this += c
            if t.get('product') == 'tip':
                tips_this += c
            if t.get('product') == 'inner_circle':
                new_subs += 1
        elif last_start <= created < this_start:
            rev_last += c
    growth = None
    if rev_last > 0:
        growth = round(((rev_this - rev_last) / rev_last) * 100, 1)
    elif rev_this > 0:
        growth = 100.0
    bal = await _payout_doc(u['id'])
    active_subs = await db.subscriptions.count_documents({'creator_id': u['id'], 'status': 'active'})
    return {
        'revenue_this_month': round(rev_this, 2),
        'revenue_last_month': round(rev_last, 2),
        'growth_pct': growth,
        'new_subs_this_month': new_subs,
        'tips_this_month': round(tips_this, 2),
        'active_subscribers': active_subs,
        'pending_payout': round(float(bal.get('pending', 0) or 0), 2),
        'currency': bal.get('currency', 'GBP'),
    }


@app.get('/api/creator/subscribers')
async def creator_subscribers(u: dict = Depends(require_monetisation)):
    """Subscribers tab: active count, churn, renewals, discounts + the subscriber list."""
    this_start, _ = _month_starts()
    active, churned, renewals = 0, 0, 0
    subs = []
    async for s in db.subscriptions.find({'creator_id': u['id']}).sort('updated_at', -1):
        buyer = await db.profiles.find_one({'id': s['buyer_id']}, {'_id': 0})
        if s.get('status') == 'active':
            active += 1
        if s.get('status') == 'canceled' and (s.get('updated_at', '') >= this_start):
            churned += 1
        subs.append({
            'buyer_handle': buyer['handle'] if buyer else 'unknown',
            'buyer_name': buyer['display_name'] if buyer else 'Unknown',
            'tier': s.get('tier'), 'price': s.get('price'), 'psp': s.get('psp'),
            'status': s.get('status'), 'since': s.get('updated_at'),
        })
    async for t in db.transactions.find({'creator_id': u['id'], 'product': 'inner_circle',
                                         'status': {'$ne': 'chargeback'}, 'created_at': {'$gte': this_start}}):
        renewals += 1
    return {'active': active, 'churn_this_month': churned, 'renewals_this_month': renewals,
            'discounts': 0, 'subscribers': subs}


# --------------------------- Shop (Printful POD + digital downloads) ---------------------------

class ShopProduct(BaseModel):
    title: str
    kind: str            # digital | physical
    price: float         # VAT-inclusive
    description: Optional[str] = ''
    download_url: Optional[str] = None      # digital goods
    printful_variant_id: Optional[str] = None  # physical (Printful)


@app.post('/api/creator/shop/products')
async def shop_create_product(body: ShopProduct, u: dict = Depends(require_monetisation)):
    kind = (body.kind or '').strip().lower()
    if kind not in SHOP_PRODUCT_KINDS:
        raise HTTPException(400, 'Invalid product kind (digital | physical)')
    if not body.title.strip() or float(body.price) <= 0:
        raise HTTPException(400, 'Title and a positive price are required')
    doc = {'id': str(uuid.uuid4()), 'creator_id': u['id'], 'title': body.title.strip(),
           'kind': kind, 'price': round(float(body.price), 2), 'description': (body.description or '')[:500],
           'download_url': body.download_url if kind == 'digital' else None,
           'printful_variant_id': body.printful_variant_id if kind == 'physical' else None,
           'active': True, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.shop_products.insert_one(dict(doc))
    doc.pop('_id', None)
    return doc


@app.delete('/api/creator/shop/products/{product_id}')
async def shop_delete_product(product_id: str, u: dict = Depends(require_monetisation)):
    # Soft delete — never destroy data in place.
    await db.shop_products.update_one({'id': product_id, 'creator_id': u['id']},
        {'$set': {'active': False, 'deleted_at': datetime.now(timezone.utc).isoformat()}})
    return {'ok': True}


@app.get('/api/creator/shop')
async def creator_shop(u: dict = Depends(require_monetisation)):
    """Shop tab: products + orders with Printful fulfilment status. Revenue feeds Finance."""
    products, orders = [], []
    async for p in db.shop_products.find({'creator_id': u['id'], 'active': True}, {'_id': 0}).sort('created_at', -1):
        products.append(p)
    async for o in db.shop_orders.find({'creator_id': u['id']}, {'_id': 0}).sort('created_at', -1).limit(200):
        orders.append(o)
    return {'products': products, 'orders': orders}


@app.post('/api/shop/order/{product_id}')
async def shop_order(product_id: str, u: dict = Depends(get_current_user)):
    """Buyer purchases a shop product. Creates an off-app checkout session (fulfilled on
    skaliapp.com). PSP follows the SELLER account's NSFW flag. Digital goods unlock a
    download entitlement on fulfilment; physical goods create a Printful order."""
    prod = await db.shop_products.find_one({'id': product_id, 'active': True})
    if not prod:
        raise HTTPException(404, 'Product not found')
    creator = await db.profiles.find_one({'id': prod['creator_id']}, {'_id': 0})
    if not creator or not monetisation_ok(creator):
        raise HTTPException(403, 'This shop is not open for orders')
    psp = route_psp(creator)
    session_id = str(uuid.uuid4())
    quote = compute_waterfall(prod['price'], 0.20, 'shop', psp)
    await db.checkout_sessions.insert_one({
        'id': session_id, 'buyer_id': u['id'], 'creator_id': creator['id'],
        'product': 'shop', 'shop_product_id': product_id, 'shop_kind': prod['kind'],
        'gross': prod['price'], 'psp': psp, 'vat_rate': 0.20, 'quote': quote,
        'content_class': 'nsfw' if account_is_nsfw(creator) else 'sfw',
        'status': 'created', 'created_at': datetime.now(timezone.utc).isoformat()})
    return {'session_id': session_id, 'psp': psp, 'gross': prod['price'], 'currency': 'GBP',
            'quote': quote, 'checkout_url': f'https://skaliapp.com/checkout?session={session_id}&psp={psp}'}


# --------------------------- Finance (payouts, VAT, tax docs, export) ---------------------------

@app.get('/api/creator/finance/export.csv')
async def creator_finance_csv(u: dict = Depends(require_monetisation)):
    """CSV export of the consolidated ledger for accounting."""
    rows = ['date,product,psp,content_class,currency,gross,vat,psp_fee,skali_fee,creator_net,status']
    async for t in db.transactions.find({'creator_id': u['id']}, {'_id': 0}).sort('created_at', -1):
        rows.append(','.join(str(x) for x in [
            t.get('created_at', ''), t.get('product', ''), t.get('psp', ''),
            t.get('content_class', ''), t.get('currency', 'GBP'), t.get('gross', 0),
            t.get('vat', 0), t.get('psp_fee', 0), t.get('skali_fee', 0),
            t.get('creator_net', 0), t.get('status', '')]))
    return PlainTextResponse('\n'.join(rows), media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="skali-earnings.csv"'})


@app.get('/api/creator/finance/tax-docs')
async def creator_tax_docs(u: dict = Depends(require_monetisation)):
    """Monthly tax statements issued by Skali (Merchant-of-Record). VAT is remitted by Skali."""
    by_month: dict[str, dict] = {}
    async for t in db.transactions.find({'creator_id': u['id'], 'status': {'$ne': 'chargeback'}}):
        m = (t.get('created_at') or '')[:7]  # YYYY-MM
        if not m:
            continue
        d = by_month.setdefault(m, {'month': m, 'gross': 0.0, 'vat': 0.0, 'skali_fee': 0.0,
                                    'psp_fee': 0.0, 'creator_net': 0.0})
        for k in ('gross', 'vat', 'skali_fee', 'psp_fee', 'creator_net'):
            d[k] = round(d[k] + float(t.get(k, 0) or 0), 2)
    docs = sorted(by_month.values(), key=lambda x: x['month'], reverse=True)
    for d in docs:
        d['issuer'] = 'Skali Ltd (Merchant-of-Record)'
        d['statement_id'] = f"SKALI-{u['handle'][:6].upper()}-{d['month']}"
    return {'tax_documents': docs}


class PayoutSettings(BaseModel):
    schedule: Optional[str] = None   # weekly | monthly | threshold
    currency: Optional[str] = None
    threshold: Optional[float] = None


@app.put('/api/creator/payout-settings')
async def set_payout_settings(body: PayoutSettings, u: dict = Depends(require_monetisation)):
    upd = {}
    if body.schedule:
        if body.schedule not in PAYOUT_SCHEDULES:
            raise HTTPException(400, 'Invalid schedule (weekly | monthly | threshold)')
        upd['schedule'] = body.schedule
    if body.currency:
        upd['currency'] = body.currency.upper()[:3]
    if body.threshold is not None:
        upd['threshold'] = round(float(body.threshold), 2)
    if upd:
        upd['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.payout_balances.update_one({'creator_id': u['id']}, {'$set': upd}, upsert=True)
    return await _payout_doc(u['id'])


@app.get('/api/creator/payouts')
async def creator_payouts(u: dict = Depends(require_monetisation)):
    bal = await _payout_doc(u['id'])
    history = []
    async for p in db.payouts.find({'creator_id': u['id']}, {'_id': 0}).sort('created_at', -1).limit(100):
        history.append(p)
    return {
        'pending': round(float(bal.get('pending', 0) or 0), 2),
        'available': round(float(bal.get('available', 0) or 0), 2),
        'paid': round(float(bal.get('paid', 0) or 0), 2),
        'currency': bal.get('currency', 'GBP'),
        'schedule': bal.get('schedule', 'monthly'),
        'threshold': bal.get('threshold'),
        'payout_kyc': bal.get('payout_kyc') or {'status': 'unverified', 'provider': None},
        'payout_review_flag': bool(bal.get('payout_review_flag')),
        'history': history,
    }


@app.post('/api/creator/payouts/request')
async def request_payout(u: dict = Depends(require_monetisation)):
    """Request a payout of the pending balance. Payout KYC is triggered HERE (on first
    payout), not upfront. If KYC isn't verified yet, we hand off to the PSP and return
    202 without moving money."""
    bal = await _payout_doc(u['id'])
    if bal.get('payout_review_flag'):
        raise HTTPException(403, 'Your account is under review after repeated chargebacks. Payouts are paused.')
    kyc = bal.get('payout_kyc') or {'status': 'unverified'}
    if kyc.get('status') != 'verified':
        psp = route_psp(u)
        await db.payout_balances.update_one({'creator_id': u['id']},
            {'$set': {'payout_kyc': {'status': 'pending', 'provider': psp,
                                     'at': datetime.now(timezone.utc).isoformat()}}}, upsert=True)
        return JSONResponse(status_code=202, content={
            'kyc_required': True, 'provider': psp,
            'kyc_url': f'https://payouts.skaliapp.com/{psp}/kyc?creator={u["handle"]}',
            'message': 'Complete payout KYC with the processor to receive your first payout.'})
    amount = round(float(bal.get('pending', 0) or 0), 2)
    if amount <= 0:
        raise HTTPException(400, 'No funds available to pay out')
    payout = {'id': str(uuid.uuid4()), 'creator_id': u['id'], 'amount': amount,
              'currency': bal.get('currency', 'GBP'), 'status': 'pending', 'psp': route_psp(u),
              'created_at': datetime.now(timezone.utc).isoformat()}
    await db.payouts.insert_one(dict(payout))
    await db.payout_balances.update_one({'creator_id': u['id']},
        {'$set': {'pending': 0.0}, '$inc': {'paid': amount}})
    payout.pop('_id', None)
    return {'ok': True, 'payout': payout}

