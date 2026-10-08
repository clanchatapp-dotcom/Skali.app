import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Film, PlayCircle, Clock } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { categoryOf } from '../lib/liveCategories'

const hoursLeft = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 3600000))
const mins = (s: number) => (s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m` : `${Math.max(1, Math.round(s / 60))}m`)

// Recorded streams still inside their 24-hour window. Tapping plays the replay (works on mobile + web).
export default function ReplaysSection() {
  const nav = useNavigate()
  const [items, setItems] = useState<any[]>([])
  useEffect(() => { api.liveReplays().then((r: any) => setItems(r || [])).catch(() => {}) }, [])
  if (!items.length) return null
  return (
    <section data-testid="replays-section">
      <div className="flex items-center gap-2 mb-1">
        <Film className="h-4 w-4 text-brand" />
        <h2 className="font-bold">Replays</h2>
        <span className="text-sm text-slate-500">{items.length}</span>
      </div>
      <p className="text-xs text-slate-500 mb-3">Recordings stay up for 24 hours after a stream ends.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map(v => {
          const cat = categoryOf(v.category)
          return (
            <button key={v.live_id} onClick={() => nav(`/watch/${v.live_id}`)} data-testid={`replay-card-${v.live_id}`}
              className="text-left flex items-center gap-3 p-3 rounded-xl bg-panel border border-edge hover:border-brand/40 transition-colors">
              <div className="relative h-14 w-24 rounded-lg bg-gradient-to-br from-brand/30 to-black grid place-items-center shrink-0">
                <PlayCircle className="h-6 w-6 text-white/80" />
                {v.duration ? <span className="absolute bottom-1 right-1 text-[10px] bg-black/70 rounded px-1">{mins(v.duration)}</span> : null}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-white truncate">{v.title || 'Untitled stream'}</div>
                <div className="flex items-center gap-1.5 mt-0.5 text-xs text-slate-400 min-w-0">
                  <Avatar id={v.host?.handle} name={v.host?.display_name} url={v.host?.avatar_url} size={16} />
                  <span className="truncate">#{v.host?.handle}</span><span className={cat.accent}>· {cat.label}</span>
                </div>
                <div className="text-[11px] text-amber-300/90 mt-0.5 flex items-center gap-1" data-testid={`replay-expiry-${v.live_id}`}>
                  <Clock className="h-3 w-3" /> {hoursLeft(v.expires_at)}h left
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
