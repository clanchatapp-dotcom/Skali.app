import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import LiveNowBanner from '../components/LiveNowBanner'
import { api } from '../lib/api'
import { TIER, TierKey } from '../lib/ui'
import PostCard from '../components/PostCard'
import { StoryRail } from '../components/Stories'
import { INTERESTS } from '../lib/interests'
import { Image as ImageIcon, Loader2, X, Mic, Square, Clock } from 'lucide-react'
import ScheduledPostsPanel, { toLocalInput, fmtWhen } from '../components/ScheduledPostsPanel'

const FEED_TABS = [
  { key: 'general', label: 'General' },
  { key: 'followers', label: 'Following' },
  { key: 'interests', label: 'Interests' }
] as const

function Composer({ onPosted, onScheduled }: { onPosted: () => void; onScheduled: (s: any) => void }) {
  const [schedOn, setSchedOn] = useState(false)
  const [schedAt, setSchedAt] = useState('')
  const [tier, setTier] = useState<TierKey>('public')
  const [text, setText] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [people, setPeople] = useState<string[]>([])
  const [peopleInput, setPeopleInput] = useState('')
  const [mediaList, setMediaList] = useState<{ url: string; type: string }[]>([])
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [aiLabel, setAiLabel] = useState('none')
  const [expanded, setExpanded] = useState(false)
  const [nsfwTags, setNsfwTags] = useState<string[]>([])
  const [nsfwVocab, setNsfwVocab] = useState<string[]>([])
  const [nsfwEligible, setNsfwEligible] = useState(false)

  useEffect(() => {
    api.nsfwTags().then((r: any) => { setNsfwEligible(!!r.eligible); setNsfwVocab(r.tags || []) }).catch(() => {})
  }, [])

  const fileRef = useRef<HTMLInputElement | null>(null)

  // Voice / audio recording for posts
  const recRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const [recording, setRecording] = useState(false)

  const startRec = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      recRef.current = mr
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setUploading(true)
        try {
          const r = await api.upload(new File([blob], `voice-${Date.now()}.webm`, { type: 'audio/webm' }))
          setMediaList(prev => [...prev, { url: r.signed_url, type: 'audio' }].slice(0, 10))
        } catch {
          alert('Upload failed')
        } finally {
          setUploading(false)
        }
      }
      mr.start()
      setRecording(true)
    } catch {
      alert('Microphone permission needed to record audio.')
    }
  }

  const stopRec = () => {
    try { recRef.current?.stop() } catch {}
    setRecording(false)
  }

  const addTag = (v: string) => {
    const t = v.replace(/[^a-z0-9]/gi, '').toLowerCase()
    if (t && tags.length < 10 && !tags.includes(t)) setTags([...tags, t])
    setTagInput('')
  }

  const addPerson = (v: string) => {
    const t = v.replace(/[^a-z0-9_]/gi, '').toLowerCase()
    if (t && people.length < 10 && !people.includes(t)) setPeople([...people, t])
    setPeopleInput('')
  }

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return

    setUploading(true)

    try {
      const uploaded: { url: string; type: string }[] = []
      for (const f of files) {
        const r = await api.upload(f)
        uploaded.push({ url: r.signed_url, type: r.media_type })
      }
      setMediaList(prev => [...prev, ...uploaded].slice(0, 10))
    } catch {
      alert('Upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const submit = async () => {
    if (!text.trim() && !mediaList.length) return
    if (schedOn && !schedAt) { alert('Pick a date and time'); return }

    setBusy(true)

    try {
      const hasVisual = mediaList.some(m => m.type !== 'audio')
      const r = await api.createPost({
        tier,
        text,
        media: mediaList,
        media_url: mediaList[0]?.url,
        media_type: mediaList[0]?.type,
        tags,
        nsfw_tags: nsfwTags,
        people_tags: people,
        ai_label: hasVisual ? aiLabel : 'none',
        ...(schedOn ? { scheduled_at: new Date(schedAt).toISOString() } : {})
      })

      setText('')
      setTags([])
      setNsfwTags([])
      setPeople([])
      setMediaList([])
      setAiLabel('none')
      setTagInput('')
      setPeopleInput('')
      setExpanded(false)
      setSchedOn(false)
      setSchedAt('')

      if (r?.scheduled) onScheduled(r)
      else onPosted()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  const closeComposer = () => {
    setExpanded(false)
  }

  // Centre "Create" button in the bottom bar opens the composer.
  useEffect(() => {
    const openIt = () => { sessionStorage.removeItem('skali:compose'); setExpanded(true) }
    if (sessionStorage.getItem('skali:compose')) openIt()
    window.addEventListener('skali:compose', openIt)
    return () => window.removeEventListener('skali:compose', openIt)
  }, [])

  // The composer only exists as a sheet opened from the centre "+" button.
  if (!expanded) return null

  return createPortal(
    <div className="fixed inset-0 z-[75] bg-black/70 backdrop-blur grid place-items-end sm:place-items-center" onClick={closeComposer} data-testid="composer-sheet">
    <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl p-4 w-full max-w-xl max-h-[90dvh] overflow-y-auto pb-[calc(1rem+env(safe-area-inset-bottom))]" onClick={e => e.stopPropagation()}>
        <div>

          {/* Header / close */}
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-sm text-slate-200">
              Create a post
            </span>

            <button
              onClick={closeComposer}
              className="h-8 w-8 grid place-items-center rounded-full text-slate-400 hover:text-white hover:bg-white/10"
              aria-label="Close composer"
              data-testid="composer-close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Public / Followers / Inner Circle */}
          <div className="flex gap-2 mb-3 flex-wrap">
            {(Object.keys(TIER) as TierKey[]).map(k => {
              const T = TIER[k]
              const I = T.icon
              const active = tier === k

              return (
                <button
                  key={k}
                  onClick={() => setTier(k)}
                  className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full border transition ${
                    active
                      ? `${T.bg} ${T.text} ${T.ring}`
                      : 'border-edge text-slate-400 hover:text-white'
                  }`}
                >
                  <I className="h-3.5 w-3.5" />
                  {T.label}
                </button>
              )
            })}
          </div>

          {/* Post text */}
          <textarea
            autoFocus
            value={text}
            onChange={e => setText(e.target.value)}
            rows={3}
            placeholder="What's happening in your gathering?"
            data-testid="composer-text"
            className="w-full bg-ink border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand resize-none"
          />

          {/* Media preview (gallery) */}
          {mediaList.length > 0 && (
            <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
              {mediaList.map((m, i) => (
                <div key={i} className="relative shrink-0">
                  {m.type === 'video'
                    ? <video src={m.url} className="rounded-xl h-28 w-28 object-cover" />
                    : m.type === 'audio'
                    ? <div className="h-28 w-44 rounded-xl bg-ink border border-edge grid place-items-center px-2"><audio src={m.url} controls className="w-full" /></div>
                    : <img src={m.url} className="rounded-xl h-28 w-28 object-cover" />
                  }
                  <button
                    onClick={() => setMediaList(prev => prev.filter((_, j) => j !== i))}
                    className="absolute top-1 right-1 h-6 w-6 grid place-items-center rounded-full bg-black/70"
                    aria-label="Remove media"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* AI label */}
          {mediaList.some(m => m.type !== 'audio') && (
            <div className="mt-2">
              <div className="text-xs text-slate-400 mb-1">
                Is this image AI?
                <span className="text-slate-600">
                  {' '}(required — shown as a permanent label)
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {[
                  ['none', 'Not AI'],
                  ['generated', 'AI Generated'],
                  ['assisted', 'AI Assisted'],
                  ['altered', 'AI Altered']
                ].map(([v, lbl]) => (
                  <button
                    key={v}
                    onClick={() => setAiLabel(v)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition ${
                      aiLabel === v
                        ? 'bg-brand/20 text-brand border-brand/40'
                        : 'border-edge text-slate-400 hover:text-white'
                    }`}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {tier !== 'inner' && (
            <div className="mt-2">
              <div className="flex flex-wrap gap-1.5 items-center">

                {tags.map(t => (
                  <span
                    key={t}
                    className="text-xs text-brand bg-brand/10 px-2 py-1 rounded-full flex items-center gap-1"
                  >
                    #{t}

                    <button
                      onClick={() => setTags(tags.filter(x => x !== t))}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}

                <input
                  value={tagInput}
                  onChange={e => {
                    const v = e.target.value

                    if (v.endsWith(' ') || v.endsWith(',')) {
                      addTag(v)
                    } else {
                      setTagInput(v)
                    }
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addTag(tagInput)
                    }
                  }}
                  placeholder={tags.length ? '' : 'Add tags or interests'}
                  data-testid="composer-tags-input"
                  className="bg-transparent text-sm outline-none flex-1 min-w-[80px] py-1"
                />

              </div>

              {/* Block 5: closed NSFW selector — adults-only, chosen from the server vocab */}
              {nsfwEligible && nsfwVocab.length > 0 && (
                <div className="mt-3 pt-3 border-t border-edge" data-testid="composer-nsfw">
                  <div className="text-xs text-rose-400/80 mb-1.5 font-medium">NSFW labels (18+ only)</div>
                  <div className="flex flex-wrap gap-1.5">
                    {nsfwVocab.map(tag => {
                      const active = nsfwTags.includes(tag)
                      return (
                        <button
                          key={tag}
                          type="button"
                          data-testid={`composer-nsfw-${tag.replace('@', '').toLowerCase()}`}
                          onClick={() => setNsfwTags(active ? nsfwTags.filter(t => t !== tag) : [...nsfwTags, tag])}
                          className={`text-xs px-2.5 py-1 rounded-full border transition ${
                            active ? 'bg-rose-500/20 text-rose-300 border-rose-500/50' : 'border-edge text-slate-400 hover:text-white'
                          }`}
                        >
                          {tag}
                        </button>
                      )
                    })}
                  </div>
                  {nsfwTags.length > 0 && (
                    <div className="text-[11px] text-slate-500 mt-1.5">This post will be marked NSFW and shown only to age-verified adults with NSFW turned on.</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Schedule */}
          {schedOn && (
            <div className="mt-3 flex items-center gap-2" data-testid="composer-schedule-row">
              <Clock className="h-4 w-4 text-brand shrink-0" />
              <input type="datetime-local" value={schedAt} min={toLocalInput(Date.now() + 60000)} onChange={e => setSchedAt(e.target.value)}
                data-testid="composer-schedule-datetime" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand [color-scheme:dark]" />
            </div>
          )}

          {/* Media + Post */}
          <div className="flex items-center gap-2 mt-3">

            <input
              ref={fileRef}
              type="file"
              accept="image/*,video/*"
              multiple
              hidden
              onChange={onFile}
            />

            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading || mediaList.length >= 10}
              className="h-10 w-10 grid place-items-center rounded-xl bg-white/5 border border-edge hover:bg-white/10 disabled:opacity-50"
            >
              {uploading
                ? <Loader2 className="h-5 w-5 animate-spin" />
                : <ImageIcon className="h-5 w-5" />
              }
            </button>

            <button
              type="button"
              onClick={recording ? stopRec : startRec}
              disabled={uploading}
              data-testid="composer-record-audio"
              title={recording ? 'Stop recording' : 'Record audio'}
              className={`h-10 w-10 grid place-items-center rounded-xl border transition ${
                recording
                  ? 'bg-rose-600 border-rose-500 animate-pulse text-white'
                  : 'bg-white/5 border-edge hover:bg-white/10'
              }`}
            >
              {recording ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
            </button>

            {recording && (
              <span className="text-xs text-rose-300 font-medium">Recording…</span>
            )}

            <button
              type="button"
              onClick={() => { setSchedOn(v => !v); if (!schedAt) setSchedAt(toLocalInput(Date.now() + 3600000)) }}
              data-testid="composer-schedule-toggle"
              title={schedOn ? 'Post now instead' : 'Schedule for later'}
              className={`h-10 w-10 grid place-items-center rounded-xl border transition ${
                schedOn ? 'bg-brand/20 border-brand text-brand' : 'bg-white/5 border-edge hover:bg-white/10'
              }`}
            >
              <Clock className="h-5 w-5" />
            </button>

            <button
              onClick={submit}
              data-testid="composer-submit"
              disabled={busy || (!text.trim() && !mediaList.length)}
              className="ml-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-brand to-violet-600 font-semibold disabled:opacity-50"
            >
              {busy ? (schedOn ? 'Scheduling…' : 'Posting…') : (schedOn ? 'Schedule' : 'Post')}
            </button>

          </div>
        </div>
    </div>
    </div>,
    document.body
  )
}

export default function Feed() {
  const [scope, setScope] = useState('general')
  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const headRef = useRef<HTMLDivElement | null>(null)
  const [headH, setHeadH] = useState(200)
  const [scheduled, setScheduled] = useState<any[]>([])
  const [schedPanel, setSchedPanel] = useState(false)
  const [schedNote, setSchedNote] = useState('')
  const loadScheduled = () => api.scheduledPosts().then(setScheduled).catch(() => {})
  useEffect(() => { loadScheduled() }, [])
  // when a queued post's time passes, refresh so it shows up in the feed
  useEffect(() => {
    if (!scheduled.length) return
    const next = new Date(scheduled[0].scheduled_at).getTime() - Date.now()
    const t = setTimeout(() => { loadScheduled(); load() }, Math.max(next, 0) + 25000)
    return () => clearTimeout(t)
  }, [scheduled])
  const onScheduled = (s: any) => {
    setScheduled(p => [...p, s].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)))
    setSchedNote(`Scheduled for ${fmtWhen(s.scheduled_at)}`)
    setTimeout(() => setSchedNote(''), 4000)
  }

  useEffect(() => {
    const el = headRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setHeadH(el.offsetHeight))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const load = async () => {
    setLoading(true)

    try {
      if (scope === 'interests') {
        const r = await api.interestsFeed()
        setPosts(Array.isArray(r) ? r : [])
      } else {
        setPosts(await api.feed(scope))
      }
    } catch {
      setPosts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [scope])

  const del = async (id: string) => {
    await api.deletePost(id)
    setPosts(p => p.filter(x => x.id !== id))
  }

  return (
    <div className="relative h-full min-h-0 overflow-hidden isolate">

      {/* Feed header — outside the scroll container, so it cannot move with the feed. */}
      <div ref={headRef} data-testid="feed-pinned-header" className="absolute top-0 left-0 right-0 z-50 bg-ink/95 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))]">
      <div className="flex items-center gap-3">

        <h1 className="text-xl font-extrabold">
          My Feed
        </h1>

        {scheduled.length > 0 && (
          <button onClick={() => setSchedPanel(true)} data-testid="feed-scheduled-chip"
            className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-full bg-brand/15 text-brand border border-brand/30 hover:bg-brand/25">
            <Clock className="h-3.5 w-3.5" /> {scheduled.length}
          </button>
        )}

        {/* General / Following / Interests tab selector */}
        <div className="ml-auto flex items-center bg-panel border border-edge rounded-full p-1" role="tablist" data-testid="feed-tabs">
          {FEED_TABS.map(t => (
            <button
              key={t.key}
              role="tab"
              aria-selected={scope === t.key}
              onClick={() => setScope(t.key)}
              data-testid={`feed-tab-${t.key}`}
              className={`px-2.5 sm:px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-semibold transition-colors ${
                scope === t.key ? 'bg-brand text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

        <div className="mt-3">
          <StoryRail />
        </div>
        <LiveNowBanner />
      </div>

      <Composer onPosted={load} onScheduled={onScheduled} />
      {schedPanel && <ScheduledPostsPanel items={scheduled} setItems={setScheduled} onClose={() => setSchedPanel(false)} />}
      {schedNote && (
        <div data-testid="feed-scheduled-toast" className="absolute left-1/2 -translate-x-1/2 bottom-6 z-[60] px-4 py-2 rounded-full bg-panel border border-brand/40 text-sm text-slate-100 shadow-lg flex items-center gap-2">
          <Clock className="h-4 w-4 text-brand" /> {schedNote}
        </div>
      )}

      {/* Feed content — the ONLY scrolling area. The header (title, tabs, stories) is pinned above it. */}
      <div className="absolute inset-0 overflow-y-auto overscroll-contain px-4 pb-4 space-y-4 touch-pan-y" style={{ paddingTop: headH + 16 }} data-testid="feed-scroll">

        {loading ? (
          <div className="py-16 grid place-items-center text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : posts.length === 0 ? (
          <p className="text-center text-slate-500 py-10" data-testid="feed-empty">
            {scope === 'interests'
              ? 'Your interest feed is quiet. Follow interests in Settings → Preferences → Interests to see fresh posts here.'
              : 'Nothing here yet. Make the first post!'}
          </p>
        ) : (
          posts.map(p => (
            <PostCard
              key={p.id}
              post={p}
              onDelete={del}
            />
          ))
        )}

      </div>
    </div>
  )
}
