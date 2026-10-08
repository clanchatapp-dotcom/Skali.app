import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import PostCard from '../components/PostCard'
import { ArrowLeft, AtSign, Check, Plus, Loader2, Users } from 'lucide-react'

export default function Interest() {
  const { tag = '' } = useParams()
  const nav = useNavigate()
  const name = decodeURIComponent(tag)
  const query = name.toLowerCase()

  const [posts, setPosts] = useState<any[]>([])
  const [people, setPeople] = useState<any[]>([])
  const [followerCount, setFollowerCount] = useState(0)
  const [postCount, setPostCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [following, setFollowing] = useState(false)
  const [busy, setBusy] = useState(false)

  // Follow state comes from the server so it's the same on every device.
  useEffect(() => {
    api.myInterests()
      .then(r => setFollowing((r.interests || []).some((s: string) => s.toLowerCase() === query)))
      .catch(() => setFollowing(false))
  }, [query])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      api.search(query).then(r => r.posts || []).catch(() => []),
      api.interestPeople(name).then(r => r).catch(() => ({ people: [], follower_count: 0, post_count: 0 })),
    ]).then(([ps, pl]) => {
      if (cancelled) return
      setPosts(ps)
      setPeople(pl.people || [])
      setFollowerCount(pl.follower_count || 0)
      setPostCount(pl.post_count || 0)
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [query, name])

  const toggleFollow = async () => {
    if (busy) return
    setBusy(true)
    const next = !following
    setFollowing(next)  // optimistic
    setFollowerCount(c => Math.max(0, c + (next ? 1 : -1)))
    try {
      if (next) await api.followInterest(name)
      else await api.unfollowInterest(name)
      // A newly-followed member should appear in this interest's People list.
      api.interestPeople(name).then(r => {
        setPeople(r.people || [])
        setFollowerCount(r.follower_count || 0)
        setPostCount(r.post_count || 0)
      }).catch(() => {})
    } catch {
      setFollowing(!next)  // revert on failure
      setFollowerCount(c => Math.max(0, c + (next ? -1 : 1)))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {/* Interest header */}
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => nav(-1)}
            className="h-9 w-9 grid place-items-center rounded-xl hover:bg-white/5 text-slate-300"
            data-testid="interest-back-btn"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3 min-w-0">
            <span className="grid place-items-center h-12 w-12 rounded-2xl bg-gradient-to-br from-brand to-violet-600 text-white shrink-0">
              <AtSign className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <h1 className="font-extrabold text-2xl truncate" data-testid="interest-name">{name}</h1>
              <p className="text-sm text-slate-500" data-testid="interest-stats">
                <span className="text-slate-300 font-semibold">{followerCount.toLocaleString()}</span> {followerCount === 1 ? 'follower' : 'followers'}
                <span className="mx-1.5">·</span>
                <span className="text-slate-300 font-semibold">{postCount.toLocaleString()}</span> {postCount === 1 ? 'post' : 'posts'}
              </p>
            </div>
          </div>
          <button
            onClick={toggleFollow}
            disabled={busy}
            data-testid="interest-follow-btn"
            className={`ml-auto flex items-center gap-1.5 px-4 py-2 rounded-full font-semibold transition disabled:opacity-60 ${
              following
                ? 'bg-panel border border-edge text-slate-200 hover:border-rose-500/40 hover:text-rose-300'
                : 'bg-gradient-to-r from-brand to-violet-600 text-white hover:opacity-95'
            }`}
          >
            {following ? <><Check className="h-4 w-4" /> Following</> : <><Plus className="h-4 w-4" /> Follow</>}
          </button>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {loading ? (
          <div className="grid place-items-center py-16 text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div>
        ) : (
          <>
            {/* People into this interest */}
            {people.length > 0 && (
              <section data-testid="interest-people-section">
                <div className="flex items-center gap-2 mb-3">
                  <span className="grid place-items-center h-7 w-7 rounded-lg bg-brand/15 text-brand"><Users className="h-4 w-4" /></span>
                  <h2 className="font-semibold tracking-wide text-slate-300">PEOPLE INTO @{name.toUpperCase()}</h2>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
                  {people.map(p => (
                    <Link
                      key={p.id}
                      to={`/u/${p.handle}`}
                      data-testid={`interest-person-${p.handle}`}
                      className="shrink-0 w-32 bg-panel border border-edge rounded-2xl p-3 flex flex-col items-center text-center hover:bg-white/5"
                    >
                      <Avatar id={p.id} name={p.display_name} url={p.avatar_url} />
                      <div className="font-medium text-sm mt-2 truncate w-full">{p.display_name}</div>
                      <div className="text-xs text-slate-500 truncate w-full">#{p.handle}</div>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Posts labelled with this interest */}
            <section>
              {posts.length > 0 ? (
                <div className="space-y-4">
                  {posts.map(p => <PostCard key={p.id} post={p} />)}
                </div>
              ) : (
                <div className="text-center text-slate-500 py-16" data-testid="interest-empty">
                  <p className="font-medium text-slate-400">No posts in @{name} yet</p>
                  <p className="text-sm mt-1">Add the @{name} interest to a post to fill this space.</p>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}
