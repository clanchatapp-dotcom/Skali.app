import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { KeyRound, Check, X } from 'lucide-react'
import { ROLE_META } from './RoleBadge'

const LOGS = ['super_admin', 'co_admin', 'moderator']
const label = (r: string) => ROLE_META[r]?.label || r
const until = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export default function AuditAccess({ log, onPick }: { log: string; onPick: (log: string) => void }) {
  const [acc, setAcc] = useState<any>(null)
  const load = async () => { try { setAcc(await api.auditAccess()) } catch { setAcc(null) } }
  useEffect(() => { load() }, [])
  if (!acc) return null

  const act = async (fn: () => Promise<any>) => { try { await fn() } catch (e: any) { alert(e.message) } load() }
  const pending = (r: string) => acc.outgoing.some((o: any) => o.log_role === r && o.status === 'pending')
  const grant = (r: string) => acc.outgoing.find((o: any) => o.log_role === r && o.status === 'approved' && acc.active.includes(r))

  return (
    <div className="space-y-2" data-testid="audit-access">
      <div className="flex gap-1.5 flex-wrap">
        {LOGS.map(r => {
          const own = r === acc.my_log
          if (!own && !acc.can_request) return null
          const open = own || acc.active.includes(r)
          return open ? (
            <button key={r} onClick={() => onPick(r)} data-testid={`audit-log-${r}`}
              className={`px-3 py-1 rounded-full text-xs border ${log === r ? 'bg-brand/20 border-brand text-white' : 'border-edge text-slate-400 hover:text-white'}`}>
              {own ? `My log (${label(r)})` : `${label(r)} log · until ${until(grant(r)?.expires_at)}`}
            </button>
          ) : (
            <button key={r} disabled={pending(r)} onClick={() => act(() => api.auditAccessRequest(r))} data-testid={`audit-request-${r}`}
              className="px-3 py-1 rounded-full text-xs border border-dashed border-edge text-slate-400 hover:text-white disabled:opacity-60 flex items-center gap-1">
              <KeyRound className="h-3 w-3" />{pending(r) ? `${label(r)} log · request sent` : `Request ${label(r)} log`}
            </button>
          )
        })}
      </div>
      {acc.incoming.map((r: any) => (
        <div key={r.id} className="bg-panel border border-amber-500/30 rounded-2xl p-3 text-sm flex items-center gap-2" data-testid="audit-access-incoming">
          <span className="flex-1">#{r.requester_handle} <span className={`text-xs ${ROLE_META[r.requester_role]?.color || ''}`}>{label(r.requester_role)}</span> wants to view your {label(r.log_role)} log for 24 hours.</span>
          <button onClick={() => act(() => api.auditAccessDecide(r.id, 'approve'))} data-testid={`audit-access-approve-${r.id}`} className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-300"><Check className="h-4 w-4" /></button>
          <button onClick={() => act(() => api.auditAccessDecide(r.id, 'decline'))} data-testid={`audit-access-decline-${r.id}`} className="p-1.5 rounded-lg bg-rose-500/20 text-rose-300"><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  )
}
