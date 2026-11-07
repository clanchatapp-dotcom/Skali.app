import { useEffect, useState } from 'react'
import { api, setInvSession } from '../../lib/api'
import { Lock, Loader2, KeyRound, ShieldAlert } from 'lucide-react'

function PinInput({ value, onChange, onEnter, testId }: { value: string; onChange: (v: string) => void; onEnter: () => void; testId: string }) {
  return (
    <input value={value} onChange={e => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} onKeyDown={e => e.key === 'Enter' && onEnter()}
      type="password" inputMode="numeric" autoComplete="off" maxLength={6} data-testid={testId} placeholder="••••••"
      className="w-full text-center tracking-[0.6em] text-2xl font-mono bg-ink border border-edge rounded-xl py-3 outline-none focus:border-rose-400" />
  )
}

export default function PinGate({ onUnlocked }: { onUnlocked: (expiresAt: string) => void }) {
  const [status, setStatus] = useState<any>(null)
  const [pin, setPin] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const loadStatus = () => api.invStatus().then(setStatus).catch((e: any) => setErr(e.message))
  useEffect(() => { loadStatus() }, [])

  const unlock = async (p = pin) => {
    if (p.length !== 6) return setErr('Enter all 6 digits')
    setBusy(true); setErr('')
    try { const r = await api.invUnlock(p); setInvSession(r.token); onUnlocked(r.expires_at) }
    catch (e: any) { setErr(e.message); setPin(''); loadStatus() }
    setBusy(false)
  }
  const create = async () => {
    if (pin.length !== 6) return setErr('Your PIN must be 6 digits')
    if (pin !== confirm) return setErr('The two PINs do not match')
    setBusy(true); setErr('')
    try { await api.invSetPin(pin); await unlock(pin) } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  if (!status) return <div className="py-16 grid place-items-center text-slate-500">{err || <Loader2 className="h-6 w-6 animate-spin" />}</div>
  const creating = !status.has_pin

  return (
    <div className="max-w-sm mx-auto py-8 space-y-5" data-testid="inv-pin-gate">
      <div className="text-center space-y-2">
        <div className="h-14 w-14 mx-auto rounded-2xl bg-rose-500/10 border border-rose-500/30 grid place-items-center"><Lock className="h-6 w-6 text-rose-300" /></div>
        <h2 className="text-lg font-bold">Restricted area</h2>
        <p className="text-sm text-slate-400">{creating ? 'Create your personal 6-digit Investigations PIN. You will enter it every time you open an investigation session.' : 'Enter your personal 6-digit PIN to open an investigation session.'}</p>
      </div>
      {status.locked_until ? (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 text-sm text-rose-200 flex gap-2" data-testid="inv-locked-notice">
          <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />Too many wrong PINs. Locked until {new Date(status.locked_until).toLocaleTimeString()}. This lockout has been logged.
        </div>
      ) : (
        <div className="space-y-3">
          <PinInput value={pin} onChange={setPin} onEnter={() => (creating ? create() : unlock())} testId="inv-pin-input" />
          {creating && <PinInput value={confirm} onChange={setConfirm} onEnter={create} testId="inv-pin-confirm-input" />}
          {err && <p className="text-sm text-rose-300 text-center" data-testid="inv-pin-error">{err}</p>}
          <button onClick={() => (creating ? create() : unlock())} disabled={busy} data-testid="inv-pin-submit-btn"
            className="w-full py-3 rounded-xl bg-rose-600 hover:bg-rose-500 font-semibold disabled:opacity-50 flex items-center justify-center gap-2 transition-colors">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}{creating ? 'Create PIN & unlock' : 'Unlock'}
          </button>
        </div>
      )}
      <p className="text-[11px] text-slate-500 text-center">Every PIN attempt, search and record you open is written to the permanent audit log.</p>
    </div>
  )
}
