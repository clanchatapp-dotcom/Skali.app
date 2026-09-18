import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar, timeAgo } from '../lib/ui'
import RoleBadge from '../components/RoleBadge'
import AccountBadge from '../components/AccountBadge'
import { Heart, UserPlus, Lock, Check, Tag, X, Trash2 } from 'lucide-react'

const ICON: any = { like: Heart, follow: UserPlus, follow_request: UserPlus, follow_accepted: Check, inner_invite: Lock, inner_accepted: Lock, tag_request: Tag }

export default function Activity() {
  const [items, setItems] = useState<any[]>([])
  const [reqs, setReqs] = useState<any[]>([])
  const load = () => { api.activity().then(setItems).catch(() => {}); api.followRequests().then(setReqs).catch(() => {}) }
  useEffect(load, [])

  const accept = async (h: string) => { await api.acceptFollow(h); load() }
  const acceptInner = async (h: string) => { await api.acceptInner(h); load() }
  const decideTag = async (postId: string, decision: 'approve' | 'reject') => { try { await api.decideTag(postId, decision) } catch {} ; load() }
  const removeOne = async (id: string) => {
    setItems(p => p.filter(a => a.id !== id))               // optimistic
    try { await api.deleteActivity(id) } catch { load() }   // rollback on failure
  }
  const clearAll = async () => {
    if (!confirm('Clear all activity? This cannot be undone.')) return
    setItems([])
    try { await api.clearActivity() } catch { load() }
  }

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center justify-between">
        <h1 className="text-xl font-extrabold">Activity</h1>
        {items.length > 0 && (
          <button onClick={clearAll} className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-rose-300 px-2 py-1 rounded-lg hover:bg-white/5">
            <Trash2 className="h-4 w-4" /> Clear all
          </button>
        )}
      </div>
      <div className="p-4 space-y-2">
        {reqs.length > 0 && <div className="bg-panel border border-edge rounded-2xl p-3 mb-2">
          <div className="font-semibold text-slate-300 mb-2">Follow requests</div>
          {reqs.map(r => (
            <div key={r.handle} className="flex items-center gap-3 py-1.5">
              <Avatar id={r.handle} name={r.display_name} url={r.avatar_url} size={36} />
              <div className="flex-1"><span className="font-medium">{r.display_name}</span> <span className="text-slate-500 text-sm">#{r.handle}</span></div>
              <button onClick={() => accept(r.handle)} className="px-3 py-1.5 rounded-lg bg-brand text-sm font-medium">Accept</button>
            </div>
          ))}
        </div>}
        {items.length === 0 && reqs.length === 0 && <p className="text-center text-slate-500 py-10">No activity yet.</p>}
        {items.map(a => {
          const I = ICON[a.type] || Heart
          return (
            <div key={a.id} className="group flex items-center gap-3 bg-panel border border-edge rounded-2xl p-3">
              <div className="h-9 w-9 grid place-items-center rounded-full bg-brand/15 text-brand shrink-0"><I className="h-4 w-4" /></div>
              <Link to={`/u/${a.actor_handle}`}><Avatar id={a.actor_id} name={a.actor_name} size={34} /></Link>
              <div className="flex-1 min-w-0 text-sm"><Link to={`/u/${a.actor_handle}`} className="font-medium hover:underline">{a.actor_name}</Link><RoleBadge role={a.actor_role} size={13} className="ml-1" /><AccountBadge type={a.actor_account_type} role={a.actor_role} size={12} className="ml-0.5" /> {a.text}
                <div className="text-slate-600 text-xs">{timeAgo(a.created_at)}</div></div>
              {a.type === 'inner_invite' && <button onClick={() => acceptInner(a.actor_handle)} className="px-3 py-1.5 rounded-lg bg-violet-500/20 text-violet-300 text-sm shrink-0">Join</button>}
              {a.type === 'tag_request' && a.post_id && (
                <div className="flex items-center gap-1.5 shrink-0">
                  <button onClick={() => decideTag(a.post_id, 'approve')} title="Approve tag" className="h-8 w-8 grid place-items-center rounded-lg bg-emerald-500/20 text-emerald-300"><Check className="h-4 w-4" /></button>
                  <button onClick={() => decideTag(a.post_id, 'reject')} title="Reject tag" className="h-8 w-8 grid place-items-center rounded-lg bg-rose-500/20 text-rose-300"><X className="h-4 w-4" /></button>
                </div>
              )}
              <button onClick={() => removeOne(a.id)} title="Delete" className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-rose-300 hover:bg-white/5 shrink-0 md:opacity-0 md:group-hover:opacity-100 transition">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
