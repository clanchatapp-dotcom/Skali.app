import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar, timeAgo, Linkify } from '../lib/ui'
import PostCard from '../components/PostCard'
import RoleBadge from '../components/RoleBadge'
import AccountBadge from '../components/AccountBadge'
import { useAuth } from '../lib/auth'
import { ArrowLeft, MoreHorizontal, Lock, Loader2, Check, Link as LinkIcon, Camera, Trash2, Ban, VolumeX, ShieldOff, Plus, MessagesSquare, Send, X, Pin, Settings as SettingsIcon, ChevronRight } from 'lucide-react'

const TABS = ['media', 'wall', 'boards', 'audio'] as const
type Tab = typeof TABS[number]
export default function Profile() {
  const { handle } = useParams()
  const nav = useNavigate()
  const { refresh } = useAuth()
  const [p, setP] = useState<any>(null)
  const [posts, setPosts] = useState<any[]>([])
  const [tab, setTab] = useState<Tab>('media')
  const [loading, setLoading] = useState(true)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const prof = await api.getUser(handle!)
      if (prof?.handle && handle && prof.handle !== handle) {
        nav(`/u/${prof.handle}`, { replace: true })
        return
      }
      setP(prof)
      setPosts(await api.getUserPosts(handle!))
    } catch {
      setP(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [handle])

  const doFollow = async () => {
    p.follow_status ? await api.unfollow(p.handle) : await api.follow(p.handle)
    load()
  }

  const invite = async () => { await api.inviteInner(p.handle); load() }

  const del = async (id: string) => {
    await api.deletePost(id)
    setPosts(x => x.filter(y => y.id !== id))
  }

  const setRel = async (kind: string) => {
    setMenuOpen(false)
    try {
      if (p.my_relation === kind) { await api.clearRelation(p.handle); await load(); return }
      await api.setRelation(p.handle, kind)
      if (kind === 'block') { nav('/', { replace: true }); return }
      await load()
    } catch (e: any) { alert(e.message || 'Could not update') }
  }

  const onAvatarPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingAvatar(true)
    try {
      const { signed_url } = await api.upload(file)
      await api.updateProfile({ avatar_url: signed_url })
      await refresh()
      await load()
    } catch { alert('Could not upload photo. Please try again.') }
    setUploadingAvatar(false)
    e.target.value = ''
  }

  if (loading) return <div className="h-full grid place-items-center text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div>
  if (!p) return <div className="h-full grid place-items-center text-center text-slate-500 px-6">User not found.</div>

  const media = posts.filter(x => x.media_url && x.media_type !== 'audio')
  const wall = posts.filter(x => !x.media_url)
  const audio = posts.filter(x => x.media_type === 'audio')
  const current = tab === 'media' ? media : tab === 'wall' ? wall : audio

  return (
    <div className="h-full min-h-0 flex flex-col overflow-hidden">
      {/* Fixed app bar */}
      <header className="shrink-0 z-30 bg-ink/95 backdrop-blur border-b border-edge px-4 pt-[env(safe-area-inset-top)] min-h-14 flex items-center justify-between">
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-300 hover:text-white py-3" aria-label="Back to feed">
          <ArrowLeft className="h-5 w-5" />
          <span className="text-lg">Feed</span>
        </button>

        {p.is_self ? (
          <button onClick={() => nav('/settings')} className="h-10 px-4 rounded-full border border-edge bg-panel/60 flex items-center gap-2 text-slate-200 hover:bg-white/10 transition" aria-label="Open Settings">
            <SettingsIcon className="h-5 w-5" />
            <span className="font-medium">Settings</span>
          </button>
        ) : (
          <div className="relative">
            <button onClick={() => setMenuOpen(o => !o)} title="More options" className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10 text-slate-300" aria-label="More options">
              <MoreHorizontal className="h-5 w-5" />
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 mt-2 w-52 z-50 bg-panel border border-edge rounded-xl shadow-xl shadow-black/40 py-1 animate-pop">
                  <MenuItem Icon={Ban} tint="text-rose-400" active={p.my_relation === 'block'} onClick={() => setRel('block')} label={p.my_relation === 'block' ? 'Unblock' : 'Block'} />
                  <MenuItem Icon={VolumeX} tint="text-amber-400" active={p.my_relation === 'mute'} onClick={() => setRel('mute')} label={p.my_relation === 'mute' ? 'Unmute' : 'Mute'} />
                  <MenuItem Icon={ShieldOff} tint="text-sky-400" active={p.my_relation === 'restrict'} onClick={() => setRel('restrict')} label={p.my_relation === 'restrict' ? 'Un-restrict' : 'Restrict'} />
                </div>
              </>
            )}
          </div>
        )}
      </header>

      {/* Compact profile summary */}
      <section className="shrink-0 border-b border-edge bg-ink">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-3 pb-2.5">
          {/* Avatar + identity row */}
          <div className="flex items-center gap-3">
            <div className="relative shrink-0">
              <div className="ring-2 ring-edge rounded-full p-0.5 bg-black/20">
                <Avatar id={p.id} name={p.display_name} url={p.avatar_url} size={60} />
              </div>
              {p.is_self && (
                <label className="absolute -bottom-0.5 -right-0.5 h-7 w-7 rounded-full bg-brand grid place-items-center cursor-pointer shadow-md shadow-violet-900/40 ring-2 ring-ink hover:brightness-110 transition">
                  {uploadingAvatar ? <Loader2 className="h-3.5 w-3.5 text-white animate-spin" /> : <Camera className="h-3.5 w-3.5 text-white" />}
                  <input type="file" accept="image/*" className="hidden" onChange={onAvatarPick} disabled={uploadingAvatar} />
                </label>
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <h1 className="text-base sm:text-lg font-extrabold leading-tight truncate max-w-full">#{p.handle}</h1>
                <RoleBadge role={p.role} size={16} />
                <AccountBadge type={p.account_type} role={p.role} verified={p.verified} size={14} />
              </div>
              <div className="text-xs text-slate-400 truncate leading-tight mt-0.5">{p.display_name}</div>
              {p.real_name && <div className="text-[11px] text-slate-500 truncate leading-tight">{p.real_name}</div>}
              {/* Follower / Following counts — inline, no overlap */}
              <div className="mt-1 flex items-center gap-4 text-xs">
                <span><span className="font-bold text-slate-100">{p.followers_count ?? 0}</span><span className="text-slate-500 uppercase tracking-wide ml-1">Followers</span></span>
                <span><span className="font-bold text-slate-100">{p.following_count ?? 0}</span><span className="text-slate-500 uppercase tracking-wide ml-1">Following</span></span>
              </div>
            </div>
          </div>

          {p.bio && <p className="mt-2 text-xs text-slate-300 line-clamp-2">{p.bio}</p>}

          {p.creator_safety_flag && !p.is_self && (
            <div className="mt-2 text-xs bg-orange-500/10 border border-orange-500/40 text-orange-200 rounded-lg px-2.5 py-1.5">
              This account has a history of upheld harassment or abusive behaviour. Please exercise caution.
            </div>
          )}

          {/* My Links (compact) */}
          <button onClick={() => nav(`/u/${p.handle}/links`)} className="mt-2.5 w-full bg-panel/70 border border-edge rounded-xl px-3 py-2 flex items-center gap-2.5 text-left hover:bg-white/5 transition">
            <span className="h-8 w-8 rounded-lg bg-brand/10 border border-brand/20 grid place-items-center shrink-0">
              <LinkIcon className="h-4 w-4 text-brand" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-medium text-sm leading-tight">My links</span>
              <span className="block text-[11px] text-slate-500 truncate leading-tight">
                {p.links?.length ? `${p.links.length} link${p.links.length === 1 ? '' : 's'} · Shop · Socials · More` : 'Shop · Socials · More'}
              </span>
            </span>
            <ChevronRight className="h-4 w-4 text-slate-400 shrink-0" />
          </button>

          {/* Actions for other profiles only */}
          {!p.is_self && (
            <div className="mt-2.5 flex flex-wrap items-center justify-center gap-2">
              <button onClick={doFollow} className={`px-5 py-1.5 rounded-full text-sm font-semibold min-w-[110px] ${p.follow_status === 'approved' ? 'border border-edge' : p.follow_status === 'pending' ? 'border border-amber-500/40 text-amber-300' : 'bg-gradient-to-r from-brand to-violet-600'}`}>
                {p.follow_status === 'approved' ? 'Following' : p.follow_status === 'pending' ? 'Requested' : 'Follow'}
              </button>
              <button onClick={() => p.can_dm ? nav(`/messages/${p.handle}`) : alert('DMs are tier-gated — you need to be a Follower (with DMs on) or in their Inner Circle.')} className="px-5 py-1.5 rounded-full border border-edge text-sm font-semibold min-w-[110px] hover:bg-white/5">Message</button>
              <button onClick={invite} disabled={p.inner_status === 'accepted'} className="px-3 py-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-300 text-xs flex items-center gap-1.5 hover:bg-violet-500/20 disabled:opacity-50">
                <Lock className="h-3.5 w-3.5" />
                {p.inner_status === 'accepted' ? 'In your Inner Circle' : p.inner_status === 'pending' ? 'Invite sent' : 'Invite to Inner Circle'}
              </button>
            </div>
          )}

          {/* Pill tabs (where the Shop / Private-account card used to live) */}
          <div className="mt-3 flex items-center gap-2 overflow-x-auto no-scrollbar -mx-1 px-1">
            {TABS.map(t => (
              <button key={t} onClick={() => setTab(t)} className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide transition ${tab === t ? 'bg-brand text-white shadow-sm shadow-violet-900/30' : 'bg-panel/60 border border-edge text-slate-400 hover:text-slate-200'}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Only content scrolls */}
      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
        <div className="max-w-3xl mx-auto px-4 py-5 pb-8 space-y-4">
          {p.pinned_posts?.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500 font-semibold">
                <Pin className="h-3.5 w-3.5 text-brand" /> Pinned
              </div>
              {p.pinned_posts.map((post: any) => (
                <PostCard key={`pin-${post.id}`} post={post} onDelete={p.is_self ? del : undefined} />
              ))}
            </div>
          )}

          {tab === 'wall' ? (
            <WallTab handle={p.handle} />
          ) : tab === 'boards' ? (
            <BoardsTab handle={p.handle} isSelf={p.is_self} />
          ) : current.length === 0 ? (
            <p className="text-center text-slate-500 py-14">No {tab} posts yet.</p>
          ) : (
            current.map(post => (
              <PostCard key={post.id} post={post} onDelete={p.is_self ? del : undefined} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

/* ---- unchanged helpers below ---- */

function WallTab({ handle }: { handle: string }) {
  const [data, setData] = useState<any>({ can_post: false, posts: [] })
  const [text, setText] = useState('')
  const load = () => api.getWall(handle).then(setData).catch(() => {})
  useEffect(() => { load() }, [handle])

  const submit = async () => {
    const t = text.trim(); if (!t) return
    try {
      const w = await api.postWall(handle, t)
      setData((d: any) => ({ ...d, posts: [w, ...d.posts] }))
      setText('')
    } catch (e: any) { alert(e.message) }
  }

  const remove = async (id: string) => {
    try {
      await api.deleteWall(id)
      setData((d: any) => ({ ...d, posts: d.posts.filter((x: any) => x.id !== id) }))
    } catch {}
  }

  return (
    <div className="space-y-4">
      {data.can_post && (
        <div className="bg-panel border border-edge rounded-2xl p-3">
          <textarea value={text} onChange={e => setText(e.target.value)} rows={2} placeholder="Write on this wall…" className="w-full bg-ink border border-edge rounded-xl px-3 py-2 outline-none focus:border-brand resize-none" />
          <div className="flex justify-end mt-2">
            <button onClick={submit} className="px-4 py-2 rounded-xl bg-brand font-medium">Post to wall</button>
          </div>
        </div>
      )}
      {data.posts.length === 0 && (
        <p className="text-center text-slate-500 py-10">No wall posts yet.{data.can_post ? ' Be the first!' : ' Only followers & Inner Circle can post here.'}</p>
      )}
      {data.posts.map((w: any) => (
        <div key={w.id} className="bg-panel border border-edge rounded-2xl p-3 flex gap-3">
          <Link to={`/u/${w.author?.handle}`}>
            <Avatar id={w.author?.id} name={w.author?.display_name} url={w.author?.avatar_url} size={38} />
          </Link>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Link to={`/u/${w.author?.handle}`} className="font-semibold hover:underline">{w.author?.display_name}</Link>
              <RoleBadge role={w.author?.role} size={15} />
              <AccountBadge type={w.author?.account_type} role={w.author?.role} verified={w.author?.verified} size={14} />
              <span className="text-xs text-slate-500">{timeAgo(w.created_at)}</span>
              {w.can_delete && (
                <button onClick={() => remove(w.id)} className="ml-auto text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
              )}
            </div>
            <p className="mt-1 whitespace-pre-wrap break-words"><Linkify text={w.text} /></p>
          </div>
        </div>
      ))}
    </div>
  )
}

function MenuItem({ Icon, label, tint, active, onClick }: { Icon: any; label: string; tint: string; active?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-white/5 text-left">
      <Icon className={`h-4 w-4 ${tint}`} />
      <span className={active ? 'font-medium' : ''}>{label}</span>
      {active && <Check className="h-4 w-4 ml-auto text-slate-400" />}
    </button>
  )
}

const TIER_LABEL: any = { public: 'Public', followers: 'Followers', inner: 'Inner Circle' }

function BoardsTab({ handle, isSelf }: { handle: string; isSelf: boolean }) {
  const [boards, setBoards] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [tier, setTier] = useState('public')
  const [open, setOpen] = useState<any>(null)

  const load = async () => { try { setBoards(await api.boards(handle)) } catch {} ; setLoading(false) }
  useEffect(() => { load() }, [handle])

  const create = async () => {
    if (!title.trim()) return
    try { await api.createBoard({ title: title.trim(), tier }); setTitle(''); setCreating(false); await load() }
    catch (e: any) { alert(e.message) }
  }

  if (loading) return <div className="py-10 grid place-items-center"><Loader2 className="h-5 w-5 animate-spin text-slate-500" /></div>

  return (
    <div className="space-y-3">
      {isSelf && (creating ? (
        <div className="bg-panel border border-edge rounded-2xl p-4 space-y-2">
          <input value={title} onChange={e => setTitle(e.target.value)} maxLength={100} placeholder="Board title" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
          <div className="flex gap-2">
            {['public', 'followers', 'inner'].map(t => (
              <button key={t} onClick={() => setTier(t)} className={`text-xs px-3 py-1.5 rounded-full border ${tier === t ? 'bg-brand/20 text-brand border-brand/40' : 'border-edge text-slate-400'}`}>{TIER_LABEL[t]}</button>
            ))}
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setCreating(false)} className="px-3 py-1.5 rounded-lg border border-edge text-sm">Cancel</button>
            <button onClick={create} disabled={!title.trim()} className="px-4 py-1.5 rounded-lg bg-brand text-sm font-medium disabled:opacity-40">Create board</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setCreating(true)} className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl border border-dashed border-edge text-slate-400 hover:text-white hover:border-brand/50">
          <Plus className="h-4 w-4" /> New board
        </button>
      ))}

      {boards.length === 0 && !isSelf && <p className="text-center text-slate-500 py-10">No boards here yet.</p>}

      {boards.map(b => (
        <button key={b.id} onClick={() => setOpen(b)} className="w-full text-left bg-panel border border-edge rounded-2xl p-4 hover:bg-white/5">
          <div className="flex items-center gap-2">
            <MessagesSquare className="h-4 w-4 text-brand" />
            <span className="font-semibold">{b.title}</span>
            <span className="ml-auto text-[11px] flex items-center gap-1 text-slate-500">
              {b.tier !== 'public' && <Lock className="h-3 w-3" />}
              {TIER_LABEL[b.tier]}
            </span>
          </div>
          {b.description && <p className="text-sm text-slate-400 mt-1">{b.description}</p>}
          <p className="text-xs text-slate-500 mt-1">{b.post_count} posts</p>
        </button>
      ))}

      {open && <BoardView board={open} onClose={() => { setOpen(null); load() }} />}
    </div>
  )
}

function BoardView({ board, onClose }: { board: any; onClose: () => void }) {
  const [data, setData] = useState<any>(null)
  const [text, setText] = useState('')
  const load = async () => { try { setData(await api.board(board.id)) } catch (e: any) { alert(e.message); onClose() } }
  useEffect(() => { load() }, [board.id])

  const send = async () => {
    const t = text.trim(); if (!t) return
    setText('')
    try { await api.boardPost(board.id, t); await load() } catch (e: any) { alert(e.message); setText(t) }
  }

  const [replyTo, setReplyTo] = useState<string | null>(null)
  const [replyText, setReplyText] = useState('')
  const sendReply = async (parentId: string) => {
    const t = replyText.trim(); if (!t) return
    setReplyText(''); setReplyTo(null)
    try { await api.boardPost(board.id, t, parentId); await load() } catch (e: any) { alert(e.message); setReplyText(t) }
  }
  const react = async (postId: string, emoji: string) => { try { await api.reactBoardPost(postId, emoji); await load() } catch (e: any) { alert(e.message) } }
  const del = async (id: string) => { try { await api.deleteBoardPost(id); await load() } catch (e: any) { alert(e.message) } }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur grid place-items-end sm:place-items-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl w-full max-w-lg h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-edge flex items-center gap-2">
          <MessagesSquare className="h-5 w-5 text-brand" />
          <div className="flex-1 min-w-0">
            <div className="font-bold truncate">{board.title}</div>
            <div className="text-xs text-slate-500">{TIER_LABEL[board.tier]}</div>
          </div>
          <button onClick={onClose} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!data ? <div className="grid place-items-center py-10"><Loader2 className="h-5 w-5 animate-spin text-slate-500" /></div>
            : data.posts.length === 0 ? <p className="text-center text-slate-500 py-10">No posts yet. Start the conversation.</p>
            : data.posts.map((p: any) => (
              <BoardPostBubble key={p.id} p={p} canPost={!!data?.can_post} replyTo={replyTo} setReplyTo={setReplyTo} replyText={replyText} setReplyText={setReplyText} onReply={sendReply} onReact={react} onDelete={del} />
            ))}
        </div>

        {data?.can_post && (
          <div className="p-3 border-t border-edge flex gap-2">
            <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Write something…" className="flex-1 bg-ink border border-edge rounded-xl px-4 py-2.5 outline-none focus:border-brand" />
            <button onClick={send} className="h-10 w-10 grid place-items-center rounded-xl bg-brand"><Send className="h-4 w-4" /></button>
          </div>
        )}
        {data && !data.can_post && <p className="p-3 text-center text-xs text-slate-500 border-t border-edge">You can read this board. Follow to post.</p>}
      </div>
    </div>
  )
}

const BOARD_REACTIONS: Record<string, string> = { like: '👍', love: '❤️', haha: '😂', wow: '😮', sad: '😢', angry: '😡' }

function BoardPostBubble({ p, isReply = false, canPost, replyTo, setReplyTo, replyText, setReplyText, onReply, onReact, onDelete }: any) {
  const counts = p.reactions?.counts || {}
  const mine = p.reactions?.mine
  const total = (Object.values(counts) as number[]).reduce((a, b) => a + b, 0)
  const [pickerOpen, setPickerOpen] = useState(false)

  return (
    <div className={`flex gap-2 group ${isReply ? 'ml-8' : ''}`}>
      <Avatar id={p.author?.id} name={p.author?.display_name} url={p.author?.avatar_url} size={isReply ? 28 : 34} />
      <div className="flex-1 min-w-0">
        <div className="bg-ink border border-edge rounded-2xl px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{p.author?.display_name}</span>
            <span className="text-xs text-slate-500">{timeAgo(p.created_at)}</span>
            {p.can_delete && (
              <button onClick={() => onDelete(p.id)} className="ml-auto text-slate-600 hover:text-rose-400"><Trash2 className="h-3.5 w-3.5" /></button>
            )}
          </div>
          <p className="text-sm whitespace-pre-wrap break-words"><Linkify text={p.text} /></p>
        </div>

        <div className="flex items-center gap-2 mt-1 pl-1 relative">
          <button onClick={() => setPickerOpen((o: boolean) => !o)} className="text-xs text-slate-500 hover:text-brand">React</button>
          {!isReply && canPost && (
            <button onClick={() => { setReplyTo(replyTo === p.id ? null : p.id); setReplyText('') }} className="text-xs text-slate-500 hover:text-brand">Reply</button>
          )}
          {total > 0 && (
            <div className="flex items-center gap-1 flex-wrap">
              {Object.entries(counts).map(([emo, n]: any) => (
                <button key={emo} onClick={() => onReact(p.id, emo)} className={`text-xs px-1.5 py-0.5 rounded-full border ${mine === emo ? 'bg-brand/20 border-brand/40 text-brand' : 'border-edge text-slate-400'}`}>
                  {BOARD_REACTIONS[emo]} {n as number}
                </button>
              ))}
            </div>
          )}
          {pickerOpen && (
            <div className="absolute bottom-full left-0 mb-1 z-10 flex gap-1 bg-panel2 border border-edge rounded-full px-2 py-1 shadow-lg">
              {Object.entries(BOARD_REACTIONS).map(([k, e]) => (
                <button key={k} onClick={() => { onReact(p.id, k); setPickerOpen(false) }} className="text-lg hover:scale-125 transition">{e}</button>
              ))}
            </div>
          )}
        </div>

        {replyTo === p.id && (
          <div className="flex gap-2 mt-2">
            <input autoFocus value={replyText} onChange={e => setReplyText(e.target.value)} onKeyDown={e => e.key === 'Enter' && onReply(p.id)} placeholder="Write a reply…" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
            <button onClick={() => onReply(p.id)} className="h-9 w-9 grid place-items-center rounded-xl bg-brand"><Send className="h-4 w-4" /></button>
          </div>
        )}

        {(p.replies || []).length > 0 && (
          <div className="mt-2 space-y-2">
            {p.replies.map((r: any) => (
              <BoardPostBubble key={r.id} p={r} isReply canPost={canPost} replyTo={replyTo} setReplyTo={setReplyTo} replyText={replyText} setReplyText={setReplyText} onReply={onReply} onReact={onReact} onDelete={onDelete} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}