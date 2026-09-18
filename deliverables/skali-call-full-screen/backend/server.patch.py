# =============================================================================
# Backend patch: full-screen incoming call while the app is out
# =============================================================================
#
# Apply these two edits to /app/backend/server.py.
#
# The important idea: today `push_to_user` sends a *notification* FCM message,
# which the Android system tray renders as a plain notification when the app is
# killed. To trigger our own custom full-screen call UI we need a **data-only,
# high-priority** FCM message; that wakes our CallMessagingService, which then
# posts the CallStyle notification with a full-screen intent.
#
# The rest of the app keeps using push_to_user (unchanged), so DMs / replies
# / etc. behave exactly as before.
# =============================================================================


# -----------------------------------------------------------------------------
# 1. ADD this new helper right after `async def push_to_user(...)` finishes
#    (i.e. just before the `@app.post('/api/push/register')` decorator).
# -----------------------------------------------------------------------------
import uuid as _uuid_for_calls  # keep with the other imports if not already there


async def push_call_ring_to_user(user_id: str,
                                 room: str,
                                 media: str,
                                 caller_handle: str,
                                 caller_name: str,
                                 caller_avatar: Optional[str]) -> Optional[str]:
    """Best-effort *data-only* high-priority ring push.

    Data-only messages are what let our own CallMessagingService run and
    render a phone-style, over-the-lockscreen full-screen incoming call
    notification even when the app has been force-killed. Notification
    messages (with a `notification` block) would just become a system-tray
    notification instead.

    Returns the generated call_id (also used as the Android notification id)
    so the caller can later match up an accept/decline.
    """
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
                # NO `notification=` block on purpose. Data-only + priority=high
                # is what lets Android wake our service on a killed app.
                messaging.send(messaging.Message(
                    token=tk,
                    data={k: str(v) for k, v in data.items()},
                    android=messaging.AndroidConfig(
                        priority='high',
                        ttl=45,  # a ring older than 45s is useless
                        direct_boot_ok=True,
                    ),
                ))
            except Exception as se:
                if 'Unregistered' in type(se).__name__ or 'NotRegistered' in str(se):
                    await db.device_tokens.delete_one({'user_id': user_id, 'token': tk})
    except Exception as e:
        log.info(f'push_call_ring_to_user failed: {e}')
    return call_id


# -----------------------------------------------------------------------------
# 2. REPLACE the existing `/api/call/ring` endpoint with the version below.
#    The only functional change is that the push is now the new ring helper.
# -----------------------------------------------------------------------------
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

    # New: data-only, high-priority ring push so the native full-screen
    # call banner appears even when the app is force-killed.
    call_id = await push_call_ring_to_user(
        user_id       = other['id'],
        room          = body.room,
        media         = media,
        caller_handle = u['handle'],
        caller_name   = caller.get('display_name') or u['handle'],
        caller_avatar = caller.get('avatar_url'),
    )
    return {'ok': True, 'call_id': call_id}
