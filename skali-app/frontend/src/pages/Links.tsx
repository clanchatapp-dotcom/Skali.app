import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Link as LinkIcon, Loader2, ShoppingBag } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'

function normaliseUrl(value: string) {
  const trimmed = value.trim()
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

export default function Links() {
  const { handle } = useParams()
  const nav = useNavigate()
  const [p, setP] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api.getUser(handle!)
      .then((prof) => {
        if (!cancelled) setP(prof)
      })
      .catch(() => {
        if (!cancelled) setP(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [handle])

  if (loading) {
    return (
      <div className="h-full grid place-items-center text-slate-500">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!p) {
    return (
      <div className="h-full grid place-items-center text-slate-500 px-6 text-center">
        User not found.
      </div>
    )
  }

  const links = Array.isArray(p.links) ? p.links : []

  return (
    <div className="h-full min-h-0 flex flex-col overflow-hidden">
      <header className="shrink-0 z-30 bg-ink/95 backdrop-blur border-b border-edge px-4 pt-[env(safe-area-inset-top)] min-h-14 flex items-center gap-3">
        <button
          onClick={() => nav(-1)}
          className="h-10 w-10 grid place-items-center rounded-xl hover:bg-white/10 text-slate-300 shrink-0"
          aria-label="Back to profile"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="min-w-0">
          <h1 className="font-extrabold text-lg">My links</h1>
          <p className="text-xs text-slate-500 truncate">#{p.handle}</p>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-xl mx-auto p-4 pb-8">
          <div className="bg-panel border border-edge rounded-2xl p-5 flex items-center gap-3">
            <div className="shrink-0">
              <Avatar id={p.id} name={p.display_name} url={p.avatar_url} size={52} />
            </div>
            <div className="min-w-0">
              <div className="font-bold truncate">{p.display_name}</div>
              <div className="text-sm text-slate-500 truncate">#{p.handle}</div>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {links.length === 0 ? (
              <div className="bg-panel border border-edge rounded-2xl p-8 text-center">
                <LinkIcon className="h-8 w-8 mx-auto text-slate-600" />
                <p className="mt-3 text-slate-400">No links added yet.</p>
                {p.is_self && (
                  <button
                    onClick={() => nav('/settings')}
                    className="mt-4 px-5 py-2.5 rounded-full bg-gradient-to-r from-brand to-violet-600 font-semibold"
                  >
                    Add links in Settings
                  </button>
                )}
              </div>
            ) : (
              links.map((value: string, i: number) => {
                const url = normaliseUrl(value)
                return (
                  <a
                    key={`${value}-${i}`}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-panel border border-edge rounded-2xl p-4 flex items-center gap-3 hover:bg-white/5 transition"
                  >
                    <span className="h-10 w-10 rounded-xl bg-brand/10 border border-brand/20 grid place-items-center shrink-0">
                      <ExternalLink className="h-5 w-5 text-brand" />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block font-semibold truncate">{value}</span>
                      <span className="block text-xs text-slate-500 truncate">Open link</span>
                    </span>
                    <ExternalLink className="h-4 w-4 text-slate-500 shrink-0" />
                  </a>
                )
              })
            )}
          </div>

          <div className="mt-5 bg-panel/50 border border-edge rounded-2xl p-4 text-sm text-slate-500 flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 shrink-0" />
            Shop · Coming soon
          </div>
        </div>
      </div>
    </div>
  )
}
