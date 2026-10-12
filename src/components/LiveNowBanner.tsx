import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Radio, X } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { liveWatchUrl } from './LiveAlertBanner'

const KEY = 'skali:live-banner-dismissed'

// Feed banner: creators you get stream alerts for who are Content Streaming right now.
export default function LiveNowBanner() {
  const nav = useNavigate()
  const [live, setLive] = useState<any[]>([])
  const [hidden, setHidden] = useState<string[]>(() => JSON.parse(sessionStorage.getItem(KEY) || '[]'))

  useEffect(() => {
    const load = () => api.liveAlertedNow().then(r => setLive(r || [])).catch(() => {})
    load()
    const t = setInterval(load, 30000)
    window.addEventListener('skali:live-changed', load)
    return () => { clearInterval(t); window.removeEventListener('skali:live-changed', load) }
  }, [])

  const shown = live.filter(l => !hidden.includes(l.id))
  if (!shown.length) return null
  const first = shown[0]
  const more = shown.length - 1

  const dismiss = () => {
    const next = [...hidden, ...shown.map(l => l.id)]
    setHidden(next)
    sessionStorage.setItem(KEY, JSON.stringify(next))
  }

  return (
    <div className="mt-3 flex items-center gap-3 bg-rose-600/10 border border-rose-500/40 rounded-2xl p-2.5 animate-pop" data-testid="feed-live-now-banner">
      <div className="relative shrink-0">
        <div className="rounded-full p-[2px] bg-rose-600"><Avatar id={first.host?.handle} name={first.host?.display_name} url={first.host?.avatar_url} size={34} /></div>
        <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-rose-600 text-white text-[7px] font-bold px-1 rounded-full ring-2 ring-ink">LIVE</span>
      </div>
      <button onClick={() => nav(liveWatchUrl(first))} data-testid="feed-live-now-watch" className="flex-1 min-w-0 text-left">
        <div className="text-sm font-semibold truncate flex items-center gap-1.5">
          <Radio className="h-3.5 w-3.5 text-rose-400 shrink-0" />#{first.host?.handle} is streaming now
        </div>
        <div className="text-xs text-slate-400 truncate">{first.title || 'Tap to watch'}{more > 0 ? ` · +${more} more live` : ''}</div>
      </button>
      {more > 0 && (
        <button onClick={() => nav('/search?tab=streamers')} data-testid="feed-live-now-more"
          className="shrink-0 text-xs font-semibold text-rose-300 px-2.5 py-1 rounded-full border border-rose-500/40 hover:bg-rose-500/10">See all</button>
      )}
      <button onClick={dismiss} aria-label="Dismiss" data-testid="feed-live-now-dismiss" className="shrink-0 p-1 rounded-full text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>
    </div>
  )
}
