import { useEffect, useMemo, useRef, useState } from 'react'
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useLocalParticipant,
  useTracks,
  useConnectionState,
} from '@livekit/components-react'
import { ConnectionState, Track } from 'livekit-client'
import { api } from '../lib/api'
import { startCallAudio, endCallAudio, setCallSpeakerOn } from '../lib/callAudio'
import {
  X, Loader2, Mic, MicOff, Video, VideoOff,
  PhoneOff, RotateCcw, Volume2, VolumeX,
} from 'lucide-react'

type CallMedia = 'audio' | 'video'

type CallModalProps = {
  room: string
  peer?: string
  media?: CallMedia          // now optional, defaults to 'video'
  onClose: () => void
}

function formatDuration(totalSeconds: number) {
  const s = Math.max(0, totalSeconds)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${r.toString().padStart(2, '0')}`
}

function CallScreen({
  peer, media, onClose,
}: { peer?: string; media: CallMedia; onClose: () => void }) {
  const { localParticipant } = useLocalParticipant()

  // ✅ Derive "connected" from the actual LiveKit room state.
  //    This is the fix for "Connecting…" forever.
  const connectionState = useConnectionState()
  const connected = connectionState === ConnectionState.Connected

  const connectedAtRef = useRef<number | null>(null)
  const [duration, setDuration] = useState(0)

  const [micMuted, setMicMuted] = useState(false)
  const [cameraEnabled, setCameraEnabled] = useState(media === 'video')
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('user')

  // Default: video calls -> loudspeaker, voice calls -> earpiece (matches native
  // phone behaviour so audio calls aren't blasted through the speaker).
  const [speakerOn, setSpeakerOn] = useState(media === 'video')

  const cameraTracks = useTracks([Track.Source.Camera], { onlySubscribed: true })

  const remoteCameraTrack = useMemo(
    () => cameraTracks.find(t => t.participant.identity !== localParticipant.identity),
    [cameraTracks, localParticipant.identity],
  )
  const localCameraTrack = useMemo(
    () => cameraTracks.find(t => t.participant.identity === localParticipant.identity),
    [cameraTracks, localParticipant.identity],
  )

  // Start the call timer AND flip Android into voice-communication mode the
  // moment the room reports Connected. endCall() is invoked by the parent
  // CallModal's cleanup so it also fires on abnormal teardown.
  useEffect(() => {
    if (!connected) return
    if (connectedAtRef.current == null) connectedAtRef.current = Date.now()

    // Route audio through the in-call stream on Android and sync the initial
    // speakerphone state with our UI toggle.
    void startCallAudio().then(() => setCallSpeakerOn(speakerOn))

    const timer = window.setInterval(() => {
      if (connectedAtRef.current != null) {
        setDuration(Math.floor((Date.now() - connectedAtRef.current) / 1000))
      }
    }, 1000)
    return () => window.clearInterval(timer)
    // speakerOn intentionally omitted — we only want this to run on connect,
    // not every time the user toggles the speaker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected])

  const toggleMic = async () => {
    try {
      const enabled = await localParticipant.setMicrophoneEnabled(micMuted)
      setMicMuted(!enabled)
    } catch (e) { console.error('mic toggle:', e) }
  }

  const toggleCamera = async () => {
    if (media !== 'video') return
    try {
      if (cameraEnabled) {
        await localParticipant.setCameraEnabled(false)
        setCameraEnabled(false)
      } else {
        await localParticipant.setCameraEnabled(true, { facingMode })
        setCameraEnabled(true)
      }
    } catch (e) { console.error('camera toggle:', e) }
  }

  const flipCamera = async () => {
    if (media !== 'video' || !cameraEnabled) return
    try {
      const pub = localParticipant.getTrackPublication(Track.Source.Camera)
      const t = pub?.track
      if (!t) return
      const next = facingMode === 'user' ? 'environment' : 'user'
      await t.restartTrack({ facingMode: next })
      setFacingMode(next)
    } catch (e) { console.error('flip camera:', e) }
  }

  const toggleSpeaker = () => {
    const next = !speakerOn
    setSpeakerOn(next)
    // Route audio to loudspeaker vs earpiece on Android. RoomAudioRenderer
    // still handles the on/off volume in the WebView.
    void setCallSpeakerOn(next)
  }

  const statusLabel = connected
    ? formatDuration(duration)
    : connectionState === ConnectionState.Reconnecting
    ? 'Reconnecting…'
    : 'Connecting…'

  return (
    <div className="relative h-full w-full overflow-hidden bg-black">
      {/* Plays every remote participant's audio track. Without this, LiveKit
          never attaches remote audio to the page, so you would see video but
          hear nothing. Volume is driven by the speaker toggle below. */}
      <RoomAudioRenderer volume={speakerOn ? 1 : 0} />
      {media === 'video' ? (
        <>
          <div className="absolute inset-0">
            {remoteCameraTrack && remoteCameraTrack.publication.isSubscribed ? (
              <VideoTrack trackRef={remoteCameraTrack} className="h-full w-full object-cover" />
            ) : (
              <div className="h-full w-full flex flex-col items-center justify-center bg-black">
                <div className="h-28 w-28 rounded-full bg-white/10 border border-white/10 grid place-items-center text-4xl font-semibold text-white">
                  {peer ? peer.replace(/^@/, '').charAt(0).toUpperCase() : '?'}
                </div>
                <div className="mt-5 text-xl font-semibold text-white">
                  {peer ? `@${peer.replace(/^@/, '')}` : 'Skali user'}
                </div>
                <div className="mt-2 text-sm text-white/60">
                  {connected ? 'Camera off' : statusLabel}
                </div>
              </div>
            )}
          </div>

          <div className="absolute top-0 left-0 right-0 z-20 pt-[env(safe-area-inset-top)]">
            <div className="px-4 pt-4 flex items-start justify-between">
              <div className="min-w-0">
                <div className="text-white font-semibold text-lg truncate drop-shadow">
                  {peer ? `@${peer.replace(/^@/, '')}` : 'Skali user'}
                </div>
                <div className="text-white/70 text-sm mt-0.5">{statusLabel}</div>
              </div>
              <button onClick={onClose}
                className="h-10 w-10 rounded-full bg-black/40 backdrop-blur grid place-items-center text-white"
                aria-label="Close call">
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {cameraEnabled && localCameraTrack && localCameraTrack.publication.isSubscribed ? (
            <div className="absolute top-24 right-4 z-20 w-28 h-40 sm:w-36 sm:h-48 rounded-2xl overflow-hidden border border-white/30 bg-black shadow-2xl">
              <VideoTrack trackRef={localCameraTrack} className="h-full w-full object-cover" />
            </div>
          ) : (
            <div className="absolute top-24 right-4 z-20 w-28 h-40 sm:w-36 sm:h-48 rounded-2xl overflow-hidden border border-white/20 bg-zinc-900 grid place-items-center">
              <VideoOff className="h-7 w-7 text-white/60" />
            </div>
          )}
        </>
      ) : (
        <div className="h-full w-full flex flex-col items-center justify-center px-6">
          <div className="h-32 w-32 rounded-full bg-white/10 border border-white/10 grid place-items-center text-5xl font-semibold text-white">
            {peer ? peer.replace(/^@/, '').charAt(0).toUpperCase() : '?'}
          </div>
          <div className="mt-7 text-2xl font-semibold text-white">
            {peer ? `@${peer.replace(/^@/, '')}` : 'Skali user'}
          </div>
          <div className="mt-2 text-white/60 text-sm">{statusLabel}</div>
          {!connected && (
            <div className="mt-4 flex items-center gap-2 text-white/40 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              {connectionState === ConnectionState.Reconnecting ? 'Reconnecting' : 'Connecting'}
            </div>
          )}
        </div>
      )}

      <div className="absolute bottom-0 left-0 right-0 z-30 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
        <div className="flex items-center justify-center gap-4 px-5">
          <button onClick={toggleMic}
            className={`h-14 w-14 rounded-full grid place-items-center text-white transition ${micMuted ? 'bg-white' : 'bg-white/15 backdrop-blur'}`}
            aria-label={micMuted ? 'Unmute microphone' : 'Mute microphone'}>
            {micMuted ? <MicOff className="h-6 w-6 text-black" /> : <Mic className="h-6 w-6" />}
          </button>

          <button onClick={toggleSpeaker}
            className={`h-14 w-14 rounded-full grid place-items-center text-white transition ${speakerOn ? 'bg-white/15 backdrop-blur' : 'bg-white'}`}
            aria-label={speakerOn ? 'Speaker on' : 'Speaker off'}>
            {speakerOn ? <Volume2 className="h-6 w-6" /> : <VolumeX className="h-6 w-6 text-black" />}
          </button>

          {media === 'video' && (
            <>
              <button onClick={toggleCamera}
                className={`h-14 w-14 rounded-full grid place-items-center text-white transition ${cameraEnabled ? 'bg-white/15 backdrop-blur' : 'bg-white'}`}
                aria-label={cameraEnabled ? 'Turn camera off' : 'Turn camera on'}>
                {cameraEnabled ? <Video className="h-6 w-6" /> : <VideoOff className="h-6 w-6 text-black" />}
              </button>
              <button onClick={flipCamera} disabled={!cameraEnabled}
                className={`h-14 w-14 rounded-full grid place-items-center text-white transition ${cameraEnabled ? 'bg-white/15 backdrop-blur' : 'bg-white/5 text-white/20'}`}
                aria-label="Flip camera">
                <RotateCcw className="h-6 w-6" />
              </button>
            </>
          )}

          <button onClick={onClose}
            className="h-16 w-16 rounded-full bg-red-600 hover:bg-red-500 grid place-items-center text-white shadow-xl"
            aria-label="End call">
            <PhoneOff className="h-7 w-7" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function CallModal({
  room, peer, media = 'video', onClose,
}: CallModalProps) {
  const [creds, setCreds] = useState<{ server_url: string; participant_token: string } | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let cancelled = false
    let mediaStream: MediaStream | null = null

    async function startCall() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: media === 'video',
        })
        mediaStream.getTracks().forEach(t => t.stop())
        mediaStream = null
        if (cancelled) return

        const result = await api.livekitToken(room, peer)
        if (cancelled) return
        setCreds(result)
      } catch (e: any) {
        if (cancelled) return
        console.error('Call permission / startup error:', e)
        const name = e?.name || ''
        const message = e?.message || ''
        if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
          setErr(media === 'video'
            ? 'Camera and microphone permission was denied. Please allow both in Android Settings.'
            : 'Microphone permission was denied. Please allow it in Android Settings.')
        } else if (name === 'NotFoundError') {
          setErr(media === 'video'
            ? 'No camera or microphone could be found on this device.'
            : 'No microphone could be found on this device.')
        } else {
          setErr(message || 'Unable to start the call.')
        }
      }
    }

    startCall()

    return () => {
      cancelled = true
      if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop())
        mediaStream = null
      }
      // Always restore the system audio mode / focus, whether the call ended
      // normally, via error, or because the modal was force-closed.
      void endCallAudio()
    }
  }, [room, peer, media])

  return (
    <div className="fixed inset-0 z-[60] bg-black flex flex-col pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      {err ? (
        <div className="h-full flex flex-col items-center justify-center px-6 text-center">
          <div className="h-20 w-20 rounded-full bg-red-500/10 grid place-items-center mb-5">
            {media === 'video' ? <VideoOff className="h-9 w-9 text-red-400" /> : <MicOff className="h-9 w-9 text-red-400" />}
          </div>
          <div className="max-w-sm text-red-400">{err}</div>
          <button onClick={onClose} className="mt-6 px-5 py-3 rounded-xl bg-white/10 text-white">Close</button>
        </div>
      ) : !creds ? (
        <div className="h-full flex flex-col items-center justify-center text-white/60">
          <Loader2 className="h-7 w-7 animate-spin" />
          <span className="mt-3">{media === 'video' ? 'Starting video call…' : 'Starting voice call…'}</span>
        </div>
      ) : (
        <div data-lk-theme="default" className="h-full w-full">
          <LiveKitRoom
            token={creds.participant_token}
            serverUrl={creds.server_url}
            connect={true}
            audio={true}
            video={media === 'video'}
            style={{ height: '100%', width: '100%' }}
            onDisconnected={onClose}
          >
            <CallScreen peer={peer} media={media} onClose={onClose} />
          </LiveKitRoom>
        </div>
      )}
    </div>
  )
}
