import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Heart, MessageCircle, Loader2, Volume2, VolumeX, Film } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'

function Reel({ post, muted, onToggleMute }: { post: any; muted: boolean; onToggleMute: () => void }) {
  const ref = useRef<HTMLVideoElement>(null)
  const [liked, setLiked] = useState(!!post.my_reaction)
  const [total, setTotal] = useState(post.reaction_total || 0)
  const a = post.author || { handle: 'unknown', display_name: 'Unknown' }

  useEffect(() => {
    const v = ref.current; if (!v) return
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { v.play().catch(() => {}) } else { v.pause(); v.currentTime = 0 }
    }, { threshold: 0.6 })
    io.observe(v); return () => io.disconnect()
  }, [])

  const like = async () => {
    try { const r = await api.reactPost(post.id, 'love'); setLiked(!!r.my_reaction); setTotal(r.reaction_total) } catch {}
  }

  return (
    <div className="relative h-full w-full snap-start shrink-0 grid place-items-center bg-black">
      <video ref={ref} src={post.media_url} loop muted={muted} playsInline onClick={() => ref.current?.paused ? ref.current?.play() : ref.current?.pause()}
        className="h-full w-full object-contain" />
      <button onClick={onToggleMute} className="absolute top-4 right-4 h-10 w-10 grid place-items-center rounded-full bg-black/40 text-white">
        {muted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
      </button>
      {/* right actions */}
      <div className="absolute right-3 bottom-24 flex flex-col items-center gap-5 text-white">
        <button onClick={like} className="flex flex-col items-center">
          <Heart className={`h-8 w-8 ${liked ? 'fill-rose-500 text-rose-500' : ''}`} />
          <span className="text-xs mt-1">{total}</span>
        </button>
        <Link to="/messages" className="flex flex-col items-center">
          <MessageCircle className="h-8 w-8" /><span className="text-xs mt-1">{post.comment_count || 0}</span>
        </Link>
      </div>
      {/* bottom info */}
      <div className="absolute left-4 right-16 bottom-8 text-white">
        <Link to={`/u/${a.handle}`} className="flex items-center gap-2 mb-2">
          <Avatar id={a.id} name={a.display_name} url={a.avatar_url} size={40} />
          <span className="font-semibold drop-shadow">{a.display_name}</span>
          <span className="opacity-70 text-sm">#{a.handle}</span>
        </Link>
        {post.text && <p className="text-sm drop-shadow line-clamp-3">{post.text}</p>}
      </div>
    </div>
  )
}

export default function Reels() {
  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [muted, setMuted] = useState(true)
  useEffect(() => { api.reels().then(setPosts).catch(() => {}).finally(() => setLoading(false)) }, [])

  if (loading) return <div className="h-full grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
  if (posts.length === 0) return (
    <div className="h-full grid place-items-center text-center text-slate-500 px-8">
      <div><Film className="h-10 w-10 mx-auto mb-3 text-brand" /><p>No reels yet. Post a video to start the scroll.</p></div>
    </div>
  )
  return (
    <div className="h-[calc(100vh-4rem)] lg:h-screen overflow-y-scroll snap-y snap-mandatory">
      {posts.map(p => <div key={p.id} className="h-full w-full"><Reel post={p} muted={muted} onToggleMute={() => setMuted(m => !m)} /></div>)}
    </div>
  )
}
