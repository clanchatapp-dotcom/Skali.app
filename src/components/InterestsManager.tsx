import { useEffect, useState } from 'react'
import { Check, Loader2, Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { INTERESTS } from '../lib/interests'

const norm = (s: string) => s.replace(/[^a-z0-9]/gi, '').toLowerCase()

// Settings → Preferences → Interests: same follows the Feed's Interests tab uses.
export default function InterestsManager() {
  const [followed, setFollowed] = useState<string[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api.myInterests().then((r: any) => setFollowed(r.interests || [])).catch(() => setFollowed([]))
  }, [])

  const isOn = (name: string) => (followed || []).some(x => norm(x) === norm(name))

  const toggle = async (name: string) => {
    setBusy(name)
    try {
      const r = isOn(name) ? await api.unfollowInterest(name) : await api.followInterest(name)
      setFollowed(r.interests || [])
    } catch (e: any) { alert(e.message || 'Could not update') }
    setBusy(null)
  }

  if (!followed) return <div className="py-10 grid place-items-center text-slate-500"><Loader2 className="h-5 w-5 animate-spin" /></div>

  const all = [...INTERESTS, ...followed.filter(f => !INTERESTS.some(i => norm(i) === norm(f)))]

  return (
    <div data-testid="interests-manager">
      <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Following</div>
      {followed.length === 0 ? (
        <p className="text-sm text-slate-500 mb-5">You aren't following any interests yet.</p>
      ) : (
        <div className="flex flex-wrap gap-2 mb-5">
          {followed.map(name => (
            <button key={name} onClick={() => toggle(name)} disabled={busy === name}
              data-testid={`interest-following-${norm(name)}`} title="Tap to unfollow"
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-brand/15 border border-brand/40 text-white hover:bg-rose-500/15 hover:border-rose-500/40 transition-colors font-medium disabled:opacity-50">
              @{name} {busy === name ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
            </button>
          ))}
        </div>
      )}

      <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">All interests</div>
      <div className="flex flex-wrap gap-2">
        {all.map(name => {
          const on = isOn(name)
          return (
            <button key={name} onClick={() => toggle(name)} disabled={busy === name}
              data-testid={`interest-option-${norm(name)}`}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full border transition-colors font-medium disabled:opacity-50 ${on ? 'bg-brand/15 border-brand/40 text-white' : 'bg-panel border-edge text-slate-300 hover:text-white hover:border-brand/40'}`}>
              {on ? <Check className="h-3.5 w-3.5 text-brand" /> : <Plus className="h-3.5 w-3.5" />} @{name}
            </button>
          )
        })}
      </div>
    </div>
  )
}
