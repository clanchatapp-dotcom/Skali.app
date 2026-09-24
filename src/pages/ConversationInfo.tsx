import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Avatar } from '../lib/ui'
import CallModal from '../components/CallModal'
import RoleBadge from '../components/RoleBadge'
import AccountBadge from '../components/AccountBadge'
import {
  ArrowLeft,
  Search,
  Phone,
  Video,
  ExternalLink,
  X,
  Loader2,
  ImageOff
} from 'lucide-react'

export default function ConversationInfo() {
  const { handle } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()

  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [lightbox, setLightbox] = useState<any>(null)
  const [call, setCall] = useState<{ media: 'audio' | 'video' } | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .dmHistory(handle as string)
      .then((d: any) => {
        if (!cancelled) setData(d)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [handle])

  const peer = data?.peer
  const messages: any[] = data?.messages || []

  const callRoom =
    handle && user
      ? `dm-${[user.handle, handle].sort().join('-')}`
      : ''

  const results = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!term) return []
    return messages
      .filter(
        m =>
          !m.deleted &&
          typeof m.text === 'string' &&
          m.text.toLowerCase().includes(term)
      )
      .slice()
      .reverse()
  }, [q, messages])

  // Visual media only (photos / videos / GIFs / stickers). Voice notes and
  // disappearing (view-once, url stripped) messages are naturally excluded.
  const media = useMemo(
    () =>
      messages
        .filter(
          m =>
            !m.deleted &&
            m.media_url &&
            m.media_type !== 'audio'
        )
        .slice()
        .reverse(),
    [messages]
  )

  const startCall = async (media: 'audio' | 'video') => {
    if (!peer || !callRoom) return
    setCall({ media })
    try {
      await api.callRing(peer.handle, callRoom, media)
    } catch (e: any) {
      setCall(null)
      alert(e?.message || 'Could not start the call')
    }
  }

  const jumpTo = (id: string) =>
    nav(`/messages/${handle}?jump=${id}`)

  return (
    <div className="flex flex-col min-h-full">
      {call && (
        <CallModal
          room={callRoom}
          peer={peer?.display_name || peer?.handle}
          media={call.media}
          onClose={() => setCall(null)}
        />
      )}

      {/* Header */}
      <div className="sticky top-0 z-30 bg-ink/90 backdrop-blur border-b border-edge px-3 pb-2 pt-[calc(0.4rem+env(safe-area-inset-top))] flex items-center gap-3">
        <button
          onClick={() => nav(`/messages/${handle}`)}
          className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10"
          title="Back to chat"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="font-semibold">Conversation info</div>
      </div>

      {loading ? (
        <div className="py-20 grid place-items-center text-slate-500">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : !peer ? (
        <div className="text-center text-slate-500 py-16">
          Couldn&apos;t load this conversation.
        </div>
      ) : (
        <div className="p-4 space-y-6">
          {/* Peer summary */}
          <div className="flex flex-col items-center text-center gap-2">
            <Avatar
              id={peer.id}
              name={peer.display_name}
              url={peer.avatar_url}
              size={80}
            />
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-bold">
                {peer.nickname || peer.display_name}
              </span>
              <RoleBadge role={peer.role} size={16} />
              <AccountBadge type={peer.account_type} role={peer.role} size={15} />
            </div>
            <div className="text-sm text-slate-500">#{peer.handle}</div>

            <div className="flex items-center gap-2 mt-2">
              <Link
                to={`/u/${peer.handle}`}
                className="flex items-center gap-1.5 bg-panel border border-edge rounded-full px-4 py-2 text-sm font-medium hover:border-brand/50"
              >
                <ExternalLink className="h-4 w-4" />
                View full profile
              </Link>

              {data?.can_call && (
                <>
                  <button
                    onClick={() => startCall('audio')}
                    title="Voice call"
                    className="h-10 w-10 grid place-items-center rounded-full bg-panel border border-edge hover:border-brand/50"
                  >
                    <Phone className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => startCall('video')}
                    title="Video call"
                    className="h-10 w-10 grid place-items-center rounded-full bg-panel border border-edge hover:border-brand/50"
                  >
                    <Video className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Search this conversation */}
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-300">
              Search conversation
            </div>
            <div className="flex items-center gap-2 bg-panel border border-edge rounded-xl px-3 py-2.5">
              <Search className="h-4 w-4 text-slate-500 shrink-0" />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search messages…"
                className="flex-1 bg-transparent outline-none text-sm text-slate-200 placeholder:text-slate-500"
              />
              {q && (
                <button
                  onClick={() => setQ('')}
                  className="text-slate-500 hover:text-slate-300"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {q.trim() && (
              <div className="space-y-1">
                {results.length === 0 ? (
                  <p className="text-sm text-slate-500 py-2">
                    No messages match &ldquo;{q.trim()}&rdquo;.
                  </p>
                ) : (
                  results.map(m => (
                    <button
                      key={m.id}
                      onClick={() => jumpTo(m.id)}
                      className="w-full text-left bg-panel border border-edge rounded-xl px-3 py-2.5 hover:border-brand/50"
                    >
                      <div className="text-sm text-slate-200 line-clamp-2">
                        {m.text}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        {m.mine ? 'You' : peer.display_name} ·{' '}
                        {new Date(m.created_at).toLocaleString()}
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Shared media */}
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-300">
              Shared media
              {media.length > 0 && (
                <span className="text-slate-500 font-normal"> · {media.length}</span>
              )}
            </div>

            {media.length === 0 ? (
              <div className="flex flex-col items-center gap-2 text-slate-500 py-10">
                <ImageOff className="h-8 w-8" />
                <p className="text-sm">No photos or videos shared yet.</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-1.5">
                {media.map(m => (
                  <button
                    key={m.id}
                    onClick={() => setLightbox(m)}
                    className="relative aspect-square rounded-lg overflow-hidden bg-panel border border-edge"
                  >
                    {m.media_type === 'video' ? (
                      <>
                        <video
                          src={m.media_url}
                          className="h-full w-full object-cover"
                          muted
                        />
                        <span className="absolute bottom-1 right-1 bg-black/60 rounded-md p-1">
                          <Video className="h-3 w-3 text-white" />
                        </span>
                      </>
                    ) : (
                      <img
                        src={m.media_url}
                        alt="shared media"
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-[70] bg-black/90 backdrop-blur grid place-items-center p-4"
          onClick={() => setLightbox(null)}
        >
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-[calc(1rem+env(safe-area-inset-top))] right-4 h-10 w-10 grid place-items-center rounded-full bg-white/10 hover:bg-white/20"
          >
            <X className="h-5 w-5 text-white" />
          </button>
          {lightbox.media_type === 'video' ? (
            <video
              src={lightbox.media_url}
              controls
              autoPlay
              className="max-h-[85vh] max-w-full rounded-xl"
              onClick={e => e.stopPropagation()}
            />
          ) : (
            <img
              src={lightbox.media_url}
              alt="shared media"
              className="max-h-[85vh] max-w-full rounded-xl object-contain"
              onClick={e => e.stopPropagation()}
            />
          )}
          <button
            onClick={e => {
              e.stopPropagation()
              const id = lightbox.id
              setLightbox(null)
              jumpTo(id)
            }}
            className="absolute bottom-[calc(1.5rem+env(safe-area-inset-bottom))] bg-white/10 hover:bg-white/20 text-white text-sm rounded-full px-4 py-2"
          >
            Jump to message
          </button>
        </div>
      )}
    </div>
  )
}
