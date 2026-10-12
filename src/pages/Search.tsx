import { useEffect, useMemo, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { INTERESTS } from '../lib/interests'
import Choices from './Choices'
import FindStreamers from '../components/FindStreamers'
import { Hash, AtSign, Search as SearchIcon, Compass, Sparkles, Radio } from 'lucide-react'

export default function Search() {
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const initTab = sp.get('tab')
  const [tab, setTab] = useState<'discover' | 'choices' | 'streamers'>(initTab === 'choices' ? 'choices' : initTab === 'streamers' ? 'streamers' : 'discover')
  const [q, setQ] = useState(sp.get('q') || '')
  const [users, setUsers] = useState<any[]>([])

  // Mode is driven by the first character the user types:
  //   #handle  -> PEOPLE search      @interest -> INTERESTS filter
  //   anything else searches people and filters interests together.
  const raw = q.trim()
  const mode: 'people' | 'interests' | 'both' =
    raw.startsWith('@') ? 'interests' : raw.startsWith('#') ? 'people' : 'both'
  const term = raw.replace(/^[#@]/, '').toLowerCase()

  useEffect(() => { setQ(sp.get('q') || '') }, [sp])

  useEffect(() => {
    if (mode !== 'interests' && term) {
      api.search(term).then(r => setUsers(r.users || [])).catch(() => setUsers([]))
    } else {
      setUsers([])
    }
  }, [term, mode])

  const filteredInterests = useMemo(() => {
    if (mode === 'people') return []
    if (!term) return mode === 'interests' ? INTERESTS : []
    return INTERESTS.filter(i => i.toLowerCase().includes(term))
  }, [term, mode])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setSp(q ? { q } : {})
  }

  const showPeople = mode !== 'interests' && !!term
  const showInterests = mode !== 'people' && (mode === 'interests' || !!term)

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
        <h1 className="font-extrabold text-2xl mb-3">Find</h1>

        {/* Tabs: Discover (search) vs Choices (opt-in discovery) */}
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
            onClick={() => setTab('choices')}
            data-testid="find-tab-choices"
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition ${
              tab === 'choices' ? 'bg-brand text-white' : 'bg-panel border border-edge text-slate-400 hover:text-white'
            }`}
          >
            <Sparkles className="h-4 w-4" /> Choices
          </button>
          <button
            onClick={() => setTab('streamers')}
            data-testid="find-tab-streamers"
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition ${
              tab === 'streamers' ? 'bg-brand text-white' : 'bg-panel border border-edge text-slate-400 hover:text-white'
            }`}
          >
            <Radio className="h-4 w-4" /> Streamers
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

      {/* CHOICES TAB (Interest Feed now lives in Feed → Interests) */}
      {tab === 'choices' && (
        <div data-testid="find-choices-panel">
          <Choices embedded />
        </div>
      )}

      {tab === 'streamers' && <FindStreamers />}

      {/* DISCOVER TAB — results only appear once you type */}
      {tab === 'discover' && raw && (
        <div className="p-4 space-y-6">
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
              ) : null}
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
