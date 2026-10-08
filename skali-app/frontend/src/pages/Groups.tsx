import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getToken, wsGroupUrl } from '../lib/api'
import { Avatar, timeAgo } from '../lib/ui'
import { useAuth } from '../lib/auth'
import { Users, Plus, Send, Loader2, ArrowLeft, Lock, Settings2, X, UserPlus, LogOut, Trash2, Check, Mic, Square, Image as ImageIcon, CheckCheck } from 'lucide-react'

const MAX = 15

export default function Groups() {
  const { user } = useAuth()
  const [groups, setGroups] = useState<any[]>([])
  const [sel, setSel] = useState<any>(null)      // group detail
  const [msgs, setMsgs] = useState<any[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [showManage, setShowManage] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)
  const seen = useRef<Set<string>>(new Set())

  const loadGroups = () => api.groups().then(setGroups).catch(() => {})
  useEffect(() => { loadGroups() }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  const openGroup = async (id: string) => {
    setLoading(true); setShowManage(false); seen.current = new Set()
    wsRef.current?.close()
    try {
      const g = await api.group(id)
      setSel(g); setMsgs(g.messages || []); g.messages?.forEach((m: any) => seen.current.add(m.id))
      loadGroups()
    } catch (e: any) { alert(e.message) }
    setLoading(false)
    const t = getToken(); if (!t) return
    const connect = () => {
      const ws = new WebSocket(wsGroupUrl(id, t)); wsRef.current = ws
      ws.onmessage = ev => {
        try {
          const d = JSON.parse(ev.data)
          if (d.type === 'group' && !seen.current.has(d.message.id)) {
            seen.current.add(d.message.id)
            setMsgs(p => [...p, { ...d.message, mine: d.message.sender_id === user?.id }])
          }
        } catch {}
      }
    }
    connect()
  }

  useEffect(() => () => { wsRef.current?.close() }, [])

  const send = async (e: React.FormEvent) => {
    e.preventDefault(); const body = text.trim(); if (!body || !sel) return
    setText('')
    try { const m = await api.groupSend(sel.id, { text: body }); if (!seen.current.has(m.id)) { seen.current.add(m.id); setMsgs(p => [...p, m]) } }
    catch (err: any) { alert(err.message); setText(body) }
  }

  const pushMsg = (m: any) => { if (!seen.current.has(m.id)) { seen.current.add(m.id); setMsgs(p => [...p, m]) } }

  // Photo upload
  const [busy, setBusy] = useState(false)
  const onPhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file || !sel) return
    setBusy(true)
    try { const { signed_url } = await api.upload(file); pushMsg(await api.groupSend(sel.id, { media_url: signed_url, media_type: 'image' })) }
    catch (err: any) { alert(err.message || 'Could not send photo') }
    setBusy(false); e.target.value = ''
  }

  // Voice recording
  const recRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recStart = useRef<number>(0)
  const [recording, setRecording] = useState(false)
  const startRec = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream); recRef.current = mr; chunksRef.current = []; recStart.current = Date.now()
      mr.ondataavailable = ev => chunksRef.current.push(ev.data)
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const dur = Math.round((Date.now() - recStart.current) / 1000)
        if (dur < 1 || !sel) return
        setBusy(true)
        try {
          const { signed_url } = await api.upload(new File([blob], `voice-${Date.now()}.webm`, { type: 'audio/webm' }))
          pushMsg(await api.groupSend(sel.id, { media_url: signed_url, media_type: 'audio', duration: dur }))
        } catch (err: any) { alert(err.message || 'Could not send voice message') }
        setBusy(false)
      }
      mr.start(); setRecording(true)
    } catch { alert('Microphone permission needed to record a voice message.') }
  }
  const stopRec = () => { recRef.current?.stop(); setRecording(false) }

  // Read receipts for the last message I sent
  const lastMine = [...msgs].reverse().find(m => m.mine && !m.deleted)
  const seenByNames = (() => {
    if (!lastMine || !sel?.reads || !sel?.members) return []
    return sel.members
      .filter((mem: any) => mem.id !== user?.id && (sel.reads[mem.id] || '') >= lastMine.created_at)
      .map((mem: any) => mem.display_name)
  })()

  return (
    <div className="flex h-screen">
      {/* Group list */}
      <div className={`${sel ? 'hidden lg:flex' : 'flex'} flex-col w-full lg:w-80 shrink-0 border-r border-edge`}>
        <div className="px-4 py-3 border-b border-edge flex items-center justify-between">
          <div className="font-extrabold text-xl flex items-center gap-2"><Users className="h-5 w-5 text-brand" /> Groups</div>
          <button onClick={() => setShowCreate(true)} className="h-9 w-9 grid place-items-center rounded-lg bg-brand hover:brightness-110"><Plus className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {groups.length === 0 && <p className="text-slate-500 text-sm p-4">No groups yet. Tap + to start a private Inner-Circle group (up to {MAX} people).</p>}
          {groups.map(g => (
            <button key={g.id} onClick={() => openGroup(g.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left ${sel?.id === g.id ? 'bg-white/5' : ''}`}>
              <div className="h-10 w-10 rounded-full bg-gradient-to-br from-brand to-violet-600 grid place-items-center shrink-0 relative">
                <Users className="h-5 w-5 text-white" />
                {g.unread > 0 && <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] grid place-items-center font-bold">{g.unread}</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{g.name}</div>
                <div className="text-sm text-slate-500 truncate">{g.member_count} members · {g.last || 'No messages yet'}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Group thread */}
      <div className={`${sel ? 'flex' : 'hidden lg:flex'} flex-col flex-1 min-w-0`}>
        {!sel ? <div className="flex-1 grid place-items-center text-slate-500">Select a group</div>
          : loading ? <div className="flex-1 grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
          : (
            <>
              <div className="min-h-16 shrink-0 border-b border-edge px-4 pt-[env(safe-area-inset-top)] flex items-center gap-3">
                <button onClick={() => setSel(null)} className="lg:hidden"><ArrowLeft className="h-5 w-5" /></button>
                <div className="h-[38px] w-[38px] rounded-full bg-gradient-to-br from-brand to-violet-600 grid place-items-center shrink-0"><Users className="h-5 w-5 text-white" /></div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{sel.name}</div>
                  <div className="text-xs text-slate-500 truncate">{sel.member_count} members</div>
                </div>
                <div className="flex items-center gap-1 text-xs text-emerald-400 mr-2"><Lock className="h-3 w-3" />Encrypted</div>
                <button onClick={() => setShowManage(true)} className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10"><Settings2 className="h-4 w-4" /></button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {msgs.length === 0 && <p className="text-center text-slate-500 py-10">No messages yet. Say hello to your circle.</p>}
                {msgs.map(m => (
                  <div key={m.id} className={`flex gap-2 ${m.mine ? 'justify-end' : ''}`}>
                    {!m.mine && <Link to={`/u/${m.sender?.handle}`} className="shrink-0 self-end"><Avatar id={m.sender?.id} name={m.sender?.display_name} url={m.sender?.avatar_url} size={30} /></Link>}
                    <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${m.deleted ? 'bg-white/5 border border-edge text-slate-500 italic' : m.mine ? 'bg-gradient-to-br from-brand to-violet-600 text-white rounded-br-sm' : 'bg-white/5 border border-edge rounded-bl-sm'}`}>
                      {!m.mine && <div className="text-[11px] text-brand font-medium mb-0.5">{m.sender?.display_name}</div>}
                      {m.media_type === 'audio' && m.media_url ? <audio src={m.media_url} controls className="max-w-[220px] h-9" />
                        : m.media_url ? <img src={m.media_url} className="rounded-lg max-h-64" /> : m.text}
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>

              {seenByNames.length > 0 && (
                <div className="px-4 pb-1 -mt-1 text-right text-[11px] text-slate-500 flex items-center justify-end gap-1">
                  <CheckCheck className="h-3.5 w-3.5 text-brand" />
                  Seen by {seenByNames.length <= 2 ? seenByNames.join(' & ') : `${seenByNames.slice(0, 2).join(', ')} +${seenByNames.length - 2}`}
                </div>
              )}

              <form onSubmit={send} className="p-3 flex gap-2 items-center border-t border-edge">
                <label className={`h-11 w-11 grid place-items-center rounded-xl shrink-0 cursor-pointer ${busy ? 'opacity-50' : 'bg-white/10 hover:bg-white/20'}`}>
                  <ImageIcon className="h-5 w-5" />
                  <input type="file" accept="image/*" className="hidden" onChange={onPhoto} disabled={busy} />
                </label>
                <input value={text} onChange={e => setText(e.target.value)} placeholder={recording ? 'Recording…' : 'Message the group (encrypted)…'} disabled={recording}
                  className="flex-1 bg-ink border border-edge rounded-xl px-4 py-3 outline-none focus:border-brand disabled:opacity-60" />
                <button type="button" onClick={recording ? stopRec : startRec} disabled={busy}
                  className={`h-11 w-11 grid place-items-center rounded-xl shrink-0 ${recording ? 'bg-rose-600 animate-pulse' : 'bg-white/10 hover:bg-white/20'}`}>
                  {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : recording ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
                </button>
                <button className="h-11 w-11 grid place-items-center rounded-xl bg-gradient-to-r from-brand to-violet-600 shrink-0"><Send className="h-5 w-5" /></button>
              </form>
            </>
          )}
      </div>

      {showCreate && <CreateGroup onClose={() => setShowCreate(false)} onCreated={(g: any) => { setShowCreate(false); loadGroups(); openGroup(g.id) }} />}
      {showManage && sel && <ManageGroup group={sel} me={user} onClose={() => setShowManage(false)} onChanged={() => { openGroup(sel.id) }} onLeft={() => { setSel(null); setShowManage(false); loadGroups() }} />}
    </div>
  )
}

function CreateGroup({ onClose, onCreated }: { onClose: () => void; onCreated: (g: any) => void }) {
  const [name, setName] = useState('')
  const [inner, setInner] = useState<any[]>([])
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.getInner().then(setInner).catch(() => {}) }, [])
  const toggle = (h: string) => setPicked(s => { const n = new Set(s); n.has(h) ? n.delete(h) : n.add(h); return n })
  const create = async () => {
    if (!name.trim()) return
    setBusy(true)
    try { const g = await api.createGroup(name.trim(), [...picked]); onCreated(g) }
    catch (e: any) { alert(e.message); setBusy(false) }
  }
  return (
    <Modal onClose={onClose} title="New group">
      <input value={name} onChange={e => setName(e.target.value)} maxLength={60} placeholder="Group name"
        className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand mb-3" />
      <div className="text-sm text-slate-400 mb-2">Add from your Inner Circle <span className="text-slate-600">({picked.size + 1}/{MAX})</span></div>
      <div className="max-h-60 overflow-y-auto -mx-1 px-1">
        {inner.length === 0 && <p className="text-sm text-slate-500 py-4">Your Inner Circle is empty. Invite people from their profile first.</p>}
        {inner.map(m => (
          <button key={m.id} onClick={() => toggle(m.handle)} className="w-full flex items-center gap-3 py-2 text-left">
            <Avatar id={m.id} name={m.display_name} url={m.avatar_url} size={36} />
            <div className="flex-1 min-w-0"><div className="font-medium truncate">{m.display_name}</div><div className="text-xs text-slate-500 truncate">#{m.handle}</div></div>
            <span className={`h-6 w-6 rounded-full grid place-items-center border ${picked.has(m.handle) ? 'bg-brand border-brand' : 'border-edge'}`}>{picked.has(m.handle) && <Check className="h-4 w-4 text-white" />}</span>
          </button>
        ))}
      </div>
      <button onClick={create} disabled={busy || !name.trim()} className="mt-4 w-full py-2.5 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center justify-center gap-2">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create group
      </button>
    </Modal>
  )
}

