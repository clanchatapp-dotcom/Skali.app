// Native (Android/iOS) Google sign-in via @capgo/capacitor-social-login@7.
// These paths only run inside the Capacitor native shell; on web they no-op.
import { Capacitor } from '@capacitor/core'
import { supabase } from './supabase'

const env = (import.meta as any).env
// IMPORTANT (Google [16] "Account reauth failed" fix):
// Native Google Sign-In MUST be given the **Web application** OAuth client ID as
// `webClientId` (this is the "server client ID" Google mints the ID token for).
// NEVER put the Android client ID here — doing so causes error [16].
// Client IDs are public and safe to ship; the baked default keeps native sign-in
// working even if no CI env var is set. Web + Android clients must be in the SAME
// Google Cloud project (skaliapp-e0dee, 572913753788), and the Android client must carry the app's
// package name (app.skali.mobile) + release SHA-1.
const PUBLIC_GOOGLE_WEB_CLIENT_ID = '572913753788-il245hv6t2tss0bc097c4jfk4cumpii8.apps.googleusercontent.com'
const WEB_CLIENT_ID = ((env.REACT_APP_GOOGLE_WEB_CLIENT_ID as string) || '').trim() || PUBLIC_GOOGLE_WEB_CLIENT_ID

export function isNative(): boolean {
  try { return Capacitor.isNativePlatform() } catch { return false }
}

let initialized = false

export async function initGoogle(): Promise<void> {
  if (initialized || !isNative()) return
  // Guard: a valid web client id ends in .apps.googleusercontent.com. If someone ever
  // wires an obviously-wrong value we log loudly (visible in `adb logcat`) instead of
  // failing silently with [16].
  if (!WEB_CLIENT_ID.endsWith('.apps.googleusercontent.com')) {
    console.error('[Google] Invalid webClientId — must be the WEB OAuth client:', WEB_CLIENT_ID)
  }
  console.info('[Google] initializing native sign-in with webClientId =', WEB_CLIENT_ID)
  const { SocialLogin } = await import('@capgo/capacitor-social-login')
  await SocialLogin.initialize({
    google: { webClientId: WEB_CLIENT_ID, mode: 'online' },
  })
  initialized = true
}

export async function signInGoogleNative() {
  await initGoogle()
  const { SocialLogin } = await import('@capgo/capacitor-social-login')
  // NOTE: do NOT pass `scopes` here — the capgo v7 plugin rejects custom scopes
  // ("You CANNOT use scopes without modifying the main activity") for the basic
  // online flow. Omitting them uses Google's default email/profile scopes, which
  // is exactly what we need for Supabase signInWithIdToken.
  const res: any = await SocialLogin.login({
    provider: 'google',
    options: {},
  })
  const idToken = res?.result?.idToken
  if (!idToken) throw new Error('No idToken from Google')
  return supabase.auth.signInWithIdToken({ provider: 'google', token: idToken })
}
