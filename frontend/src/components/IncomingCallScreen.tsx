import { useEffect, useRef } from 'react'
import { Phone, PhoneOff, Video } from 'lucide-react'
import { Avatar } from '../lib/ui'

export type IncomingCall = {
  room: string
  media: 'audio' | 'video'
  from: { handle: string; display_name?: string; avatar_url?: string | null }
}

// Full-screen ringing UI shown to the recipient when a call comes in.
export default function IncomingCallScreen({ call, onAccept, onDecline }: {
  call: IncomingCall
  onAccept: () => void
  onDecline: () => void
}) {
  const ctxRef = useRef<any>(null)
  const timerRef = useRef<any>(null)

  useEffect(() => {
    // Generate a repeating two-tone ringtone with the Web Audio API so we don't
    // need to bundle an audio asset. Wrapped in try/catch for autoplay policies.
    let stopped = false
    try {
      const AC = (window as any).AudioContext || (window as any).webkitAudioContext
      if (AC) {
        const ctx = new AC()
        ctxRef.current = ctx
        const ring = () => {
          if (stopped) return
          try {
            const now = ctx.currentTime
            ;[0, 0.4].forEach((offset, i) => {
              const osc = ctx.createOscillator()
              const gain = ctx.createGain()
              osc.type = 'sine'
              osc.frequency.value = i === 0 ? 480 : 620
              gain.gain.setValueAtTime(0.0001, now + offset)
              gain.gain.exponentialRampToValueAtTime(0.25, now + offset + 0.03)
              gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.32)
              osc.connect(gain); gain.connect(ctx.destination)
              osc.start(now + offset); osc.stop(now + offset + 0.34)
            })
          } catch { /* ignore */ }
        }
        ctx.resume?.().catch(() => {})
        ring()
        timerRef.current = setInterval(ring, 2000)
      }
    } catch { /* audio not available */ }

    // Vibrate pattern on supported devices (mobile / native).
    try { (navigator as any).vibrate?.([500, 300, 500, 300, 500]) } catch {}
    const vib = setInterval(() => { try { (navigator as any).vibrate?.([500, 300, 500]) } catch {} }, 2000)

    return () => {
      stopped = true
      if (timerRef.current) clearInterval(timerRef.current)
      clearInterval(vib)
      try { (navigator as any).vibrate?.(0) } catch {}
      try { ctxRef.current?.close?.() } catch {}
    }
  }, [call.room])

  const name = call.from.display_name || `@${call.from.handle}`

  return (
    <div className="fixed inset-0 z-[80] bg-gradient-to-b from-slate-900 via-slate-950 to-black flex flex-col items-center justify-between py-16 pt-[calc(env(safe-area-inset-top)+4rem)] pb-[calc(env(safe-area-inset-bottom)+4rem)]">
      <div className="flex flex-col items-center gap-4 text-center px-6">
        <p className="text-slate-400 text-sm tracking-wide uppercase">
          Incoming {call.media === 'video' ? 'video' : 'voice'} call
        </p>
        <div className="relative">
          <span className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />
          <span className="absolute -inset-3 rounded-full border border-emerald-500/30 animate-pulse" />
          <div className="relative">
            <Avatar id={call.from.handle} url={call.from.avatar_url || undefined} name={name} size={112} />
          </div>
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-white">{name}</h2>
          <p className="text-slate-400 mt-1">@{call.from.handle}</p>
        </div>
      </div>

      <div className="flex items-center justify-center gap-16 w-full max-w-sm px-8">
        <button onClick={onDecline} className="flex flex-col items-center gap-2 group">
          <span className="h-16 w-16 grid place-items-center rounded-full bg-rose-600 group-active:scale-95 transition shadow-lg shadow-rose-900/40">
            <PhoneOff className="h-7 w-7 text-white" />
          </span>
          <span className="text-sm text-slate-300">Decline</span>
        </button>
        <button onClick={onAccept} className="flex flex-col items-center gap-2 group">
          <span className="h-16 w-16 grid place-items-center rounded-full bg-emerald-500 group-active:scale-95 transition shadow-lg shadow-emerald-900/40 animate-bounce">
            {call.media === 'video' ? <Video className="h-7 w-7 text-white" /> : <Phone className="h-7 w-7 text-white" />}
          </span>
          <span className="text-sm text-slate-300">Accept</span>
        </button>
      </div>
    </div>
  )
}