function ManageGroup({ group, me, onClose, onChanged, onLeft }: any) {
  const isOwner = group.owner_id === me?.id
  const [name, setName] = useState(group.name)
  const [inner, setInner] = useState<any[]>([])
  const [adding, setAdding] = useState(false)
  useEffect(() => { if (isOwner) api.getInner().then(setInner).catch(() => {}) }, [isOwner])
  const memberIds = new Set(group.members.map((m: any) => m.id))
  const addable = inner.filter(m => !memberIds.has(m.id))

  const rename = async () => { if (!name.trim() || name === group.name) return; try { await api.renameGroup(group.id, name.trim()); onChanged() } catch (e: any) { alert(e.message) } }
  const addMember = async (h: string) => { setAdding(true); try { await api.addGroupMembers(group.id, [h]); onChanged() } catch (e: any) { alert(e.message) } setAdding(false) }
  const removeMember = async (h: string) => { try { await api.removeGroupMember(group.id, h); onChanged() } catch (e: any) { alert(e.message) } }
  const leave = async () => { try { await api.removeGroupMember(group.id, me.handle); onLeft() } catch (e: any) { alert(e.message) } }
  const del = async () => { if (!confirm('Delete this group for everyone?')) return; try { await api.deleteGroup(group.id); onLeft() } catch (e: any) { alert(e.message) } }

  return (
    <Modal onClose={onClose} title="Group settings">
      {isOwner && (
        <div className="flex gap-2 mb-4">
          <input value={name} onChange={e => setName(e.target.value)} maxLength={60} className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
          <button onClick={rename} disabled={!name.trim() || name === group.name} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40">Save</button>
        </div>
      )}
      <div className="text-sm text-slate-400 mb-1">Members ({group.member_count}/{MAX})</div>
      <div className="max-h-48 overflow-y-auto mb-3">
        {group.members.map((m: any) => (
          <div key={m.id} className="flex items-center gap-3 py-2">
            <Avatar id={m.id} name={m.display_name} url={m.avatar_url} size={34} />
            <div className="flex-1 min-w-0"><div className="font-medium truncate">{m.display_name}{m.id === group.owner_id && <span className="text-xs text-brand ml-1">· owner</span>}</div><div className="text-xs text-slate-500 truncate">#{m.handle}</div></div>
            {isOwner && m.id !== group.owner_id && <button onClick={() => removeMember(m.handle)} className="text-slate-500 hover:text-rose-400"><X className="h-4 w-4" /></button>}
          </div>
        ))}
      </div>

      {isOwner && addable.length > 0 && (
        <>
          <div className="text-sm text-slate-400 mb-1 flex items-center gap-1"><UserPlus className="h-4 w-4" /> Add from Inner Circle</div>
          <div className="max-h-40 overflow-y-auto mb-3">
            {addable.map(m => (
              <div key={m.id} className="flex items-center gap-3 py-2">
                <Avatar id={m.id} name={m.display_name} url={m.avatar_url} size={32} />
                <div className="flex-1 min-w-0"><div className="text-sm font-medium truncate">{m.display_name}</div></div>
                <button onClick={() => addMember(m.handle)} disabled={adding} className="px-3 py-1.5 rounded-lg border border-edge text-sm hover:bg-white/5">Add</button>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="flex gap-2 pt-2 border-t border-edge">
        <button onClick={leave} className="flex-1 py-2.5 rounded-xl border border-edge hover:bg-white/5 flex items-center justify-center gap-2 text-sm"><LogOut className="h-4 w-4" /> Leave group</button>
        {isOwner && <button onClick={del} className="flex-1 py-2.5 rounded-xl border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 flex items-center justify-center gap-2 text-sm"><Trash2 className="h-4 w-4" /> Delete</button>}
      </div>
    </Modal>
  )
}

function Modal({ children, onClose, title }: { children: React.ReactNode; onClose: () => void; title: string }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onClick={onClose}>
      <div className="bg-panel border border-edge rounded-2xl p-5 max-w-md w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg">{title}</h3>
          <button onClick={onClose} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
