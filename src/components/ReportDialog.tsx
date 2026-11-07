import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import { Flag, X, Loader2, Check } from 'lucide-react'

export const REPORT_REASONS: { key: string; label: string }[] = [
  { key: 'spam', label: 'Spam' },
  { key: 'harassment', label: 'Harassment or bullying' },
  { key: 'hate', label: 'Hate speech' },
  { key: 'impersonation', label: 'Impersonation' },
  { key: 'nsfw', label: 'Sexual / NSFW content' },
  { key: 'csam', label: 'Child sexual abuse material' },
  { key: 'other', label: 'Something else' },
]

type Props = { targetType: 'user' | 'post' | 'message'; targetId: string; title: string; onClose: () => void }

export default function ReportDialog({ targetType, targetId, title, onClose }: Props) {
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async () => {
    if (!reason) return
    setBusy(true)
    try { await api.report(targetType, targetId, reason, note.trim()); setDone(true) }
    catch (e: any) { alert(e.message || 'Could not send report') }
    setBusy(false)
  }

  // Portal to body: ancestors with backdrop-blur/transform would otherwise trap this fixed overlay
  return createPortal(
    <div className="fixed inset-0 z-[70] bg-black/70 flex items-end sm:items-center justify-center p-4" onClick={onClose} data-testid="report-dialog">
      <div className="bg-panel border border-edge rounded-2xl w-full max-w-sm p-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <Flag className="h-4 w-4 text-amber-400" />
          <div className="font-semibold flex-1 truncate">{title}</div>
          <button onClick={onClose} data-testid="report-dialog-close" className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-4 w-4" /></button>
        </div>
        {done ? (
          <div className="py-6 text-center space-y-2" data-testid="report-dialog-done">
            <Check className="h-8 w-8 text-emerald-400 mx-auto" />
            <p className="text-sm text-slate-300">Thanks. Our safety team will review this report.</p>
            <button onClick={onClose} className="mt-2 px-4 py-2 rounded-xl bg-white/5 text-sm">Close</button>
          </div>
        ) : (
          <>
            <div className="space-y-1">
              {REPORT_REASONS.map(r => (
                <button key={r.key} onClick={() => setReason(r.key)} data-testid={`report-reason-${r.key}`}
                  className={`w-full text-left text-sm px-3 py-2 rounded-xl border transition-colors ${reason === r.key ? 'border-brand bg-brand/15 text-white' : 'border-transparent hover:bg-white/5 text-slate-300'}`}>{r.label}</button>
              ))}
            </div>
            <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={2} data-testid="report-note-input"
              placeholder="Add details (optional)" className="mt-3 w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand resize-none" />
            <button onClick={submit} disabled={!reason || busy} data-testid="report-submit-btn"
              className="mt-3 w-full py-2.5 rounded-xl bg-brand font-semibold disabled:opacity-40 flex items-center justify-center gap-2">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}Send report
            </button>
          </>
        )}
      </div>
    </div>,
    document.body
  )
}
