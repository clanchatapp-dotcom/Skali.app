import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useWatchHeartbeat } from '../lib/watchTime'
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
  useLocalParticipant,
  useConnectionState,
  useDataChannel,
  useRemoteParticipants,
} from '@livekit/components-react'
import { ConnectionState, Track } from 'livekit-client'
import { api, getToken, wsLiveUrl } from '../lib/api'

// Chat + hearts travel over LiveKit's own data channel (it is already connected
// for the video, so it works even where the separate side-channel WebSocket is
// blocked — e.g. inside the Android WebView). TextEncoder/Decoder are reused.
const LIVE_DC_TOPIC = 'skali-live'
const dcEncoder = new TextEncoder()
const dcDecoder = new TextDecoder()
import { Avatar } from '../lib/ui'
import { LIVE_CATEGORIES, categoryOf } from '../lib/liveCategories'
import { Capacitor } from '@capacitor/core'
import { useAuth } from '../lib/auth'
import ObsStudioPanel from './stream/ObsStudioPanel'
import StreamBoundary from './stream/StreamBoundary'
import {
  X, Loader2, Heart, Send, Radio, Users, Users2, Globe2, Save, Lock,
  Mic, MicOff, Video, VideoOff, RotateCcw, MonitorPlay, Camera,
} from 'lucide-react'

const isNativeApp = (() => { try { return Capacitor.isNativePlatform() } catch { return false } })()

type Audience = 'public' | 'followers' | 'inner' | 'group'
type Creds = { id: string; room: string; server_url: string; participant_token: string; is_host?: boolean; host?: any; title?: string; category?: string; audience?: string }

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

