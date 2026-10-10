import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { Film, Download, Loader2, PlayCircle } from 'lucide-react'

const STATUS: Record<string, string> = {
  recording: 'Recording…', processing: 'Processing…', ready: 'Ready', failed: 'Recording failed',
}

const left = (iso?: string) => {
  if (!iso) return ''
  const s = (new Date(iso).getTime() - Date.now()) / 1000
  if (s <= 0) return 'Deleting…'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return `Deletes in ${h ? `${h}h ` : ''}${m}m`
}

export default function StreamVods() {
  const [vods, setVods] = useState<any[] | null>(null)
  const [busy, setBusy] = useState('')
  useEffect(() => {
    const load = () => api.streamVods().then(setVods).catch(() => setVods([]))
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  const download = async (id: string) => {
    setBusy(id)
    try { const r = await api.streamVodDownload(id); window.open(r.url, '_blank') }
    catch (e: any) { alert(e.message) } finally { setBusy('') }
  }

  return (
    <div className="p-4 border-t md:border-t-0 border-edge" data-testid="stream-vods">
      <div className="flex items-center gap-2 mb-1">
        <Film className="h-4 w-4 text-brand" />
        <h3 className="font-semibold text-sm">Recordings (VODs)</h3>
      </div>
      <p className="text-[11px] text-slate-500 mb-2">Each stream is kept for 24 hours after it ends, then deleted automatically. Download it to keep it.</p>
      {!vods ? <Loader2 className="h-4 w-4 animate-spin text-slate-500" /> : vods.length === 0 ? (
        <p className="text-xs text-slate-500" data-testid="vods-empty">No recordings yet.</p>
      ) : (
        <div className="space-y-2">
          {vods.map(v => (
            <div key={v.id} className="flex items-center gap-2.5 p-2.5 rounded-xl bg-ink border border-edge" data-testid={`vod-${v.id}`}>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{v.title || 'Untitled stream'}</div>
                <div className="text-[11px] text-slate-500 truncate">
                  <span className={v.status === 'ready' ? 'text-emerald-300' : v.status === 'failed' ? 'text-rose-300' : ''}>{STATUS[v.status] || v.status}</span>
                  {v.expires_at && v.status !== 'failed' && <> · {left(v.expires_at)}</>}
                </div>
              </div>
              {v.status === 'ready' && (
                <>
                  <Link to={`/watch/${v.live_id}`} data-testid={`vod-watch-${v.id}`} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/5 text-slate-300" aria-label="Watch">
                    <PlayCircle className="h-4 w-4" />
                  </Link>
                  <button onClick={() => download(v.id)} disabled={busy === v.id} data-testid={`vod-download-${v.id}`}
                    className="h-8 px-3 rounded-lg bg-brand text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50">
                    {busy === v.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />} Download
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
