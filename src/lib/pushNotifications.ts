// Drop-in replacement for src/lib/pushNotifications.ts
//
// What changed vs your current file:
//   1. After the FCM token is delivered to the backend, we also stash the
//      user's auth token + API base URL in Android SharedPreferences. The
//      native CallActionReceiver reads those to call /api/call/decline
//      while the app is out.
//   2. On cold start & resume we look for the `skali://call?...` deep link
//      that IncomingCallActivity fires when the user answers, and route the
//      SPA straight into the call room.
//
// Nothing else about your notification handling has changed.

import { Capacitor, registerPlugin } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { api } from './api'
import { supabase } from './supabase'

// A super-tiny Capacitor plugin that Just Writes To SharedPreferences.
// The Java side is a standard Capacitor Preferences read; we're using the
// bundled @capacitor/preferences plugin for the write.
import { Preferences } from '@capacitor/preferences'

let configured = false

// -----------------------------------------------------------------------------
// Persist auth + API base in a way the native decline receiver can read.
// -----------------------------------------------------------------------------
async function persistCallAuth() {
  try {
    // API base URL (must match what the app already uses at runtime).
    // Prefer the same value your api.ts uses; falling back to VITE env.
    const apiBase =
      (import.meta as any).env?.VITE_API_URL ||
      (window as any).__SKALI_API_BASE__ ||
      window.location.origin

    // Current Supabase JWT (short-lived). Native side will use it verbatim.
    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token || ''

    // @capacitor/preferences uses SharedPreferences under the hood on Android.
    // The receiver reads `skali_call_prefs` -> {api_base_url, auth_token},
    // so we must write to that named group.
    await Preferences.configure({ group: 'skali_call_prefs' })
    await Preferences.set({ key: 'api_base_url', value: apiBase })
    await Preferences.set({ key: 'auth_token',   value: token })
  } catch {
    /* best effort */
  }
}

// Re-persist whenever the session changes (login / refresh / logout).
supabase.auth.onAuthStateChange(() => { persistCallAuth() })

// -----------------------------------------------------------------------------
// Deep link from the full-screen incoming-call banner (Accept button).
// -----------------------------------------------------------------------------
function routeCallDeepLink(url: string) {
  try {
    const u = new URL(url)
    if (u.protocol !== 'skali:' || u.hostname !== 'call') return
    const room  = u.searchParams.get('room')   || ''
    const peer  = u.searchParams.get('peer')   || ''
    const media = u.searchParams.get('media')  || 'video'
    if (!room || !peer) return
    // App.tsx listens for this and opens the CallModal in "answering" mode.
    window.dispatchEvent(new CustomEvent('skali:incoming-call-accept', {
      detail: { room, peer, media },
    }))
  } catch { /* ignore malformed */ }
}

export async function configurePush() {
  if (configured) return
  if (Capacitor.getPlatform() !== 'android') return
  configured = true

  // Persist auth ASAP so a call landing seconds later can still be declined.
  persistCallAuth()

  // Cold-start deep link: IncomingCallActivity launched us with skali://call?...
  try {
    const launch = await CapApp.getLaunchUrl()
    if (launch?.url) routeCallDeepLink(launch.url)
  } catch { /* ignore */ }

  // Warm deep links (app was already backgrounded when Accept was tapped).
  CapApp.addListener('appUrlOpen', ({ url }) => routeCallDeepLink(url))

  try {
    const { PushNotifications } = await import('@capacitor/push-notifications')

    // Non-call channel (existing behaviour).
    try {
      await PushNotifications.createChannel({
        id: 'high_priority',
        name: 'Messages & Calls',
        description: 'Instant alerts for new messages, media and calls',
        importance: 5,
        visibility: 1,
        sound: 'default',
        vibration: true,
        lights: true,
      })
    } catch { /* ignore */ }

    let perm = await PushNotifications.checkPermissions()
    if (perm.receive !== 'granted') perm = await PushNotifications.requestPermissions()
    if (perm.receive !== 'granted') { configured = false; return }

    await PushNotifications.addListener('registration', async (token) => {
      api.registerPush(token.value, 'android').catch(() => {})
      // Make sure the receiver has fresh creds the moment FCM is ready.
      persistCallAuth()
    })
    await PushNotifications.addListener('registrationError', () => {})
    await PushNotifications.addListener('pushNotificationReceived', () => {
      // App is in the foreground — the badge poller already refreshes counts.
    })
    await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
      const data: any = action?.notification?.data || {}
      if (data?.url) { try { window.location.hash = data.url } catch { /* ignore */ } }
    })
    await PushNotifications.register()
  } catch { configured = false }
}
