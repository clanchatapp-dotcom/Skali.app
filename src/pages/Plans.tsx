import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { ArrowLeft, Check, Star, BadgeCheck, Shield } from 'lucide-react'

const TIERS = [
  {
    key: 'free', name: 'Free', price: '£0', color: 'from-slate-500 to-slate-700',
    icon: <Shield className="h-5 w-5" />, tagline: 'Everything to get started',
    perks: ['Photos up to 50MB', 'Videos up to 500MB / 10 min', 'Audio up to 100MB', '3 pinned posts', 'Bio up to 150 characters', '3 profile links'],
  },
  {
    key: 'premium', name: 'Premium', price: '£3–5/mo', color: 'from-amber-400 to-amber-600',
    icon: <Star className="h-5 w-5 fill-current" />, tagline: 'For active creators', highlight: true,
    perks: ['Photos up to 500MB', 'Videos up to 2GB', 'Audio up to 1GB', '6 pinned posts', 'Bio up to 300 characters', '8 profile links', 'Premium badge', 'Post scheduling & advanced analytics (coming soon)'],
  },
  {
    key: 'verified', name: 'Verified', price: 'By approval', color: 'from-sky-400 to-blue-600',
    icon: <BadgeCheck className="h-5 w-5" />, tagline: 'Trusted, verified accounts',
    perks: ['Photos up to 500MB', 'Videos up to 4GB', 'Unlimited audio', '6 pinned posts', 'Bio up to 300 characters', 'Unlimited profile links', 'Verified shield badge', 'Full analytics (coming soon)'],
  },
]

export default function Plans() {
  const nav = useNavigate()
  const [current, setCurrent] = useState('free')
  useEffect(() => { api.me().then((m: any) => setCurrent(m?.account_type || 'free')).catch(() => {}) }, [])

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-3">
        <button onClick={() => nav('/settings')} className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10"><ArrowLeft className="h-5 w-5" /></button>
        <h1 className="text-xl font-extrabold">Membership plans</h1>
      </div>
      <div className="p-4 grid gap-4 md:grid-cols-3">
        {TIERS.map(t => {
          const isCurrent = current === t.key
          return (
            <div key={t.key} className={`relative rounded-2xl border p-5 flex flex-col ${isCurrent ? 'border-brand ring-2 ring-brand/40' : 'border-edge'} ${t.highlight ? 'bg-white/[0.03]' : 'bg-panel'}`}>
              {isCurrent && <span className="absolute -top-2.5 left-4 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-brand text-white">Your plan</span>}
              <div className={`inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-xl bg-gradient-to-br ${t.color} text-white font-semibold`}>
                {t.icon}{t.name}
              </div>
              <div className="mt-3 text-2xl font-extrabold">{t.price}</div>
              <div className="text-sm text-slate-400 mb-4">{t.tagline}</div>
              <ul className="space-y-2 flex-1">
                {t.perks.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Check className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" /><span>{p}</span>
                  </li>
                ))}
              </ul>
              <button disabled className="mt-5 w-full py-2.5 rounded-xl border border-edge text-slate-400 text-sm cursor-not-allowed">
                {isCurrent ? 'Current plan' : t.key === 'verified' ? 'Apply for verification (soon)' : 'Upgrade (coming soon)'}
              </button>
            </div>
          )
        })}
      </div>
      <p className="px-4 pb-8 text-center text-xs text-slate-500">Billing isn’t live yet — plans are assigned manually while payments are being set up.</p>
    </div>
  )
}
