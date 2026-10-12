import { useEffect, useState } from 'react'
import { Radio, Trash2 } from 'lucide-react'
import { api } from '../lib/api'

// Owner-only: grant/remove "Go Live" access. Staff (moderators, co-admins, super admin) always have it.
export default function StreamersPanel({ isSuper }: { isSuper: boolean }) {
  const [list, setList] = useState<any[]>([])
  const [handle, setHandle] = useState('')
  const load = () => api.adminStreamers().then(setList).catch(() => {})
  useEffect(() => { load() }, [])
  const run = async (fn: () => Promise<any>) => { try { await fn(); await load() } catch (e: any) { alert(e.message) } }
  const add = () => { const h = handle.trim().replace(/^[#@]/, ''); if (h) run(() => api.adminAssignStreamer(h)).then(() => setHandle('')) }

  return (
    <div className="bg-panel border border-edge rounded-2xl p-4 space-y-3" data-testid="streamers-panel">
      <div className="flex items-center gap-2 text-sm font-medium"><Radio className="h-4 w-4 text-rose-400" /> Go Live access</div>
      <p className="text-xs text-slate-500">Going live is limited to Moderators, Co-Admins and the Super Admin, plus anyone listed here.{!isSuper && ' Only the owner (Super Admin) can change this list.'}</p>
      {isSuper && (
        <div className="flex gap-2">
          <input value={handle} onChange={e => setHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} placeholder="@handle"
            data-testid="streamer-handle-input" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
          <button onClick={add} data-testid="streamer-assign-btn" className="px-4 py-2.5 rounded-xl bg-brand font-medium">Allow</button>
        </div>
      )}
      {list.length === 0 && <p className="text-xs text-slate-500" data-testid="streamers-empty">No extra streamers yet.</p>}
      {list.map(s => (
        <div key={s.id} className="flex items-center gap-3 border-t border-edge pt-3" data-testid={`streamer-row-${s.handle}`}>
          <div className="flex-1 min-w-0"><div className="font-medium truncate">{s.display_name}</div><div className="text-xs text-slate-500">#{s.handle}</div></div>
          {isSuper && <button onClick={() => run(() => api.adminRemoveStreamer(s.handle))} data-testid={`streamer-remove-${s.handle}`}
            className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-rose-300 hover:bg-white/5"><Trash2 className="h-4 w-4" /></button>}
        </div>
      ))}
    </div>
  )
}
