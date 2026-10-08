import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { timeAgo } from '../lib/ui'
import { ScrollText, Lock, Check, X, Clock, Loader2 } from 'lucide-react'

const LOG_LABEL: Record<string, string> = { super_admin: 'Super Admin', co_admin: 'Co-Admin', moderator: 'Moderator' }

function LogTab({ log, access, active, onSelect, onRequest }: any) {
  const mine = log === access.my_log
  const granted = access.granted.includes(log)
  const pending = access.outgoing.some((r: any) => r.log_role === log && r.status === 'pending')
  const open = mine || granted
  return (
    <button data-testid={`audit-log-tab-${log}`} onClick={() => (open ? onSelect(log) : !pending && onRequest(log))}
      className={`px-3 py-2 rounded-xl text-sm flex items-center gap-1.5 border transition-colors ${active ? 'bg-brand/20 border-brand text-white' : 'bg-panel border-edge text-slate-300 hover:border-brand/50'}`}>
      {!open && <Lock className="h-3.5 w-3.5" />}
      {LOG_LABEL[log]}{mine && <span className="text-[10px] text-slate-400">(yours)</span>}
      {!open && <span className="text-[11px] text-slate-500">{pending ? '· pending' : '· request access'}</span>}
      {granted && !mine && <span className="text-[11px] text-emerald-300">· 24h access</span>}
    </button>
  )
}

function IncomingRequests({ items, onDecide }: { items: any[]; onDecide: (id: string, d: 'approve' | 'deny') => void }) {
  if (!items.length) return null
  return (
    <div className="bg-panel border border-amber-500/30 rounded-2xl p-3 space-y-2" data-testid="audit-incoming-requests">
      <div className="text-xs text-amber-300">Access requests for your log (approving grants 24 hours)</div>
      {items.map(r => (
        <div key={r.id} className="flex items-center gap-2 text-sm" data-testid={`audit-request-${r.id}`}>
          <span className="flex-1">#{r.requester_handle} <span className="text-slate-500">({LOG_LABEL[r.requester_role] || r.requester_role}) · {timeAgo(r.created_at)}</span></span>
          <button data-testid={`audit-approve-${r.id}`} onClick={() => onDecide(r.id, 'approve')} className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs flex items-center gap-1"><Check className="h-3 w-3" />Approve</button>
          <button data-testid={`audit-deny-${r.id}`} onClick={() => onDecide(r.id, 'deny')} className="px-2.5 py-1 rounded-lg bg-rose-500/15 text-rose-300 text-xs flex items-center gap-1"><X className="h-3 w-3" />Deny</button>
        </div>
      ))}
    </div>
  )
}

export default function AuditPanel() {
  const [access, setAccess] = useState<any>(null)
  const [log, setLog] = useState('')
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const loadAccess = async () => {
    const a = await api.adminAuditAccess()
    setAccess(a)
    return a
  }
  const loadRows = async (l: string) => {
    setLoading(true)
    try { setRows(await api.adminAudit(l)) } catch (e: any) { setRows([]); alert(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { loadAccess().then(a => { setLog(a.my_log); loadRows(a.my_log) }).catch(() => setLoading(false)) }, [])

  const select = (l: string) => { setLog(l); loadRows(l) }
  const request = async (l: string) => {
    if (!window.confirm(`Request 24-hour access to the ${LOG_LABEL[l]} audit log? Their team will be notified.`)) return
    try { await api.adminAuditRequest(l); await loadAccess() } catch (e: any) { alert(e.message) }
  }
  const decide = async (id: string, d: 'approve' | 'deny') => {
    try { await api.adminAuditDecide(id, d); await loadAccess() } catch (e: any) { alert(e.message) }
  }

  if (!access) return loading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : <p className="text-sm text-slate-500">Could not load audit logs.</p>
  return (
    <div className="space-y-3" data-testid="audit-panel">
      <div className="flex flex-wrap gap-2">
        {access.logs.map((l: string) => <LogTab key={l} log={l} access={access} active={l === log} onSelect={select} onRequest={request} />)}
      </div>
      <IncomingRequests items={access.incoming} onDecide={decide} />
      <div className="text-xs text-slate-500 flex items-center gap-1"><Clock className="h-3 w-3" />Showing the {LOG_LABEL[log]} log · last 100 entries</div>
      {loading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : rows.length === 0
        ? <p className="text-sm text-slate-500" data-testid="audit-empty">No entries yet.</p>
        : rows.map(r => (
          <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 text-sm flex items-center gap-3" data-testid="audit-entry">
            <ScrollText className="h-4 w-4 text-slate-500" />
            <div className="flex-1"><span className="font-medium">#{r.admin_handle}</span> <span className="text-brand">{r.action}</span> <span className="text-slate-400">{r.target}</span>
              {r.detail && <span className="text-slate-500"> — {r.detail}</span>}</div>
            <span className="text-xs text-slate-600">{timeAgo(r.created_at)}</span>
          </div>
        ))}
    </div>
  )
}
