"""Live alerts (per-creator opt-out for followers) + 24h stream replays for viewers — isolated, additive module."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

srv = None


class AlertPref(BaseModel):
    enabled: bool


async def alerts_subscribed_for(creator_id: str) -> set:
    """Viewers who switched ON live alerts for this creator (e.g. from Find → Streamers), followers or not."""
    return {d['user_id'] async for d in srv.db.live_alerts.find({'creator_id': creator_id, 'enabled': True}, {'_id': 0, 'user_id': 1})}


async def alert_default(user_id: str, creator_id: str) -> bool:
    """Without an explicit choice, alerts are on only for followers / Inner Circle (they are the ones notified)."""
    if await srv.db.follows.find_one({'follower_id': user_id, 'target_id': creator_id, 'status': 'approved'}):
        return True
    return bool(await srv.db.inner.find_one({'owner_id': creator_id, 'member_id': user_id, 'status': 'accepted'}))


async def alert_enabled(user_id: str, creator_id: str) -> bool:
    pref = await srv.db.live_alerts.find_one({'user_id': user_id, 'creator_id': creator_id}, {'_id': 0})
    return pref['enabled'] if pref else await alert_default(user_id, creator_id)


async def alerts_disabled_for(creator_id: str) -> set:
    """Fans who switched OFF live alerts for this creator (default is ON for followers + Inner Circle)."""
    return {d['user_id'] async for d in srv.db.live_alerts.find({'creator_id': creator_id, 'enabled': False}, {'_id': 0, 'user_id': 1})}


def watch_url(doc: dict) -> str:
    return f"/watch/{doc['id']}" if doc.get('source') == 'obs' else f"/live?watch={doc['id']}"


def build_router() -> APIRouter:
    r = APIRouter()
    auth = srv.get_current_user

    @r.get('/api/live-alerts/{handle}')
    async def get_alert(handle: str, u: dict = Depends(auth)):
        prof = await srv.resolve_profile(handle, {'_id': 0, 'id': 1})
        if not prof:
            raise srv.HTTPException(404, 'User not found')
        return {'enabled': await alert_enabled(u['id'], prof['id'])}

    @r.put('/api/live-alerts/{handle}')
    async def set_alert(handle: str, body: AlertPref, u: dict = Depends(auth)):
        prof = await srv.resolve_profile(handle, {'_id': 0, 'id': 1})
        if not prof:
            raise srv.HTTPException(404, 'User not found')
        await srv.db.live_alerts.update_one({'user_id': u['id'], 'creator_id': prof['id']},
                                            {'$set': {'enabled': body.enabled,
                                                      'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {'enabled': body.enabled}

    @r.get('/api/live/alerted-now')
    async def alerted_now(u: dict = Depends(auth)):
        """Content streams live right now from creators this viewer gets alerts for (Feed banner)."""
        out, seen = [], set()
        async for s in srv.db.live_streams.find({'status': 'live'}, {'_id': 0}).sort('started_at', -1):
            if s.get('source') != 'obs' and (s.get('kind') or 'stream') != 'stream':
                continue
            host = s['host_id']
            if host == u['id'] or host in seen or not await alert_enabled(u['id'], host):
                continue
            if await srv._can_watch_live(u['id'], s):
                seen.add(host)
                out.append({**srv._live_out(s), 'watch_url': watch_url(s)})
        return out

    @r.get('/api/live/replays')
    async def replays(handle: Optional[str] = None, u: dict = Depends(auth)):
        """Recorded streams still inside their 24h window that this viewer is allowed to watch."""
        now = datetime.now(timezone.utc).isoformat()
        q = {'status': 'ready', 'expires_at': {'$gt': now}}
        if handle:
            prof = await srv.resolve_profile(handle, {'_id': 0, 'id': 1})
            if not prof:
                return []
            q['host_id'] = prof['id']
        out = []
        async for v in srv.db.stream_vods.find(q, {'_id': 0}).sort('started_at', -1).limit(60):
            s = await srv.db.live_streams.find_one({'id': v['live_id']}, {'_id': 0})
            if not s or s.get('status') != 'ended' or not await srv._can_watch_live(u['id'], s):
                continue
            out.append({'live_id': v['live_id'], 'title': v.get('title') or s.get('title', ''),
                        'category': v.get('category') or s.get('category'), 'host': s.get('host'),
                        'started_at': v.get('started_at'), 'ended_at': v.get('ended_at'),
                        'expires_at': v.get('expires_at'), 'duration': v.get('duration', 0)})
        return out

    return r


def setup(app, server_module):
    global srv
    srv = server_module
    app.include_router(build_router())
