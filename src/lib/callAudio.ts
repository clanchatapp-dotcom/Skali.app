// In-call audio routing.
//
// The LiveKit web SDK plays remote audio inside the WebView, which defaults to
// Android's STREAM_MUSIC. That makes the volume rocker control "Media" during
// a call and forces loud-speaker routing. On native Android we bridge to the
// CallAudio plugin, which flips the system into MODE_IN_COMMUNICATION and
// requests voice-communication audio focus. On web / iOS these are no-ops.
import { registerPlugin, Capacitor } from '@capacitor/core'

interface CallAudioPlugin {
  startCall(): Promise<void>
  endCall(): Promise<void>
  setSpeakerOn(options: { on: boolean }): Promise<void>
}

const Plugin = registerPlugin<CallAudioPlugin>('CallAudio')

const isNativeAndroid = () => Capacitor.getPlatform() === 'android'

export async function startCallAudio() {
  if (!isNativeAndroid()) return
  try { await Plugin.startCall() } catch { /* plugin missing on this build — ignore */ }
}

export async function endCallAudio() {
  if (!isNativeAndroid()) return
  try { await Plugin.endCall() } catch { /* ignore */ }
}

export async function setCallSpeakerOn(on: boolean) {
  if (!isNativeAndroid()) return
  try { await Plugin.setSpeakerOn({ on }) } catch { /* ignore */ }
}
