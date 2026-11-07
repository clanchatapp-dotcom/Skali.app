import { useState } from 'react'
import { Download, Loader2, Check, EyeOff } from 'lucide-react'
import { downloadMedia } from '../lib/download'

export function DownloadButton({ url, type, testId, className = '', label, getBlob }: { url: string; type: string; testId: string; className?: string; label?: boolean; getBlob?: () => Promise<Blob> }) {
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle')
  const [msg, setMsg] = useState('')
  const go = async (e: React.MouseEvent) => {
    e.stopPropagation(); e.preventDefault()
    if (state === 'busy') return
    setState('busy')
    try { setMsg(await downloadMedia(url, type, getBlob)); setState('done') } catch (err: any) { setMsg(err?.message || 'Download failed'); setState('idle') }
    setTimeout(() => { setState('idle'); setMsg('') }, 2500)
  }
  const Icon = state === 'busy' ? Loader2 : state === 'done' ? Check : Download
  return (
    <button type="button" onClick={go} data-testid={testId} title="Download" aria-label="Download"
      className={`inline-flex items-center gap-1.5 rounded-full bg-black/60 text-white hover:bg-black/80 backdrop-blur transition-colors ${label || msg ? 'px-3 h-9 text-xs font-medium' : 'h-9 w-9 justify-center'} ${className}`}>
      <Icon className={`h-4 w-4 ${state === 'busy' ? 'animate-spin' : ''}`} />
      {msg || (label ? 'Download' : '')}
    </button>
  )
}

export function SpoilerCover({ onReveal, testId, compact }: { onReveal: () => void; testId: string; compact?: boolean }) {
  return (
    <button type="button" onClick={e => { e.stopPropagation(); onReveal() }} data-testid={testId}
      className="absolute inset-0 z-10 grid place-items-center bg-black/40 backdrop-blur-2xl text-white">
      <span className={`flex flex-col items-center gap-1 ${compact ? 'text-xs' : 'text-sm'}`}>
        <EyeOff className={compact ? 'h-5 w-5' : 'h-7 w-7'} />
        <span className="font-semibold uppercase tracking-wider">Spoiler</span>
        <span className="text-white/70 text-[11px]">Tap to reveal</span>
      </span>
    </button>
  )
}
