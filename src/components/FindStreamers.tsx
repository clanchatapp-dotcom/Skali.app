import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Bell, BellOff, Loader2, Radio, Search as SearchIcon, Users } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import LiveModal from './LiveModal'

// Find → Streamers: creators who Content Stream. Live now on top, everyone below.
export default function FindStreamers() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [data, setData] = useState<{ live: any[]; creators: any[] } | null>(null)
  const [watch, setWatch] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => {
      api.streamers(q.trim()).then(setData).catch(() => setData({ live: [], creators: [] }))
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  const open = (c: any) => c.live.source === 'obs' ? nav(`/watch/${c.live.id}`) : setWatch(c.live.id)

  return (
    <div className="p-4 space-y-6" data-testid="find-streamers-panel">
      <div className="flex items-center gap-2 bg-panel border border-edge rounded-xl px-3">
        <SearchIcon className="h-4 w-4 text-slate-500" />
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search streamers by name or handle"
          className="flex-1 bg-transparent py-3 outline-none" data-testid="streamers-search-input" />
      </div>

      {!data ? (
        <div className="py-16 grid place-items-center text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : (
        <>
          <section data-testid="streamers-live-section">
            <div className="flex items-center gap-2 mb-3">
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
              <h2 className="font-semibold tracking-wide text-slate-300">LIVE NOW</h2>
              <span className="text-sm text-slate-500">{data.live.length}</span>
            </div>
            {data.live.length === 0 ? (
              <p className="text-sm text-slate-500">No creators are streaming right now.</p>
            ) : (
              <div className="space-y-2">
                {data.live.map(c => (
                  <button key={c.id} onClick={() => open(c)} data-testid={`streamer-live-${c.handle}`}
                    className="w-full flex items-center gap-3 bg-rose-600/10 border border-rose-600/40 rounded-2xl p-3 text-left hover:bg-rose-600/15 transition-colors">
                    <Avatar id={c.id} name={c.display_name} url={c.avatar_url} />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{c.display_name}</div>
                      <div className="text-sm text-slate-400 truncate">{c.live.title || `#${c.handle}`}</div>
                    </div>
                    <span className="text-xs text-slate-400 flex items-center gap-1"><Users className="h-3 w-3" />{c.live.viewers ?? 0}</span>
                    <span className="neon-live flex items-center gap-1 bg-rose-600 text-white text-[10px] font-bold px-2 py-1 rounded-md"><Radio className="h-3 w-3" />LIVE</span>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section data-testid="streamers-all-section">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="font-semibold tracking-wide text-slate-300">ALL CREATORS</h2>
              <span className="text-sm text-slate-500">{data.creators.length}</span>
            </div>
            {data.creators.length === 0 ? (
              <p className="text-sm text-slate-500">{q.trim() ? `No streamers found for “${q.trim()}”.` : 'No creators yet.'}</p>
            ) : (
              <div className="space-y-2">
                {data.creators.map(c => (
                  <Link key={c.id} to={`/u/${c.handle}`} data-testid={`streamer-${c.handle}`}
                    className="flex items-center gap-3 bg-panel border border-edge rounded-2xl p-3 hover:bg-white/5">
                    <Avatar id={c.id} name={c.display_name} url={c.avatar_url} />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{c.display_name}</div>
                      <div className="text-sm text-slate-500 truncate">#{c.handle}</div>
                    </div>
                    {c.live && <span className="bg-rose-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">LIVE</span>}
                    {!c.is_self && <AlertBell c={c} onChange={on => setData(d => d && { ...d, creators: d.creators.map(x => x.id === c.id ? { ...x, alert: on } : x) })} />}
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {watch && <LiveModal mode="viewer" liveId={watch} onClose={() => setWatch(null)} />}
    </div>
  )
}

// Per-creator "alert me when they start streaming" toggle.
function AlertBell({ c, onChange }: { c: any; onChange: (on: boolean) => void }) {
  const [busy, setBusy] = useState(false)
  const toggle = async (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation()
    const next = !c.alert
    setBusy(true); onChange(next)
    try { await api.setLiveAlert(c.handle, next) } catch { onChange(!next) }
    setBusy(false)
  }
  return (
    <button onClick={toggle} disabled={busy} data-testid={`streamer-alert-${c.handle}`} aria-pressed={!!c.alert}
      title={c.alert ? 'Stream alerts on' : 'Alert me when they go live'}
      className={`h-8 px-3 rounded-full border text-xs font-semibold flex items-center gap-1.5 transition-colors shrink-0 ${c.alert ? 'border-rose-500/40 bg-rose-500/10 text-rose-300' : 'border-edge text-slate-400 hover:bg-white/5'}`}>
      {c.alert ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}{c.alert ? 'Alerts on' : 'Alert me'}
    </button>
  )
}
