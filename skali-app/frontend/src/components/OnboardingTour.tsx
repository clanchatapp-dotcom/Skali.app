import React, { useState } from 'react'
import { api } from '../lib/api'
import { Users, ScrollText, Shield, Sparkles, Loader2, Lock, Check } from 'lucide-react'

// "Before you enter Skali…" — one-time welcome + Comfort-Zone setup for new sign-ups.
export default function OnboardingTour({ user, onDone }: { user: any; onDone: () => void }) {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const isMinor = !!user?.is_minor
  const [cz, setCz] = useState<Record<string, boolean>>({
    nsfw: false, ai: true, language: true, violence: false, drugs: false,
    ...(user?.comfort_zone || {}),
  })

  const toggle = (k: string) => {
    if (k === 'nsfw' && isMinor) return
    setCz(p => ({ ...p, [k]: !p[k] }))
  }

  const finish = async () => {
    setSaving(true)
    try { await api.updateProfile({ comfort_zone: cz, onboarded: true }) } catch {}
    setSaving(false)
    onDone()
  }

  const steps = [
    {
      icon: Sparkles,
      title: 'Welcome to Skali',
      body: (
        <p className="text-slate-300">
          Skali is an online version of chilling with your homies — not a stage, not a broadcast.
          Before you head in, let's set up <span className="text-white font-medium">your space</span>. Takes 20 seconds.
        </p>
      ),
    },
    {
      icon: Users,
      title: 'Three tiers, your rules',
      body: (
        <div className="space-y-2 text-sm">
          <div className="flex items-start gap-2"><span className="mt-0.5 h-2 w-2 rounded-full bg-emerald-500" /><span><b className="text-white">Public</b> — anyone can see it. No DMs, no 18+.</span></div>
          <div className="flex items-start gap-2"><span className="mt-0.5 h-2 w-2 rounded-full bg-amber-500" /><span><b className="text-white">Followers</b> — approved followers only. Optional DMs.</span></div>
          <div className="flex items-start gap-2"><span className="mt-0.5 h-2 w-2 rounded-full bg-violet-500" /><span><b className="text-white">Inner Circle</b> — invite-only, your closest people. DMs always open.</span></div>
        </div>
      ),
    },
    {
      icon: ScrollText,
      title: 'No algorithm. Ever.',
      body: (
        <p className="text-slate-300">
          Your feed is <span className="text-white font-medium">chronological</span> — newest first, nothing "suggested",
          no ads in your personal feed, and every metric stays private. What you see is who you follow. That's it.
        </p>
      ),
    },
    {
      icon: Shield,
      title: 'Your Comfort Zone',
      body: (
        <div className="space-y-2">
          <p className="text-sm text-slate-400 mb-1">Choose what shows up in your feed. You can change these anytime in Settings.</p>
          {[
            ['nsfw', 'NSFW content', 'Nudity & sexual content'],
            ['ai', 'AI-generated content', 'Posts labelled as AI'],
            ['language', 'Strong language', 'Swearing & crude humour'],
            ['violence', 'Violence & gore', 'Graphic injury, blood'],
          ].map(([k, label, desc]) => {
            const locked = k === 'nsfw' && isMinor
            const on = !!cz[k as string]
            return (
              <button key={k} onClick={() => toggle(k as string)} disabled={locked}
                className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition ${on && !locked ? 'border-brand/40 bg-brand/10' : 'border-edge bg-white/5'} ${locked ? 'opacity-60' : 'hover:border-brand/40'}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-medium flex items-center gap-1.5">{label}{locked && <Lock className="h-3 w-3 text-slate-500" />}</div>
                  <div className="text-xs text-slate-500">{locked ? 'Locked off — under-18 protection' : desc}</div>
                </div>
                <div className={`h-6 w-11 rounded-full p-0.5 shrink-0 transition ${on && !locked ? 'bg-brand' : 'bg-white/10'}`}>
                  <div className={`h-5 w-5 rounded-full bg-white transition ${on && !locked ? 'translate-x-5' : ''}`} />
                </div>
              </button>
            )
          })}
        </div>
      ),
    },
  ]

  const S = steps[step]
  const Icon = S.icon
  const last = step === steps.length - 1

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/80 backdrop-blur p-4">
      <div className="bg-panel border border-edge rounded-2xl p-6 max-w-md w-full">
        <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-brand to-violet-600 grid place-items-center mb-4">
          <Icon className="h-6 w-6 text-white" />
        </div>
        <h3 className="font-extrabold text-xl mb-2">{S.title}</h3>
        <div className="mb-5">{S.body}</div>

        <div className="flex items-center gap-1.5 mb-4">
          {steps.map((_, i) => (
            <div key={i} className={`h-1.5 rounded-full transition-all ${i === step ? 'w-6 bg-brand' : 'w-1.5 bg-white/15'}`} />
          ))}
        </div>

        <div className="flex items-center gap-2">
          {step > 0 && (
            <button onClick={() => setStep(s => s - 1)} className="px-4 py-2.5 rounded-xl border border-edge text-sm font-medium">Back</button>
          )}
          {!last ? (
            <button onClick={() => setStep(s => s + 1)} className="ml-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-brand to-violet-600 font-semibold">Next</button>
          ) : (
            <button onClick={finish} disabled={saving} className="ml-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-brand to-violet-600 font-semibold disabled:opacity-50 flex items-center gap-2">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Enter Skali
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
