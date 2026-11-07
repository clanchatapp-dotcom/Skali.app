import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { ScrollText, Lock, Loader2, Search, ShieldCheck } from 'lucide-react'
import { ROLE_META } from './RoleBadge'

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'report_', label: 'Reports' },
  { key: 'strike', label: 'Strikes' },
  { key: 'inv_', label: 'Investigations', full: true },
  { key: 'assign_role', label: 'Roles' },
]

const exact = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })

function Entry({ r }: { r: any }) {
  return (
    <div className={`bg-panel border rounded-2xl p-3 text-sm flex items-start gap-3 ${r.restricted ? 'border-rose-500/30' : 'border-edge'}`} data-testid="audit-entry">
      {r.restricted ? <Lock className="h-4 w-4 text-rose-300 mt-0.5 shrink-0" /> : <ScrollText className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />}
      <div className="flex-1 min-w-0 break-words">
        <span className="font-medium">#{r.admin_handle}</span>
        {r.admin_role && <span className={`text-[10px] ml-1 ${ROLE_META[r.admin_role]?.color || 'text-slate-500'}`}>{ROLE_META[r.admin_role]?.label}</span>}
        {' '}<span className="text-brand font-mono text-xs">{r.action}</span>
        {r.target && <span className="text-slate-300"> → {r.target}</span>}
        {r.detail && <div className="text-slate-500 text-xs mt-0.5">{r.detail}</div>}
      </div>
      <span className="text-[11px] text-slate-500 shrink-0 text-right tabular-nums">{exact(r.created_at)}</span>
    </div>
  )
}

export default function AuditPanel() {
  const [q, setQ] = useState('')
  const [action, setAction] = useState('')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = async (act = action) => {
    setLoading(true)
    try { setData(await api.adminAudit(q.trim(), act)) } catch (e: any) { alert(e.message); setData(null) }
    setLoading(false)
  }
  useEffect(() => { load() }, [])
  const full = data?.scope === 'full'

  return (
    <div className="space-y-3" data-testid="audit-panel">
      <div className="bg-panel border border-edge rounded-2xl p-3 text-xs text-slate-400 flex items-start gap-2">
        <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
        <span>Permanent legal record. Entries cannot be edited or deleted by anyone, and each one is chained to the previous entry so tampering is detectable.
          {data && !full && ' You are seeing general moderation actions only.'}</span>
      </div>
      <div className="flex gap-2">
        <div className="flex-1 flex items-center gap-2 bg-ink border border-edge rounded-xl px-3 focus-within:border-brand">
          <Search className="h-4 w-4 text-slate-500" />
          <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} data-testid="audit-search-input"
            placeholder="Search staff, @handle or detail…" className="flex-1 bg-transparent py-2.5 outline-none text-sm" />
        </div>
        <button onClick={() => load()} data-testid="audit-search-btn" className="px-4 rounded-xl bg-brand font-medium text-sm">Search</button>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {FILTERS.filter(f => !f.full || full).map(f => (
          <button key={f.key || 'all'} onClick={() => { setAction(f.key); load(f.key) }} data-testid={`audit-filter-${f.key || 'all'}`}
            className={`px-3 py-1 rounded-full text-xs border ${action === f.key ? 'bg-brand/20 border-brand text-white' : 'border-edge text-slate-400 hover:text-white'}`}>{f.label}</button>
        ))}
      </div>
      {loading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
        : !data?.entries?.length ? <p className="text-sm text-slate-500" data-testid="audit-empty">No entries.</p>
        : data.entries.map((r: any) => <Entry key={r.id} r={r} />)}
    </div>
  )
}
