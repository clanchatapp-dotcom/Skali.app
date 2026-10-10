import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ReplaysSection from '../components/ReplaysSection'
import { Capacitor } from '@capacitor/core'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Avatar } from '../lib/ui'
import LiveModal from '../components/LiveModal'
import ObsStudioPanel from '../components/stream/ObsStudioPanel'
import StreamBoundary from '../components/stream/StreamBoundary'
import { LIVE_CATEGORIES, categoryOf } from '../lib/liveCategories'
import { Radio, Users, Loader2, Video, Clock, PlayCircle, Lock, Users2, Globe2 } from 'lucide-react'

type Stream = {
  id: string; host: any; audience: string; category: string
  title: string; viewers: number; peak_viewers: number; started_at: string; source?: string
}

const isNative = (() => { try { return Capacitor.isNativePlatform() } catch { return false } })()

const fmtDuration = (sec?: number | null) => {
  if (!sec || sec < 0) return ''
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

const timeAgo = (iso?: string) => {
  if (!iso) return ''
  const d = (Date.now() - new Date(iso).getTime()) / 1000
  if (d < 3600) return `${Math.max(1, Math.floor(d / 60))}m ago`
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`
  return `${Math.floor(d / 86400)}d ago`
}

const AudienceTag = ({ a }: { a: string }) => {
  const map: Record<string, { icon: any; label: string }> = {
    public: { icon: Globe2, label: 'Public' },
    followers: { icon: Users, label: 'Followers' },
    inner: { icon: Users2, label: 'Inner Circle' },
    group: { icon: Lock, label: 'Group' },
  }
  const v = map[a] || map.public
  const Icon = v.icon
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
      <Icon className="h-3 w-3" />{v.label}
    </span>
  )
}

function StreamCard({ s, onOpen }: { s: Stream; onOpen: () => void }) {
  const cat = categoryOf(s.category)
  const CatIcon = cat.icon
  return (
    <button onClick={onOpen} data-testid={`live-card-${s.id}`}
      className="group text-left rounded-2xl overflow-hidden bg-panel border border-edge hover:border-neon-pink/50 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_30px_-8px_rgb(var(--neon-pink)/.6)]">
      <div className="relative aspect-video overflow-hidden bg-[radial-gradient(120%_90%_at_50%_110%,rgb(var(--neon-pink)/.35),transparent_60%),linear-gradient(160deg,rgb(var(--brand)/.35),#050507_70%)]">
        {/* Night Drive light streaks */}
        <span className="absolute inset-x-0 top-1/3 h-px bg-gradient-to-r from-transparent via-neon-pink/60 to-transparent" />
        <span className="absolute inset-x-0 top-2/3 h-px bg-gradient-to-r from-transparent via-neon-cyan/40 to-transparent" />
        <div className="absolute inset-0 grid place-items-center">
          <Avatar id={s.host?.handle || s.id} name={s.host?.display_name} url={s.host?.avatar_url} size={84} />
        </div>
        <span className="neon-live absolute top-2.5 left-2.5 flex items-center gap-1.5 bg-rose-600 text-white text-[11px] font-bold px-2 py-0.5 rounded-md shadow">
          <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" /> LIVE
        </span>
        <span className="absolute top-2.5 right-2.5 flex items-center gap-1 bg-black/60 backdrop-blur text-white text-[11px] font-semibold px-2 py-0.5 rounded-md">
          <Users className="h-3 w-3" />{s.viewers}
        </span>
        <span className={`absolute bottom-2.5 left-2.5 flex items-center gap-1 bg-black/60 backdrop-blur text-[11px] font-semibold px-2 py-0.5 rounded-md ${cat.accent}`}>
          <CatIcon className="h-3 w-3" />{cat.label}
        </span>
      </div>
      <div className="flex gap-3 p-3">
        <Avatar id={s.host?.handle || s.id} name={s.host?.display_name} url={s.host?.avatar_url} size={38} />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-white truncate group-hover:text-brand transition">
            {s.title || `${s.host?.display_name || 'Someone'} is live`}
          </div>
          <div className="text-xs text-slate-400 truncate">{s.host?.display_name} · #{s.host?.handle}</div>
          <div className="mt-1"><AudienceTag a={s.audience} /></div>
        </div>
      </div>
    </button>
  )
}

export default function Live() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [streams, setStreams] = useState<Stream[]>([])
  const [cats, setCats] = useState<any[]>([])
  const [active, setActive] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [past, setPast] = useState<any[]>([])
  const [liveOpen, setLiveOpen] = useState<{ mode: 'host' | 'viewer'; liveId?: string } | null>(null)

  const myHandle = (user as any)?.handle
  const [params, setParams] = useSearchParams()
  const watchId = params.get('watch')
  useEffect(() => {
    // Opened from a live alert: jump straight into that stream.
    if (!watchId) return
    setLiveOpen({ mode: 'viewer', liveId: watchId })
    setParams({}, { replace: true })
  }, [watchId])

  const load = useCallback(() => {
    api.liveList(active === 'all' ? undefined : active).then((r: any) => setStreams(r || [])).catch(() => {}).finally(() => setLoading(false))
    api.liveCategories().then((r: any) => setCats(r || [])).catch(() => {})
  }, [active])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  useEffect(() => {
    if (myHandle) api.livePast(myHandle).then((r: any) => setPast(r || [])).catch(() => {})
  }, [myHandle, liveOpen])

  const mine = streams.find(s => s.host?.handle === myHandle)
  const others = streams.filter(s => s.host?.handle !== myHandle)

  const open = (s: Stream) => s.source === 'obs' ? nav(`/watch/${s.id}`) : setLiveOpen({ mode: 'viewer', liveId: s.id })
  const goLive = () => mine ? open(mine) : setLiveOpen({ mode: 'host' })
  const allowed = !!(user as any)?.can_go_live
  // Streaming is website-only; the mobile app is for watching.
  const canGoLive = allowed && !isNative

  return (
    <div className="min-h-full">
      <div className="sticky top-0 z-20 bg-ink/85 backdrop-blur border-b border-edge px-4 md:px-6 pt-[calc(1rem+env(safe-area-inset-top))] pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-rose-600/15 grid place-items-center">
            <Radio className="h-5 w-5 text-rose-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-extrabold tracking-tight">Live</h1>
            <p className="text-xs text-slate-400">Streaming now across Skali</p>
          </div>
          {canGoLive && <button onClick={goLive} data-testid="live-page-golive"
            className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-gradient-to-r from-rose-600 to-brand text-white font-bold text-sm active:scale-95 transition hover:brightness-110">
            <Video className="h-4 w-4" />{mine ? 'Your stream' : 'Go Live'}
          </button>}
        </div>

        <div className="mt-4 flex gap-2 overflow-x-auto no-scrollbar -mx-1 px-1">
          <button onClick={() => setActive('all')} data-testid="live-cat-all"
            className={`shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold border transition ${active === 'all' ? 'bg-brand text-white border-brand' : 'bg-panel text-slate-300 border-edge hover:border-brand/40'}`}>
            <Radio className="h-3.5 w-3.5" /> All
          </button>
          {LIVE_CATEGORIES.map(c => {
            const Icon = c.icon
            const count = cats.find(x => x.key === c.key)?.live || 0
            return (
              <button key={c.key} onClick={() => setActive(c.key)} data-testid={`live-cat-${c.key}`}
                className={`shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold border transition ${active === c.key ? 'bg-brand text-white border-brand' : 'bg-panel text-slate-300 border-edge hover:border-brand/40'}`}>
                <Icon className="h-3.5 w-3.5" /> {c.label}
                {count > 0 && <span className={`ml-0.5 text-[11px] ${active === c.key ? 'text-white/80' : 'text-rose-400'}`}>{count}</span>}
              </button>
            )
          })}
        </div>
      </div>

      <div className="p-4 md:p-6 space-y-8">
        {!canGoLive && (
          <div className="rounded-2xl border border-edge bg-panel p-4 flex items-start gap-3" data-testid="live-restricted-note">
            <Lock className="h-5 w-5 text-slate-400 shrink-0 mt-0.5" />
            <p className="text-sm text-slate-400">{allowed
              ? 'Going live is only available on the Skali website. Open skaliapp.com in a browser to start streaming — you can watch every stream here.'
              : 'Going live is currently limited to the Skali team and invited streamers. You can still watch every stream here.'}</p>
          </div>
        )}

        {!isNative && canGoLive && (
          <StreamBoundary label="OBS streaming">
            <ObsStudioPanel />
          </StreamBoundary>
        )}

        {mine && (
          <button onClick={() => open(mine)} data-testid="live-mine-banner"
            className="w-full flex items-center gap-3 p-4 rounded-2xl bg-rose-600/10 border border-rose-600/40 text-left hover:bg-rose-600/15 transition">
            <span className="neon-live flex items-center gap-1.5 bg-rose-600 text-white text-xs font-bold px-2 py-1 rounded-md"><Radio className="h-3.5 w-3.5" />LIVE</span>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-white truncate">You're live now</div>
              <div className="text-xs text-slate-400 truncate">{mine.viewers} watching · tap to open your stream</div>
            </div>
          </button>
        )}

        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
            <h2 className="font-bold">Live Now</h2>
            {!loading && <span className="text-sm text-slate-500">{others.length}</span>}
          </div>

          {loading ? (
            <div className="py-16 grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
          ) : others.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-edge p-10 text-center">
              <div className="h-14 w-14 rounded-2xl bg-brand/10 grid place-items-center mx-auto mb-3">
                <Video className="h-7 w-7 text-brand" />
              </div>
              <p className="text-slate-300 font-semibold">No one's live right now</p>
              <p className="text-sm text-slate-500 mt-1">{canGoLive ? 'Be the first — start your stream and let your community join.' : 'Check back soon.'}</p>
              {canGoLive && <button onClick={goLive} data-testid="live-empty-golive"
                className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-rose-600 to-brand text-white font-bold text-sm">
                <Radio className="h-4 w-4" /> Go Live
              </button>}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="live-grid">
              {others.map(s => (
                <StreamCard key={s.id} s={s} onOpen={() => open(s)} />
              ))}
            </div>
          )}
        </section>

        <ReplaysSection />

        {past.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Clock className="h-4 w-4 text-slate-400" />
              <h2 className="font-bold">Your past streams</h2>
            </div>
            <div className="space-y-2">
              {past.map(p => {
                const cat = categoryOf(p.category)
                const CatIcon = cat.icon
                return (
                  <div key={p.id} data-testid={`past-stream-${p.id}`}
                    className="flex items-center gap-3 p-3 rounded-xl bg-panel border border-edge">
                    <div className="h-12 w-20 rounded-lg bg-gradient-to-br from-brand/25 to-black grid place-items-center shrink-0">
                      <PlayCircle className="h-5 w-5 text-white/70" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-white truncate">{p.title || 'Untitled stream'}</div>
                      <div className="text-xs text-slate-400 flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center gap-1 ${cat.accent}`}><CatIcon className="h-3 w-3" />{cat.label}</span>
                        <span>· {timeAgo(p.started_at)}</span>
                        <span className="inline-flex items-center gap-1"><Users className="h-3 w-3" />{p.peak_viewers} peak</span>
                        {p.duration ? <span>· {fmtDuration(p.duration)}</span> : null}
                      </div>
                    </div>
                    {p.saved && <span className="text-[11px] text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-full shrink-0">Saved</span>}
                  </div>
                )
              })}
            </div>
          </section>
        )}
      </div>

      {liveOpen && (
        <LiveModal mode={liveOpen.mode} liveId={liveOpen.liveId}
          onClose={() => { setLiveOpen(null); load() }} />
      )}
    </div>
  )
}
