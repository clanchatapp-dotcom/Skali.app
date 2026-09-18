import { useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { App as CapApp } from '@capacitor/app'
import { Capacitor } from '@capacitor/core'

// Android hardware/gesture back-button behaviour:
//  - On the feed ("/"), double-tap back within 2s to exit the app (single tap shows a hint).
//  - Anywhere else, back navigates to the previous screen (or the feed if there's no history).
export function useAndroidBackButton() {
  const nav = useNavigate()
  const loc = useLocation()
  const lastBack = useRef(0)
  const locRef = useRef(loc)
  locRef.current = loc

  useEffect(() => {
    if (Capacitor.getPlatform() !== 'android') return
    let handle: any
    const setup = async () => {
      handle = await CapApp.addListener('backButton', ({ canGoBack }) => {
        const path = locRef.current.pathname
        const atRoot = path === '/'
        if (atRoot) {
          const now = Date.now()
          if (now - lastBack.current < 2000) {
            CapApp.exitApp()
          } else {
            lastBack.current = now
            // Lightweight hint; avoids adding a toast dependency.
            try { window.dispatchEvent(new CustomEvent('cc-back-hint')) } catch {}
          }
        } else if (canGoBack) {
          nav(-1)
        } else {
          nav('/')
        }
      })
    }
    setup()
    return () => { try { handle?.remove?.() } catch {} }
  }, [nav])
}
