import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Compass, Megaphone, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import PostCard from '../components/PostCard'

export default function Choices() {
  const nav = useNavigate()
  const [data, setData] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = () => api.choices().then(setData).catch(() => setData({ opt_in: false, posts: [], sponsored: [] }))
  useEffect(() => { load() }, [])

  const toggle = async () => {
    setBusy(true); setErr('')
    try { await api.choicesOptIn(); await load() }
    catch (e: any) {
      const m = String(e?.message || '')
      setErr(/not found/i.test(m) ? "Choices isn't available on this server yet. If you just updated the app, please redeploy the backend." : m)
    } finally { setBusy(false) }
  }

  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <header className="sticky top-0 z-30 bg-ink/95 backdrop-blur border-b border-edge px-4 pt-[env(safe-area-inset-top)] min-h-14 flex items-center gap-3">
        <button onClick={() => nav(-1)} className="text-slate-300 hover:text-white py-3" data-testid="choices-back"><ArrowLeft className="h-5 w-5" /></button>
        <Compass className="h-5 w-5 text-brand" />
        <h1 className="text-lg font-bold flex-1">Choices</h1>
        {data?.opt_in && (
          <button onClick={toggle} disabled={busy} className="text-xs text-slate-400 hover:text-slate-200" data-testid="choices-toggle-off">Turn off</button>
        )}
      </header>

      <div className="max-w-2xl mx-auto px-4 py-5">
        {!data ? (
          <div className="grid place-items-center py-20"><Loader2 className="animate-spin text-slate-500" /></div>
        ) : !data.opt_in ? (
          <div className="bg-panel border border-edge rounded-2xl p-8 text-center" data-testid="choices-optin-card">
            <Compass className="mx-auto text-brand mb-3" size={32} />
            <h2 className="text-xl font-bold mb-1">Discover more, on your terms</h2>
            <p className="text-sm text-slate-400 mb-5">Choices is an opt-in discovery layer driven by the topics you follow — kept separate from your feed. It's also the only place you'll see labelled sponsored posts.</p>
            <button onClick={toggle} disabled={busy} className="px-6 py-2.5 rounded-xl bg-brand text-white font-semibold" data-testid="choices-optin-btn">
              {busy ? 'Turning on…' : 'Turn on Choices'}
            </button>
            {err && <p className="text-sm text-rose-400 mt-3" data-testid="choices-error">{err}</p>}
          </div>
        ) : (
          <div className="space-y-4">
            {(data.sponsored || []).map((p: any) => (
              <div key={`sp-${p.id}`} data-testid="sponsored-post">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-400 mb-1 px-1">
                  <Megaphone size={12} /> {p.sponsor_label || 'Sponsored'}
                </div>
                <PostCard post={p} />
              </div>
            ))}
            {(data.posts || []).length === 0 && (data.sponsored || []).length === 0 && (
              <p className="text-center text-slate-500 py-14">Follow a few topics to fill your Choices.</p>
            )}
            {(data.posts || []).map((p: any) => <PostCard key={p.id} post={p} />)}
          </div>
        )}
      </div>
    </div>
  )
}
