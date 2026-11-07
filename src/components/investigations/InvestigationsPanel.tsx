import { useEffect, useState } from 'react'
import { api, setInvSession, hasInvSession } from '../../lib/api'
import PinGate from './PinGate'
import CaseLists from './CaseLists'
import { FeedView, DmsView } from './RecordViews'
import { Search, Loader2, Lock, LayoutGrid, MessagesSquare, Eye, KeyRound, Send } from 'lucide-react'

function SubjectCard({ s, onFeed, onDms, onRequest, busy }: any) {
  const c = s.case
  const blocked = c && !c.has_access
  return (
    <div className="bg-panel border border-edge rounded-2xl p-4 space-y-3" data-testid="inv-subject-card">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-full bg-white/5 overflow-hidden shrink-0">{s.subject.avatar_url && <img src={s.subject.avatar_url} className="h-full w-full object-cover" />}</div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold truncate">{s.subject.display_name} <span className="text-xs text-slate-500">#{s.subject.handle}</span></div>
          <div className="text-[11px] text-slate-500">{s.subject.account_type}{s.subject.is_minor && ' · MINOR'}{s.subject.flagged && ' · flagged'}{s.subject.watchlisted && ' · watchlisted'}{s.subject.banned && ' · banned'}</div>
        </div>
      </div>
      {blocked ? (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-3 text-sm text-amber-200 space-y-2" data-testid="inv-case-locked">
          <div className="flex items-center gap-2"><Lock className="h-4 w-4" />This person is in <b>#{c.owner_handle}</b>'s private case list.</div>
          {c.request_status === 'pending'
            ? <div className="text-xs text-amber-300/80" data-testid="inv-request-pending">Access requested · waiting for #{c.owner_handle}</div>
            : <button onClick={onRequest} disabled={busy} data-testid="inv-request-access-btn" className="px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-200 text-xs font-semibold flex items-center gap-1"><Send className="h-3 w-3" />Request access{c.request_status === 'declined' ? ' again' : ''}</button>}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <button onClick={onFeed} disabled={busy} data-testid="inv-feed-btn" className="py-3 rounded-xl bg-brand/15 border border-brand/40 text-brand font-bold tracking-widest flex items-center justify-center gap-2 hover:bg-brand/25 transition-colors disabled:opacity-50"><LayoutGrid className="h-4 w-4" />FEED</button>
          <button onClick={onDms} disabled={busy} data-testid="inv-dms-btn" className="py-3 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-300 font-bold tracking-widest flex items-center justify-center gap-2 hover:bg-rose-500/25 transition-colors disabled:opacity-50"><MessagesSquare className="h-4 w-4" />DMS</button>
        </div>
      )}
      {c && c.has_access && <div className="text-[11px] text-slate-500">{c.mine ? 'In your private case list' : `Shared with you by #${c.owner_handle}`}</div>}
    </div>
  )
}

