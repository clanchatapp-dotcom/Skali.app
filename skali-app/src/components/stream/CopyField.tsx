import { useState } from 'react'
import { Check, Copy, Eye, EyeOff } from 'lucide-react'

export default function CopyField({ label, value, secret = false, testId }: {
  label: string; value: string; secret?: boolean; testId: string
}) {
  const [shown, setShown] = useState(!secret)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      window.prompt(`Copy your ${label.toLowerCase()}:`, value)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">{label}</div>
      <div className="flex items-center gap-2 bg-ink border border-edge rounded-xl pl-3 pr-1.5 py-1.5">
        <code className="flex-1 min-w-0 truncate text-sm text-slate-200 font-mono" data-testid={`${testId}-value`}>
          {shown ? value : '•'.repeat(Math.min(28, value.length || 12))}
        </code>
        {secret && (
          <button onClick={() => setShown(s => !s)} data-testid={`${testId}-toggle`} aria-label={shown ? 'Hide' : 'Show'}
            className="h-8 w-8 grid place-items-center rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
            {shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
        <button onClick={copy} data-testid={`${testId}-copy`}
          className="h-8 px-3 rounded-lg bg-white/5 border border-edge text-xs font-semibold flex items-center gap-1.5 hover:bg-white/10 transition-colors">
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}
