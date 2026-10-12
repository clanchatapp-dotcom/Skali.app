import { useEffect, useRef, useState } from 'react'
import { Room, RoomEvent, RemoteParticipant } from 'livekit-client'
import { api } from '../../lib/api'
import { Avatar } from '../../lib/ui'
import { Send, Trash2, Clock, ShieldCheck, Radio } from 'lucide-react'

type Msg = {
  id: string; uid: string; name: string; avatar?: string; badge?: 'host' | 'mod' | null
  text: string; deleted?: boolean; system?: boolean
}

const enc = new TextEncoder()
const dec = new TextDecoder()
const meta = (raw?: string) => { try { return JSON.parse(raw || '{}') } catch { return {} } }
const newId = () => (crypto as any).randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`

function Line({ m, canMod, onDelete, onTimeout }: { m: Msg; canMod: boolean; onDelete: () => void; onTimeout: () => void }) {
  if (m.system) return <div className="text-[11px] text-slate-500 italic px-1 py-0.5" data-testid="chat-system-line">{m.text}</div>
  return (
    <div className="group flex items-start gap-2 px-1 py-1 rounded-lg hover:bg-white/[0.03]" data-testid={`chat-msg-${m.id}`}>
      <Avatar id={m.uid} name={m.name} url={m.avatar} size={22} />
      <div className="flex-1 min-w-0 text-sm leading-snug break-words">
        {m.badge === 'host' && <Radio className="inline h-3 w-3 text-rose-400 mr-1 -mt-0.5" />}
        {m.badge === 'mod' && <ShieldCheck className="inline h-3 w-3 text-emerald-400 mr-1 -mt-0.5" />}
        <span className={`font-semibold mr-1.5 ${m.badge === 'host' ? 'text-rose-300' : m.badge === 'mod' ? 'text-emerald-300' : 'text-brand'}`}>{m.name}</span>
        {m.deleted ? <span className="text-slate-600 italic">message deleted by a moderator</span> : <span className="text-slate-200">{m.text}</span>}
      </div>
      {canMod && !m.deleted && (
        <div className="flex opacity-100 md:opacity-0 md:group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <button onClick={onDelete} title="Delete message" data-testid={`chat-delete-${m.id}`} className="h-6 w-6 grid place-items-center rounded text-slate-500 hover:text-rose-300"><Trash2 className="h-3.5 w-3.5" /></button>
          <button onClick={onTimeout} title="Time out 5 min" data-testid={`chat-timeout-${m.id}`} className="h-6 w-6 grid place-items-center rounded text-slate-500 hover:text-amber-300"><Clock className="h-3.5 w-3.5" /></button>
        </div>
      )}
    </div>
  )
}

export default function StreamChat({ room, liveId, meId, canModerate, timedOutUntil, setTimedOutUntil, onEnded }: {
  room: Room | null; liveId: string; meId: string; canModerate: boolean
  timedOutUntil: string | null; setTimedOutUntil: (v: string | null) => void; onEnded: () => void
}) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const lastSent = useRef(0)
  const endRef = useRef<HTMLDivElement>(null)
  const add = (m: Msg) => setMsgs(v => [...v, m].slice(-200))

  useEffect(() => {
    if (!room) return
    const onData = (payload: Uint8Array, p?: RemoteParticipant) => {
      let m: any
      try { m = JSON.parse(dec.decode(payload)) } catch { return }
      if (!m || m.live_id !== liveId) return
      if (p) {
        if (m.type !== 'chat' || typeof m.text !== 'string') return
        const md = meta(p.metadata)
        add({ id: String(m.id).slice(0, 64), uid: p.identity, name: md.display_name || p.name || 'viewer', avatar: md.avatar_url,
              badge: md.is_host ? 'host' : md.is_mod ? 'mod' : null, text: m.text.slice(0, 300) })
        return
      }
      // Packets without a participant come from the server (moderation / lifecycle).
      if (m.type === 'mod_delete') setMsgs(v => v.map(x => x.id === m.msg_id ? { ...x, deleted: true } : x))
      if (m.type === 'mod_timeout') {
        if (m.user_id === meId) setTimedOutUntil(m.until)
        setMsgs(v => [...v.map(x => x.uid === m.user_id ? { ...x, deleted: true } : x),
          { id: newId(), uid: '', name: '', text: 'A chatter was timed out by a moderator.', system: true }])
      }
      if (m.type === 'stream_ended') { setMsgs([]); onEnded() }
    }
    room.on(RoomEvent.DataReceived, onData)
    return () => { room.off(RoomEvent.DataReceived, onData) }
  }, [room, liveId, meId])

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs.length])

  const timedOut = !!timedOutUntil && new Date(timedOutUntil).getTime() > Date.now()

  const send = async () => {
    const t = text.trim().slice(0, 300)
    if (!t || !room || timedOut || Date.now() - lastSent.current < 800) return
    const id = newId()
    try {
      await room.localParticipant.publishData(enc.encode(JSON.stringify({ type: 'chat', id, live_id: liveId, text: t })), { reliable: true, topic: 'chat' })
      lastSent.current = Date.now()
      const md = meta(room.localParticipant.metadata)
      add({ id, uid: meId, name: md.display_name || 'You', avatar: md.avatar_url, badge: md.is_host ? 'host' : md.is_mod ? 'mod' : null, text: t })
      setText('')
    } catch {
      alert("Couldn't send your message.")
    }
  }

  const mod = (fn: () => Promise<any>) => fn().catch((e: any) => alert(e.message))

  return (
    <div className="flex flex-col h-full min-h-0" data-testid="stream-chat">
      <div className="px-4 py-3 border-b border-edge text-xs font-bold uppercase tracking-wider text-slate-400">Stream chat</div>
      <div className="flex-1 min-h-0 overflow-y-auto px-2 py-2 space-y-0.5" data-testid="chat-messages">
        {msgs.length === 0 && <p className="text-xs text-slate-500 text-center py-8">Welcome to the chat. Messages disappear when the stream ends.</p>}
        {msgs.map(m => (
          <Line key={m.id} m={m} canMod={canModerate && m.uid !== meId && m.badge !== 'host'}
            onDelete={() => mod(() => api.streamDeleteMsg(liveId, m.id))}
            onTimeout={() => mod(() => api.streamTimeout(liveId, m.uid, 5))} />
        ))}
        <div ref={endRef} />
      </div>
      <div className="p-3 border-t border-edge">
        {timedOut ? (
          <p className="text-xs text-amber-300 text-center py-2" data-testid="chat-timed-out">
            You're timed out until {new Date(timedOutUntil!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.
          </p>
        ) : (
          <div className="flex gap-2">
            <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} maxLength={300}
              disabled={!room} placeholder={room ? 'Send a message' : 'Connecting…'} data-testid="chat-input"
              className="flex-1 min-w-0 bg-ink border border-edge rounded-xl px-3 py-2.5 text-sm outline-none focus:border-brand disabled:opacity-50" />
            <button onClick={send} disabled={!room || !text.trim()} data-testid="chat-send-btn"
              className="h-10 w-10 grid place-items-center rounded-xl bg-brand text-white disabled:opacity-40"><Send className="h-4 w-4" /></button>
          </div>
        )}
      </div>
    </div>
  )
}
