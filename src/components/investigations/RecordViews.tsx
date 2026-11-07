import { timeAgo } from '../../lib/ui'
import { Users, Lock, Image as ImageIcon } from 'lucide-react'

export function FeedView({ data }: { data: any }) {
  return (
    <div className="space-y-3" data-testid="inv-feed-view">
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(data.tiers || {}).map(([t, n]: any) => (
          <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-white/5 border border-edge text-slate-300">{t} · {n}</span>
        ))}
      </div>
      {data.posts.length === 0 && <p className="text-slate-500 text-sm">No posts on any feed.</p>}
      {data.posts.map((p: any) => (
        <div key={p.id} className="bg-ink border border-edge rounded-xl p-3 text-sm" data-testid="inv-feed-post">
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1 flex gap-2 flex-wrap">
            <span className="text-brand">{p.tier}</span><span>{timeAgo(p.created_at)}</span>
            {p.nsfw && <span className="text-rose-300">nsfw</span>}{p.quarantined && <span className="text-amber-300">quarantined</span>}
            {p.ai_label !== 'none' && <span>AI: {p.ai_label}</span>}
          </div>
          {p.text && <p className="whitespace-pre-wrap break-words">{p.text}</p>}
          {p.media_url && (p.media_type === 'video'
            ? <video src={p.media_url} controls className="mt-2 rounded-lg max-h-64" />
            : p.media_type === 'audio' ? <audio src={p.media_url} controls className="mt-2 w-full" />
            : <img src={p.media_url} className="mt-2 rounded-lg max-h-64" />)}
        </div>
      ))}
    </div>
  )
}

export function DmsView({ data }: { data: any }) {
  return (
    <div className="space-y-3" data-testid="inv-dms-view">
      {data.threads.length === 0 && <p className="text-slate-500 text-sm">No direct messages.</p>}
      {data.threads.map((t: any, i: number) => (
        <div key={i} className="border border-edge rounded-xl overflow-hidden">
          <div className="px-3 py-2 bg-white/5 text-sm font-medium flex items-center gap-2"><Users className="h-3.5 w-3.5 text-slate-400" />with {t.peer.display_name} <span className="text-slate-500">#{t.peer.handle}</span><span className="ml-auto text-[11px] text-slate-500">{t.messages.length} msg</span></div>
          <div className="p-3 space-y-1.5 max-h-96 overflow-y-auto">
            {t.messages.map((m: any, k: number) => (
              <div key={k} className={`flex ${m.from_subject ? 'justify-end' : ''}`}>
                <div className={`max-w-[80%] rounded-xl px-3 py-1.5 text-sm ${m.from_subject ? 'bg-rose-500/15' : 'bg-white/5 border border-edge'}`}>
                  <div className="text-[10px] text-slate-500 mb-0.5">{m.from_subject ? `#${data.subject.handle}` : `#${t.peer.handle}`} · {new Date(m.created_at).toLocaleString()}</div>
                  {m.deleted ? <em className="text-slate-500">(deleted by user) </em> : null}
                  {m.text}
                  {m.media_url && (m.media_type === 'image' || !m.media_type ? <img src={m.media_url} className="mt-1 rounded max-h-40" /> : <a href={m.media_url} target="_blank" rel="noreferrer" className="mt-1 flex items-center gap-1 text-brand text-xs"><ImageIcon className="h-3 w-3" />{m.media_type}</a>)}
                  {m.view_once && <span className="ml-1 text-[10px] text-slate-500 inline-flex items-center gap-0.5"><Lock className="h-2.5 w-2.5" />view-once</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
