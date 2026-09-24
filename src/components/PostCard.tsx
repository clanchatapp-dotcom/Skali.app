import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2, Flag, MessageCircle, Send, CornerDownRight, SmilePlus, Sparkles, History, X, Pin } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar, TIER, TierKey, timeAgo, Linkify } from '../lib/ui'
import RoleBadge from './RoleBadge'
import AccountBadge from './AccountBadge'

const REPORT_CATS = ['harassment', 'hate', 'self_harm', 'inappropriate', 'unlabelled_ai', 'impersonation', 'underage', 'spam', 'csam', 'other']
const RX: Record<string, string> = { like: '👍', love: '❤️', haha: '😂', wow: '😮', sad: '😢', angry: '😡' }

export default function PostCard({ post, onDelete }: { post: any; onDelete?: (id: string) => void }) {
  const [rx, setRx] = useState<Record<string, number>>(post.reactions || {})
  const [mine, setMine] = useState<string | null>(post.my_reaction || null)
  const [total, setTotal] = useState<number>(post.reaction_total || 0)
  const [pick, setPick] = useState(false)
  const [showReport, setShowReport] = useState(false)
  const [reported, setReported] = useState(false)
  const [openC, setOpenC] = useState(false)
  const [comments, setComments] = useState<any[]>([])
  const [cCount, setCCount] = useState<number>(post.comment_count || 0)
  const [cText, setCText] = useState('')
  const [replyTo, setReplyTo] = useState<any>(null)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(post.text || '')
  const [text, setText] = useState(post.text)
  const [edited, setEdited] = useState(!!post.edited)
  const [pinned, setPinned] = useState(!!post.pinned)
  const togglePin = async () => {
    try { const r = await api.pinPost(post.id); setPinned(r.pinned) } catch (e: any) { alert(e.message) }
  }
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<any | null>(null)
  const openHistory = async () => {
    setShowHistory(true)
    try { setHistory(await api.postHistory(post.id)) } catch (e: any) { setHistory({ error: e.message }) }
  }
  const saveEdit = async () => {
    try { const r = await api.editPost(post.id, editText); setText(r.text); setEdited(true); setEditing(false) }
    catch (e: any) { alert(e.message) }
  }
  const [loadingC, setLoadingC] = useState(false)
  const tier = TIER[(post.tier as TierKey)] || TIER.public
  const TierIcon = tier.icon
  const a = post.author || { id: '', handle: 'unknown', display_name: 'Unknown' }

  const react = async (emoji: string) => {
    setPick(false)
    try { const r = await api.reactPost(post.id, emoji); setRx(r.reactions); setTotal(r.reaction_total); setMine(r.my_reaction) } catch {}
  }

  const toggleComments = async () => {
    const next = !openC; setOpenC(next)
    if (next && comments.length === 0) {
      setLoadingC(true)
      try { setComments(await api.listComments(post.id)) } catch {}
      setLoadingC(false)
    }
  }
  const submitComment = async () => {
    const t = cText.trim(); if (!t) return
    try {
      const c = await api.addComment(post.id, t, replyTo?.id)
      setComments(x => [...x, c]); setCCount(n => n + 1); setCText(''); setReplyTo(null)
    } catch {}
  }
  const removeComment = async (id: string) => {
    try { await api.deleteComment(id); const ids = new Set([id]); comments.forEach(c => { if (c.parent_id === id) ids.add(c.id) }); setComments(x => x.filter(c => !ids.has(c.id))); setCCount(n => Math.max(0, n - ids.size)) } catch {}
  }

  const roots = comments.filter(c => !c.parent_id)
  const repliesOf = (id: string) => comments.filter(c => c.parent_id === id)

  return (
    <article className="bg-panel border border-edge rounded-2xl p-4 animate-pop">
      <div className="flex items-start gap-3">
        <Link to={`/u/${a.handle}`}><Avatar id={a.id} name={a.display_name} url={a.avatar_url} /></Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link to={`/u/${a.handle}`} className="font-semibold hover:underline">{a.display_name}</Link>
            <RoleBadge role={a.role} size={17} />
            <AccountBadge type={a.account_type} role={a.role} size={16} />
            <span className="text-slate-500 text-sm">#{a.handle}</span>
            <span className="text-slate-600 text-sm">· {timeAgo(post.created_at)}</span>
            {pinned && <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-brand/40 bg-brand/10 text-brand"><Pin className="h-3 w-3" />Pinned</span>}
            <span className={`ml-auto inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${tier.bg} ${tier.text} ${tier.ring}`}>
              <TierIcon className="h-3 w-3" />{tier.label}
            </span>
          </div>
          {editing ? (
            <div className="mt-2">
              <textarea value={editText} onChange={e => setEditText(e.target.value)} rows={3}
                className="w-full bg-ink border border-edge rounded-xl px-3 py-2 outline-none focus:border-brand text-sm" />
              <div className="flex gap-2 justify-end mt-1">
                <button onClick={() => { setEditing(false); setEditText(text || '') }} className="text-xs px-3 py-1 rounded-lg border border-edge">Cancel</button>
                <button onClick={saveEdit} className="text-xs px-3 py-1 rounded-lg bg-brand font-medium">Save</button>
              </div>
            </div>
          ) : (
            text && <p className="mt-2 whitespace-pre-wrap break-words leading-relaxed"><Linkify text={text} />{edited && <button onClick={openHistory} className="text-xs text-slate-500 ml-1 hover:text-brand underline decoration-dotted">(edited)</button>}</p>
          )}
          {post.can_edit && !editing && (
            <div className="mt-1 flex items-center gap-3">
              <button onClick={() => { setEditText(text || ''); setEditing(true) }} className="text-xs text-slate-500 hover:text-brand">Edit</button>
              <button onClick={togglePin} className="text-xs text-slate-500 hover:text-brand inline-flex items-center gap-1"><Pin className="h-3 w-3" />{pinned ? 'Unpin' : 'Pin to profile'}</button>
            </div>
          )}
          {post.people_tags?.filter((pt: any) => pt.status === 'approved').length > 0 && (
            <div className="mt-1.5 text-xs text-slate-400">
              with {post.people_tags.filter((pt: any) => pt.status === 'approved').map((pt: any, i: number, arr: any[]) => (
                <span key={pt.handle}><Link to={`/u/${pt.handle}`} className="text-violet-300 hover:underline">@{pt.handle}</Link>{i < arr.length - 1 ? ', ' : ''}</span>
              ))}
            </div>
          )}
          {post.my_tag_status === 'pending' && !post.can_edit && (
            <div className="mt-1.5 text-xs text-amber-400">You're tagged here — approve or reject it from your Activity.</div>
          )}
          {post.media_url && (
            <div className="relative mt-3">
              {post.media_type === 'video'
                ? <video src={post.media_url} controls className="rounded-xl max-h-96 w-full" />
                : <img src={post.media_url} className="rounded-xl max-h-96 object-cover w-full" />}
              {post.ai_label && post.ai_label !== 'none' && (
                <span className="absolute top-2 left-2 text-[11px] font-semibold px-2 py-1 rounded-md bg-black/70 text-white backdrop-blur flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-brand" />
                  {post.ai_label === 'generated' ? 'AI Generated' : post.ai_label === 'assisted' ? 'AI Assisted' : 'AI Altered'}
                </span>
              )}
            </div>
          )}
          {post.tags?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {post.tags.map((t: string) => <span key={t} className="text-xs text-brand bg-brand/10 px-2 py-0.5 rounded-full">#{t}</span>)}
            </div>
          )}

          {/* reaction summary */}
          {total > 0 && (
            <div className="mt-2 flex items-center gap-1 text-xs text-slate-400">
              <span className="flex -space-x-1">{Object.keys(rx).filter(k => rx[k] > 0).slice(0, 3).map(k => <span key={k}>{RX[k]}</span>)}</span>
              <span>{total}</span>
            </div>
          )}

          <div className="mt-2 pt-2 border-t border-edge/60 flex items-center gap-2 text-slate-400">
            <div className="relative"
              onMouseEnter={() => setPick(true)} onMouseLeave={() => setPick(false)}>
              <button onClick={() => (mine ? react(mine) : react('like'))}
                className={`flex items-center gap-1.5 text-sm px-2 py-1 rounded-lg hover:bg-white/5 transition ${mine ? 'text-brand font-medium' : ''}`}>
                {mine ? <span className="text-base leading-none">{RX[mine]}</span> : <SmilePlus className="h-4 w-4" />}
                <span className="capitalize">{mine || 'React'}</span>
              </button>
              {pick && (
                <div className="absolute bottom-9 left-0 z-20 flex gap-1 bg-panel2 border border-edge rounded-full px-2 py-1.5 shadow-xl">
                  {Object.keys(RX).map(k => (
                    <button key={k} onClick={() => react(k)} title={k}
                      className="text-xl hover:scale-125 transition-transform">{RX[k]}</button>
                  ))}
                </div>
              )}
            </div>

            <button onClick={toggleComments} className="flex items-center gap-1.5 text-sm px-2 py-1 rounded-lg hover:bg-white/5">
              <MessageCircle className="h-4 w-4" /> {cCount > 0 ? cCount : ''} <span className="hidden sm:inline">Comment</span>
            </button>

            <div className="ml-auto flex items-center gap-3 relative">
              {post.is_mine && onDelete && (
                <button onClick={() => onDelete(post.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
              )}
              {!post.is_mine && (reported ? <span className="text-xs text-emerald-400">Reported</span> : (
                <button onClick={() => setShowReport(s => !s)} className="text-slate-500 hover:text-amber-400"><Flag className="h-4 w-4" /></button>
              ))}
              {showReport && (
                <div className="absolute bottom-8 right-0 z-20 w-44 bg-panel2 border border-edge rounded-xl p-1 shadow-xl">
                  <div className="text-xs text-slate-500 px-2 py-1">Report post</div>
                  {REPORT_CATS.map(c => (
                    <button key={c} onClick={async () => { try { await api.report('post', post.id, c); setReported(true) } catch {} setShowReport(false) }}
                      className="w-full text-left text-sm px-2 py-1.5 rounded-lg hover:bg-white/5 capitalize">{c.replace('_', ' ')}</button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* comments */}
          {openC && (
            <div className="mt-3 border-t border-edge/60 pt-3 space-y-3">
              {loadingC && <p className="text-xs text-slate-500">Loading…</p>}
              {roots.map(c => (
                <div key={c.id}>
                  <Comment c={c} onReply={() => setReplyTo(c)} onDelete={removeComment} />
                  {repliesOf(c.id).map(r => (
                    <div key={r.id} className="ml-8 mt-2 flex gap-1"><CornerDownRight className="h-3.5 w-3.5 text-slate-600 mt-2 shrink-0" /><div className="flex-1"><Comment c={r} onDelete={removeComment} /></div></div>
                  ))}
                </div>
              ))}
              {!loadingC && roots.length === 0 && <p className="text-xs text-slate-500">No comments yet. Be the first.</p>}

              {replyTo && (
                <div className="text-xs text-slate-500 flex items-center gap-2">Replying to <b>{replyTo.author?.display_name}</b>
                  <button onClick={() => setReplyTo(null)} className="text-rose-400">cancel</button></div>
              )}
              <div className="flex gap-2">
                <input value={cText} onChange={e => setCText(e.target.value)} onKeyDown={e => e.key === 'Enter' && submitComment()}
                  placeholder={replyTo ? 'Write a reply…' : 'Write a comment…'}
                  className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
                <button onClick={submitComment} className="h-9 w-9 grid place-items-center rounded-xl bg-brand shrink-0"><Send className="h-4 w-4" /></button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showHistory && (
        <div className="fixed inset-0 z-[60] grid place-items-center bg-black/70 backdrop-blur p-4" onClick={() => setShowHistory(false)}>
          <div className="bg-panel border border-edge rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-edge flex items-center gap-2">
              <History className="h-5 w-5 text-brand" />
              <h3 className="font-bold flex-1">Edit history</h3>
              <button onClick={() => setShowHistory(false)} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-5 w-5" /></button>
            </div>
            <div className="p-4 overflow-y-auto space-y-3">
              {!history ? <p className="text-slate-500 text-sm">Loading…</p>
                : history.error ? <p className="text-rose-400 text-sm">{history.error}</p>
                : (
                  <>
                    <div className="rounded-xl border border-brand/40 bg-brand/10 p-3">
                      <div className="text-[10px] uppercase tracking-wide text-brand mb-1">Current{history.current?.at ? ` · ${timeAgo(history.current.at)}` : ''}</div>
                      <p className="text-sm whitespace-pre-wrap break-words">{history.current?.text}</p>
                    </div>
                    {(history.history || []).length === 0
                      ? <p className="text-xs text-slate-500">No previous versions recorded.</p>
                      : history.history.map((v: any, i: number) => (
                        <div key={i} className="rounded-xl border border-edge bg-ink p-3">
                          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Previous{v.at ? ` · ${timeAgo(v.at)}` : ''}</div>
                          <p className="text-sm whitespace-pre-wrap break-words text-slate-300">{v.text || <em className="text-slate-600">empty</em>}</p>
                        </div>
                      ))}
                  </>
                )}
            </div>
          </div>
        </div>
      )}
    </article>
  )
}

function Comment({ c, onReply, onDelete }: { c: any; onReply?: () => void; onDelete: (id: string) => void }) {
  const a = c.author || { handle: 'unknown', display_name: 'Unknown' }
  return (
    <div className="flex gap-2">
      <Link to={`/u/${a.handle}`}><Avatar id={a.id} name={a.display_name} url={a.avatar_url} size={30} /></Link>
      <div className="flex-1 min-w-0">
        <div className="bg-ink border border-edge rounded-2xl px-3 py-2">
          <Link to={`/u/${a.handle}`} className="text-sm font-medium hover:underline">{a.display_name}</Link>
          <RoleBadge role={(a as any).role} size={14} className="ml-1" />
          <AccountBadge type={(a as any).account_type} role={(a as any).role} size={13} className="ml-0.5" />
          {c.restricted && <span className="ml-2 text-[10px] uppercase tracking-wide text-amber-400 border border-amber-500/40 rounded-full px-1.5 py-0.5">Restricted · only visible to them</span>}
          <p className="text-sm whitespace-pre-wrap break-words"><Linkify text={c.text} /></p>
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 px-2">
          <span>{timeAgo(c.created_at)}</span>
          {onReply && <button onClick={onReply} className="hover:text-brand">Reply</button>}
          {c.is_mine && <button onClick={() => onDelete(c.id)} className="hover:text-rose-400">Delete</button>}
        </div>
      </div>
    </div>
  )
}
