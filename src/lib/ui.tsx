import { Globe, Users, Lock } from 'lucide-react'
import { useState, useEffect } from 'react'

export const TIER = {
  public: { label: 'Public', icon: Globe, text: 'text-emerald-400', bg: 'bg-emerald-500/15', ring: 'border-emerald-500/30', dot: 'bg-emerald-400' },
  followers: { label: 'Followers', icon: Users, text: 'text-amber-400', bg: 'bg-amber-500/15', ring: 'border-amber-500/30', dot: 'bg-amber-400' },
  inner: { label: 'Inner Circle', icon: Lock, text: 'text-violet-400', bg: 'bg-violet-500/15', ring: 'border-violet-500/30', dot: 'bg-violet-400' },
} as const

export type TierKey = keyof typeof TIER

const GRAD = ['from-indigo-400 to-violet-500', 'from-violet-400 to-fuchsia-500', 'from-emerald-400 to-teal-500', 'from-amber-400 to-orange-500', 'from-sky-400 to-indigo-500', 'from-rose-400 to-pink-500']
export function gradFor(id = '') { let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return GRAD[h % GRAD.length] }
export function initials(n = '') { return (n || '?').split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase() }

export function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'now'
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  if (s < 604800) return `${Math.floor(s / 86400)}d`
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export function Avatar({ id, name, url, size = 40 }: { id: string; name: string; url?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false)
  // Reset the error state if the url changes (e.g. after uploading a new photo)
  useEffect(() => { setFailed(false) }, [url])
  if (url && !failed) {
    return (
      <img src={url} alt={name} style={{ width: size, height: size }}
        onError={() => setFailed(true)}
        className="rounded-full object-cover shrink-0 bg-white/5" />
    )
  }
  return (
    <div style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={`rounded-full shrink-0 grid place-items-center font-bold text-white bg-gradient-to-br ${gradFor(id)}`}>
      {initials(name)}
    </div>
  )
}


// Turns URLs (http/https and www.) inside plain text into clickable links.
// Safe: opens in a new tab with noopener/noreferrer; no HTML injection (text only).
const URL_RX = /((?:https?:\/\/|www\.)[^\s<]+[^\s<.,!?:;'")\]])/gi

export function Linkify({ text }: { text?: string | null }) {
  if (!text) return null
  const parts = String(text).split(URL_RX)
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 1) {
          const href = part.startsWith('http') ? part : `https://${part}`
          return (
            <a key={i} href={href} target="_blank" rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="text-brand underline decoration-brand/40 hover:decoration-brand break-all">
              {part}
            </a>
          )
        }
        return part
      })}
    </>
  )
}
