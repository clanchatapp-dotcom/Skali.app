
import { Capacitor, registerPlugin } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { Preferences } from '@capacitor/preferences'
import { api } from './api'
import { supabase } from './supabase'
import { getWebMessaging } from './firebase'
import { getToken, onMessage } from 'firebase/messaging'

// ---------------------------------------------------------------------------
// CallAcceptBus — buffers a cold-start call accept until Layout subscribes
// ---------------------------------------------------------------------------

type CallAcceptDetail = {
  room: string
  peer: string
  media: 'audio' | 'video'
}

const CallAcceptBus = (() => {
  let buffered: CallAcceptDetail | null = null
  let listener: ((detail: CallAcceptDetail) => void) | null = null

  return {
    emit(detail: CallAcceptDetail) {
      if (listener) listener(detail)
      else buffered = detail
    },

    subscribe(fn: (detail: CallAcceptDetail) => void) {
      listener = fn

      if (buffered) {
        fn(buffered)
        buffered = null
      }

      return () => {
        listener = null
      }
    },
  }
})()

export { CallAcceptBus }

// ---------------------------------------------------------------------------
// Persist auth + API base for the native decline receiver
// ---------------------------------------------------------------------------

async function persistCallAuth() {
  try {
    const apiBase =
      (import.meta as any).env?.VITE_API_URL ||
      (window as any).__SKALI_API_BASE__ ||
      window.location.origin

    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token || ''

    await Preferences.configure({ group: 'skali_call_prefs' })
    await Preferences.set({ key: 'api_base_url', value: apiBase })
    await Preferences.set({ key: 'auth_token', value: token })
  } catch {
    // Best effort; native call handling must not block app startup.
  }
}

supabase.auth.onAuthStateChange(() => {
  void persistCallAuth()
})

// ---------------------------------------------------------------------------
// Read call-accept extras injected by MainActivity.java
// ---------------------------------------------------------------------------

function readIntentExtras(): CallAcceptDetail | null {
  try {
    const extras = (window as any).__SKALI_CALL_EXTRAS__
    if (!extras || extras.skali_call_action !== 'accept') return null

    const room = extras.room as string
    const peer = extras.from_handle as string
    const media = (extras.media || 'video') as 'audio' | 'video'

    if (!room || !peer) return null

    return { room, peer, media }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Bootstrap call handoff before React mounts
// ---------------------------------------------------------------------------

let bootstrapped = false

export function bootstrapCallHandoff() {
  if (bootstrapped) return
  bootstrapped = true

  if (Capacitor.getPlatform() !== 'android') return

  const fromExtras = readIntentExtras()

  if (fromExtras) {
    CallAcceptBus.emit(fromExtras)
  }

  CapApp.addListener('appUrlOpen', ({ url }) => {
    try {
      const parsed = new URL(url)

      if (parsed.protocol !== 'skali:' || parsed.hostname !== 'call') {
        return
      }

      const room = parsed.searchParams.get('room') || ''
      const peer = parsed.searchParams.get('peer') || ''
      const media = (parsed.searchParams.get('media') || 'video') as
        | 'audio'
        | 'video'

      if (!room || !peer) return

      CallAcceptBus.emit({ room, peer, media })
    } catch {
      // Ignore malformed deep links.
    }
  })
}

// ---------------------------------------------------------------------------
// Push configuration
// ---------------------------------------------------------------------------

let androidConfigured = false
let webConfigured = false

const WEB_VAPID_KEY =
  'BNppFLpE9-QB8wTzHjv9ddGM7wO0GAns6bIhOJQsc0PI7DP8gAWlSS7OcWVVrPz06WHqjho9Qy_p2iAKoY9DJYs'

// ---------------------------------------------------------------------------
// Android push — preserve the existing Capacitor implementation
// ---------------------------------------------------------------------------

async function configureAndroidPush() {
  if (androidConfigured) return
  androidConfigured = true

  void persistCallAuth()

  try {
    const { PushNotifications } = await import(
      '@capacitor/push-notifications'
    )

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
    } catch {
      // The channel may already exist.
    }

    let permission = await PushNotifications.checkPermissions()

    if (permission.receive !== 'granted') {
      permission = await PushNotifications.requestPermissions()
    }

    if (permission.receive !== 'granted') {
      androidConfigured = false
      return
    }

    await PushNotifications.addListener('registration', async (token) => {
      api.registerPush(token.value, 'android').catch(() => {})
      void persistCallAuth()
    })

    await PushNotifications.addListener('registrationError', () => {})

    await PushNotifications.addListener(
      'pushNotificationReceived',
      () => {},
    )

    await PushNotifications.addListener(
      'pushNotificationActionPerformed',
      (action) => {
        const data: any = action?.notification?.data || {}

        if (data?.url) {
          try {
            window.location.hash = data.url
          } catch {
            // Ignore navigation errors.
          }
        }
      },
    )

    await PushNotifications.register()
  } catch (error) {
    console.error('[Push] Android setup failed:', error)
    androidConfigured = false
  }
}

// ---------------------------------------------------------------------------
// Web push — Firebase Cloud Messaging
// ---------------------------------------------------------------------------

async function configureWebPush() {
  if (webConfigured) return
  webConfigured = true

  try {
    if (!('serviceWorker' in navigator) || !('Notification' in window)) {
      webConfigured = false
      return
    }

    if (!window.isSecureContext) {
      console.warn('[Push] Web push requires HTTPS or localhost.')
      webConfigured = false
      return
    }

    const messaging = await getWebMessaging()

    if (!messaging) {
      webConfigured = false
      return
    }

    // Register the service worker used for background notifications.
    const registration = await navigator.serviceWorker.register(
      '/firebase-messaging-sw.js',
    )

    let permission = Notification.permission

    if (permission === 'default') {
      permission = await Notification.requestPermission()
    }

    if (permission !== 'granted') {
      webConfigured = false
      return
    }

    const token = await getToken(messaging, {
      vapidKey: WEB_VAPID_KEY,
      serviceWorkerRegistration: registration,
    })

    if (!token) {
      console.warn('[Push] Firebase did not return a web token.')
      webConfigured = false
      return
    }

    await api.registerPush(token, 'web')

    // Foreground messages are received here. Background messages are handled
    // by firebase-messaging-sw.js.
    onMessage(messaging, (payload) => {
      window.dispatchEvent(
        new CustomEvent('skali:web-push', { detail: payload }),
      )
    })
  } catch (error) {
    console.error('[Push] Web setup failed:', error)
    webConfigured = false
  }
}

// ---------------------------------------------------------------------------
// Public entry point — native Android and browser web push
// ---------------------------------------------------------------------------

export async function configurePush() {
  const platform = Capacitor.getPlatform()

  if (platform === 'android') {
    await configureAndroidPush()
    return
  }

  if (platform === 'web') {
    await configureWebPush()
  }
}
