import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { Avatar } from '../../lib/ui'
import { ShieldCheck, Plus, X, Loader2 } from 'lucide-react'

type P = { id: string; handle: string; display_name?: string; avatar_url?: string }

function Row({ p, action, onClick, testId }: { p: P; action: 'add' | 'remove'; onClick: () => void; testId: string }) {
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <Avatar id={p.id} name={p.display_name || p.handle} url={p.avatar_url} size={30} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{p.display_name || p.handle}</div>
        <div className="text-[11px] text-slate-500 truncate">#{p.handle}</div>
      </div>
      <button onClick={onClick} data-testid={testId}
        className={`h-7 px-2.5 rounded-full text-xs font-semibold flex items-center gap-1 transition-colors ${action === 'add' ? 'bg-brand/15 text-brand hover:bg-brand/25' : 'bg-white/5 text-slate-300 hover:bg-rose-500/15 hover:text-rose-300'}`}>
        {action === 'add' ? <><Plus className="h-3 w-3" /> Make mod</> : <><X className="h-3 w-3" /> Remove</>}
      </button>
    </div>
  )
}

export default function StreamMods() {
  const [d, setD] = useState<{ mods: P[]; candidates: P[] } | null>(null)
  const load = () => api.streamMods().then(setD).catch(() => setD({ mods: [], candidates: [] }))
  useEffect(() => { load() }, [])

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); await load() } catch (e: any) { alert(e.message) }
  }

  return (
    <div className="p-4 md:border-r border-edge" data-testid="stream-mods">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck className="h-4 w-4 text-emerald-400" />
        <h3 className="font-semibold text-sm">Chat moderators</h3>
      </div>
      <p className="text-[11px] text-slate-500 mb-2">Only members of your Inner Circle can be mods. Mods can delete messages and time out chatters.</p>
      {!d ? <Loader2 className="h-4 w-4 animate-spin text-slate-500" /> : (
        <>
          {d.mods.map(p => <Row key={p.id} p={p} action="remove" testId={`mod-remove-${p.handle}`} onClick={() => act(() => api.streamRemoveMod(p.handle))} />)}
          {d.mods.length === 0 && <p className="text-xs text-slate-500 py-1" data-testid="mods-empty">No moderators yet.</p>}
          {d.candidates.length > 0 && <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mt-3 mb-1">Inner Circle</div>}
          {d.candidates.map(p => <Row key={p.id} p={p} action="add" testId={`mod-add-${p.handle}`} onClick={() => act(() => api.streamAddMod(p.handle))} />)}
          {d.mods.length === 0 && d.candidates.length === 0 && (
            <p className="text-xs text-slate-500" data-testid="mods-no-inner">Invite people to your Inner Circle to make them mods.</p>
          )}
        </>
      )}
    </div>
  )
}
