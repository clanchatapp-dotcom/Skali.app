import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Room, RoomEvent, RemoteTrack, Track } from 'livekit-client'
import { api } from '../lib/api'
import { useWatchHeartbeat } from '../lib/watchTime'
import { useAuth } from '../lib/auth'
import { Avatar } from '../lib/ui'
import { categoryOf } from '../lib/liveCategories'
import StreamChat from '../components/stream/StreamChat'
import StreamBoundary from '../components/stream/StreamBoundary'
import { ArrowLeft, Loader2, Users, Volume2, VolumeX, Radio, Film } from 'lucide-react'

function useStreamRoom(liveId: string, live: boolean, videoRef: React.RefObject<HTMLVideoElement>, audioRef: React.RefObject<HTMLAudioElement>) {
  const [room, setRoom] = useState<Room | null>(null)
  const [hasVideo, setHasVideo] = useState(false)
  const [timedOutUntil, setTimedOutUntil] = useState<string | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!live) return
    let r: Room | null = null
    let cancelled = false
    const attach = (t: RemoteTrack) => {
      if (t.kind === Track.Kind.Video && videoRef.current) { t.attach(videoRef.current); setHasVideo(true) }
      if (t.kind === Track.Kind.Audio && audioRef.current) t.attach(audioRef.current)
    }
    api.streamJoin(liveId).then(async (j: any) => {
      if (cancelled) return
      setTimedOutUntil(j.timed_out_until)
      r = new Room({ adaptiveStream: true })
      r.on(RoomEvent.TrackSubscribed, t => attach(t as RemoteTrack))
      r.on(RoomEvent.TrackUnsubscribed, t => { t.detach(); if (t.kind === Track.Kind.Video) setHasVideo(false) })
      await r.connect(j.server_url, j.participant_token)
      if (cancelled) { r.disconnect(); return }
      r.remoteParticipants.forEach(p => p.trackPublications.forEach(pub => pub.track && attach(pub.track as RemoteTrack)))
      setRoom(r)
    }).catch((e: any) => setErr(e.message || 'Could not join the stream'))
    return () => { cancelled = true; r?.disconnect(); setRoom(null) }
  }, [liveId, live])

  return { room, hasVideo, timedOutUntil, setTimedOutUntil, err }
}

function Ended({ info }: { info: any }) {
  const vod = info?.vod
  if (vod?.playback_url) {
    const left = vod.expires_at ? Math.max(0, Math.ceil((new Date(vod.expires_at).getTime() - Date.now()) / 3600000)) : null
    return (
      <div className="absolute inset-0">
        <video src={vod.playback_url} controls playsInline preload="metadata" className="w-full h-full bg-black" data-testid="vod-player" />
        <span className="absolute top-2 left-2 text-[11px] font-semibold bg-black/70 rounded-md px-2 py-0.5 text-amber-200" data-testid="vod-expiry">
          Replay{left != null ? ` · ${left}h left` : ''}
        </span>
      </div>
    )
  }
  return (
    <div className="absolute inset-0 grid place-items-center text-center px-6" data-testid="stream-ended">
      <div>
        <Film className="h-8 w-8 text-slate-500 mx-auto mb-2" />
        <p className="font-semibold text-slate-200">This stream has ended</p>
        <p className="text-xs text-slate-500 mt-1">
          {vod?.status === 'processing' || vod?.status === 'recording' ? 'The recording is processing — it will be here for 24 hours.' : 'No recording is available.'}
        </p>
      </div>
    </div>
  )
}

