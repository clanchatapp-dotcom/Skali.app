import { timeAgo } from '../../lib/ui'
import { FolderLock, Check, X, Share2, Trash2 } from 'lucide-react'

type Props = { cases: any; onOpen: (handle: string) => void; onDecide: (id: string, d: 'approve' | 'decline') => void; onRevoke: (caseId: string, adminId: string) => void; onClose: (caseId: string) => void }

function Row({ c, children, onOpen }: any) {
  return (
    <div className="bg-ink border border-edge rounded-xl p-3 flex items-center gap-3 flex-wrap" data-testid={`inv-case-${c.subject_handle}`}>
      <FolderLock className="h-4 w-4 text-rose-300 shrink-0" />
      <button onClick={() => onOpen(c.subject_handle)} className="flex-1 min-w-0 text-left">
        <div className="font-medium truncate">{c.subject_name} <span className="text-xs text-slate-500">#{c.subject_handle}</span></div>
        <div className="text-[11px] text-slate-500 truncate">{c.mine ? 'Your case' : `Owner #${c.owner_handle}`} · opened {timeAgo(c.created_at)}{c.reason ? ` · ${c.reason}` : ''}</div>
      </button>
      {children}
    </div>
  )
}

export default function CaseLists({ cases, onOpen, onDecide, onRevoke, onClose }: Props) {
  return (
    <div className="space-y-4" data-testid="inv-case-lists">
      {cases.incoming.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-2xl p-3 space-y-2" data-testid="inv-incoming-requests">
          <div className="text-xs text-amber-300 font-medium">Access requests for your cases</div>
          {cases.incoming.map((r: any) => (
            <div key={r.id} className="flex items-center gap-2 text-sm flex-wrap">
              <span className="flex-1 min-w-0">#{r.requester_handle} wants to see <b>#{r.subject_handle}</b> <span className="text-slate-500 text-xs">· {timeAgo(r.created_at)}</span></span>
              <button onClick={() => onDecide(r.id, 'approve')} data-testid={`inv-approve-${r.id}`} className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs flex items-center gap-1"><Check className="h-3 w-3" />Approve</button>
              <button onClick={() => onDecide(r.id, 'decline')} data-testid={`inv-decline-${r.id}`} className="px-2.5 py-1 rounded-lg bg-rose-500/15 text-rose-300 text-xs flex items-center gap-1"><X className="h-3 w-3" />Decline</button>
            </div>
          ))}
        </div>
      )}
      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">My private case list · {cases.mine.length}</div>
        {cases.mine.length === 0 && <p className="text-sm text-slate-500">No open cases. Search a handle and open FEED or DMS to start one.</p>}
        {cases.mine.map((c: any) => (
          <Row key={c.id} c={c} onOpen={onOpen}>
            {c.grants.map((g: any) => (
              <button key={g.admin_id} onClick={() => onRevoke(c.id, g.admin_id)} title="Revoke access" data-testid={`inv-revoke-${c.id}-${g.handle}`}
                className="px-2 py-1 rounded-lg bg-white/5 text-[11px] text-slate-300 flex items-center gap-1 hover:text-rose-300"><Share2 className="h-3 w-3" />#{g.handle}<X className="h-3 w-3" /></button>
            ))}
            <button onClick={() => onClose(c.id)} data-testid={`inv-close-${c.id}`} className="px-2 py-1 rounded-lg border border-edge text-[11px] text-slate-400 flex items-center gap-1 hover:text-white"><Trash2 className="h-3 w-3" />Close case</button>
          </Row>
        ))}
      </div>
      {cases.shared.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Shared with me · {cases.shared.length}</div>
          {cases.shared.map((c: any) => <Row key={c.id} c={c} onOpen={onOpen} />)}
        </div>
      )}
      {cases.outgoing.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">My access requests</div>
          {cases.outgoing.map((r: any) => (
            <div key={r.id} className="text-xs text-slate-400">#{r.subject_handle} (owner #{r.owner_handle}) · <span className={r.status === 'approved' ? 'text-emerald-400' : ['declined', 'revoked'].includes(r.status) ? 'text-rose-400' : 'text-amber-400'}>{r.status}</span> · {timeAgo(r.created_at)}</div>
          ))}
        </div>
      )}
    </div>
  )
}
