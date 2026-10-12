import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../lib/api'
import CopyField from './CopyField'
import { Loader2, MonitorUp, Radio, X } from 'lucide-react'

const STATUS: Record<string, { label: string; cls: string }> = {
  publishing: { label: 'OBS connected — receiving video', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/40' },
  buffering: { label: 'OBS buffering…', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/40' },
  error: { label: 'OBS error', cls: 'text-rose-300 bg-rose-500/10 border-rose-500/40' },
  idle: { label: 'Waiting for OBS signal', cls: 'text-slate-300 bg-white/5 border-edge' },
  unknown: { label: 'Signal status unavailable', cls: 'text-slate-400 bg-white/5 border-edge' },
}

const STEPS = [
  'Open OBS → Settings → Stream.',
  'Service: Custom… then paste the Server URL and Stream Key below.',
  'Click "Start Streaming" in OBS, then press Go live here.',
]

export default function ConnectObsModal({ busy, error, onStart, onClose }: {
  busy: boolean; error?: string; onStart: () => void; onClose: () => void
}) {
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    const load = () => api.streamObsConnect().then(setD).catch((e: any) => setErr(e.message))
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  const st = STATUS[d?.status] || STATUS.unknown

  return createPortal(
    <div className="fixed inset-0 z-[90] bg-black/75 backdrop-blur grid place-items-center p-4" onClick={onClose} data-testid="connect-obs-modal">
      <div className="bg-panel border border-edge rounded-2xl w-full max-w-xl overflow-hidden animate-pop" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-edge flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-brand/15 grid place-items-center"><MonitorUp className="h-5 w-5 text-brand" /></div>
          <div className="flex-1 min-w-0">
            <h2 className="font-extrabold text-lg leading-tight" data-testid="connect-obs-title">Connect to OBS</h2>
            <p className="text-xs text-slate-400">LiveKit ingress · RTMPS</p>
          </div>
          <button onClick={onClose} aria-label="Close" data-testid="connect-obs-close"
            className="h-9 w-9 grid place-items-center rounded-full text-slate-400 hover:bg-white/10 transition-colors"><X className="h-4 w-4" /></button>
        </div>

        <div className="p-5 space-y-4">
          {!d && !err ? (
            <div className="py-8 grid place-items-center"><Loader2 className="h-5 w-5 animate-spin text-slate-500" /></div>
          ) : d && (
            <>
              <ol className="space-y-1.5 text-sm text-slate-300 list-decimal list-inside" data-testid="connect-obs-steps">
                {STEPS.map(s => <li key={s}>{s}</li>)}
              </ol>
              <CopyField label="Server / URL (OBS → Server)" value={d.server_url} testId="connect-obs-url" />
              <CopyField label="Stream Key (OBS → Stream Key)" value={d.stream_key} secret testId="connect-obs-key" />
              <div className="grid gap-3 sm:grid-cols-2">
                <CopyField label={`Ingress ID (name: ${d.ingress_name})`} value={d.ingress_id} testId="connect-obs-ingress" />
                <CopyField label="Room" value={d.room} testId="connect-obs-room" />
              </div>
              <div className={`text-xs font-semibold px-3 py-2 rounded-xl border ${st.cls}`} data-testid="connect-obs-status">
                {st.label}{d.error ? ` · ${d.error}` : ''}
              </div>
            </>
          )}
          {error && <p className="text-sm text-rose-400" data-testid="connect-obs-start-error">{error}</p>}
          {err && <p className="text-sm text-rose-400" data-testid="connect-obs-error">{err}</p>}
        </div>

        <div className="px-5 py-4 border-t border-edge flex justify-end gap-2">
          <button onClick={onClose} data-testid="connect-obs-cancel"
            className="px-4 py-2 rounded-full border border-edge text-sm text-slate-300 hover:bg-white/5 transition-colors">Cancel</button>
          <button onClick={onStart} disabled={busy || !d} data-testid="connect-obs-golive-btn"
            className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-gradient-to-r from-rose-600 to-brand text-white font-bold text-sm disabled:opacity-40 active:scale-95 transition-transform">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />} Go live
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
