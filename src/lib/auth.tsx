import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { supabase, signInGoogleWeb } from './supabase'
import { isNative, signInGoogleNative } from './nativeGoogle'
import { api, getToken, setToken, withRetry } from './api'

type User = { id: string; name: string; email?: string; avatar_url?: string | null }

type AuthCtx = {
  user: User | null
  loading: boolean
  loginDev: (name: string) => Promise<void>
  loginEmail: (email: string, password: string, onProgress?: (n: number) => void) => Promise<void>
  registerEmail: (email: string, password: string, name: string, dob?: string, onProgress?: (n: number) => void) => Promise<void>
  loginGoogle: () => Promise<void>
  logout: () => Promise<void>
  // Returns the loaded user (or null) so callers such as the OAuth callback can
  // tell "signed in" apart from "token was not accepted" before navigating.
  refresh: () => Promise<User | null>
}

const Ctx = createContext<AuthCtx>(null as any)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async (): Promise<User | null> => {
    // Always sync to the freshest Supabase token first (auto-refreshes an
    // expired Supabase session), then fall back to the stored token (dev login).
    try {
      const { data } = await supabase.auth.getSession()
      if (data.session?.access_token) setToken(data.session.access_token)
    } catch { /* ignore — dev-login users have no Supabase session */ }

    if (!getToken()) { setUser(null); return null }

    try {
      const me = await api.me()
      setUser(me)
      return me
    } catch (e: any) {
      if (e?.status === 401) {
        // Token rejected. Try one Supabase refresh before giving up so that
        // returning to the app after the access token expired does NOT log you out.
        try {
          const { data } = await supabase.auth.refreshSession()
          if (data.session?.access_token) {
            setToken(data.session.access_token)
            const me = await api.me()
            setUser(me)
            return me
          }
        } catch { /* no refreshable Supabase session */ }
        // Genuine auth failure (e.g. dev JWT truly expired) -> sign out.
        setToken(null)
        setUser(null)
      }
      // Any non-401 (network blip, 5xx, offline) -> keep the current session.
      return null
    }
  }, [])

  useEffect(() => {
    (async () => {
      await refresh()
      setLoading(false)
    })()

    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT') {
        setToken(null)
        setUser(null)
        return
      }
      if (session?.access_token) {
        setToken(session.access_token)
        refresh()
      }
    })
    return () => sub.subscription.unsubscribe()
  }, [refresh])

  const loginDev = async (name: string) => {
    const { access_token, user } = await api.devLogin(name)
    setToken(access_token)
    setUser(user)
  }

  const loginEmail = async (email: string, password: string, onProgress?: (n: number) => void) => {
    const { access_token, user } = await withRetry(() => api.authLogin(email, password), onProgress)
    setToken(access_token)
    setUser(user)
  }

  const registerEmail = async (email: string, password: string, name: string, dob?: string, onProgress?: (n: number) => void) => {
    const { access_token, user } = await withRetry(() => api.authRegister(email, password, name, dob), onProgress)
    setToken(access_token)
    setUser(user)
  }

  const loginGoogle = async () => {
    if (isNative()) {
      const { data } = await signInGoogleNative()
      if (data.session?.access_token) {
        setToken(data.session.access_token)
        await refresh()
      }
    } else {
      await signInGoogleWeb() // full-page redirect to Google
    }
  }

  const logout = async () => {
    await supabase.auth.signOut().catch(() => {})
    setToken(null)
    setUser(null)
  }

  return (
    <Ctx.Provider value={{ user, loading, loginDev, loginEmail, registerEmail, loginGoogle, logout, refresh }}>
      {children}
    </Ctx.Provider>
  )
}