function SuperPinReset() {
  const [h, setH] = useState('')
  const reset = async () => {
    const handle = h.trim().replace(/^[#@]/, '')
    if (!handle || !confirm(`Reset #${handle}'s Investigations PIN? They will create a new one next time.`)) return
    try { await api.invResetPin(handle); setH(''); alert('PIN reset.') } catch (e: any) { alert(e.message) }
  }
  return (
    <div className="bg-panel border border-edge rounded-2xl p-3 flex gap-2 items-center" data-testid="inv-super-reset">
      <KeyRound className="h-4 w-4 text-amber-300 shrink-0" />
      <input value={h} onChange={e => setH(e.target.value)} placeholder="Reset a staff PIN: @handle" data-testid="inv-reset-pin-input" className="flex-1 bg-ink border border-edge rounded-lg px-3 py-2 text-sm outline-none focus:border-brand" />
      <button onClick={reset} data-testid="inv-reset-pin-btn" className="px-3 py-2 rounded-lg bg-amber-500/15 text-amber-300 text-xs font-semibold">Reset PIN</button>
    </div>
  )
}

export default function InvestigationsPanel({ isSuper }: { isSuper: boolean }) {
  const [unlocked, setUnlocked] = useState<string | null>(hasInvSession() ? 'active' : null)
  const [handle, setHandle] = useState('')
  const [reason, setReason] = useState('')
  const [subject, setSubject] = useState<any>(null)
  const [view, setView] = useState<{ kind: 'feed' | 'dms'; data: any } | null>(null)
  const [cases, setCases] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  const expired = (e: any) => { if (/session|PIN/i.test(e.message || '')) { setInvSession(''); setUnlocked(null) } }
  const loadCases = () => api.invCases().then(setCases).catch(expired)
  useEffect(() => { if (unlocked) loadCases() }, [unlocked])

  const run = async (fn: () => Promise<any>) => {
    setBusy(true)
    try { await fn() } catch (e: any) { alert(e.message); expired(e) }
    setBusy(false)
  }
  const search = (h = handle) => run(async () => {
    const x = h.trim().replace(/^[#@]/, ''); if (!x) return
    setHandle(x); setView(null); setSubject(await api.invSearch(x))
  })
  const open = (kind: 'feed' | 'dms') => run(async () => {
    const h = subject.subject.handle
    const data = kind === 'feed' ? await api.invFeed(h, reason) : await api.invDms(h, reason)
    setView({ kind, data }); setSubject(await api.invSearch(h)); loadCases()
  })
  const request = () => run(async () => { await api.invRequest(subject.case.id); setSubject(await api.invSearch(subject.subject.handle)); loadCases() })
  const lock = async () => { try { await api.invLock() } catch {} setInvSession(''); setUnlocked(null); setSubject(null); setView(null); setCases(null) }

  if (!unlocked) return <PinGate onUnlocked={setUnlocked} />

  return (
    <div className="space-y-4" data-testid="investigations-panel">
      <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-3 text-xs text-rose-200 flex items-center gap-2" data-testid="inv-logged-notice">
        <Eye className="h-4 w-4 shrink-0" />
        <span className="flex-1"><b>This session is logged.</b> Every search, FEED and DMS you open is recorded with your name and the exact time. The person is not notified.</span>
        <button onClick={lock} data-testid="inv-lock-btn" className="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-100 font-semibold flex items-center gap-1 shrink-0"><Lock className="h-3 w-3" />Lock</button>
      </div>
      <div className="flex gap-2">
        <div className="flex-1 flex items-center gap-2 bg-panel border border-edge rounded-xl px-3 focus-within:border-rose-400">
          <Search className="h-4 w-4 text-slate-500" />
          <input value={handle} onChange={e => setHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} data-testid="inv-handle-input"
            placeholder="@handle" className="flex-1 bg-transparent py-2.5 outline-none" />
        </div>
        <button onClick={() => search()} disabled={busy} data-testid="inv-search-btn" className="px-4 rounded-xl bg-rose-600 hover:bg-rose-500 font-semibold disabled:opacity-50 flex items-center gap-2 transition-colors">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}Search</button>
      </div>
      {subject && !subject.case && (
        <input value={reason} onChange={e => setReason(e.target.value)} maxLength={300} data-testid="inv-reason-input"
          placeholder="Case reason / legal basis (saved on the case and in the audit log)" className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-rose-400" />
      )}
      {subject && <SubjectCard s={subject} busy={busy} onFeed={() => open('feed')} onDms={() => open('dms')} onRequest={request} />}
      {view && (
        <div className="bg-panel border border-edge rounded-2xl p-4 space-y-3">
          <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">{view.kind === 'feed' ? 'Feed · all tiers' : 'Direct messages'} · #{view.data.subject.handle}</div>
          {view.kind === 'feed' ? <FeedView data={view.data} /> : <DmsView data={view.data} />}
        </div>
      )}
      {cases && <CaseLists cases={cases} onOpen={h => search(h)}
        onDecide={(id, d) => run(async () => { await api.invDecide(id, d); loadCases() })}
        onRevoke={(cid, aid) => confirm('Revoke this colleague\'s access to the case?') && run(async () => { await api.invRevoke(cid, aid); loadCases() })}
        onClose={cid => confirm('Close this case? It leaves your list; the audit log keeps the record.') && run(async () => { await api.invClose(cid); setSubject(null); setView(null); loadCases() })} />}
      {isSuper && <SuperPinReset />}
    </div>
  )
}
