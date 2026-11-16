import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { Capacitor } from '@capacitor/core'
import { Flame, Lock, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import PostCard from '../components/PostCard'
import NsfwGate from '../components/nsfw/NsfwGate'

const isNative = (() => { try { return Capacitor.isNativePlatform() } catch { return false } })()

function Creators({ list }: { list: any[] }) {
  if (!list.length) return <p className="text-slate-500 text-sm p-4">No adult creators yet.</p>
  return (
    <div className="grid sm:grid-cols-2 gap-3" data-testid="nsfw-creators">
      {list.map(c => (
        <Link key={c.id} to={`/u/${c.handle}`} data-testid={`nsfw-creator-${c.handle}`}
          className="flex items-center gap-3 bg-panel border border-edge rounded-2xl p-3 hover:border-rose-500/40 transition-colors">
          <img src={c.avatar_url || `https://api.dicebear.com/7.x/initials/svg?seed=${c.handle}`} alt="" className="h-11 w-11 rounded-full object-cover" />
          <div className="min-w-0">
            <div className="font-medium truncate">{c.display_name}</div>
            <div className="text-xs text-slate-500 truncate">#{c.handle}</div>
          </div>
        </Link>
      ))}
    </div>
  )
}

export default function Nsfw() {
  const [session, setSession] = useState('')
  const [tab, setTab] = useState<'feed' | 'creators'>('feed')
  const [posts, setPosts] = useState<any[] | null>(null)
  const [creators, setCreators] = useState<any[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!session) return
    api.nsfwFeed(session).then(setPosts).catch((e: any) => setErr(e.message))
    api.nsfwCreators(session).then(setCreators).catch((e: any) => setErr(e.message))
  }, [session])

  if (isNative) return <Navigate to="/" replace />
  if (!session) return <NsfwGate onUnlocked={setSession} />

  const tabCls = (t: string) => `px-4 py-1.5 rounded-full text-sm border transition-colors ${tab === t ? 'bg-rose-500/15 border-rose-500/50 text-white' : 'border-edge text-slate-400 hover:text-white'}`
  return (
    <div className="max-w-2xl mx-auto p-4 pb-28 space-y-4" data-testid="nsfw-page">
      <div className="flex items-center gap-2">
        <Flame className="h-5 w-5 text-rose-400" />
        <h1 className="text-lg font-semibold">Adult content</h1>
        <button onClick={() => { setSession(''); setPosts(null); setCreators(null) }} data-testid="nsfw-lock-btn"
          className="ml-auto text-xs text-slate-400 hover:text-white flex items-center gap-1"><Lock className="h-3.5 w-3.5" />Lock</button>
      </div>
      <div className="flex gap-2">
        <button className={tabCls('feed')} onClick={() => setTab('feed')} data-testid="nsfw-tab-feed">Feed</button>
        <button className={tabCls('creators')} onClick={() => setTab('creators')} data-testid="nsfw-tab-creators">Creators</button>
      </div>
      {err && <p className="text-sm text-rose-400" data-testid="nsfw-error">{err}</p>}
      {tab === 'feed' ? (
        posts === null ? <Loader2 className="h-5 w-5 animate-spin text-slate-500 mx-auto" /> :
          posts.length ? <div className="space-y-4" data-testid="nsfw-feed">{posts.map(p => <PostCard key={p.id} post={p} onDelete={id => setPosts(ps => (ps || []).filter(x => x.id !== id))} />)}</div>
            : <p className="text-slate-500 text-sm p-4">No adult posts yet.</p>
      ) : creators === null ? <Loader2 className="h-5 w-5 animate-spin text-slate-500 mx-auto" /> : <Creators list={creators} />}
    </div>
  )
}
