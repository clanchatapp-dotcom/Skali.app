import { useEffect, useState } from 'react'
import { KeyRound, Loader2 } from 'lucide-react'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/ui'

// Adult section code resets: requests reach Super/Co-admins; only Super admins can reset.
export default function NsfwResetsPanel({ isSuper }: { isSuper: boolean }) {
  const [list, setList] = useState<any[] | null>(null)
  const [handle, setHandle] = useState('')
  const load = () => api.adminNsfwResets().then(setList).catch(() => setList([]))
  useEffect(() => { load() }, [])

  const reset = async (h: string) => {
    if (!h.trim() || !confirm(`Reset the adult section code for #${h}? They will create a new one next visit.`)) return
    try { await api.adminNsfwReset(h.trim()); setHandle(''); load() } catch (e: any) { alert(e.message) }
  }

  return (
    <div className="space-y-3" data-testid="nsfw-resets-panel">
      {isSuper && (
        <div className="flex gap-2">
          <input value={handle} onChange={e => setHandle(e.target.value)} placeholder="#handle" data-testid="nsfw-reset-handle-input"
            className="flex-1 bg-panel border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
          <button onClick={() => reset(handle)} data-testid="nsfw-reset-handle-btn" className="px-4 rounded-xl bg-rose-500 hover:bg-rose-600 text-sm font-semibold flex items-center gap-1.5">
            <KeyRound className="h-4 w-4" />Reset code
          </button>
        </div>
      )}
      {!isSuper && <p className="text-xs text-slate-500">Only the Super admin can reset codes.</p>}
      {list === null ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : list.length === 0 ? (
        <p className="text-sm text-slate-500" data-testid="nsfw-resets-empty">No pending code reset requests.</p>
      ) : list.map(r => (
        <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3 text-sm" data-testid={`nsfw-reset-request-${r.handle}`}>
          <span className="flex-1">{r.display_name} <span className="text-slate-500">#{r.handle}</span> asked for a code reset · {timeAgo(r.created_at)}</span>
          {isSuper && <button onClick={() => reset(r.handle)} data-testid={`nsfw-reset-btn-${r.handle}`} className="px-3 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30">Reset</button>}
        </div>
      ))}
    </div>
  )
}
