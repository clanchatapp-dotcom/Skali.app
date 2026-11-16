import { useEffect, useState } from 'react'
import { Flame, Loader2, KeyRound } from 'lucide-react'
import { api } from '../../lib/api'

function CodeInput({ value, onChange, onEnter, testId, placeholder = '••••••' }: { value: string; onChange: (v: string) => void; onEnter?: () => void; testId: string; placeholder?: string }) {
  return (
    <input value={value} onChange={e => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} onKeyDown={e => e.key === 'Enter' && onEnter?.()}
      type="password" inputMode="numeric" autoComplete="off" maxLength={6} data-testid={testId} placeholder={placeholder}
      className="w-full text-center tracking-[0.6em] text-2xl font-mono bg-ink border border-edge rounded-xl py-3 outline-none focus:border-rose-400" />
  )
}

// Asked for on every visit; the session token lives only in memory.
export default function NsfwGate({ onUnlocked }: { onUnlocked: (token: string) => void }) {
  const [status, setStatus] = useState<any>(null)
  const [mode, setMode] = useState<'enter' | 'change'>('enter')
  const [pin, setPin] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api.nsfwStatus().then(setStatus).catch((e: any) => setErr(e.message))
  useEffect(() => { load() }, [])

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setErr(''); setMsg('')
    try { await fn() } catch (e: any) { setErr(e.message); setPin(''); load() }
    setBusy(false)
  }
  const unlock = () => run(async () => {
    if (pin.length !== 6) throw new Error('Enter all 6 digits')
    onUnlocked((await api.nsfwUnlock(pin)).token)
  })
  const create = () => run(async () => {
    if (next.length !== 6) throw new Error('Your code must be 6 digits')
    if (next !== confirm) throw new Error('Codes do not match')
    await api.nsfwSetPin(next, status?.has_pin ? pin : undefined)
    setNext(''); setConfirm(''); setPin(''); setMode('enter'); setMsg('Code saved. Enter it to continue.'); load()
  })

  if (!status) return <div className="grid place-items-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
  if (!status.eligible) return <p className="text-slate-400 text-sm p-6" data-testid="nsfw-not-eligible">Verify your age to access adult content.</p>
  const creating = !status.has_pin || mode === 'change'

  return (
    <div className="max-w-sm mx-auto py-16 px-4 space-y-4" data-testid="nsfw-gate">
      <div className="h-14 w-14 rounded-2xl bg-rose-500/10 border border-rose-500/30 grid place-items-center mx-auto"><Flame className="h-7 w-7 text-rose-400" /></div>
      <h1 className="text-xl font-semibold text-center">{!status.has_pin ? 'Create your 6-digit code' : mode === 'change' ? 'Change your code' : 'Enter your 6-digit code'}</h1>
      <p className="text-sm text-slate-500 text-center">Adult content is locked behind your personal code. You'll be asked for it every time.</p>
      {creating ? (
        <>
          {status.has_pin && <CodeInput value={pin} onChange={setPin} testId="nsfw-current-code" placeholder="current" />}
          <CodeInput value={next} onChange={setNext} testId="nsfw-new-code" placeholder="new" />
          <CodeInput value={confirm} onChange={setConfirm} onEnter={create} testId="nsfw-confirm-code" placeholder="confirm" />
          <button onClick={create} disabled={busy} data-testid="nsfw-save-code" className="w-full py-3 rounded-xl bg-rose-500 hover:bg-rose-600 font-semibold disabled:opacity-60">Save code</button>
        </>
      ) : (
        <>
          <CodeInput value={pin} onChange={setPin} onEnter={unlock} testId="nsfw-code-input" />
          <button onClick={unlock} disabled={busy || !!status.locked_until} data-testid="nsfw-unlock" className="w-full py-3 rounded-xl bg-rose-500 hover:bg-rose-600 font-semibold disabled:opacity-60">Unlock</button>
        </>
      )}
      {status.has_pin && (
        <button onClick={() => { setMode(mode === 'change' ? 'enter' : 'change'); setErr(''); setMsg(''); setPin('') }} data-testid="nsfw-change-code-toggle"
          className="w-full text-xs text-slate-400 hover:text-white flex items-center justify-center gap-1"><KeyRound className="h-3 w-3" />{mode === 'change' ? 'Back to unlock' : 'Change code'}</button>
      )}
      {status.has_pin && (
        <button onClick={() => run(async () => { await api.nsfwResetRequest(); setMsg('Reset requested. An admin will reset your code.'); load() })}
          disabled={busy || status.reset_pending} data-testid="nsfw-request-reset"
          className="w-full text-xs text-slate-500 hover:text-white disabled:opacity-60">
          {status.reset_pending ? 'Code reset requested' : 'Forgot your code? Request a reset'}
        </button>
      )}
      {err && <p className="text-sm text-rose-400 text-center" data-testid="nsfw-gate-error">{err}</p>}
      {msg && <p className="text-sm text-emerald-400 text-center" data-testid="nsfw-gate-msg">{msg}</p>}
    </div>
  )
}
