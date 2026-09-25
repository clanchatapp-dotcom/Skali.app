import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

// Fullscreen viewer for post media. Tap the media to open; close with the X,
// by tapping the backdrop, pressing Escape, or swiping the media downwards.
export default function MediaLightbox({ url, type, onClose }: { url: string; type: string; onClose: () => void }) {
  const [dy, setDy] = useState(0)
  const startY = useRef<number | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose])

  const onTouchStart = (e: React.TouchEvent) => { startY.current = e.touches[0].clientY }
  const onTouchMove = (e: React.TouchEvent) => {
    if (startY.current == null) return
    const d = e.touches[0].clientY - startY.current
    if (d > 0) setDy(d)
  }
  const onTouchEnd = () => {
    if (dy > 110) { onClose(); return }
    setDy(0); startY.current = null
  }

  const opacity = Math.max(0, 1 - dy / 450)

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center"
      style={{ background: `rgba(0,0,0,${0.96 * opacity})` }}
      onClick={onClose}
      data-testid="media-lightbox"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onClose() }}
        data-testid="lightbox-close"
        aria-label="Close"
        className="absolute right-4 top-[calc(0.75rem+env(safe-area-inset-top))] z-10 h-10 w-10 grid place-items-center rounded-full bg-black/60 text-white hover:bg-black/80 transition"
      >
        <X className="h-6 w-6" />
      </button>

      <div
        className="max-h-full max-w-full p-4"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        style={{ transform: `translateY(${dy}px)`, transition: startY.current == null ? 'transform .2s ease' : 'none' }}
      >
        {type === 'video'
          ? <video src={url} controls autoPlay playsInline className="max-h-[85vh] max-w-[92vw] rounded-lg" />
          : <img src={url} className="max-h-[85vh] max-w-[92vw] rounded-lg object-contain" />}
      </div>
    </div>
  )
}
