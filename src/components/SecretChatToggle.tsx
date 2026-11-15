import { useEffect, useState } from 'react'
import { EyeOff, Eye } from 'lucide-react'
import { api } from '../lib/api'

// Secret chat: while on, this DM's push alerts only say "Someone sent you a message".
export default function SecretChatToggle({ handle }: { handle: string }) {
  const [secret, setSecret] = useState<boolean | null>(null)
  useEffect(() => { api.dmSecret(handle).then((r: any) => setSecret(!!r.secret)).catch(() => setSecret(false)) }, [handle])

  const toggle = async () => {
    try { setSecret(!!(await api.dmSetSecret(handle, !secret)).secret) } catch (e: any) { alert(e.message) }
  }

  return (
    <button type="button" onClick={toggle} disabled={secret === null} data-testid="secret-chat-toggle"
      className="w-full flex items-center gap-3 px-4 py-3 text-left text-sm text-slate-100 hover:bg-white/5 border-t border-edge disabled:opacity-60">
      {secret ? <Eye className="h-4 w-4 text-emerald-400" /> : <EyeOff className="h-4 w-4 text-fuchsia-400" />}
      <span className="flex-1">{secret ? 'Turn off secret chat' : 'Turn on secret chat'}</span>
      {secret && <span className="text-[10px] text-fuchsia-300" data-testid="secret-chat-on">ON</span>}
    </button>
  )
}