function ChatRow({ m }: { m: any }) {
  if (m.type === 'system') return <div className="text-white/60 text-xs">{m.text}</div>
  return (
    <div className="text-sm leading-snug break-words">
      <span className="text-brand font-semibold mr-1.5">{m.who?.display_name || m.who?.handle}</span>
      <span className="text-white/90">{m.text}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inner stage: host video + chat/hearts. Mobile keeps the overlay; desktop
// adds a Twitch-style chat rail. Chat + hearts ride the LiveKit data channel.
// ---------------------------------------------------------------------------
function LiveStage({
  liveId, isHost, host, title, category, audience, save, onClose,
}: {
  liveId: string; isHost: boolean; host: any; title?: string; category?: string
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
  const chatEndRef2 = useRef<HTMLDivElement | null>(null)
  const heartId = useRef(0)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const cat = categoryOf(category)
  const CatIcon = cat.icon

  const cameraTracks = useTracks([Track.Source.Camera], { onlySubscribed: true })
  const remoteParticipants = useRemoteParticipants()
  const liveCount = Math.max(viewers, remoteParticipants.length + 1)
  const hostCam = useMemo(() => {
    if (isHost) return cameraTracks.find(t => t.participant.identity === localParticipant.identity)
    return cameraTracks.find(t => t.participant.identity !== localParticipant.identity)
  }, [cameraTracks, isHost, localParticipant.identity])

  // Side-channel WS: live viewer count, join notices and end events only.
  useEffect(() => {
    const token = getToken()
    if (!token) return
    let closed = false
    let retry = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const open = () => {
      if (closed) return
      const ws = new WebSocket(wsLiveUrl(liveId, token))
      wsRef.current = ws
      ws.onopen = () => { retry = 0 }
      ws.onmessage = ev => {
        try {
          const m = JSON.parse(ev.data)
          if (m.type === 'system') setMessages(prev => [...prev.slice(-120), m])
          else if (m.type === 'viewers') setViewers(m.count || 0)
          else if (m.type === 'live_ended' && !isHost) setEnded(true)
        } catch { /* ignore */ }
      }
      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null
        if (closed) return
        retry += 1
        reconnectTimer = setTimeout(open, Math.min(1000 * retry, 5000))
      }
      ws.onerror = () => { try { ws.close() } catch { /* noop */ } }
    }

    open()
    return () => {
      closed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      try { wsRef.current?.close() } catch { /* noop */ }
      wsRef.current = null
    }
  }, [liveId, isHost])

  // Chat + hearts over the LiveKit data channel (reliable P2P; no self-echo).
  const { send: sendData } = useDataChannel(LIVE_DC_TOPIC, (msg) => {
    try {
      const d = JSON.parse(dcDecoder.decode(msg.payload))
      const name = (msg.from?.name || '').replace(/^#/, '') || msg.from?.identity || 'Guest'
      if (d.t === 'chat' && d.text) {
        setMessages(prev => [...prev.slice(-120), { type: 'chat', who: { display_name: name }, text: String(d.text) }])
      } else if (d.t === 'heart') {
        heartId.current += 1
        const id = heartId.current
        setHearts(prev => [...prev, { id, left: 8 + Math.random() * 60 }])
        setTimeout(() => setHearts(prev => prev.filter(h => h.id !== id)), 2600)
      }
    } catch { /* ignore */ }
  })

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    chatEndRef2.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
        tier: audience === 'inner' ? 'inner' : audience === 'public' ? 'public' : 'followers',
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

  const myName = () => (localParticipant.name || '').replace(/^#/, '') || 'You'

  const sendChat = () => {
    const t = chatText.trim()
    if (!t) return
    setMessages(prev => [...prev.slice(-120), { type: 'chat', who: { display_name: myName() }, text: t }])
    try { sendData(dcEncoder.encode(JSON.stringify({ t: 'chat', text: t })), { reliable: true }) } catch { /* noop */ }
    setChatText('')
  }
  const sendHeart = () => {
    heartId.current += 1
    const id = heartId.current
    setHearts(prev => [...prev, { id, left: 8 + Math.random() * 60 }])
    setTimeout(() => setHearts(prev => prev.filter(h => h.id !== id)), 2600)
    try { sendData(dcEncoder.encode(JSON.stringify({ t: 'heart' })), { reliable: true }) } catch { /* noop */ }
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
    <div className="relative h-full w-full overflow-hidden bg-black md:flex md:flex-row">
      <RoomAudioRenderer />

      {/* ---- Video column ---- */}
      <div className="relative flex-1 min-w-0 h-full overflow-hidden">
        <div className="absolute inset-0">
          {hostCam && hostCam.publication?.isSubscribed ? (
            <VideoTrack trackRef={hostCam} className="h-full w-full object-cover md:object-contain" />
          ) : (
            <div className="h-full w-full flex flex-col items-center justify-center bg-gradient-to-b from-zinc-900 to-black">
              <Avatar id={host?.handle || 'host'} name={hostName} url={host?.avatar_url} size={96} />
              <div className="mt-4 text-white/70 text-sm">
                {ended ? 'Live stream ended' : connected ? (isHost ? 'Camera off' : 'Waiting for host video…') : 'Connecting…'}
              </div>
            </div>
          )}
        </div>

        {/* Top bar */}
        <div className="absolute top-0 inset-x-0 z-30 pt-[calc(0.6rem+env(safe-area-inset-top))] px-3">
          <div className="flex items-center gap-2">
            <span className="neon-live flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2 py-1 rounded-md shadow" data-testid="live-badge">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" /> LIVE
            </span>
            <div className="flex items-center gap-2 bg-black/45 backdrop-blur rounded-full pl-1 pr-3 py-1 min-w-0">
              <Avatar id={host?.handle || 'host'} name={hostName} url={host?.avatar_url} size={26} />
              <span className="text-white text-sm font-semibold truncate max-w-[32vw] md:max-w-[220px]">{hostName}</span>
            </div>
            <span className={`hidden sm:flex items-center gap-1 bg-black/45 backdrop-blur text-xs px-2.5 py-1.5 rounded-full ${cat.accent}`}>
              <CatIcon className="h-3.5 w-3.5" />{cat.label}
            </span>
            <span className="flex items-center gap-1 bg-black/45 backdrop-blur text-white text-xs px-2.5 py-1.5 rounded-full" data-testid="live-viewers">
              <Users className="h-3.5 w-3.5" />{liveCount}
            </span>
            <button onClick={isHost ? endLive : onClose} data-testid="live-close"
              className="ml-auto h-9 w-9 grid place-items-center rounded-full bg-black/45 backdrop-blur text-white">
              <X className="h-5 w-5" />
            </button>
          </div>
          {title ? <div className="mt-1.5 text-white/85 text-sm px-1 truncate drop-shadow font-medium">{title}</div> : null}
        </div>

        <FloatingHearts hearts={hearts} />

        {/* Chat feed — MOBILE overlay only */}
        <div className="md:hidden absolute left-0 right-16 bottom-24 z-20 max-h-[42%] overflow-y-auto no-scrollbar px-3 space-y-1.5"
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

        {/* Bottom controls (host both platforms; viewer MOBILE only) */}
        <div className="absolute bottom-0 inset-x-0 z-30 pb-[calc(0.9rem+env(safe-area-inset-bottom))] px-3">
          {ended && !isHost ? (
            <button onClick={onClose} data-testid="live-ended-close"
              className="w-full py-3 rounded-xl bg-white/15 text-white font-semibold md:max-w-xs md:mx-auto md:block">This live has ended · Close</button>
          ) : isHost ? (
            <div className="flex items-center justify-center gap-3">
              <button onClick={toggleMic} data-testid="live-mic-toggle" aria-label={micOn ? 'Mute mic' : 'Unmute mic'}
                className={`h-12 w-12 rounded-full grid place-items-center shrink-0 ${micOn ? 'bg-white/15 text-white' : 'bg-white text-black'}`}>
                {micOn ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
              </button>
              <button onClick={toggleCam} data-testid="live-cam-toggle" aria-label={camOn ? 'Turn cam off' : 'Turn cam on'}
                className={`h-12 w-12 rounded-full grid place-items-center shrink-0 ${camOn ? 'bg-white/15 text-white' : 'bg-white text-black'}`}>
                {camOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
              </button>
              <button onClick={flipCam} data-testid="live-flip-cam" aria-label="Turn cam around"
                className="h-12 w-12 rounded-full grid place-items-center bg-white/15 text-white shrink-0"><RotateCcw className="h-5 w-5" /></button>
              <button onClick={endLive} disabled={saving} data-testid="live-end"
                className="h-12 px-5 rounded-full bg-rose-600 text-white font-semibold shrink-0 flex items-center gap-1.5 disabled:opacity-60">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{saving ? 'Saving…' : 'End live'}
              </button>
            </div>
          ) : (
            <div className="md:hidden flex items-center gap-2">
              <div className="flex-1 flex items-center gap-2 bg-black/45 backdrop-blur rounded-full px-3 py-2">
                <input value={chatText} onChange={e => setChatText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendChat()}
                  placeholder="Say something…" data-testid="live-chat-input"
                  className="flex-1 bg-transparent outline-none text-white placeholder:text-white/50 text-sm min-w-0" />
                <button onClick={sendChat} data-testid="live-chat-send" className="text-white/90 shrink-0"><Send className="h-5 w-5" /></button>
              </div>
              <button onClick={sendHeart} data-testid="live-heart"
                className="h-11 w-11 rounded-full grid place-items-center bg-rose-500/25 text-rose-300 shrink-0">
                <Heart className="h-5 w-5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ---- Desktop chat sidebar (Twitch-style) ---- */}
      <aside className="hidden md:flex md:flex-col w-[360px] shrink-0 h-full bg-ink border-l border-white/10">
        <div className="px-4 py-3 border-b border-white/10">
          <div className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="h-4 w-4 text-brand" /> Stream chat
            <span className="ml-auto text-xs text-slate-400 font-medium">{liveCount} watching</span>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2" data-testid="live-chat-desktop">
          {messages.length === 0 && <div className="text-slate-500 text-sm">Say hi to start the conversation.</div>}
          {messages.map((m, i) => <ChatRow key={i} m={m} />)}
          <div ref={chatEndRef2} />
        </div>
        {!ended && (
          <div className="p-3 border-t border-white/10">
            <div className="flex items-center gap-2">
              <div className="flex-1 flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-3 py-2">
                <input value={chatText} onChange={e => setChatText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendChat()}
                  placeholder="Send a message…" data-testid="live-chat-input-desktop"
                  className="flex-1 bg-transparent outline-none text-white placeholder:text-white/40 text-sm min-w-0" />
                <button onClick={sendChat} data-testid="live-chat-send-desktop" className="text-brand shrink-0"><Send className="h-5 w-5" /></button>
              </div>
              <button onClick={sendHeart} data-testid="live-heart-desktop"
                className="h-10 w-10 rounded-full grid place-items-center bg-rose-500/20 text-rose-300 shrink-0 hover:bg-rose-500/30 transition">
                <Heart className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Outer modal: setup (host only) -> connect (LiveKit) -> stage.
// ---------------------------------------------------------------------------
export default function LiveModal({
  mode, liveId, onClose, kind = 'stream',
}: { mode: 'host' | 'viewer'; liveId?: string; onClose: () => void; kind?: 'story' | 'stream' }) {
  const [phase, setPhase] = useState<'setup' | 'connecting' | 'live'>(mode === 'host' ? 'setup' : 'connecting')
  const [audience, setAudience] = useState<Audience>('public')
  const [category, setCategory] = useState('just_chatting')
  const [save, setSave] = useState(false)
  const [title, setTitle] = useState('')
  const [groups, setGroups] = useState<any[]>([])
  const [groupId, setGroupId] = useState('')
  const [creds, setCreds] = useState<Creds | null>(null)
  const [err, setErr] = useState('')
  const { user } = useAuth()
  // OBS streaming is website-only and limited to approved streamers.
  const canObs = mode === 'host' && !isNativeApp && !!(user as any)?.can_go_live
  const [source, setSource] = useState<'camera' | 'obs'>('camera')

  useEffect(() => {
    if (mode === 'host') api.groups().then((r: any) => setGroups(r || [])).catch(() => {})
  }, [mode])

  const beginHost = async () => {
    if (audience === 'group' && !groupId) { setErr('Pick a group to stream into.'); return }
    setPhase('connecting'); setErr('')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: true })
      s.getTracks().forEach(t => t.stop())
      const r = await api.liveStart({ audience, category: kind === 'story' ? undefined : category, save, title: title.trim(), group_id: groupId || undefined, kind })
      setCreds({ ...r, is_host: true, host: undefined, title: title.trim(), category, audience })
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
  useWatchHeartbeat(liveId, mode === 'viewer' && phase === 'live')

  const AUD: { key: Audience; icon: any; label: string; hint: string }[] = [
    { key: 'public', icon: Globe2, label: 'Public', hint: 'Anyone on Skali' },
    { key: 'followers', icon: Users, label: 'Followers', hint: 'Followers + Inner' },
    { key: 'inner', icon: Users2, label: 'Inner Circle', hint: 'Inner Circle only' },
    { key: 'group', icon: Lock, label: 'Group', hint: 'A group DM' },
  ]

  return createPortal(
    <div className="fixed inset-0 z-[90] bg-black flex flex-col" data-testid="live-modal">
      {phase === 'setup' && (
        <div className="h-full flex flex-col overflow-y-auto">
          <div className="w-full max-w-xl mx-auto p-5 pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(3rem+env(safe-area-inset-bottom))]">
            <div className="flex items-center gap-2 mb-6">
              <span data-testid="live-setup-kind" className="neon-live flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2 py-1 rounded-md"><Radio className="h-3.5 w-3.5" />{source === 'obs' ? 'CONTENT STREAMING' : kind === 'story' ? 'LIVE STORY' : 'CONTENT STREAMING'}</span>
              <button onClick={onClose} data-testid="live-setup-close" className="ml-auto h-9 w-9 grid place-items-center rounded-full bg-white/10 text-white"><X className="h-5 w-5" /></button>
            </div>

            {canObs && (
              <>
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Stream from</div>
                <div className="grid grid-cols-2 gap-2 mb-5" data-testid="live-source-picker">
                  {([['camera', Camera, 'Camera', 'This device’s camera & mic'], ['obs', MonitorPlay, 'OBS Studio', 'Stream key for OBS']] as const).map(([k, Icon, label, hint]) => {
                    const on = source === k
                    return (
                      <button key={k} onClick={() => setSource(k)} data-testid={`live-source-${k}`}
                        className={`rounded-xl border p-3 text-left transition ${on ? 'border-brand bg-brand/10' : 'border-edge bg-panel hover:border-brand/40'}`}>
                        <Icon className={`h-5 w-5 mb-1 ${on ? 'text-brand' : 'text-slate-400'}`} />
                        <div className="font-semibold text-white text-sm">{label}</div>
                        <div className="text-xs text-slate-500">{hint}</div>
                      </button>
                    )
                  })}
                </div>
              </>
            )}

            {source === 'obs' ? (
              <div data-testid="live-obs-panel">
                <StreamBoundary label="OBS streaming">
                  <ObsStudioPanel />
                </StreamBoundary>
              </div>
            ) : (<>

            <label className="text-xs uppercase tracking-wide text-slate-400 mb-1.5 block">Stream title</label>
            <input value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
              placeholder="What's happening?" data-testid="live-title-input"
              className="w-full bg-panel border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand text-white mb-5" />

            {kind !== 'story' && (
              <>
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Category</div>
                <div className="grid grid-cols-3 gap-2 mb-5">
                  {LIVE_CATEGORIES.map(c => {
                    const Icon = c.icon
                    const on = category === c.key
                    return (
                      <button key={c.key} onClick={() => setCategory(c.key)} data-testid={`live-cat-pick-${c.key}`}
                        className={`rounded-xl border p-3 flex flex-col items-center gap-1.5 transition ${on ? 'border-brand bg-brand/10' : 'border-edge bg-panel hover:border-brand/40'}`}>
                        <Icon className={`h-5 w-5 ${on ? 'text-brand' : c.accent}`} />
                        <span className={`text-xs font-semibold ${on ? 'text-white' : 'text-slate-300'}`}>{c.label}</span>
                      </button>
                    )
                  })}
                </div>
              </>
            )}

            <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Who can watch</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {AUD.map(a => {
                const Icon = a.icon
                const on = audience === a.key
                return (
                  <button key={a.key} onClick={() => setAudience(a.key)} data-testid={`live-aud-${a.key}`}
                    className={`rounded-xl border p-3 text-left transition ${on ? 'border-brand bg-brand/10' : 'border-edge bg-panel hover:border-brand/40'}`}>
                    <Icon className={`h-5 w-5 mb-1 ${on ? 'text-brand' : 'text-slate-400'}`} />
                    <div className="font-semibold text-white text-sm">{a.label}</div>
                    <div className="text-xs text-slate-500">{a.hint}</div>
                  </button>
                )
              })}
            </div>

            {audience === 'group' && (
              <div className="mb-4">
                {groups.length === 0 ? (
                  <div className="text-sm text-slate-500 bg-panel border border-edge rounded-xl p-3">You're not in any groups yet.</div>
                ) : (
                  <select value={groupId} onChange={e => setGroupId(e.target.value)} data-testid="live-group-select"
                    className="w-full bg-panel border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand text-white">
                    <option value="">Select a group…</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name} ({g.member_count})</option>)}
                  </select>
                )}
              </div>
            )}

            <button onClick={() => setSave(s => !s)} data-testid="live-save-toggle"
              className="w-full flex items-center gap-3 bg-panel border border-edge rounded-xl p-3 mb-5">
              <Save className={`h-5 w-5 ${save ? 'text-brand' : 'text-slate-400'}`} />
              <div className="flex-1 text-left">
                <div className="text-sm font-medium text-white">Save to my wall when I finish</div>
                <div className="text-xs text-slate-500">Off = the stream is deleted when it ends</div>
              </div>
              <span className={`h-7 w-12 rounded-full p-0.5 transition shrink-0 ${save ? 'bg-emerald-500' : 'bg-white/15'}`}>
                <span className={`block h-6 w-6 rounded-full bg-white transition ${save ? 'translate-x-5' : ''}`} />
              </span>
            </button>

            {err && <div className="text-rose-400 text-sm mt-2 mb-2">{err}</div>}
            <button onClick={beginHost} data-testid="live-start-btn"
              className="mt-2 w-full py-3.5 rounded-xl bg-gradient-to-r from-rose-600 to-brand hover:brightness-110 text-white font-bold flex items-center justify-center gap-2 transition">
              <Radio className="h-5 w-5" /> Start live stream
            </button>
            </>)}
          </div>
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
              category={creds.category}
              audience={(creds.audience as Audience) || audience}
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
