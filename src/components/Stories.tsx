import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { useAuth } from '../lib/auth'
import { Plus, X, Loader2, Trash2, Eye, Radio, Image as ImageIcon, PlayCircle } from 'lucide-react'
import LiveModal from './LiveModal'
import MediaLightbox from './MediaLightbox'
import { Capacitor } from '@capacitor/core'

const isNative = (() => { try { return Capacitor.isNativePlatform() } catch { return false } })()

export type StoryItem = {
  id: string; media_url: string; media_type: string; caption: string
  created_at: string; viewed: boolean; mine: boolean; viewer_count: number | null
}
export type StoryGroup = {
  user: { id: string; handle: string; display_name: string; avatar_url?: string | null }
  is_self: boolean; all_viewed: boolean; stories: StoryItem[]
}

const IMG_DURATION = 5000 // ms an image story is shown before auto-advancing

// ---------------------------------------------------------------------------
// Full-screen Instagram-style viewer
// ---------------------------------------------------------------------------
export function StoryViewer({ groups, startGroup = 0, onClose, onChanged }: {
  groups: StoryGroup[]; startGroup?: number; onClose: () => void; onChanged?: () => void
}) {
  const [gi, setGi] = useState(startGroup)
  const [si, setSi] = useState(0)
  const [paused, setPaused] = useState(false)
  const [progress, setProgress] = useState(0)
  const [showViewers, setShowViewers] = useState<any[] | null>(null)
  const raf = useRef<number | null>(null)
  const start = useRef<number>(0)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const group = groups[gi]
  const story = group?.stories[si]

  const nextGroup = useCallback(() => {
    if (gi < groups.length - 1) { setGi(gi + 1); setSi(0) } else onClose()
  }, [gi, groups.length, onClose])

  const next = useCallback(() => {
    if (group && si < group.stories.length - 1) setSi(si + 1)
    else nextGroup()
  }, [group, si, nextGroup])

  const prev = useCallback(() => {
    if (si > 0) setSi(si - 1)
    else if (gi > 0) { const pg = groups[gi - 1]; setGi(gi - 1); setSi(Math.max(0, pg.stories.length - 1)) }
  }, [si, gi, groups])

  // Mark the current story viewed (fire-and-forget) when it appears.
  useEffect(() => {
    if (story && !story.mine) { api.viewStory(story.id).catch(() => {}) }
  }, [story?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Progress + auto-advance for image stories (videos advance on 'ended').
  useEffect(() => {
    setProgress(0)
    if (!story || story.media_type === 'video') return
    start.current = performance.now()
    let acc = 0
    const tick = (t: number) => {
      if (paused) { start.current = t - acc; raf.current = requestAnimationFrame(tick); return }
      acc = t - start.current
      const pct = Math.min(1, acc / IMG_DURATION)
      setProgress(pct)
      if (pct >= 1) next()
      else raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [story?.id, paused]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') prev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [next, prev, onClose])

  const del = async () => {
    if (!story || !confirm('Delete this story?')) return
    try {
      await api.deleteStory(story.id)
      onChanged?.()
      // Remove locally; advance or close.
      group.stories.splice(si, 1)
      if (group.stories.length === 0) nextGroup()
      else setSi(Math.min(si, group.stories.length - 1))
    } catch (e: any) { alert(e.message) }
  }

  const openViewers = async () => {
    if (!story) return
    setPaused(true)
    try { setShowViewers(await api.storyViewers(story.id)) } catch { setShowViewers([]) }
  }

  if (!group || !story) return null

  return (
    <div className="fixed inset-0 z-[80] bg-black flex items-center justify-center select-none" data-testid="story-viewer">
      <div className="relative w-full h-full max-w-[480px] mx-auto flex flex-col">
        {/* Progress bars */}
        <div className="absolute top-0 inset-x-0 z-20 flex gap-1 px-3 pt-[calc(0.5rem+env(safe-area-inset-top))]">
          {group.stories.map((s, i) => (
            <div key={s.id} className="flex-1 h-0.5 rounded-full bg-white/30 overflow-hidden">
              <div className="h-full bg-white transition-[width] duration-75"
                style={{ width: i < si ? '100%' : i > si ? '0%' : `${(story.media_type === 'video' ? 0 : progress) * 100}%` }} />
            </div>
          ))}
        </div>

        {/* Header */}
        <div className="absolute top-0 inset-x-0 z-20 flex items-center gap-2.5 px-3 pt-[calc(1.4rem+env(safe-area-inset-top))]">
          <Avatar id={group.user.id} name={group.user.display_name} url={group.user.avatar_url} size={34} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-white truncate">{group.user.display_name}</div>
            <div className="text-[11px] text-white/60 truncate">#{group.user.handle}</div>
          </div>
          <button onClick={onClose} data-testid="story-close" className="h-9 w-9 grid place-items-center rounded-full text-white/90 hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Media */}
        <div className="flex-1 grid place-items-center overflow-hidden"
          onMouseDown={() => setPaused(true)} onMouseUp={() => setPaused(false)}
          onTouchStart={() => setPaused(true)} onTouchEnd={() => setPaused(false)}>
          {story.media_type === 'video' ? (
            <video ref={videoRef} src={story.media_url} autoPlay playsInline
              onEnded={next} className="max-h-full max-w-full object-contain" />
          ) : (
            <img src={story.media_url} className="max-h-full max-w-full object-contain" alt="" />
          )}
        </div>

        {/* Caption */}
        {story.caption && (
          <div className="absolute bottom-24 inset-x-0 z-20 px-6 text-center">
            <span className="inline-block bg-black/45 backdrop-blur text-white text-sm rounded-2xl px-4 py-2">{story.caption}</span>
          </div>
        )}

        {/* Tap zones (prev / next) */}
        <button aria-label="Previous" onClick={prev} className="absolute left-0 top-16 bottom-16 w-1/3 z-10" data-testid="story-prev" />
        <button aria-label="Next" onClick={next} className="absolute right-0 top-16 bottom-16 w-1/3 z-10" data-testid="story-next" />

        {/* Owner footer: viewer count + delete */}
        {story.mine && (
          <div className="absolute bottom-0 inset-x-0 z-20 flex items-center gap-3 px-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
            <button onClick={openViewers} data-testid="story-viewers-btn"
              className="flex items-center gap-1.5 text-white/90 text-sm bg-white/10 rounded-full px-3 py-1.5">
              <Eye className="h-4 w-4" />{story.viewer_count ?? 0}
            </button>
            <button onClick={del} data-testid="story-delete"
              className="ml-auto flex items-center gap-1.5 text-rose-300 text-sm bg-rose-500/15 rounded-full px-3 py-1.5">
              <Trash2 className="h-4 w-4" />Delete
            </button>
          </div>
        )}
      </div>

      {/* Viewers sheet */}
      {showViewers && (
        <div className="absolute inset-0 z-[90] bg-black/60 flex items-end sm:items-center justify-center"
          onClick={() => { setShowViewers(null); setPaused(false) }}>
          <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl w-full max-w-md max-h-[60vh] overflow-y-auto p-4"
            onClick={e => e.stopPropagation()}>
            <div className="text-sm font-semibold mb-3 flex items-center gap-2"><Eye className="h-4 w-4 text-brand" />Viewers ({showViewers.length})</div>
            {showViewers.length === 0 ? <p className="text-slate-500 text-sm py-6 text-center">No views yet.</p> : showViewers.map((v: any) => (
              <div key={v.handle} className="flex items-center gap-2.5 py-2">
                <Avatar id={v.handle} name={v.display_name} url={v.avatar_url} size={34} />
                <div className="min-w-0"><div className="text-sm font-medium truncate">{v.display_name}</div><div className="text-xs text-slate-500 truncate">#{v.handle}</div></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Horizontal rail shown at the top of the feed
// ---------------------------------------------------------------------------
export function StoryRail() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [groups, setGroups] = useState<StoryGroup[]>([])
  const [open, setOpen] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const load = useCallback(() => { api.stories().then(setGroups).catch(() => {}) }, [])
  useEffect(() => { load() }, [load])

  const [live, setLive] = useState<any[]>([])
  const [liveOpen, setLiveOpen] = useState<{ mode: 'host' | 'viewer'; liveId?: string } | null>(null)
  const [chooser, setChooser] = useState(false)
  const loadLive = useCallback(() => { api.liveList().then(setLive).catch(() => {}) }, [])
  useEffect(() => {
    loadLive()
    const t = setInterval(loadLive, 20000)
    const onFocus = () => loadLive()
    window.addEventListener('focus', onFocus)
    window.addEventListener('skali:live-changed', onFocus)
    return () => { clearInterval(t); window.removeEventListener('focus', onFocus); window.removeEventListener('skali:live-changed', onFocus) }
  }, [loadLive])
  const myHandle = (user as any)?.handle
  // Live Stories (everyone) show as story rings; Content Streams (creators) live behind the Watch circle.
  const liveStories = live.filter(l => l.kind === 'story')
  const streamsLive = live.filter(l => l.kind !== 'story' && l.host?.handle !== myHandle)
  const myLiveStory = liveStories.find(l => l.host?.handle === myHandle)
  const othersLiveStories = liveStories.filter(l => l.host?.handle !== myHandle)

  const myIdx = groups.findIndex(g => g.is_self)
  const hasMine = myIdx >= 0
  const others = groups.filter(g => !g.is_self)

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      const r = await api.upload(file)
      const caption = window.prompt('Add a caption (optional):', '') || ''
      await api.createStory(r.signed_url, r.media_type === 'video' ? 'video' : 'image', caption)
      load()
    } catch (err: any) { alert(err?.message || 'Could not add story') }
    finally { setUploading(false) }
  }

  const openGroupByUser = (handle: string) => {
    const idx = groups.findIndex(g => g.user.handle === handle)
    if (idx >= 0) setOpen(idx)
  }

  return (
    <div className="bg-panel border border-edge rounded-2xl px-3 py-3" data-testid="story-rail">
      <input ref={fileRef} type="file" accept="image/*,video/*" hidden onChange={onFile} />
      <div className="flex gap-4 overflow-x-auto no-scrollbar">
        {/* Watch Streams — Content Streaming discovery (Find → Streamers) */}
        <button data-testid="watch-live-btn" onClick={() => nav('/search?tab=streamers')} className="shrink-0 flex flex-col items-center gap-1.5 w-16">
          <div className={`rounded-full p-[2.5px] ${streamsLive.length ? 'bg-rose-600' : 'bg-edge'}`}>
            <div className="rounded-full p-[2px] bg-ink">
              <div className="h-14 w-14 rounded-full bg-rose-500/15 grid place-items-center"><PlayCircle className="h-6 w-6 text-rose-400" /></div>
            </div>
          </div>
          <span className="text-[11px] text-rose-300 font-semibold truncate max-w-full">Watch Streams</span>
        </button>

        {/* Your live story (while you are live) */}
        {myLiveStory && (
          <button data-testid="my-live-story-btn" onClick={() => setLiveOpen({ mode: 'viewer', liveId: myLiveStory.id })}
            className="shrink-0 flex flex-col items-center gap-1.5 w-16">
            <div className="relative">
              <div className="rounded-full p-[2.5px] bg-rose-600 animate-pulse">
                <div className="rounded-full p-[2px] bg-ink">
                  <Avatar id={user?.id || 'me'} name={(user as any)?.display_name || 'You'} url={(user as any)?.avatar_url} size={56} />
                </div>
              </div>
              <span className="neon-live absolute -bottom-1 left-1/2 -translate-x-1/2 bg-rose-600 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full ring-2 ring-ink">LIVE</span>
            </div>
            <span className="text-[11px] text-rose-300 font-semibold truncate max-w-full">Your live</span>
          </button>
        )}

        {/* Your story */}
        <button data-testid="add-story-btn"
          onClick={() => hasMine ? setOpen(myIdx) : setChooser(true)}
          className="shrink-0 flex flex-col items-center gap-1.5 w-16">
          <div className="relative">
            <div className={`rounded-full p-[2.5px] ${hasMine && !groups[myIdx]?.all_viewed ? 'bg-gradient-to-tr from-brand via-fuchsia-500 to-amber-400' : 'bg-edge'}`}>
              <div className="rounded-full p-[2px] bg-ink">
                <Avatar id={user?.id || 'me'} name={(user as any)?.display_name || 'You'} url={(user as any)?.avatar_url} size={56} />
              </div>
            </div>
            <span onClick={e => { e.stopPropagation(); setChooser(true) }} data-testid="add-story-plus"
              className="absolute -bottom-0.5 -right-0.5 h-6 w-6 rounded-full bg-brand grid place-items-center ring-2 ring-ink cursor-pointer hover:brightness-110">
              {uploading ? <Loader2 className="h-3.5 w-3.5 text-white animate-spin" /> : <Plus className="h-3.5 w-3.5 text-white" />}
            </span>
          </div>
          <span className="text-[11px] text-slate-400 truncate max-w-full">Your story</span>
        </button>

        {/* People on a Live Story right now */}
        {othersLiveStories.map(l => (
          <button key={l.id} data-testid={`live-ring-${l.host?.handle}`}
            onClick={() => setLiveOpen({ mode: 'viewer', liveId: l.id })}
            className="shrink-0 flex flex-col items-center gap-1.5 w-16">
            <div className="relative">
              <div className="rounded-full p-[2.5px] bg-gradient-to-tr from-rose-600 via-neon-pink to-brand neon-ring">
                <div className="rounded-full p-[2px] bg-ink">
                  <Avatar id={l.host?.handle} name={l.host?.display_name} url={l.host?.avatar_url} size={56} />
                </div>
              </div>
              <span className="neon-live absolute -bottom-1 left-1/2 -translate-x-1/2 bg-rose-600 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full ring-2 ring-ink">LIVE</span>
            </div>
            <span className="text-[11px] text-slate-400 truncate max-w-full">{l.host?.display_name}</span>
          </button>
        ))}

        {/* Followed people's stories */}
        {others.map(g => (
          <button key={g.user.id} data-testid={`story-ring-${g.user.handle}`}
            onClick={() => openGroupByUser(g.user.handle)}
            className="shrink-0 flex flex-col items-center gap-1.5 w-16">
            <div className={`rounded-full p-[2.5px] ${g.all_viewed ? 'bg-edge' : 'bg-gradient-to-tr from-brand via-fuchsia-500 to-amber-400'}`}>
              <div className="rounded-full p-[2px] bg-ink">
                <Avatar id={g.user.id} name={g.user.display_name} url={g.user.avatar_url} size={56} />
              </div>
            </div>
            <span className="text-[11px] text-slate-400 truncate max-w-full">{g.user.display_name}</span>
          </button>
        ))}
      </div>

      {open !== null && (
        <StoryViewer groups={groups} startGroup={open} onClose={() => setOpen(null)} onChanged={load} />
      )}

      {chooser && createPortal(
        <div className="fixed inset-0 z-[88] bg-black/70 backdrop-blur grid place-items-end sm:place-items-center"
          onClick={() => setChooser(false)} data-testid="story-chooser">
          <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl w-full max-w-sm p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]" onClick={e => e.stopPropagation()}>
            <button onClick={() => { setChooser(false); fileRef.current?.click() }} data-testid="story-chooser-media"
              className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white">
              <ImageIcon className="h-5 w-5 text-brand" /> Photo or video story
            </button>
            {isNative && (
              <button onClick={() => { setChooser(false); setLiveOpen({ mode: 'host' }) }} data-testid="story-chooser-live"
                className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white">
                <Radio className="h-5 w-5 text-rose-400" /> Live Story
              </button>
            )}
            <button onClick={() => setChooser(false)} data-testid="story-chooser-cancel"
              className="w-full px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 text-center">Cancel</button>
          </div>
        </div>,
        document.body
      )}

      {liveOpen && (
        <LiveModal mode={liveOpen.mode} liveId={liveOpen.liveId} kind="story"
          onClose={() => { setLiveOpen(null); loadLive(); load() }} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Standalone "Add to Story" button (used on the profile page)
// ---------------------------------------------------------------------------
export function AddStoryButton({ onAdded, className = '' }: { onAdded?: () => void; className?: string }) {
  const fileRef = useRef<HTMLInputElement | null>(null)
  const [uploading, setUploading] = useState(false)
  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      const r = await api.upload(file)
      const caption = window.prompt('Add a caption (optional):', '') || ''
      await api.createStory(r.signed_url, r.media_type === 'video' ? 'video' : 'image', caption)
      onAdded?.()
    } catch (err: any) { alert(err?.message || 'Could not add story') }
    finally { setUploading(false) }
  }
  return (
    <>
      <input ref={fileRef} type="file" accept="image/*,video/*" hidden onChange={onFile} />
      <button onClick={() => fileRef.current?.click()} disabled={uploading} data-testid="profile-add-story"
        className={className || 'px-4 py-1.5 rounded-full border border-edge text-sm font-semibold flex items-center gap-1.5 hover:bg-white/5 disabled:opacity-50'}>
        {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Add to Story
      </button>
    </>
  )
}

export function ProfileStoryAvatar({ profile, size = 60, children }: {
  profile: any; size?: number; children?: React.ReactNode
}) {
  const [group, setGroup] = useState<StoryGroup | null>(null)
  const [open, setOpen] = useState(false)
  const [photo, setPhoto] = useState(false)
  const [choose, setChoose] = useState(false)
  const active = !!profile?.has_active_story
  const hasPhoto = !!profile?.avatar_url

  const viewStory = async () => {
    setChoose(false)
    try {
      const r = await api.storiesOfUser(profile.handle)
      if (r.stories?.length) { setGroup({ user: r.user, is_self: r.is_self, all_viewed: false, stories: r.stories }); setOpen(true) }
      else if (hasPhoto) setPhoto(true)
    } catch { if (hasPhoto) setPhoto(true) }
  }
  const viewPhoto = () => { setChoose(false); if (hasPhoto) setPhoto(true) }

  // Tap behaviour: always open the chooser; options that aren't available are shown disabled.
  const onTap = () => setChoose(true)

  const interactive = true

  return (
    <>
      <div className={`rounded-full p-[2.5px] ${active ? 'bg-gradient-to-tr from-brand via-fuchsia-500 to-amber-400' : 'ring-2 ring-edge'} ${interactive ? 'cursor-pointer' : ''}`}
        onClick={onTap} data-testid="profile-story-avatar">
        <div className={active ? 'rounded-full p-[2px] bg-ink' : ''}>
          <Avatar id={profile.id} name={profile.display_name} url={profile.avatar_url} size={size} />
        </div>
      </div>

      {choose && createPortal(
        <div className="fixed inset-0 z-[88] bg-black/70 backdrop-blur grid place-items-end sm:place-items-center p-0 sm:p-4"
          onClick={() => setChoose(false)} data-testid="avatar-chooser">
          <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl w-full max-w-sm p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]" onClick={e => e.stopPropagation()}>
            <button onClick={viewStory} disabled={!active} data-testid="avatar-view-story"
              className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white disabled:opacity-40 disabled:hover:bg-transparent">
              <PlayCircle className="h-5 w-5 text-brand" /> View story
              {!active && <span className="ml-auto text-xs text-slate-500">No active story</span>}
            </button>
            <button onClick={viewPhoto} disabled={!hasPhoto} data-testid="avatar-view-photo"
              className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white disabled:opacity-40 disabled:hover:bg-transparent">
              <ImageIcon className="h-5 w-5 text-slate-300" /> View profile photo
              {!hasPhoto && <span className="ml-auto text-xs text-slate-500">No photo yet</span>}
            </button>
            <button onClick={() => setChoose(false)} data-testid="avatar-chooser-cancel"
              className="w-full px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 text-center">Cancel</button>
          </div>
        </div>,
        document.body
      )}

      {open && group && <StoryViewer groups={[group]} startGroup={0} onClose={() => setOpen(false)} />}
      {photo && hasPhoto && (
        <MediaLightbox items={[{ url: profile.avatar_url, type: 'image' }]} onClose={() => setPhoto(false)} />
      )}
    </>
  )
}
