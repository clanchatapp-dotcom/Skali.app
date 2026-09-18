import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import PostCard from '../components/PostCard'
import { Search as SearchIcon } from 'lucide-react'

export default function Search() {
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState(sp.get('q') || '')
  const [res, setRes] = useState<{ users: any[]; posts: any[] }>({ users: [], posts: [] })

  useEffect(() => {
    const query = sp.get('q') || ''
    setQ(query)
    if (query) api.search(query).then(setRes).catch(() => {})
    else setRes({ users: [], posts: [] })
  }, [sp])

  const submit = (e: React.FormEvent) => { e.preventDefault(); setSp(q ? { q } : {}) }

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
        <form onSubmit={submit} className="flex items-center gap-2 bg-panel border border-edge rounded-xl px-3">
          <SearchIcon className="h-4 w-4 text-slate-500" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search #handles or #tags…"
            className="flex-1 bg-transparent py-3 outline-none" />
        </form>
      </div>
      <div className="p-4 space-y-4">
        {res.users.length > 0 && <>
          <h2 className="font-semibold text-slate-400">People</h2>
          {res.users.map(u => (
            <Link key={u.id} to={`/u/${u.handle}`} className="flex items-center gap-3 bg-panel border border-edge rounded-2xl p-3 hover:bg-white/5">
              <Avatar id={u.id} name={u.display_name} url={u.avatar_url} />
              <div><div className="font-medium">{u.display_name}</div><div className="text-sm text-slate-500">#{u.handle}</div></div>
            </Link>
          ))}
        </>}
        {res.posts.length > 0 && <>
          <h2 className="font-semibold text-slate-400 pt-2">Posts</h2>
          {res.posts.map(p => <PostCard key={p.id} post={p} />)}
        </>}
        {q && res.users.length === 0 && res.posts.length === 0 && <p className="text-center text-slate-500 py-10">No results for “{q}”</p>}
        {!q && <p className="text-center text-slate-500 py-10">Search people and public tags. Tier 2/3 content never shows here.</p>}
      </div>
    </div>
  )
}
