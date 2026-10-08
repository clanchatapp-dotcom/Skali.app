// Screenshot / screen-record protection.
// On native Android this calls the PrivacyScreen plugin (FLAG_SECURE, OS-enforced).
// On web/iOS there is no OS-level equivalent, so these are no-ops and the UI shows
// an honest banner instead.
import { registerPlugin, Capacitor } from '@capacitor/core'

interface PrivacyScreenPlugin {
  enable(): Promise<void>
  disable(): Promise<void>
}

const Plugin = registerPlugin<PrivacyScreenPlugin>('PrivacyScreen')

export const isNativeAndroid = () => Capacitor.getPlatform() === 'android'

// Screenshot blocking is only actually enforceable on native Android.
export const screenshotProtectionAvailable = () => isNativeAndroid()

export async function secureOn() {
  if (!isNativeAndroid()) return
  try { await Plugin.enable() } catch { /* plugin missing on this build — ignore */ }
}

export async function secureOff() {
  if (!isNativeAndroid()) return
  try { await Plugin.disable() } catch { /* ignore */ }
}
