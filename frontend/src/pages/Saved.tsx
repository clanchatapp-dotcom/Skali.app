import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Bookmark, Play, Trash2, X } from 'lucide-react'
import MediaLightbox from '../components/MediaLightbox'
import { getSaved, removeSaved, clearSaved, SAVED_CHANGED_EVENT, SavedItem } from '../lib/savedMedia'

export default function Saved() {
  const nav = useNavigate()
  const [items, setItems] = useState<SavedItem[]>(getSaved())
  const [lbIndex, setLbIndex] = useState<number | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)

  useEffect(() => {
    const refresh = () => setItems(getSaved())
    window.addEventListener(SAVED_CHANGED_EVENT, refresh)
    window.addEventListener('focus', refresh)
    return () => { window.removeEventListener(SAVED_CHANGED_EVENT, refresh); window.removeEventListener('focus', refresh) }
  }, [])

  return (
    <div className="h-full min-h-0 flex flex-col overflow-hidden">
      <header className="shrink-0 z-30 bg-ink/95 backdrop-blur border-b border-edge px-4 pt-[env(safe-area-inset-top)] min-h-14 flex items-center gap-3">
        <button
          onClick={() => nav(-1)}
          className="h-10 w-10 grid place-items-center rounded-xl hover:bg-white/10 text-slate-300 shrink-0"
          aria-label="Back"
          data-testid="saved-back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="font-extrabold text-lg">Saved</h1>
          <p className="text-xs text-slate-500 truncate">{items.length} {items.length === 1 ? 'item' : 'items'} saved to this device</p>
        </div>
        {items.length > 0 && (
          <button onClick={() => setConfirmClear(true)} data-testid="saved-clear"
            className="text-xs font-semibold px-3 py-1.5 rounded-full border border-edge text-slate-300 hover:bg-white/5">
            Clear all
          </button>
        )}
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-xl mx-auto p-4 pb-[calc(5.25rem+env(safe-area-inset-bottom))] md:pb-8">
          {items.length === 0 ? (
            <div className="bg-panel border border-edge rounded-2xl p-10 text-center mt-6" data-testid="saved-empty">
              <Bookmark className="h-9 w-9 mx-auto text-slate-600" />
              <p className="mt-3 text-slate-300 font-semibold">Nothing saved yet</p>
              <p className="mt-1 text-sm text-slate-500">Tap the save icon on any photo or video and it'll show up here.</p>
              <button onClick={() => nav('/')} className="mt-5 px-5 py-2.5 rounded-full bg-gradient-to-r from-brand to-violet-600 font-semibold">
                Browse the feed
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-1.5" data-testid="saved-grid">
              {items.map((m, i) => (
                <div key={m.url} className="relative aspect-square rounded-lg overflow-hidden bg-panel group">
                  <button
                    type="button"
                    onClick={() => setLbIndex(i)}
                    data-testid={`saved-item-${i}`}
                    className="absolute inset-0 w-full h-full cursor-zoom-in"
                  >
                    {m.type === 'video' ? (
                      <>
                        <video src={m.url} muted playsInline preload="metadata" className="h-full w-full object-cover" />
                        <span className="absolute inset-0 grid place-items-center">
                          <span className="h-10 w-10 rounded-full bg-black/60 grid place-items-center">
                            <Play className="h-5 w-5 text-white ml-0.5" />
                          </span>
                        </span>
                      </>
                    ) : (
                      <img src={m.url} className="h-full w-full object-cover" />
                    )}
                  </button>
                  <button
                    onClick={() => removeSaved(m.url)}
                    data-testid={`saved-remove-${i}`}
                    aria-label="Remove from saved"
                    className="absolute top-1.5 right-1.5 h-7 w-7 grid place-items-center rounded-full bg-black/60 text-white hover:bg-rose-600 transition"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {lbIndex !== null && items[lbIndex] && (
        <MediaLightbox
          items={items.map(m => ({ url: m.url, type: m.type }))}
          index={lbIndex}
          allowSave
          onClose={() => setLbIndex(null)}
        />
      )}

      {confirmClear && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-black/70 backdrop-blur p-4" onClick={() => setConfirmClear(false)}>
          <div className="bg-panel border border-edge rounded-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
            <div className="h-11 w-11 rounded-2xl bg-rose-500/15 grid place-items-center mb-3">
              <Trash2 className="h-5 w-5 text-rose-400" />
            </div>
            <h3 className="font-bold text-lg">Clear saved list?</h3>
            <p className="text-sm text-slate-400 mt-1">This only clears the in-app list. Files already downloaded to your device are not deleted.</p>
            <div className="flex gap-2 justify-end mt-5">
              <button onClick={() => setConfirmClear(false)} className="px-4 py-2.5 rounded-xl border border-edge text-sm font-medium">Cancel</button>
              <button onClick={() => { clearSaved(); setConfirmClear(false) }} data-testid="saved-clear-confirm" className="px-4 py-2.5 rounded-xl bg-rose-600 text-white text-sm font-semibold">Clear all</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
