import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
  useLocalParticipant,
  useConnectionState,
} from '@livekit/components-react'
import { ConnectionState, Track } from 'livekit-client'
import { api, getToken, wsLiveUrl } from '../lib/api'
import { Avatar } from '../lib/ui'
import {
  X, Loader2, Heart, Send, Radio, Users, Users2, Globe2, Save,
  Mic, MicOff, Video, VideoOff, RotateCcw,
} from 'lucide-react'

type Audience = 'followers' | 'inner'
type Creds = { id: string; room: string; server_url: string; participant_token: string; is_host?: boolean; host?: any; title?: string }

// A single floating heart that drifts up and fades.
function FloatingHearts({ hearts }: { hearts: { id: number; left: number }[] }) {
  return (
    <div className="pointer-events-none absolute bottom-28 right-3 z-30 h-64 w-24">
      {hearts.map(h => (
        <span key={h.id}
          className="absolute bottom-0 text-rose-400 animate-[floatup_2.6s_ease-out_forwards]"
          style={{ right: `${h.left}px` }}>
          <Heart className="h-7 w-7 fill-rose-500 text-rose-500 drop-shadow" />
        </span>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inner stage: renders the host's video and the chat / hearts overlay. Works
// for both the host (publishes camera) and viewers (subscribe only).
// ---------------------------------------------------------------------------
function LiveStage({
  liveId, isHost, host, title, audience, save, onClose,
}: {
  liveId: string; isHost: boolean; host: any; title?: string
  audience: Audience; save: boolean; onClose: () => void
}) {
  const { localParticipant } = useLocalParticipant()
  const connectionState = useConnectionState()
  const connected = connectionState === ConnectionState.Connected

  const [messages, setMessages] = useState<any[]>([])
  const [viewers, setViewers] = useState(0)
  const [hearts, setHearts] = useState<{ id: number; left: number }[]>([])
  const [chatText, setChatText] = useState('')
  const [micOn, setMicOn] = useState(true)
  const [camOn, setCamOn] = useState(true)
  const [facing, setFacing] = useState<'user' | 'environment'>('user')
  const [ended, setEnded] = useState(false)
  const [saving, setSaving] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const heartId = useRef(0)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const cameraTracks = useTracks([Track.Source.Camera], { onlySubscribed: true })
  const hostCam = useMemo(() => {
    if (isHost) return cameraTracks.find(t => t.participant.identity === localParticipant.identity)
    return cameraTracks.find(t => t.participant.identity !== localParticipant.identity)
  }, [cameraTracks, isHost, localParticipant.identity])

  // --- Live side channel: chat, hearts, viewer count ---
  useEffect(() => {
    const token = getToken()
    if (!token) return
    const ws = new WebSocket(wsLiveUrl(liveId, token))
    wsRef.current = ws
    ws.onmessage = ev => {
      try {
        const m = JSON.parse(ev.data)
        if (m.type === 'chat') setMessages(prev => [...prev.slice(-120), m])
        else if (m.type === 'system') setMessages(prev => [...prev.slice(-120), m])
        else if (m.type === 'viewers') setViewers(m.count || 0)
        else if (m.type === 'heart') {
          heartId.current += 1
          const id = heartId.current
          setHearts(prev => [...prev, { id, left: 8 + Math.random() * 60 }])
          setTimeout(() => setHearts(prev => prev.filter(h => h.id !== id)), 2600)
        } else if (m.type === 'live_ended' && !isHost) {
          setEnded(true)
        }
      } catch { /* ignore */ }
    }
    return () => { try { ws.close() } catch { /* noop */ } }
  }, [liveId, isHost])

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // --- Host recording (to save the broadcast to the wall on finish) ---
  const startRecording = useCallback(() => {
    if (!isHost || !save || recorderRef.current) return
    try {
      const camPub = localParticipant.getTrackPublication(Track.Source.Camera)
      const micPub = localParticipant.getTrackPublication(Track.Source.Microphone)
      const tracks: MediaStreamTrack[] = []
      if (camPub?.track?.mediaStreamTrack) tracks.push(camPub.track.mediaStreamTrack)
      if (micPub?.track?.mediaStreamTrack) tracks.push(micPub.track.mediaStreamTrack)
      if (!tracks.length) return
      const stream = new MediaStream(tracks)
      const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
        ? 'video/webm;codecs=vp8,opus' : 'video/webm'
      const rec = new MediaRecorder(stream, { mimeType: mime })
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data && e.data.size) chunksRef.current.push(e.data) }
      rec.start(1000)
      recorderRef.current = rec
    } catch (e) { console.warn('recording unavailable', e) }
  }, [isHost, save, localParticipant])

  useEffect(() => {
    if (isHost && connected && save) {
      // Small delay so LiveKit has published the camera track.
      const t = setTimeout(startRecording, 1500)
      return () => clearTimeout(t)
    }
  }, [isHost, connected, save, startRecording])

  const finishAndSave = useCallback(async (): Promise<void> => {
    const rec = recorderRef.current
    if (!rec) return
    await new Promise<void>(resolve => {
      rec.onstop = () => resolve()
      try { rec.stop() } catch { resolve() }
    })
    recorderRef.current = null
    const blob = new Blob(chunksRef.current, { type: 'video/webm' })
    chunksRef.current = []
    if (blob.size < 1000) return
    try {
      const file = new File([blob], `live-${liveId}.webm`, { type: 'video/webm' })
      const up = await api.upload(file)
      await api.createPost({
        tier: audience === 'inner' ? 'inner' : 'followers',
        text: title ? `🔴 Live replay · ${title}` : '🔴 Live replay',
        media: [{ url: up.signed_url, type: 'video' }],
      })
    } catch (e) { console.warn('save live failed', e) }
  }, [liveId, audience, title])

  const endLive = async () => {
    setSaving(save && isHost)
    try {
      if (isHost) {
        await api.liveEnd(liveId).catch(() => {})
        if (save) await finishAndSave()
      }
    } finally {
      setSaving(false)
      onClose()
    }
  }

  const sendChat = () => {
    const t = chatText.trim()
    if (!t || !wsRef.current || wsRef.current.readyState !== 1) return
    wsRef.current.send(JSON.stringify({ type: 'chat', text: t }))
    setChatText('')
  }
  const sendHeart = () => {
    wsRef.current?.readyState === 1 && wsRef.current.send(JSON.stringify({ type: 'heart' }))
  }

  const toggleMic = async () => {
    try { const on = await localParticipant.setMicrophoneEnabled(!micOn); setMicOn(on) } catch { /* noop */ }
  }
  const toggleCam = async () => {
    try {
      if (camOn) { await localParticipant.setCameraEnabled(false); setCamOn(false) }
      else { await localParticipant.setCameraEnabled(true, { facingMode: facing }); setCamOn(true) }
    } catch { /* noop */ }
  }
  const flipCam = async () => {
    try {
      const t = localParticipant.getTrackPublication(Track.Source.Camera)?.track
      if (!t) return
      const next = facing === 'user' ? 'environment' : 'user'
      await t.restartTrack({ facingMode: next }); setFacing(next)
    } catch { /* noop */ }
  }

  const hostName = host?.display_name || (isHost ? 'You' : 'Host')

  return (
    <div className="relative h-full w-full overflow-hidden bg-black">
      <RoomAudioRenderer />

      {/* Video */}
      <div className="absolute inset-0">
        {hostCam && hostCam.publication?.isSubscribed ? (
          <VideoTrack trackRef={hostCam} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full flex flex-col items-center justify-center bg-gradient-to-b from-zinc-900 to-black">
            <Avatar id={host?.handle || 'host'} name={hostName} url={host?.avatar_url} size={96} />
            <div className="mt-4 text-white/70 text-sm">
              {ended ? 'Live stream ended' : connected ? (isHost ? 'Camera off' : 'Waiting for host video…') : 'Connecting…'}
            </div>
          </div>
        )}
      </div>

      {/* Top bar: LIVE + host + viewers + close */}
      <div className="absolute top-0 inset-x-0 z-30 pt-[calc(0.6rem+env(safe-area-inset-top))] px-3">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2 py-1 rounded-md shadow" data-testid="live-badge">
            <Radio className="h-3.5 w-3.5" /> LIVE
          </span>
          <div className="flex items-center gap-2 bg-black/45 backdrop-blur rounded-full pl-1 pr-3 py-1 min-w-0">
            <Avatar id={host?.handle || 'host'} name={hostName} url={host?.avatar_url} size={26} />
            <span className="text-white text-sm font-semibold truncate max-w-[38vw]">{hostName}</span>
          </div>
          <span className="flex items-center gap-1 bg-black/45 backdrop-blur text-white text-xs px-2.5 py-1.5 rounded-full" data-testid="live-viewers">
            <Users className="h-3.5 w-3.5" />{viewers}
          </span>
          <button onClick={isHost ? endLive : onClose} data-testid="live-close"
            className="ml-auto h-9 w-9 grid place-items-center rounded-full bg-black/45 backdrop-blur text-white">
            <X className="h-5 w-5" />
          </button>
        </div>
        {title ? <div className="mt-1.5 text-white/80 text-sm px-1 truncate drop-shadow">{title}</div> : null}
      </div>

      <FloatingHearts hearts={hearts} />

      {/* Chat feed */}
      <div className="absolute left-0 right-16 bottom-24 z-20 max-h-[42%] overflow-y-auto no-scrollbar px-3 space-y-1.5"
        data-testid="live-chat">
        {messages.map((m, i) => (
          <div key={i} className="flex items-start gap-1.5">
            {m.type === 'system' ? (
              <span className="text-white/60 text-xs bg-black/35 rounded-full px-2 py-1">{m.text}</span>
            ) : (
              <span className="text-sm bg-black/40 backdrop-blur rounded-2xl px-2.5 py-1.5 max-w-full">
                <span className="text-white/70 font-semibold mr-1.5">{m.who?.display_name || m.who?.handle}</span>
                <span className="text-white break-words">{m.text}</span>
              </span>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Bottom controls */}
      <div className="absolute bottom-0 inset-x-0 z-30 pb-[calc(0.9rem+env(safe-area-inset-bottom))] px-3">
        {ended && !isHost ? (
          <button onClick={onClose} data-testid="live-ended-close"
            className="w-full py-3 rounded-xl bg-white/15 text-white font-semibold">This live has ended · Close</button>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 bg-black/45 backdrop-blur rounded-full px-3 py-2">
              <input value={chatText} onChange={e => setChatText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendChat()}
                placeholder="Say something…" data-testid="live-chat-input"
                className="flex-1 bg-transparent outline-none text-white placeholder:text-white/50 text-sm min-w-0" />
              <button onClick={sendChat} data-testid="live-chat-send" className="text-white/90 shrink-0"><Send className="h-5 w-5" /></button>
            </div>

            {isHost && (
              <>
                <button onClick={toggleMic} className={`h-11 w-11 rounded-full grid place-items-center shrink-0 ${micOn ? 'bg-white/15 text-white' : 'bg-white text-black'}`}>
                  {micOn ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
                </button>
                <button onClick={toggleCam} className={`h-11 w-11 rounded-full grid place-items-center shrink-0 ${camOn ? 'bg-white/15 text-white' : 'bg-white text-black'}`}>
                  {camOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
                </button>
                <button onClick={flipCam} className="h-11 w-11 rounded-full grid place-items-center bg-white/15 text-white shrink-0"><RotateCcw className="h-5 w-5" /></button>
              </>
            )}

            <button onClick={sendHeart} data-testid="live-heart"
              className="h-11 w-11 rounded-full grid place-items-center bg-rose-500/25 text-rose-300 shrink-0">
              <Heart className="h-5 w-5" />
            </button>

            {isHost && (
              <button onClick={endLive} disabled={saving} data-testid="live-end"
                className="h-11 px-4 rounded-full bg-rose-600 text-white font-semibold shrink-0 flex items-center gap-1.5 disabled:opacity-60">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{saving ? 'Saving…' : 'End'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Outer modal: setup (host only) -> connect (LiveKit) -> stage.
// ---------------------------------------------------------------------------
export default function LiveModal({
  mode, liveId, onClose,
}: { mode: 'host' | 'viewer'; liveId?: string; onClose: () => void }) {
  const [phase, setPhase] = useState<'setup' | 'connecting' | 'live'>(mode === 'host' ? 'setup' : 'connecting')
  const [audience, setAudience] = useState<Audience>('followers')
  const [save, setSave] = useState(false)
  const [title, setTitle] = useState('')
  const [creds, setCreds] = useState<Creds | null>(null)
  const [err, setErr] = useState('')

  const beginHost = async () => {
    setPhase('connecting'); setErr('')
    try {
      // Ask for camera + mic up front so the browser prompt appears before we connect.
      const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: true })
      s.getTracks().forEach(t => t.stop())
      const r = await api.liveStart({ audience, save, title: title.trim() })
      setCreds({ ...r, is_host: true, host: undefined, title: title.trim() })
      setPhase('live')
    } catch (e: any) {
      const name = e?.name || ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError')
        setErr('Camera and microphone permission was denied. Allow both to go live.')
      else setErr(e?.message || 'Could not start your live stream.')
      setPhase('setup')
    }
  }

  const joinViewer = useCallback(async () => {
    setErr('')
    try {
      const r = await api.liveJoin(liveId as string)
      setCreds(r)
      setPhase('live')
    } catch (e: any) {
      setErr(e?.message || 'This live stream is not available.')
    }
  }, [liveId])

  useEffect(() => { if (mode === 'viewer' && liveId) joinViewer() }, [mode, liveId, joinViewer])

  return createPortal(
    <div className="fixed inset-0 z-[90] bg-black flex flex-col" data-testid="live-modal">
      {phase === 'setup' && (
        <div className="h-full flex flex-col overflow-y-auto p-5 pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(1.25rem+env(safe-area-inset-bottom))]">
          <div className="flex items-center gap-2 mb-6">
            <span className="flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2 py-1 rounded-md"><Radio className="h-3.5 w-3.5" />GO LIVE</span>
            <button onClick={onClose} className="ml-auto h-9 w-9 grid place-items-center rounded-full bg-white/10 text-white"><X className="h-5 w-5" /></button>
          </div>

          <label className="text-xs uppercase tracking-wide text-slate-400 mb-1.5">Title (optional)</label>
          <input value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
            placeholder="What's happening?" data-testid="live-title-input"
            className="bg-panel border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand text-white mb-5" />

          <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Who can watch</div>
          <div className="grid grid-cols-2 gap-2 mb-5">
            <button onClick={() => setAudience('followers')} data-testid="live-aud-followers"
              className={`rounded-xl border p-3 text-left ${audience === 'followers' ? 'border-brand bg-brand/10' : 'border-edge bg-panel'}`}>
              <Globe2 className={`h-5 w-5 mb-1 ${audience === 'followers' ? 'text-brand' : 'text-slate-400'}`} />
              <div className="font-semibold text-white text-sm">Followers</div>
              <div className="text-xs text-slate-500">Followers + Inner Circle</div>
            </button>
            <button onClick={() => setAudience('inner')} data-testid="live-aud-inner"
              className={`rounded-xl border p-3 text-left ${audience === 'inner' ? 'border-brand bg-brand/10' : 'border-edge bg-panel'}`}>
              <Users2 className={`h-5 w-5 mb-1 ${audience === 'inner' ? 'text-brand' : 'text-slate-400'}`} />
              <div className="font-semibold text-white text-sm">Inner Circle</div>
              <div className="text-xs text-slate-500">Inner Circle only</div>
            </button>
          </div>

          <button onClick={() => setSave(s => !s)} data-testid="live-save-toggle"
            className="flex items-center gap-3 bg-panel border border-edge rounded-xl p-3 mb-auto">
            <Save className={`h-5 w-5 ${save ? 'text-brand' : 'text-slate-400'}`} />
            <div className="flex-1 text-left">
              <div className="text-sm font-medium text-white">Save to my wall when I finish</div>
              <div className="text-xs text-slate-500">Off = the stream is deleted when it ends</div>
            </div>
            <span className={`h-7 w-12 rounded-full p-0.5 transition shrink-0 ${save ? 'bg-emerald-500' : 'bg-white/15'}`}>
              <span className={`block h-6 w-6 rounded-full bg-white transition ${save ? 'translate-x-5' : ''}`} />
            </span>
          </button>

          {err && <div className="text-rose-400 text-sm mt-4">{err}</div>}
          <button onClick={beginHost} data-testid="live-start-btn"
            className="mt-4 w-full py-3.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold flex items-center justify-center gap-2">
            <Radio className="h-5 w-5" /> Start live stream
          </button>
        </div>
      )}

      {phase === 'connecting' && (
        <div className="h-full flex flex-col items-center justify-center text-white/70">
          {err ? (
            <div className="text-center px-8">
              <div className="text-rose-400 mb-4">{err}</div>
              <button onClick={onClose} className="px-5 py-2.5 rounded-xl bg-white/10 text-white">Close</button>
            </div>
          ) : (
            <><Loader2 className="h-7 w-7 animate-spin" /><span className="mt-3">{mode === 'host' ? 'Starting your live…' : 'Joining live…'}</span></>
          )}
        </div>
      )}

      {phase === 'live' && creds && (
        <div data-lk-theme="default" className="h-full w-full">
          <LiveKitRoom
            token={creds.participant_token}
            serverUrl={creds.server_url}
            connect
            audio={!!creds.is_host}
            video={!!creds.is_host}
            style={{ height: '100%', width: '100%' }}
            onDisconnected={onClose}
          >
            <LiveStage
              liveId={creds.id}
              isHost={!!creds.is_host}
              host={creds.host}
              title={creds.title}
              audience={audience}
              save={save}
              onClose={onClose}
            />
          </LiveKitRoom>
        </div>
      )}
    </div>,
    document.body,
  )
}
