"""Phase 2 (web): OBS → LiveKit Ingress streaming, live-chat moderation and 24h VODs.

Isolated module: server.py mounts it inside a try/except, so a failure here can never
break the rest of the API. Reuses existing LiveKit + Supabase env; VOD recording is
enabled only when Supabase S3 settings are present (see _s3_upload).
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse, quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from livekit import api as lk_api

log = logging.getLogger('skali.streaming')

VOD_TTL = timedelta(hours=24)
IDLE_END = timedelta(minutes=3)
LOOP_EVERY = 60
OBS_AUDIENCES = {'public', 'followers', 'inner'}
_STATUS = {'ENDPOINT_PUBLISHING': 'publishing', 'ENDPOINT_BUFFERING': 'buffering',
           'ENDPOINT_ERROR': 'error'}

srv = None  # the server module, injected by setup()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(iso: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(iso) if iso else None
    except Exception:
        return None


def room_for(uid: str) -> str:
    return f'obs-{uid}'


def ingress_identity(uid: str) -> str:
    return f'obs-host-{uid}'


def lk_configured() -> bool:
    return bool(srv.LIVEKIT_URL and srv.LIVEKIT_API_KEY and srv.LIVEKIT_API_SECRET)


async def _lk(fn):
    if not lk_configured():
        raise HTTPException(503, 'LiveKit is not configured on the server yet.')
    c = lk_api.LiveKitAPI(srv.LIVEKIT_URL, srv.LIVEKIT_API_KEY, srv.LIVEKIT_API_SECRET)
    try:
        return await fn(c)
    finally:
        await c.aclose()


def _s3_endpoint() -> str:
    return os.environ.get('SUPABASE_S3_ENDPOINT', '') or (f'{srv.SUPABASE_URL}/storage/v1/s3' if srv.SUPABASE_URL else '')


def vod_bucket() -> str:
    # Dedicated bucket: the shared media bucket is capped at 50 MB by ensure_bucket() on every boot.
    return os.environ.get('SUPABASE_VOD_BUCKET', '') or 'skali-vods'


def _s3_keys():
    ak = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', '')
    sk = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', '')
    region = os.environ.get('SUPABASE_S3_REGION', '')
    endpoint = _s3_endpoint()
    return (endpoint, region, ak, sk) if (ak and sk and region and endpoint) else None


def _presign(method: str, path: str, seconds: int, extra: Optional[dict] = None) -> str:
    """AWS SigV4 query-string presign against the Supabase S3 endpoint (no extra deps)."""
    endpoint, region, ak, sk = _s3_keys()
    ep = urlparse(endpoint)
    uri = ep.path.rstrip('/') + '/' + vod_bucket() + ('/' + quote(path, safe='/') if path else '')
    t = _now()
    amz, day = t.strftime('%Y%m%dT%H%M%SZ'), t.strftime('%Y%m%d')
    scope = f'{day}/{region}/s3/aws4_request'
    q = {'X-Amz-Algorithm': 'AWS4-HMAC-SHA256', 'X-Amz-Credential': f'{ak}/{scope}', 'X-Amz-Date': amz,
         'X-Amz-Expires': str(max(60, min(604800, int(seconds)))), 'X-Amz-SignedHeaders': 'host', **(extra or {})}
    cq = '&'.join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(q.items()))
    creq = '\n'.join([method, uri, cq, f'host:{ep.netloc}\n', 'host', 'UNSIGNED-PAYLOAD'])
    sts = '\n'.join(['AWS4-HMAC-SHA256', amz, scope, hashlib.sha256(creq.encode()).hexdigest()])
    k = ('AWS4' + sk).encode()
    for part in (day, region, 's3', 'aws4_request'):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    return f'{ep.scheme}://{ep.netloc}{uri}?{cq}&X-Amz-Signature={sig}'


def _s3_upload():
    """Supabase Storage S3 target. Explicit S3 keys win; otherwise session-token mode
    (project ref + anon key + service-role JWT) reuses the existing Supabase creds."""
    region = os.environ.get('SUPABASE_S3_REGION', '')
    endpoint = _s3_endpoint()
    if not (endpoint and region):
        return None
    common = dict(region=region, endpoint=endpoint, bucket=vod_bucket(), force_path_style=True)
    ak = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', '')
    sk = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', '')
    if ak and sk:
        return lk_api.S3Upload(access_key=ak, secret=sk, **common)
    anon = os.environ.get('SUPABASE_ANON_KEY', '')
    if anon and srv.SERVICE_ROLE_KEY:
        ref = (urlparse(srv.SUPABASE_URL).hostname or '').split('.')[0]
        return lk_api.S3Upload(access_key=ref, secret=anon, session_token=srv.SERVICE_ROLE_KEY, **common)
    return None


def vod_enabled() -> bool:
    return lk_configured() and _s3_upload() is not None


_vod_bucket_ready = False


async def _ensure_vod_bucket():
    """Create the private VOD bucket once (no per-bucket size cap; project upload limit applies)."""
    global _vod_bucket_ready
    if _vod_bucket_ready:
        return
    async with httpx.AsyncClient(timeout=20) as c:
        if _s3_keys():
            r = await c.put(_presign('PUT', '', 300))
        elif srv._supabase_configured():
            r = await c.post(f'{srv.SUPABASE_URL}/storage/v1/bucket',
                             headers={**srv.admin_headers(), 'Content-Type': 'application/json'},
                             json={'id': vod_bucket(), 'name': vod_bucket(), 'public': False})
        else:
            return
    log.info('vod bucket ensure %s', r.status_code)
    if r.status_code < 300 or r.status_code in (400, 409):
        _vod_bucket_ready = True


async def _signed_url(path: str, seconds: int, download: Optional[str] = None) -> str:
    if _s3_keys():
        extra = {'response-content-disposition': f'attachment; filename="{download}"'} if download else None
        return _presign('GET', path, seconds, extra)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f'{srv.SUPABASE_URL}/storage/v1/object/sign/{vod_bucket()}/{path}',
                         headers={**srv.admin_headers(), 'Content-Type': 'application/json'},
                         json={'expiresIn': max(60, int(seconds))})
        r.raise_for_status()
        url = r.json()['signedURL']
    url = url if url.startswith('http') else f'{srv.SUPABASE_URL}/storage/v1{url}'
    if download:
        url += ('&' if '?' in url else '?') + 'download=' + quote(download)
    return url


async def _delete_object(path: str):
    if _s3_keys():
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(_presign('DELETE', path, 300))
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()
        return
    if not srv._supabase_configured():
        return
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request('DELETE', f'{srv.SUPABASE_URL}/storage/v1/object/{vod_bucket()}',
                            headers={**srv.admin_headers(), 'Content-Type': 'application/json'},
                            json={'prefixes': [path]})
        r.raise_for_status()


async def _ingress_info(uid: str):
    doc = await srv.db.stream_ingress.find_one({'user_id': uid}, {'_id': 0})
    if not doc:
        return None
    res = await _lk(lambda c: c.ingress.list_ingress(lk_api.ListIngressRequest(ingress_id=doc['ingress_id'])))
    if not res.items:
        await srv.db.stream_ingress.delete_one({'user_id': uid})
        return None
    return res.items[0]


def _ingress_out(info) -> Optional[dict]:
    if info is None:
        return None
    status = _STATUS.get(lk_api.IngressState.Status.Name(info.state.status), 'idle')
    return {'url': info.url, 'stream_key': info.stream_key, 'status': status,
            'error': info.state.error or ''}


async def _create_ingress(u: dict):
    info = await _lk(lambda c: c.ingress.create_ingress(lk_api.CreateIngressRequest(
        input_type=lk_api.IngressInput.RTMP_INPUT, name=f"skali-{u['handle']}",
        room_name=room_for(u['id']), participant_identity=ingress_identity(u['id']),
        participant_name=u.get('display_name') or u['handle'],
        participant_metadata=json.dumps({'role': 'broadcaster', 'handle': u['handle']}),
        enable_transcoding=True)))
    await srv.db.stream_ingress.update_one(
        {'user_id': u['id']},
        {'$set': {'user_id': u['id'], 'ingress_id': info.ingress_id, 'room': room_for(u['id']),
                  'created_at': _now().isoformat()}}, upsert=True)
    return info


async def _live_doc(uid: str) -> Optional[dict]:
    return await srv.db.live_streams.find_one({'host_id': uid, 'status': 'live', 'source': 'obs'}, {'_id': 0})


async def is_mod(host_id: str, uid: str) -> bool:
    if not await srv.db.stream_mods.find_one({'host_id': host_id, 'mod_id': uid}):
        return False
    return await srv.in_inner(host_id, uid)


async def _can_moderate(s: dict, u: dict) -> bool:
    return s['host_id'] == u['id'] or await is_mod(s['host_id'], u['id']) or srv.is_admin_user(u)


async def _send(room: str, payload: dict):
    try:
        await _lk(lambda c: c.room.send_data(lk_api.SendDataRequest(
            room=room, data=json.dumps(payload).encode(), kind=lk_api.DataPacket.Kind.RELIABLE,
            topic='mod')))
    except Exception as e:
        log.warning('stream send_data failed: %s', e)


async def _stop_recording(live_id: str, ended_at: datetime):
    v = await srv.db.stream_vods.find_one({'live_id': live_id, 'status': 'recording'})
    if not v:
        return
    try:
        await _lk(lambda c: c.egress.stop_egress(lk_api.StopEgressRequest(egress_id=v['egress_id'])))
    except Exception as e:
        log.warning('stop egress failed: %s', e)
    await srv.db.stream_vods.update_one({'id': v['id']}, {'$set': {
        'status': 'processing', 'ended_at': ended_at.isoformat(),
        'expires_at': (ended_at + VOD_TTL).isoformat()}})


async def end_session(s: dict):
    ended = _now()
    await srv.db.live_streams.update_one({'id': s['id']}, {'$set': {'status': 'ended', 'ended_at': ended.isoformat()}})
    await _stop_recording(s['id'], ended)
    await _send(s['room'], {'type': 'stream_ended', 'live_id': s['id']})
    # Ephemeral chat: drop every viewer from the room and forget moderation state.
    try:
        res = await _lk(lambda c: c.room.list_participants(lk_api.ListParticipantsRequest(room=s['room'])))
        for p in res.participants:
            if p.identity != ingress_identity(s['host_id']):
                await _lk(lambda c, i=p.identity: c.room.remove_participant(
                    lk_api.RoomParticipantIdentity(room=s['room'], identity=i)))
    except Exception as e:
        log.warning('clear stream room failed: %s', e)
    await srv.db.stream_timeouts.delete_many({'live_id': s['id']})


def _vod_out(v: dict) -> dict:
    return {'id': v['id'], 'live_id': v['live_id'], 'title': v.get('title', ''),
            'category': v.get('category'), 'status': v['status'], 'error': v.get('error', ''),
            'started_at': v.get('started_at'), 'ended_at': v.get('ended_at'),
            'expires_at': v.get('expires_at'), 'size': v.get('size', 0), 'duration': v.get('duration', 0)}


class StreamStart(BaseModel):
    title: Optional[str] = ''
    category: Optional[str] = 'just_chatting'
    audience: Optional[str] = 'public'


class ModBody(BaseModel):
    handle: str


class DeleteMsg(BaseModel):
    msg_id: str


class TimeoutBody(BaseModel):
    user_id: str
    minutes: int = 5


def build_router() -> APIRouter:
    r = APIRouter(prefix='/api/stream')
    auth = srv.get_current_user
    db = srv.db

    @r.get('/ingress')
    async def get_ingress(u: dict = Depends(auth)):
        out = {'configured': lk_configured(), 'vod_enabled': vod_enabled(), 'ingress': None, 'live': None}
        if not out['configured']:
            return out
        out['ingress'] = _ingress_out(await _ingress_info(u['id']))
        live = await _live_doc(u['id'])
        out['live'] = srv._live_out(live) if live else None
        return out

    @r.post('/ingress')
    async def create_ingress(u: dict = Depends(auth)):
        srv.require_can_go_live(u)
        info = await _ingress_info(u['id']) or await _create_ingress(u)
        return _ingress_out(info)

    @r.post('/ingress/reset')
    async def reset_ingress(u: dict = Depends(auth)):
        srv.require_can_go_live(u)
        if await _live_doc(u['id']):
            raise HTTPException(409, 'End your live stream before resetting the stream key.')
        doc = await db.stream_ingress.find_one({'user_id': u['id']})
        if doc:
            try:
                await _lk(lambda c: c.ingress.delete_ingress(lk_api.DeleteIngressRequest(ingress_id=doc['ingress_id'])))
            except Exception as e:
                log.warning('delete ingress failed: %s', e)
            await db.stream_ingress.delete_one({'user_id': u['id']})
        return _ingress_out(await _create_ingress(u))

    @r.post('/start')
    async def start(body: StreamStart, u: dict = Depends(auth)):
        srv.require_can_go_live(u)
        info = await _ingress_info(u['id'])
        if not info:
            raise HTTPException(400, 'Create your stream key first.')
        if _ingress_out(info)['status'] != 'publishing':
            raise HTTPException(409, 'We are not receiving video from OBS yet. Click "Start Streaming" in OBS, then try again.')
        now = _now()
        await db.live_streams.update_many({'host_id': u['id'], 'status': 'live'},
                                          {'$set': {'status': 'ended', 'ended_at': now.isoformat()}})
        live_id = uuid.uuid4().hex[:12]
        audience = body.audience if body.audience in OBS_AUDIENCES else 'public'
        category = body.category if body.category in srv.LIVE_CATEGORY_KEYS else 'just_chatting'
        doc = {'id': live_id, 'room': room_for(u['id']), 'host_id': u['id'], 'source': 'obs',
               'host': {'handle': u['handle'], 'display_name': u['display_name'],
                        'avatar_url': u.get('avatar_url'), 'account_nsfw': srv.is_adult_account(u),
                        'role': srv.effective_role(u)},
               'audience': audience, 'category': category, 'group_id': None,
               'title': (body.title or '')[:120], 'save': False, 'status': 'live',
               'peak_viewers': 0, 'lk_viewers': 0, 'started_at': now.isoformat(),
               'last_publishing_at': now.isoformat()}
        await db.live_streams.insert_one(dict(doc))
        vod = {'id': live_id, 'live_id': live_id, 'host_id': u['id'], 'title': doc['title'],
               'category': category, 'audience': audience, 'started_at': now.isoformat(),
               'path': f"vods/{u['id']}/{live_id}.mp4", 'egress_id': '', 'status': 'disabled'}
        s3 = _s3_upload()
        if s3 is not None:
            try:
                await _ensure_vod_bucket()
            except Exception as e:
                log.warning('vod bucket ensure failed: %s', e)
        if s3 is not None:
            try:
                eg = await _lk(lambda c: c.egress.start_room_composite_egress(lk_api.RoomCompositeEgressRequest(
                    room_name=doc['room'], layout='speaker',
                    file_outputs=[lk_api.EncodedFileOutput(file_type=lk_api.EncodedFileType.MP4,
                                                           filepath=vod['path'], s3=s3)])))
                vod.update(egress_id=eg.egress_id, status='recording')
            except Exception as e:
                log.warning('start egress failed: %s', e)
                vod.update(status='failed', error='Recording could not start')
        await db.stream_vods.insert_one(dict(vod))
        try:
            await srv._notify_live(doc, u)
        except Exception as e:
            log.warning('obs live notify failed: %s', e)
        return srv._live_out(doc)

    @r.post('/end')
    async def end(u: dict = Depends(auth)):
        s = await _live_doc(u['id'])
        if not s:
            raise HTTPException(404, "You're not live right now.")
        await end_session(s)
        return {'ok': True, 'id': s['id']}

    @r.get('/mods')
    async def list_mods(u: dict = Depends(auth)):
        mod_ids = {m['mod_id'] async for m in db.stream_mods.find({'host_id': u['id']})}
        mods, candidates = [], []
        async for row in db.inner.find({'owner_id': u['id'], 'status': 'accepted'}):
            p = await db.profiles.find_one({'id': row['member_id']}, {'_id': 0})
            if not p:
                continue
            item = {'id': p['id'], 'handle': p['handle'], 'display_name': p.get('display_name'),
                    'avatar_url': p.get('avatar_url')}
            (mods if p['id'] in mod_ids else candidates).append(item)
        return {'mods': mods, 'candidates': candidates}

    @r.post('/mods')
    async def add_mod(body: ModBody, u: dict = Depends(auth)):
        t = await db.profiles.find_one({'handle': body.handle.lstrip('#').lower()}, {'_id': 0})
        if not t or t['id'] == u['id']:
            raise HTTPException(404, 'User not found')
        if not await srv.in_inner(u['id'], t['id']):
            raise HTTPException(403, 'Moderators must be in your Inner Circle.')
        await db.stream_mods.update_one({'host_id': u['id'], 'mod_id': t['id']},
                                        {'$set': {'host_id': u['id'], 'mod_id': t['id'],
                                                  'created_at': _now().isoformat()}}, upsert=True)
        return {'ok': True}

    @r.delete('/mods/{handle}')
    async def remove_mod(handle: str, u: dict = Depends(auth)):
        t = await db.profiles.find_one({'handle': handle.lstrip('#').lower()}, {'_id': 0})
        if t:
            await db.stream_mods.delete_one({'host_id': u['id'], 'mod_id': t['id']})
        return {'ok': True}

    @r.get('/vods')
    async def list_vods(u: dict = Depends(auth)):
        cur = db.stream_vods.find({'host_id': u['id'], 'status': {'$in': ['recording', 'processing', 'ready', 'failed']}},
                                  {'_id': 0}).sort('started_at', -1).limit(50)
        return [_vod_out(v) async for v in cur]

    @r.get('/vods/{vod_id}/download')
    async def download_vod(vod_id: str, u: dict = Depends(auth)):
        v = await db.stream_vods.find_one({'id': vod_id}, {'_id': 0})
        if not v or v['host_id'] != u['id']:
            raise HTTPException(404, 'Recording not found')
        exp = _parse(v.get('expires_at'))
        if v['status'] != 'ready' or not exp or exp <= _now():
            raise HTTPException(410 if exp and exp <= _now() else 409, 'This recording is not available for download.')
        name = (v.get('title') or 'skali-stream').strip()[:60] + '.mp4'
        return {'url': await _signed_url(v['path'], (exp - _now()).total_seconds(), download=name),
                'expires_at': v['expires_at']}

    @r.get('/{live_id}')
    async def stream_info(live_id: str, u: dict = Depends(auth)):
        s = await db.live_streams.find_one({'id': live_id, 'source': 'obs'}, {'_id': 0})
        if not s:
            raise HTTPException(404, 'Stream not found')
        if not await srv._can_watch_live(u['id'], s):
            raise HTTPException(403, 'This stream is not available to you')
        out = {**srv._live_out(s), 'source': 'obs', 'is_host': s['host_id'] == u['id'],
               'can_moderate': await _can_moderate(s, u), 'vod': None}
        v = await db.stream_vods.find_one({'live_id': live_id}, {'_id': 0})
        if v and v['status'] in ('recording', 'processing', 'ready'):
            out['vod'] = {'status': v['status'], 'expires_at': v.get('expires_at')}
            exp = _parse(v.get('expires_at'))
            if v['status'] == 'ready' and exp and exp > _now() and s['status'] == 'ended':
                try:
                    out['vod']['playback_url'] = await _signed_url(v['path'], min(3600, (exp - _now()).total_seconds()))
                except Exception as e:
                    log.warning('vod sign failed: %s', e)
        return out

    @r.post('/{live_id}/join')
    async def join(live_id: str, u: dict = Depends(auth)):
        s = await db.live_streams.find_one({'id': live_id, 'source': 'obs'}, {'_id': 0})
        if not s or s.get('status') != 'live':
            raise HTTPException(404, 'This live stream has ended')
        if not await srv._can_watch_live(u['id'], s):
            raise HTTPException(403, 'This stream is not available to you')
        to = await db.stream_timeouts.find_one({'live_id': live_id, 'user_id': u['id']}, {'_id': 0})
        timed_out = bool(to and (_parse(to.get('until')) or _now()) > _now())
        meta = {'handle': u['handle'], 'display_name': u.get('display_name') or u['handle'],
                'avatar_url': u.get('avatar_url'), 'role': srv.effective_role(u),
                'is_host': s['host_id'] == u['id'], 'is_mod': await is_mod(s['host_id'], u['id'])}
        if not lk_configured():
            raise HTTPException(503, 'LiveKit is not configured on the server yet.')
        token = (lk_api.AccessToken(srv.LIVEKIT_API_KEY, srv.LIVEKIT_API_SECRET)
                 .with_identity(u['id']).with_name(meta['display_name'])
                 .with_metadata(json.dumps(meta)).with_ttl(timedelta(hours=6))
                 .with_grants(lk_api.VideoGrants(room_join=True, room=s['room'], can_publish=False,
                                                 can_subscribe=True, can_publish_data=not timed_out)))
        return {'id': live_id, 'room': s['room'], 'server_url': srv.LIVEKIT_URL,
                'participant_token': token.to_jwt(), 'broadcaster': ingress_identity(s['host_id']),
                'timed_out_until': to.get('until') if timed_out else None}

    @r.post('/{live_id}/chat/delete')
    async def delete_msg(live_id: str, body: DeleteMsg, u: dict = Depends(auth)):
        s = await db.live_streams.find_one({'id': live_id, 'source': 'obs', 'status': 'live'}, {'_id': 0})
        if not s:
            raise HTTPException(404, 'Stream not live')
        if not await _can_moderate(s, u):
            raise HTTPException(403, 'Only the streamer and their moderators can do that.')
        await _send(s['room'], {'type': 'mod_delete', 'live_id': live_id, 'msg_id': body.msg_id[:64]})
        return {'ok': True}

    @r.post('/{live_id}/timeout')
    async def timeout_user(live_id: str, body: TimeoutBody, u: dict = Depends(auth)):
        s = await db.live_streams.find_one({'id': live_id, 'source': 'obs', 'status': 'live'}, {'_id': 0})
        if not s:
            raise HTTPException(404, 'Stream not live')
        if not await _can_moderate(s, u):
            raise HTTPException(403, 'Only the streamer and their moderators can do that.')
        if body.user_id == s['host_id'] or body.user_id == u['id']:
            raise HTTPException(400, "You can't time out this user.")
        if s['host_id'] != u['id'] and await is_mod(s['host_id'], body.user_id):
            raise HTTPException(403, 'Only the streamer can time out a moderator.')
        minutes = max(1, min(60, body.minutes))
        until = (_now() + timedelta(minutes=minutes)).isoformat()
        await db.stream_timeouts.update_one({'live_id': live_id, 'user_id': body.user_id},
                                            {'$set': {'live_id': live_id, 'user_id': body.user_id,
                                                      'room': s['room'], 'until': until}}, upsert=True)
        try:
            await _lk(lambda c: c.room.update_participant(lk_api.UpdateParticipantRequest(
                room=s['room'], identity=body.user_id,
                permission=lk_api.ParticipantPermission(can_subscribe=True, can_publish=False,
                                                        can_publish_data=False))))
        except Exception as e:
            log.warning('timeout permission update failed: %s', e)
        await _send(s['room'], {'type': 'mod_timeout', 'live_id': live_id, 'user_id': body.user_id, 'until': until})
        return {'ok': True, 'until': until}

    return r


async def _sweep_vods():
    now = _now()
    async for v in srv.db.stream_vods.find({'status': {'$in': ['processing', 'ready', 'failed']},
                                             'expires_at': {'$lte': now.isoformat()}}):
        try:
            if v.get('egress_id'):
                await _delete_object(v['path'])
            await srv.db.stream_vods.update_one({'id': v['id']}, {'$set': {'status': 'deleted', 'deleted_at': now.isoformat()}})
        except Exception as e:
            log.warning('vod delete failed (%s): %s', v['id'], e)
    if not lk_configured():
        return
    async for v in srv.db.stream_vods.find({'status': 'recording'}):
        s = await srv.db.live_streams.find_one({'id': v['live_id']})
        if not s or s.get('status') != 'live':
            await _stop_recording(v['live_id'], _parse((s or {}).get('ended_at')) or now)
    async for v in srv.db.stream_vods.find({'status': 'processing'}):
        try:
            res = await _lk(lambda c: c.egress.list_egress(lk_api.ListEgressRequest(egress_id=v['egress_id'])))
        except Exception as e:
            log.warning('egress status failed: %s', e)
            continue
        if not res.items:
            continue
        e = res.items[0]
        st = lk_api.EgressStatus.Name(e.status)
        files = list(e.file_results) or ([e.file] if e.HasField('file') and e.file.filename else [])
        if st in ('EGRESS_COMPLETE', 'EGRESS_LIMIT_REACHED') and files:
            f = files[0]
            await srv.db.stream_vods.update_one({'id': v['id']}, {'$set': {
                'status': 'ready', 'size': int(f.size or 0), 'duration': int((f.duration or 0) / 1e9)}})
        elif st in ('EGRESS_FAILED', 'EGRESS_ABORTED', 'EGRESS_LIMIT_REACHED'):
            await srv.db.stream_vods.update_one({'id': v['id']}, {'$set': {'status': 'failed', 'error': e.error or st}})


async def _sweep_sessions():
    if not lk_configured():
        return
    now = _now()
    async for s in srv.db.live_streams.find({'status': 'live', 'source': 'obs'}, {'_id': 0}):
        try:
            info = await _ingress_info(s['host_id'])
            publishing = bool(info) and _ingress_out(info)['status'] == 'publishing'
            if publishing:
                res = await _lk(lambda c: c.room.list_participants(lk_api.ListParticipantsRequest(room=s['room'])))
                n = sum(1 for p in res.participants if p.identity != ingress_identity(s['host_id']))
                await srv.db.live_streams.update_one({'id': s['id']}, {'$set': {
                    'last_publishing_at': now.isoformat(), 'lk_viewers': n},
                    '$max': {'peak_viewers': n}})
            elif now - (_parse(s.get('last_publishing_at')) or now) > IDLE_END:
                await end_session(s)
        except Exception as e:
            log.warning('obs session sweep failed (%s): %s', s.get('id'), e)
    async for t in srv.db.stream_timeouts.find({'until': {'$lte': now.isoformat()}}):
        try:
            await _lk(lambda c: c.room.update_participant(lk_api.UpdateParticipantRequest(
                room=t['room'], identity=t['user_id'],
                permission=lk_api.ParticipantPermission(can_subscribe=True, can_publish=False, can_publish_data=True))))
        except Exception:
            pass
        await srv.db.stream_timeouts.delete_one({'_id': t['_id']})


async def run_maintenance_once():
    for step in (_sweep_vods, _sweep_sessions):
        try:
            await step()
        except Exception as e:
            log.warning('stream maintenance step %s failed: %s', step.__name__, e)


async def _maintenance_loop():
    while True:
        await run_maintenance_once()
        await asyncio.sleep(LOOP_EVERY)


def setup(app, server_module):
    global srv
    srv = server_module
    app.include_router(build_router())

    @app.on_event('startup')
    async def _start_stream_maintenance():
        asyncio.create_task(_maintenance_loop())