export default function StreamWatch() {
  const { liveId = '' } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const [info, setInfo] = useState<any>(null)
  const [loadErr, setLoadErr] = useState('')
  const [ended, setEnded] = useState(false)
  const [muted, setMuted] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  const loadInfo = () => api.streamInfo(liveId).then((i: any) => { setInfo(i); if (i.status !== 'live') setEnded(true) })
    .catch((e: any) => setLoadErr(e.message || 'Stream not found'))
  useEffect(() => { loadInfo() }, [liveId])

  const live = !!info && info.status === 'live' && !ended
  const { room, hasVideo, timedOutUntil, setTimedOutUntil, err } = useStreamRoom(liveId, live, videoRef, audioRef)
  useWatchHeartbeat(liveId, !!room && live)

  useEffect(() => { if (audioRef.current) { audioRef.current.muted = muted; if (!muted) audioRef.current.play().catch(() => {}) } }, [muted, room])

  const onEnded = () => { setEnded(true); setTimeout(loadInfo, 1500) }
  const cat = categoryOf(info?.category)

  if (loadErr) return <div className="min-h-[100dvh] grid place-items-center text-slate-400 px-6 text-center" data-testid="stream-load-error">{loadErr}</div>
  if (!info) return <div className="min-h-[100dvh] grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>

  return (
    <div className="min-h-[100dvh] lg:h-[100dvh] flex flex-col bg-ink text-slate-100" data-testid="stream-watch-page">
      <header className="shrink-0 z-10 glass border-b border-white/10 px-4 pt-[calc(0.6rem+env(safe-area-inset-top))] pb-2.5 flex items-center gap-3">
        <button onClick={() => nav(-1)} data-testid="stream-back-btn" className="h-9 w-9 grid place-items-center rounded-xl hover:bg-white/5"><ArrowLeft className="h-5 w-5" /></button>
        <Avatar id={info.host?.handle} name={info.host?.display_name} url={info.host?.avatar_url} size={36} />
        <div className="min-w-0 flex-1">
          <div className="font-semibold truncate" data-testid="stream-title">{info.title || `${info.host?.display_name} is live`}</div>
          <div className="text-xs text-slate-400 truncate">#{info.host?.handle} · <span className={cat.accent}>{cat.label}</span></div>
        </div>
        {live ? (
          <span className="neon-live flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2.5 py-1 rounded-md" data-testid="stream-live-badge"><Radio className="h-3 w-3" />LIVE · <Users className="h-3 w-3" />{info.viewers}</span>
        ) : <span className="text-xs text-slate-400 border border-edge rounded-md px-2.5 py-1" data-testid="stream-offline-badge">Offline</span>}
      </header>

      <div className="flex-1 min-h-0 grid grid-rows-[auto_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-h-0 flex flex-col">
          <div className="relative w-full aspect-video lg:aspect-auto lg:flex-1 bg-black shadow-[0_20px_60px_-20px_rgb(var(--neon-pink)/.45)]">
            {live ? (
              <>
                <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-contain" data-testid="stream-video" />
                <audio ref={audioRef} autoPlay />
                {!hasVideo && (
                  <div className="absolute inset-0 grid place-items-center text-sm text-slate-400">
                    {err ? <span className="text-rose-300 px-6 text-center" data-testid="stream-join-error">{err}</span> : <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Waiting for video…</span>}
                  </div>
                )}
                <button onClick={() => setMuted(m => !m)} data-testid="stream-mute-btn"
                  className="absolute bottom-3 left-3 flex items-center gap-1.5 bg-black/60 backdrop-blur px-3 py-1.5 rounded-full text-xs font-semibold hover:bg-black/80 transition-colors">
                  {muted ? <><VolumeX className="h-4 w-4" /> Tap to unmute</> : <><Volume2 className="h-4 w-4" /> Mute</>}
                </button>
              </>
            ) : <Ended info={info} />}
          </div>
        </section>

        <aside className="min-h-[50vh] lg:min-h-0 flex flex-col border-t lg:border-t-0 lg:border-l border-white/10 glass">
          <div className="flex-1 min-h-0 h-0">
          <StreamBoundary label="Chat">
            {live ? (
              <StreamChat room={room} liveId={liveId} meId={(user as any)?.id || ''} canModerate={!!info.can_moderate}
                timedOutUntil={timedOutUntil} setTimedOutUntil={setTimedOutUntil} onEnded={onEnded} />
            ) : (
              <div className="h-full grid place-items-center text-xs text-slate-500 px-6 text-center" data-testid="chat-closed">Chat is closed — it was cleared when the stream ended.</div>
            )}
          </StreamBoundary>
          </div>
        </aside>
      </div>
    </div>
  )
}
