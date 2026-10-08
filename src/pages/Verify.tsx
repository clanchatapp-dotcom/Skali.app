import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldCheck, ShieldAlert, ShieldQuestion, Clock, Lock, Unlock } from 'lucide-react'
import { api } from '../lib/api'

type VStatus = 'unverified' | 'pending' | 'verified' | 'failed'
interface VState {
  verification: { identity: { status: VStatus; provider?: string }, age: { status: VStatus; provider?: string, region?: string } }
  monetisation_enabled: boolean
  is_minor: boolean
}

const STATUS_META: Record<VStatus, { label: string; cls: string; Icon: any }> = {
  verified: { label: 'Verified', cls: 'text-emerald-400', Icon: ShieldCheck },
  pending: { label: 'Pending', cls: 'text-amber-400', Icon: Clock },
  failed: { label: 'Failed', cls: 'text-rose-400', Icon: ShieldAlert },
  unverified: { label: 'Not verified', cls: 'text-slate-400', Icon: ShieldQuestion },
}

export default function Verify() {
  const nav = useNavigate()
  const [state, setState] = useState<VState | null>(null)
  const [busy, setBusy] = useState<string>('')
  const [err, setErr] = useState('')

  const load = async () => {
    try { setState(await api.verificationStatus()) } catch (e: any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  const start = async (type: 'identity' | 'age', provider: 'yoti' | 'oneid') => {
    setBusy(`${type}:${provider}`); setErr('')
    try {
      const r = await api.verificationStart(type, provider)
      // In production this would redirect to the provider's hosted flow:
      if (r.redirect_url) window.open(r.redirect_url, '_blank')
      await load()
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  const Row = ({ title, type, desc }: { title: string; type: 'identity' | 'age'; desc: string }) => {
    const st = (state?.verification?.[type]?.status || 'unverified') as VStatus
    const meta = STATUS_META[st]
    const done = st === 'verified'
    return (
      <div className="bg-panel border border-edge rounded-2xl p-5" data-testid={`verify-${type}-card`}>
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold">{title}</h3>
          <span className={`flex items-center gap-1.5 text-sm font-medium ${meta.cls}`} data-testid={`verify-${type}-status`}>
            <meta.Icon size={16} /> {meta.label}
          </span>
        </div>
        <p className="text-sm text-slate-400 mb-4">{desc}</p>
        {!done && (
          <div className="flex gap-2">
            <button data-testid={`verify-${type}-yoti`} disabled={!!busy} onClick={() => start(type, 'yoti')}
              className="flex-1 px-3 py-2.5 rounded-xl bg-brand text-white font-semibold text-sm disabled:opacity-50">
              {busy === `${type}:yoti` ? 'Starting…' : 'Verify with Yoti'}
            </button>
            <button data-testid={`verify-${type}-oneid`} disabled={!!busy} onClick={() => start(type, 'oneid')}
              className="flex-1 px-3 py-2.5 rounded-xl border border-edge font-semibold text-sm disabled:opacity-50">
              {busy === `${type}:oneid` ? 'Starting…' : 'Verify with OneID'}
            </button>
          </div>
        )}
      </div>
    )
  }

  const unlocked = !!state?.monetisation_enabled

  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <div className="max-w-lg mx-auto px-4 py-6">
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-4" data-testid="verify-back">
          <ArrowLeft size={18} /> Back
        </button>
        <h1 className="text-2xl font-bold mb-1">Verification</h1>
        <p className="text-sm text-slate-400 mb-5">Verify your identity and age to unlock creator tools and monetisation. We store your verification <span className="text-slate-200">status only</span> — never your documents.</p>

        <div className={`rounded-2xl p-4 mb-5 border flex items-center gap-3 ${unlocked ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-edge bg-panel'}`} data-testid="verify-monetisation-banner">
          {unlocked ? <Unlock className="text-emerald-400" size={22} /> : <Lock className="text-slate-400" size={22} />}
          <div>
            <div className="font-semibold text-sm">{unlocked ? 'Monetisation unlocked' : 'Monetisation locked'}</div>
            <div className="text-xs text-slate-400">{unlocked ? 'Creator tools, subscriptions and tips are available.' : 'Both identity and age must be verified as an adult.'}</div>
          </div>
        </div>

        {err && <div className="text-rose-400 text-sm mb-4" data-testid="verify-error">{err}</div>}

        <div className="space-y-3">
          <Row title="Identity" type="identity" desc="Confirm who you are with a government ID check." />
          <Row title="Age" type="age" desc="Confirm you are 18+ to access and create adult content." />
        </div>

        {state?.is_minor && (
          <p className="text-xs text-amber-400/90 mt-4" data-testid="verify-minor-note">
            Your account is registered as under 18. Adult verification and adult content are permanently unavailable.
          </p>
        )}
      </div>
    </div>
  )
}
