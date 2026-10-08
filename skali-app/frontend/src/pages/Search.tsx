import { useEffect, useMemo, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { INTERESTS } from '../lib/interests'
import PostCard from '../components/PostCard'
import { Hash, AtSign, Search as SearchIcon, Star, Compass, Loader2 } from 'lucide-react'

export default function Search() {
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const [tab, setTab] = useState<'discover' | 'feed'>('discover')
  const [q, setQ] = useState(sp.get('q') || '')
  const [users, setUsers] = useState<any[]>([])
  const [followed, setFollowed] = useState<string[]>([])
  const [feed, setFeed] = useState<any[]>([])
  const [feedLoading, setFeedLoading] = useState(false)

  // Mode is driven by the first character the user types:
  //   #handle  -> PEOPLE search      @interest -> INTERESTS filter
  //   anything else searches people and filters interests together.
  const raw = q.trim()
  const mode: 'people' | 'interests' | 'both' =
    raw.startsWith('@') ? 'interests' : raw.startsWith('#') ? 'people' : 'both'
  const term = raw.replace(/^[#@]/, '').toLowerCase()

  useEffect(() => { setQ(sp.get('q') || '') }, [sp])

  // The member's followed interests (synced from the server, so they appear on every device).
  useEffect(() => {
    api.myInterests().then(r => setFollowed(r.interests || [])).catch(() => setFollowed([]))
  }, [])

  useEffect(() => {
    if (mode !== 'interests' && term) {
      api.search(term).then(r => setUsers(r.users || [])).catch(() => setUsers([]))
    } else {
      setUsers([])
    }
  }, [term, mode])

  // Interest feed — fresh posts aggregated from everything the member follows.
  useEffect(() => {
    if (tab !== 'feed') return
    setFeedLoading(true)
    api.interestsFeed()
      .then(r => setFeed(Array.isArray(r) ? r : []))
      .catch(() => setFeed([]))
      .finally(() => setFeedLoading(false))
  }, [tab])

  const filteredInterests = useMemo(() => {
    if (mode === 'people') return []
    if (!term) return INTERESTS
    return INTERESTS.filter(i => i.toLowerCase().includes(term))
  }, [term, mode])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setSp(q ? { q } : {})
  }

  const showPeople = mode !== 'interests'
  const showInterests = mode !== 'people'

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
        <h1 className="font-extrabold text-2xl mb-3">Find</h1>

        {/* Tabs: Discover (search) vs Interest Feed */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setTab('discover')}
            data-testid="find-tab-discover"
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition ${
              tab === 'discover' ? 'bg-brand text-white' : 'bg-panel border border-edge text-slate-400 hover:text-white'
            }`}
          >
            <Compass className="h-4 w-4" /> Discover
          </button>
          <button
            onClick={() => setTab('feed')}
            data-testid="find-tab-feed"
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition ${
              tab === 'feed' ? 'bg-brand text-white' : 'bg-panel border border-edge text-slate-400 hover:text-white'
            }`}
          >
            <Star className="h-4 w-4" /> Interest Feed
          </button>
        </div>

        {tab === 'discover' && (
          <form onSubmit={submit} className="flex items-center gap-2 bg-panel border border-edge rounded-xl px-3" data-testid="find-search-form">
            <SearchIcon className="h-4 w-4 text-slate-500" />
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="# to find people · @ to find interests"
              className="flex-1 bg-transparent py-3 outline-none"
              data-testid="find-search-input"
            />
          </form>
        )}
      </div>

      {/* INTEREST FEED TAB */}
      {tab === 'feed' && (
        <div className="p-4 space-y-4" data-testid="interest-feed">
          {feedLoading ? (
            <div className="grid place-items-center py-16 text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : feed.length > 0 ? (
            feed.map(p => <PostCard key={p.id} post={p} />)
          ) : (
            <div className="text-center text-slate-500 py-16" data-testid="interest-feed-empty">
              <p className="font-medium text-slate-400">Your interest feed is quiet</p>
              <p className="text-sm mt-1">
                {followed.length === 0
                  ? 'Follow interests in Discover to see fresh posts here.'
                  : 'No recent posts from your interests yet — check back soon.'}
              </p>
            </div>
          )}
        </div>
      )}

      {/* DISCOVER TAB */}
      {tab === 'discover' && (
        <div className="p-4 space-y-6">
          {/* FOLLOWING — quick access to the interests you follow */}
          {!raw && followed.length > 0 && (
            <section data-testid="following-section">
              <div className="flex items-center gap-2 mb-3">
                <span className="grid place-items-center h-7 w-7 rounded-lg bg-amber-400/15 text-amber-300"><Star className="h-4 w-4" /></span>
                <h2 className="font-semibold tracking-wide text-slate-300">FOLLOWING</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {followed.map(name => (
                  <button
                    key={name}
                    onClick={() => nav(`/interest/${encodeURIComponent(name)}`)}
                    data-testid={`following-chip-${name.toLowerCase()}`}
                    className="px-4 py-2 rounded-full bg-brand/15 border border-brand/40 text-white hover:bg-brand/25 transition font-medium"
                  >
                    @{name}
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* PEOPLE — found using # */}
          {showPeople && (
            <section data-testid="people-section">
              <div className="flex items-center gap-2 mb-3">
                <span className="grid place-items-center h-7 w-7 rounded-lg bg-brand/15 text-brand"><Hash className="h-4 w-4" /></span>
                <h2 className="font-semibold tracking-wide text-slate-300">PEOPLE</h2>
              </div>
              {term ? (
                users.length > 0 ? (
                  <div className="space-y-2">
                    {users.map(u => (
                      <Link
                        key={u.id}
                        to={`/u/${u.handle}`}
                        data-testid={`people-result-${u.handle}`}
                        className="flex items-center gap-3 bg-panel border border-edge rounded-2xl p-3 hover:bg-white/5"
                      >
                        <Avatar id={u.id} name={u.display_name} url={u.avatar_url} />
                        <div>
                          <div className="font-medium">{u.display_name}</div>
                          <div className="text-sm text-slate-500">#{u.handle}</div>
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No people found for “{term}”.</p>
                )
              ) : (
                <p className="text-sm text-slate-500">Type <span className="text-brand font-medium">#</span> and a name or handle to find people.</p>
              )}
            </section>
          )}

          {/* INTERESTS — found using @ */}
          {showInterests && (
            <section data-testid="interests-section">
              <div className="flex items-center gap-2 mb-3">
                <span className="grid place-items-center h-7 w-7 rounded-lg bg-brand/15 text-brand"><AtSign className="h-4 w-4" /></span>
                <h2 className="font-semibold tracking-wide text-slate-300">INTERESTS</h2>
              </div>
              {filteredInterests.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {filteredInterests.map(name => (
                    <button
                      key={name}
                      onClick={() => nav(`/interest/${encodeURIComponent(name)}`)}
                      data-testid={`interest-chip-${name.toLowerCase()}`}
                      className="px-4 py-2 rounded-full bg-panel border border-edge text-slate-200 hover:bg-brand/15 hover:border-brand/40 hover:text-white transition font-medium"
                    >
                      @{name}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No interests match “{term}”.</p>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  )
}
