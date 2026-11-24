import { useState } from 'react'
import { BellRing, Loader2 } from 'lucide-react'
import { api } from '../lib/api'

// Sends a test alert to this account's phones and shows what happened, to diagnose push.
export default function PushTestCard() {
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<any>(null)
  const [err, setErr] = useState('')

  const run = async () => {
    setBusy(true); setErr(''); setRes(null)
    try { setRes(await api.pushTest()) } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  return (
    <section className="bg-panel border border-edge rounded-2xl p-5 mt-4 space-y-3" data-testid="push-test-card">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="font-medium">Test notifications</div>
          <div className="text-xs text-slate-500">Sends a test alert to every phone signed in to this account.</div>
        </div>
        <button onClick={run} disabled={busy} data-testid="push-test-btn"
          className="px-4 py-2 rounded-xl bg-brand/20 border border-brand/40 text-sm flex items-center gap-2 disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BellRing className="h-4 w-4" />}Send test
        </button>
      </div>
      {err && <p className="text-sm text-rose-400" data-testid="push-test-error">{err}</p>}
      {res && (
        <div className="text-sm space-y-1.5" data-testid="push-test-result">
          {!res.server_ready && <p className="text-rose-400">The server has no Firebase credentials, so it can't send push.</p>}
          {res.server_ready && res.devices.length === 0 && <p className="text-amber-300" data-testid="push-test-no-devices">No phone is registered for push on this account yet. Open the app on your phone and allow notifications.</p>}
          {res.devices.map((d: any, i: number) => (
            <p key={i} className={d.ok ? 'text-emerald-400' : 'text-rose-400'} data-testid={`push-test-device-${i}`}>
              {d.platform || 'device'}: {d.ok ? 'sent - check your phone' : d.ok === null ? 'registered' : d.error}
            </p>
          ))}
          {res.device_errors?.map((d: any, i: number) => (
            <p key={'e' + i} className="text-amber-300" data-testid={`push-test-device-error-${i}`}>{d.platform} reported: {d.error}</p>
          ))}
        </div>
      )}
    </section>
  )
}
