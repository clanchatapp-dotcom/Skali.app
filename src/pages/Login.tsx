import { useState, useEffect } from 'react'
import { useAuth } from '../lib/auth'
import { warmup } from '../lib/api'
import { Lock, Users, Sparkles, Mail, Loader2 } from 'lucide-react'

export default function Login() {
  const { loginEmail, registerEmail, loginGoogle } = useAuth()
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [name, setName] = useState('')
  const [dob, setDob] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [err, setErr] = useState('')

  // Wake a sleeping backend the moment the login screen opens so the user's
  // actual sign-in lands on an already-warming server (Render cold starts).
  useEffect(() => { warmup() }, [])

  const WAIT_MSGS = [
    'Waking up the server — hang tight…',
    'Almost there, connecting…',
    'Still connecting, thanks for your patience…',
    'One more moment…',
  ]
  const onProgress = (n: number) => setStatus(WAIT_MSGS[Math.min(n - 1, WAIT_MSGS.length - 1)])

  const google = async () => {
    setErr(''); setBusy(true); setStatus('Opening Google…')
    try { await loginGoogle() } catch (e: any) { setErr(e.message || 'Google sign-in failed') }
    finally { setBusy(false); setStatus('') }
  }
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    setStatus(mode === 'register' ? 'Creating your account…' : 'Signing you in…')
    try {
      if (mode === 'register') await registerEmail(email.trim(), password, name.trim() || email.split('@')[0], dob, onProgress)
      else await loginEmail(email.trim(), password, onProgress)
    } catch (e: any) {
      // Invalid credentials / validation -> show the real message. Anything else
      // (server still unreachable after retries) -> gentle, non-scary prompt.
      if (e?.status === 400 || e?.status === 401 || e?.status === 409) setErr(e.message || 'Please check your details and try again.')
      else setErr("We couldn't reach the server just yet. Please tap the button again in a moment.")
    } finally { setBusy(false); setStatus('') }
  }

  return (
    <div className="min-h-full grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-12 relative overflow-hidden">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Skali" className="h-12 w-12 object-contain drop-shadow-lg" />
          <span className="text-2xl font-extrabold tracking-tight">Skali</span>
        </div>
        <div className="space-y-6 max-w-md">
          <h1 className="text-5xl font-extrabold leading-tight">
            Your place to <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand to-violet-400">gather</span>.
          </h1>
          <p className="text-slate-300 text-lg">No algorithm. No ads in your feed. No toxic metrics. Your circle. Your rules. No bullshit.</p>
          <div className="space-y-3 pt-2">
            {[[Users, 'Three tiers: Public, Followers & Inner Circle'], [Lock, 'Tier-gated, encrypted DMs & calls'], [Sparkles, 'Chronological feed — never an algorithm']].map(([Icon, t]: any, i) => (
              <div key={i} className="flex items-center gap-3 text-slate-200">
                <div className="h-9 w-9 rounded-xl bg-white/5 border border-edge grid place-items-center"><Icon className="h-4 w-4 text-brand" /></div>
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="text-slate-500 text-sm">Skali · web + android</div>
        <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute -top-24 -left-16 h-72 w-72 rounded-full bg-brand/20 blur-3xl" />
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm bg-panel/80 backdrop-blur border border-edge rounded-3xl p-8 shadow-2xl shadow-black/50">
          <div className="lg:hidden flex items-center gap-3 mb-6">
            <img src="/logo.png" alt="Skali" className="h-10 w-10 object-contain" />
            <span className="text-xl font-extrabold">Skali</span>
          </div>
          <h2 className="text-2xl font-bold">{mode === 'register' ? 'Create your account' : 'Welcome back'}</h2>
          <p className="text-slate-400 text-sm mt-1 mb-6">{mode === 'register' ? 'Join the gathering.' : 'Sign in to continue.'}</p>

          <button onClick={google} disabled={busy}
            className="w-full flex items-center justify-center gap-3 bg-white text-slate-900 font-semibold rounded-xl py-3 hover:bg-slate-100 transition disabled:opacity-60">
            <svg className="h-5 w-5" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.9 2.4 30.3 0 24 0 14.6 0 6.4 5.4 2.5 13.3l7.9 6.1C12.3 13.2 17.6 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.1-3.8 6.5-9.4 6.5-16z"/><path fill="#FBBC05" d="M10.4 28.6c-.5-1.4-.8-2.9-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C.9 16.5 0 20.1 0 24s.9 7.5 2.5 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.3 0 11.6-2.1 15.5-5.7l-7.1-5.5c-2 1.4-4.6 2.2-8.4 2.2-6.4 0-11.7-3.7-13.6-9.9l-7.9 6.1C6.4 42.6 14.6 48 24 48z"/></svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 my-6 text-slate-500 text-xs">
            <div className="h-px bg-edge flex-1" /> OR <div className="h-px bg-edge flex-1" />
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === 'register' && (
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Display name"
                className="w-full bg-ink border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand transition" />
            )}
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1 px-1">Date of birth</label>
                <input type="date" required value={dob} onChange={e => setDob(e.target.value)}
                  max={new Date().toISOString().split('T')[0]}
                  className="w-full bg-ink border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand transition text-slate-200" />
                <p className="text-[11px] text-slate-500 mt-1 px-1">You must be 13+. This keeps under-18s protected and can't be changed later.</p>
              </div>
            )}
            <div className="relative">
              <Mail className="h-4 w-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@email.com"
                className="w-full bg-ink border border-edge rounded-xl pl-10 pr-4 py-3 outline-none focus:border-brand transition" />
            </div>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="Password (min 6 chars)"
              className="w-full bg-ink border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand transition" />
            <button disabled={busy}
              className="w-full bg-gradient-to-r from-brand to-violet-600 font-semibold rounded-xl py-3 hover:opacity-95 transition disabled:opacity-80 flex items-center justify-center gap-2">
              {busy ? (<><Loader2 className="h-4 w-4 animate-spin" />{status || 'Please wait…'}</>) : (mode === 'register' ? 'Create account' : 'Sign in')}
            </button>
          </form>

          {busy && !err && <p className="text-slate-400 text-xs mt-3 text-center">This can take a few seconds the first time while the server wakes up.</p>}
          {err && <p className="text-rose-400 text-sm mt-4">{err}</p>}

          <p className="text-sm text-slate-400 mt-5 text-center">
            {mode === 'register' ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button onClick={() => { setErr(''); setMode(mode === 'register' ? 'signin' : 'register') }}
              className="text-brand font-semibold hover:underline">
              {mode === 'register' ? 'Sign in' : 'Create one'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
