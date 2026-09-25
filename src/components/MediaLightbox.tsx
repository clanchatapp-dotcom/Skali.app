import { useEffect, useRef, useState } from 'react'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'

type Item = { url: string; type: string }

// Fullscreen media viewer with:
//  - X button / backdrop tap / Escape to close
//  - swipe DOWN to dismiss
//  - swipe LEFT/RIGHT (or arrows) to move between a person's photos/videos
//  - pinch-to-zoom + drag-to-pan on photos (double-tap toggles 2x)
export default function MediaLightbox({ items, index = 0, onClose }: { items: Item[]; index?: number; onClose: () => void }) {
  const [idx, setIdx] = useState(index)
  const [scale, setScale] = useState(1)
  const [tx, setTx] = useState(0)
  const [ty, setTy] = useState(0)
  const [dragging, setDragging] = useState(false)

  const g = useRef<{ mode: string | null; startX: number; startY: number; lastX: number; lastY: number; baseScale: number; startDist: number; baseTx: number; baseTy: number }>({
    mode: null, startX: 0, startY: 0, lastX: 0, lastY: 0, baseScale: 1, startDist: 0, baseTx: 0, baseTy: 0,
  })

  const cur = items[idx]
  const resetZoom = () => { setScale(1); setTx(0); setTy(0) }
  const go = (d: number) => {
    setIdx(i => Math.min(items.length - 1, Math.max(0, i + d)))
    resetZoom()
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight') go(1)
      else if (e.key === 'ArrowLeft') go(-1)
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose, items.length])

  const dist = (t: React.TouchList) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)

  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.touches
    const st = g.current
    if (t.length === 2) {
      st.mode = 'pinch'; st.startDist = dist(t); st.baseScale = scale; st.baseTx = tx; st.baseTy = ty
    } else if (t.length === 1) {
      st.mode = scale > 1 ? 'pan' : 'swipe'
      st.startX = t[0].clientX; st.startY = t[0].clientY
      st.baseTx = tx; st.baseTy = ty; st.lastX = 0; st.lastY = 0
      setDragging(true)
    }
  }
  const onTouchMove = (e: React.TouchEvent) => {
    const t = e.touches
    const st = g.current
    if (st.mode === 'pinch' && t.length === 2) {
      setScale(Math.min(4, Math.max(1, st.baseScale * (dist(t) / (st.startDist || 1)))))
    } else if (st.mode === 'pan' && t.length === 1) {
      setTx(st.baseTx + (t[0].clientX - st.startX))
      setTy(st.baseTy + (t[0].clientY - st.startY))
    } else if (st.mode === 'swipe' && t.length === 1) {
      st.lastX = t[0].clientX - st.startX
      st.lastY = t[0].clientY - st.startY
      if (Math.abs(st.lastY) > Math.abs(st.lastX)) { setTy(st.lastY); setTx(0) }
      else { setTx(st.lastX); setTy(0) }
    }
  }
  const onTouchEnd = () => {
    const st = g.current
    setDragging(false)
    if (st.mode === 'pinch') {
      if (scale < 1.1) resetZoom()
      st.mode = null
      return
    }
    if (st.mode === 'swipe') {
      const dx = st.lastX, dy = st.lastY
      if (Math.abs(dy) > Math.abs(dx) && dy > 110) { onClose(); return }
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) go(dx < 0 ? 1 : -1)
      setTx(0); setTy(0)
    }
    st.mode = null; st.lastX = 0; st.lastY = 0
  }

  const onDouble = () => { if (scale > 1) resetZoom(); else setScale(2) }

  const fade = (g.current.mode === 'swipe' && scale === 1) ? Math.max(0.2, 1 - Math.abs(ty) / 450) : 1

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center"
      style={{ background: `rgba(0,0,0,${0.96 * fade})` }}
      onClick={onClose}
      data-testid="media-lightbox"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onClose() }}
        data-testid="lightbox-close"
        aria-label="Close"
        className="absolute right-4 top-[calc(0.75rem+env(safe-area-inset-top))] z-20 h-10 w-10 grid place-items-center rounded-full bg-black/60 text-white hover:bg-black/80 transition"
      >
        <X className="h-6 w-6" />
      </button>

      {items.length > 1 && (
        <span className="absolute left-4 top-[calc(0.9rem+env(safe-area-inset-top))] z-20 text-sm text-white/85 bg-black/50 px-2.5 py-1 rounded-full">{idx + 1} / {items.length}</span>
      )}

      {items.length > 1 && idx > 0 && (
        <button onClick={(e) => { e.stopPropagation(); go(-1) }} data-testid="lightbox-prev" aria-label="Previous"
          className="hidden md:grid absolute left-4 z-20 h-11 w-11 place-items-center rounded-full bg-black/50 text-white hover:bg-black/70"><ChevronLeft className="h-6 w-6" /></button>
      )}
      {items.length > 1 && idx < items.length - 1 && (
        <button onClick={(e) => { e.stopPropagation(); go(1) }} data-testid="lightbox-next" aria-label="Next"
          className="hidden md:grid absolute right-4 z-20 h-11 w-11 place-items-center rounded-full bg-black/50 text-white hover:bg-black/70"><ChevronRight className="h-6 w-6" /></button>
      )}

      <div
        className="max-h-full max-w-full p-4 select-none touch-none"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onDoubleClick={onDouble}
        style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})`, transition: dragging ? 'none' : 'transform .2s ease' }}
      >
        {cur.type === 'video'
          ? <video src={cur.url} controls autoPlay playsInline className="max-h-[85vh] max-w-[92vw] rounded-lg" />
          : <img src={cur.url} draggable={false} className="max-h-[85vh] max-w-[92vw] rounded-lg object-contain" />}
      </div>

      {items.length > 1 && (
        <div className="absolute bottom-[calc(1rem+env(safe-area-inset-bottom))] inset-x-0 z-20 flex justify-center gap-1.5">
          {items.map((_, i) => <span key={i} className={`h-1.5 rounded-full transition-all ${i === idx ? 'w-4 bg-white' : 'w-1.5 bg-white/40'}`} />)}
        </div>
      )}
    </div>
  )
}
