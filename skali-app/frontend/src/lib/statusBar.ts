// Reserves real OS space for the status bar instead of letting the WebView draw
// underneath it (Android's default "edge-to-edge" behavior on newer targets).
//
// Without this, app headers only ever get an *approximate* gap from CSS
// env(safe-area-inset-top), which reports the static notch/status-bar height —
// it has no way to react to temporary system overlays (Samsung's media "Now
// Playing" pill, changing notification icons, etc.), so those can still draw
// straight over app content.
//
// With overlay:false, Android reserves the space at the native window level,
// so nothing — static or temporary — ever renders over the app again.
import { Capacitor } from '@capacitor/core'
import { StatusBar, Style } from '@capacitor/status-bar'

const isNativeAndroid = () => Capacitor.getPlatform() === 'android'

export async function initStatusBar() {
  if (!isNativeAndroid()) return
  try {
    await StatusBar.setOverlaysWebView({ overlay: false })
  } catch { /* plugin not linked on this build yet — ignore, falls back to CSS safe-area */ }
}

// Keeps the status bar's own background/icon color in sync with the app's theme toggle.
export async function setStatusBarTheme(light: boolean) {
  if (!isNativeAndroid()) return
  try {
    await StatusBar.setBackgroundColor({ color: light ? '#ffffff' : '#050507' })
    await StatusBar.setStyle({ style: light ? Style.Light : Style.Dark })
  } catch { /* ignore */ }
}
