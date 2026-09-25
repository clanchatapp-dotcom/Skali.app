// src/lib/pushNotifications.ts
//
// Fix 3:
//   - The call-accept handoff (reading the MainActivity intent extras that
//     IncomingCallActivity wrote) is now registered at bootstrap via
//     bootstrapCallHandoff(), which runs unconditionally before any React
//     tree mounts.  configurePush() is still called from Layout on mount,
//     but it no longer owns the cold-start accept path.
//
//   - A tiny CallAcceptBus buffers a cold-start accept event so that even
//     if Layout hasn't mounted yet, the event is replayed the moment
//     Layout registers its listener.
//
// Fix 2 (companion):
//   IncomingCallActivity no longer fires a skali:// URI deep link.
//   Instead it puts plain extras on the MainActivity intent:
//     skali_call_action = "accept"
//     room / from_handle / media / call_id
//   The Capacitor Bridge exposes these via window.__SKALI_CALL_EXTRAS__
//   (injected by MainActivity.java, see companion fix there), and we read
//   them here at bootstrap time.

import { Capacitor, registerPlugin } from '@capacitor/core'
import { App as CapApp }             from '@capacitor/app'
import { Preferences }               from '@capacitor/preferences'
import { api }                       from './api'
import { supabase }                  from './supabase'

// ---------------------------------------------------------------------------
// CallAcceptBus  –  tiny pub/sub that buffers one event across mount timing
// ---------------------------------------------------------------------------
type CallAcceptDetail = { room: string; peer: string; media: 'audio' | 'video' }

const CallAcceptBus = (() => {
  let _buffered: CallAcceptDetail | null = null
  let _listener: ((d: CallAcceptDetail) => void) | null = null

  return {
    /** Called by bootstrap or deep-link handler when a cold-start accept arrives */
    emit(detail: CallAcceptDetail) {
      if (_listener) {
        _listener(detail)
      } else {
        _buffered = detail           // Layout hasn't mounted yet — buffer it
      }
    },
    /** Called by Layout on mount; replays buffered event immediately if any */
    subscribe(fn: (d: CallAcceptDetail) => void) {
      _listener = fn
      if (_buffered) {
        fn(_buffered)
        _buffered = null
      }
      return () => { _listener = null }
    },
  }
})()

export { CallAcceptBus }

// ---------------------------------------------------------------------------
// Persist auth + API base so the native decline receiver can call the API
// ---------------------------------------------------------------------------
async function persistCallAuth() {
  try {
    const apiBase =
      (import.meta as any).env?.VITE_API_URL ||
      (window as any).__SKALI_API_BASE__       ||
      window.location.origin

    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token || ''

    await Preferences.configure({ group: 'skali_call_prefs' })
    await Preferences.set({ key: 'api_base_url', value: apiBase })
    await Preferences.set({ key: 'auth_token',   value: token  })
  } catch { /* best effort */ }
}

supabase.auth.onAuthStateChange(() => { persistCallAuth() })

// ---------------------------------------------------------------------------
// Read intent extras that IncomingCallActivity put on the MainActivity intent.
// MainActivity.java injects them as window.__SKALI_CALL_EXTRAS__ before the
// WebView is created (see companion MainActivity fix).
// ---------------------------------------------------------------------------
function readIntentExtras(): CallAcceptDetail | null {
  try {
    const extras = (window as any).__SKALI_CALL_EXTRAS__
    if (!extras || extras.skali_call_action !== 'accept') return null
    const room  = extras.room        as string
    const peer  = extras.from_handle as string
    const media = (extras.media || 'video') as 'audio' | 'video'
    if (!room || !peer) return null
    return { room, peer, media }
  } catch { return null }
}

// ---------------------------------------------------------------------------
// bootstrapCallHandoff  –  must run at app startup, before Layout mounts.
// Called from main.tsx (or App.tsx) once, unconditionally.
// ---------------------------------------------------------------------------
let _bootstrapped = false

export function bootstrapCallHandoff() {
  if (_bootstrapped) return
  _bootstrapped = true

  if (Capacitor.getPlatform() !== 'android') return

  // 1. Cold-start: MainActivity was launched by IncomingCallActivity with extras
  const fromExtras = readIntentExtras()
  if (fromExtras) {
    CallAcceptBus.emit(fromExtras)
  }

  // 2. Warm: app resumed via appUrlOpen (kept for forward-compat / PWA mode)
  CapApp.addListener('appUrlOpen', ({ url }) => {
    try {
      const u = new URL(url)
      if (u.protocol !== 'skali:' || u.hostname !== 'call') return
      const room  = u.searchParams.get('room')  || ''
      const peer  = u.searchParams.get('peer')  || ''
      const media = (u.searchParams.get('media') || 'video') as 'audio' | 'video'
      if (!room || !peer) return
      CallAcceptBus.emit({ room, peer, media })
    } catch { /* ignore */ }
  })
}

// ---------------------------------------------------------------------------
// configurePush  –  called from Layout after mount (needs user context)
// ---------------------------------------------------------------------------
let configured = false

export async function configurePush() {
  if (configured) return
  if (Capacitor.getPlatform() !== 'android') return
  configured = true

  persistCallAuth()

  try {
    const { PushNotifications } = await import('@capacitor/push-notifications')

    try {
      await PushNotifications.createChannel({
        id:          'high_priority',
        name:        'Messages & Calls',
        description: 'Instant alerts for new messages, media and calls',
        importance:  5,
        visibility:  1,
        sound:       'default',
        vibration:   true,
        lights:      true,
      })
    } catch { /* ignore */ }

    let perm = await PushNotifications.checkPermissions()
    if (perm.receive !== 'granted') perm = await PushNotifications.requestPermissions()
    if (perm.receive !== 'granted') { configured = false; return }

    await PushNotifications.addListener('registration', async (token) => {
      api.registerPush(token.value, 'android').catch(() => {})
      persistCallAuth()
    })
    await PushNotifications.addListener('registrationError',           () => {})
    await PushNotifications.addListener('pushNotificationReceived',    () => {})
    await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
      const data: any = action?.notification?.data || {}
      if (data?.url) { try { window.location.hash = data.url } catch { /* ignore */ } }
    })
    await PushNotifications.register()
  } catch { configured = false }
}
