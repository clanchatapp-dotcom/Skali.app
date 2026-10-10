import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import { TIER } from '../lib/ui'
import { Clock, Pencil, Trash2, X } from 'lucide-react'

export const toLocalInput = (ms: number) => {
  const d = new Date(ms)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

export const fmtWhen = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export default function ScheduledPostsPanel({ items, setItems, onClose }: { items: any[]; setItems: (f: (s: any[]) => any[]) => void; onClose: () => void }) {
  const [edit, setEdit] = useState<any>(null)

  const cancel = async (id: string) => {
    if (!confirm('Cancel this scheduled post?')) return
    try { await api.cancelScheduledPost(id); setItems(s => s.filter(x => x.id !== id)) } catch (e: any) { alert(e.message) }
  }

  const save = async () => {
    if (!edit.local) return
    try {
      const iso = new Date(edit.local).toISOString()
      await api.editScheduledPost(edit.id, { text: edit.text, scheduled_at: iso })
      setItems(s => s.map(x => x.id === edit.id ? { ...x, text: edit.text.trim(), scheduled_at: iso } : x)
        .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)))
      setEdit(null)
    } catch (e: any) { alert(e.message) }
  }

  return createPortal(
    <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur grid place-items-end sm:place-items-center" onClick={onClose}>
      <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl p-4 w-full max-w-xl max-h-[85dvh] overflow-y-auto pb-[calc(1rem+env(safe-area-inset-bottom))]" onClick={e => e.stopPropagation()} data-testid="scheduled-posts-panel">
        <div className="flex items-center justify-between mb-3">
          <span className="font-semibold text-sm text-slate-200 flex items-center gap-2"><Clock className="h-4 w-4 text-brand" /> Scheduled posts</span>
          <button onClick={onClose} data-testid="scheduled-posts-close" className="h-8 w-8 grid place-items-center rounded-full text-slate-400 hover:text-white hover:bg-white/10"><X className="h-4 w-4" /></button>
        </div>
        {items.length === 0 && <p className="text-sm text-slate-500 py-6 text-center">Nothing scheduled.</p>}
        <div className="space-y-2">
          {items.map(s => edit?.id === s.id ? (
            <div key={s.id} className="rounded-xl border border-brand/50 bg-black/20 p-3 space-y-2" data-testid={`scheduled-post-edit-${s.id}`}>
              <textarea value={edit.text} onChange={e => setEdit({ ...edit, text: e.target.value })} rows={3} data-testid="scheduled-post-edit-text"
                className="w-full bg-ink border border-edge rounded-xl px-3 py-2 outline-none focus:border-brand resize-none" />
              <input type="datetime-local" value={edit.local} min={toLocalInput(Date.now() + 60000)} onChange={e => setEdit({ ...edit, local: e.target.value })}
                data-testid="scheduled-post-edit-datetime" className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand [color-scheme:dark]" />
              <div className="flex justify-end gap-2">
                <button onClick={() => setEdit(null)} data-testid="scheduled-post-edit-cancel" className="px-3 py-1.5 rounded-xl border border-edge text-sm">Close</button>
                <button onClick={save} data-testid="scheduled-post-edit-save" className="px-3 py-1.5 rounded-xl bg-brand text-sm font-medium">Save</button>
              </div>
            </div>
          ) : (
            <div key={s.id} className="rounded-xl border border-edge bg-black/20 p-3 flex gap-3" data-testid={`scheduled-post-item-${s.id}`}>
              {s.media?.[0] && s.media[0].type === 'image' && <img src={s.media[0].url} className="h-14 w-14 rounded-lg object-cover shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="text-xs text-brand font-medium">{fmtWhen(s.scheduled_at)} · <span className="text-slate-400">{(TIER as any)[s.tier]?.label || s.tier}</span></div>
                <p className="mt-1 text-sm whitespace-pre-wrap break-words line-clamp-3">{s.text || <span className="text-slate-500">{s.media?.length} media item(s)</span>}</p>
              </div>
              <button onClick={() => setEdit({ id: s.id, text: s.text, local: toLocalInput(new Date(s.scheduled_at).getTime()) })}
                data-testid={`scheduled-post-edit-btn-${s.id}`} className="h-8 w-8 grid place-items-center rounded-lg text-slate-300 hover:bg-white/10"><Pencil className="h-4 w-4" /></button>
              <button onClick={() => cancel(s.id)} data-testid={`scheduled-post-cancel-${s.id}`} className="h-8 w-8 grid place-items-center rounded-lg text-rose-400 hover:bg-white/10"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body
  )
}
