import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Radio, X } from 'lucide-react'
import { Avatar } from '../lib/ui'

export const liveWatchUrl = (l: any) => (l?.source === 'obs' ? `/watch/${l.id}` : `/live?watch=${l.id}`)

// In-app alert when someone you follow goes live (pushed over the user websocket).
export default function LiveAlertBanner({ live, onClose }: { live: any; onClose: () => void }) {
  const nav = useNavigate()
  useEffect(() => { const t = setTimeout(onClose, 10000); return () => clearTimeout(t) }, [live, onClose])
  return (
    <div className="fixed left-1/2 -translate-x-1/2 top-[calc(0.75rem+env(safe-area-inset-top))] z-[80] w-[calc(100%-1.5rem)] max-w-sm animate-pop" data-testid="live-alert-banner">
      <div className="flex items-center gap-3 bg-panel2/95 backdrop-blur border border-rose-500/40 rounded-2xl p-3 shadow-2xl">
        <Avatar id={live.host?.handle} name={live.host?.display_name} url={live.host?.avatar_url} size={36} />
        <button onClick={() => { onClose(); nav(liveWatchUrl(live)) }} data-testid="live-alert-watch" className="flex-1 min-w-0 text-left">
          <div className="text-sm font-semibold truncate flex items-center gap-1.5"><Radio className="h-3.5 w-3.5 text-rose-400" />#{live.host?.handle} is live</div>
          <div className="text-xs text-slate-400 truncate">{live.title || 'Tap to watch'}</div>
        </button>
        <button onClick={onClose} data-testid="live-alert-close" aria-label="Dismiss" className="p-1 rounded-full text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>
      </div>
    </div>
  )
}
