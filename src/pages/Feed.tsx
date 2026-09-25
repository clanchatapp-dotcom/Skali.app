import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { TIER, TierKey } from '../lib/ui'
import PostCard from '../components/PostCard'
import { INTERESTS } from '../lib/interests'
import { Image as ImageIcon, Loader2, X, ChevronDown, Mic, Square } from 'lucide-react'

function Composer({ onPosted }: { onPosted: () => void }) {
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

    setBusy(true)

    try {
      const hasVisual = mediaList.some(m => m.type !== 'audio')
      await api.createPost({
        tier,
        text,
        media: mediaList,
        media_url: mediaList[0]?.url,
        media_type: mediaList[0]?.type,
        tags,
        nsfw_tags: nsfwTags,
        people_tags: people,
        ai_label: hasVisual ? aiLabel : 'none'
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

      onPosted()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  const closeComposer = () => {
    setExpanded(false)
  }

  return (
    <div className="bg-panel border border-edge rounded-2xl p-4">

      {/* Collapsed composer */}
      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="w-full text-left text-slate-400 text-base py-2"
        >
          What's happening in your gathering?
        </button>
      ) : (

        /* Expanded composer */
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
              onClick={submit}
              disabled={busy || (!text.trim() && !mediaList.length)}
              className="ml-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-brand to-violet-600 font-semibold disabled:opacity-50"
            >
              {busy ? 'Posting…' : 'Post'}
            </button>

          </div>
        </div>
      )}
    </div>
  )
}

export default function Feed() {
  const [scope, setScope] = useState('general')
  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)

    try {
      setPosts(await api.feed(scope))
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
      <div className="absolute top-0 left-0 right-0 z-50 bg-ink/95 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-3">

        <h1 className="text-xl font-extrabold">
          My Feed
        </h1>

        {/* General / Followers pill */}
        <button
          onClick={() =>
            setScope(scope === 'general' ? 'followers' : 'general')
          }
          className="ml-auto flex items-center gap-1.5 bg-panel border border-edge rounded-full px-4 py-2 text-sm font-medium transition hover:border-brand/50"
        >
          <span className="text-slate-200 capitalize">
            {scope}
          </span>

          <ChevronDown className="h-4 w-4 text-slate-400" />
        </button>

      </div>

      {/* Feed content — the ONLY scrolling area. The header is a sibling, not part of this scroller. */}
      <div className="absolute inset-0 overflow-y-auto overscroll-contain pt-[calc(5.5rem+env(safe-area-inset-top))] md:pt-4 px-4 pb-4 space-y-4 touch-pan-y">

        <Composer onPosted={load} />

        {loading ? (
          <div className="py-16 grid place-items-center text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : posts.length === 0 ? (
          <p className="text-center text-slate-500 py-10">
            Nothing here yet. Make the first post!
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
