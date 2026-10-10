import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { LIVE_CATEGORIES } from '../../lib/liveCategories'
import CopyField from './CopyField'
import StreamMods from './StreamMods'
import StreamVods from './StreamVods'
import { Loader2, MonitorUp, RefreshCw, Radio, Square, ExternalLink, Globe2, Users, Users2, AlertTriangle } from 'lucide-react'

const SIGNAL: Record<string, { label: string; cls: string }> = {
  publishing: { label: 'OBS connected', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' },
  buffering: { label: 'OBS buffering', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/40' },
  error: { label: 'OBS error', cls: 'bg-rose-500/15 text-rose-300 border-rose-500/40' },
  idle: { label: 'No OBS signal', cls: 'bg-white/5 text-slate-400 border-edge' },
}

const AUDIENCES = [
  { key: 'public', label: 'Public', icon: Globe2 },
  { key: 'followers', label: 'Followers', icon: Users },
  { key: 'inner', label: 'Inner Circle', icon: Users2 },
]

function StatusPills({ signal, live }: { signal: string; live: boolean }) {
  const s = SIGNAL[signal] || SIGNAL.idle
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="obs-status">
      <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${s.cls}`} data-testid="obs-signal">
        <span className={`h-1.5 w-1.5 rounded-full ${signal === 'publishing' ? 'bg-emerald-400 animate-pulse' : 'bg-current'}`} />{s.label}
      </span>
      <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border ${live ? 'bg-rose-600 text-white border-rose-500' : 'bg-white/5 text-slate-400 border-edge'}`} data-testid="obs-live-state">
        <Radio className="h-3 w-3" />{live ? 'LIVE' : 'Offline'}
      </span>
    </div>
  )
}

function SignalLight({ signal, live }: { signal: string; live: boolean }) {
  const on = signal === 'publishing'
  const text = on ? (live ? 'OBS connected — you are live' : 'OBS connected — receiving video')
    : signal === 'buffering' ? 'OBS connecting…' : signal === 'error' ? 'OBS error — check your settings' : 'Waiting for OBS…'
  const tone = on ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300'
    : signal === 'buffering' ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
    : signal === 'error' ? 'border-rose-500/50 bg-rose-500/10 text-rose-300' : 'border-edge bg-white/5 text-slate-400'
  return (
    <div className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${tone}`} data-testid="obs-signal-light" data-signal={signal}>
      <span className="relative flex h-3.5 w-3.5">
        {on && <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 animate-ping" />}
        <span className={`relative inline-flex h-3.5 w-3.5 rounded-full ${on ? 'bg-emerald-400' : signal === 'buffering' ? 'bg-amber-400' : signal === 'error' ? 'bg-rose-500' : 'bg-slate-600'}`} />
      </span>
      <span className="font-semibold text-sm" data-testid="obs-signal-text">{text}</span>
    </div>
  )
}

function StreamInfoForm({ initial, live, ready, busy, onStart }: { initial: any; live: boolean; ready: boolean; busy: boolean; onStart: (b: any) => void }) {
  const [f, setF] = useState(initial)
  const [saved, setSaved] = useState('')
  const save = async (patch: any) => {
    const next = { ...f, ...patch }; setF(next)
    try { await api.saveStreamSettings(patch); setSaved('Saved'); setTimeout(() => setSaved(''), 1500) } catch (e: any) { setSaved(e.message) }
  }
  const chip = (on: boolean) => `shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${on ? 'bg-brand text-white border-brand' : 'bg-ink text-slate-300 border-edge hover:border-brand/40'}`
  return (
    <div className="space-y-3" data-testid="obs-golive-form">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-slate-400">Stream info {live && '· editable while live'}</span>
        {saved && <span className="text-xs text-emerald-300" data-testid="obs-settings-saved">{saved}</span>}
      </div>
      <input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} onBlur={() => save({ title: f.title })} maxLength={120} placeholder="Stream title"
        data-testid="obs-title-input" className="w-full bg-ink border border-edge rounded-xl px-3 py-2.5 text-sm outline-none focus:border-brand" />
      <div className="flex gap-2 overflow-x-auto no-scrollbar">
        {LIVE_CATEGORIES.map(c => (
          <button key={c.key} onClick={() => save({ category: c.key })} data-testid={`obs-cat-${c.key}`} className={chip(f.category === c.key)}>
            <c.icon className="h-3.5 w-3.5" />{c.label}
          </button>
        ))}
      </div>
      <div className="flex gap-2 flex-wrap">
        {AUDIENCES.map(a => (
          <button key={a.key} onClick={() => save({ audience: a.key })} data-testid={`obs-aud-${a.key}`} className={chip(f.audience === a.key)}>
            <a.icon className="h-3.5 w-3.5" />{a.label}
          </button>
        ))}
      </div>
      {!live && (
        <>
          <label className="flex items-center gap-3 text-sm text-slate-200 cursor-pointer select-none" data-testid="obs-auto-live">
            <input type="checkbox" checked={!!f.auto_live} onChange={e => save({ auto_live: e.target.checked })} data-testid="obs-auto-live-toggle" className="h-4 w-4 accent-rose-500" />
            Go live automatically when OBS starts streaming
          </label>
          {f.auto_live ? (
            <p className="text-xs text-slate-500" data-testid="obs-waiting-hint">Click "Start Streaming" in OBS — you'll go live automatically with the info above. Stop streaming in OBS to end.</p>
          ) : (
            <>
              <button onClick={() => onStart({ title: f.title, category: f.category, audience: f.audience })} disabled={!ready || busy} data-testid="obs-golive-btn"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-rose-600 to-brand text-white font-bold text-sm disabled:opacity-40 active:scale-95 transition-transform">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />} Go live with OBS
              </button>
              {!ready && <p className="text-xs text-slate-500" data-testid="obs-waiting-hint">Click "Start Streaming" in OBS — Go live unlocks once we receive your video.</p>}
            </>
          )}
        </>
      )}
    </div>
  )
}

export default function ObsStudioPanel() {
  const nav = useNavigate()
  const [d, setD] = useState<any>(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => api.streamIngress().then(setD).catch((e: any) => setErr(e.message)), [])
  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  const run = async (key: string, fn: () => Promise<any>) => {
    setBusy(key); setErr('')
    try { await fn(); await load() } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  const ing = d?.ingress
  const live = d?.live
  const reset = () => window.confirm('Reset your stream key? OBS will stop working until you paste the new key.') &&
    run('reset', api.streamResetIngress)

  return (
    <section className="rounded-2xl border border-edge bg-panel overflow-hidden" data-testid="obs-studio-panel">
      <div className="px-4 py-3.5 border-b border-edge flex flex-wrap items-center gap-3">
        <div className="h-9 w-9 rounded-xl bg-brand/15 grid place-items-center"><MonitorUp className="h-5 w-5 text-brand" /></div>
        <div className="flex-1 min-w-0">
          <h2 className="font-bold leading-tight">Stream from OBS</h2>
          <p className="text-xs text-slate-400">Creator Studio · web · RTMP</p>
        </div>
        {d?.configured && ing && <StatusPills signal={ing.status} live={!!live} />}
      </div>

      <div className="p-4 space-y-4">
        {!d ? (
          <div className="py-6 grid place-items-center"><Loader2 className="h-5 w-5 animate-spin text-slate-500" /></div>
        ) : !d.configured ? (
          <p className="text-sm text-slate-400" data-testid="obs-not-configured">Streaming server isn't configured yet (LiveKit keys missing on the backend).</p>
        ) : !ing ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-slate-400 flex-1 min-w-[200px]">Get a personal RTMP server URL and stream key to broadcast from OBS.</p>
            <button onClick={() => run('create', api.streamCreateIngress)} disabled={!!busy} data-testid="obs-create-key-btn"
              className="px-5 py-2.5 rounded-full bg-brand text-white font-semibold text-sm disabled:opacity-50">
              {busy === 'create' ? 'Creating…' : 'Create stream key'}
            </button>
          </div>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-2">
              <CopyField label="Server URL" value={ing.url} testId="obs-url" />
              <CopyField label="Stream key" value={ing.stream_key} secret testId="obs-key" />
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="flex-1 min-w-[220px]">OBS → Settings → Stream → Service: <b className="text-slate-300">Custom…</b> → paste both values.</span>
              <button onClick={reset} disabled={!!busy || !!live} data-testid="obs-reset-key-btn"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-edge text-slate-300 hover:bg-white/5 disabled:opacity-40 transition-colors">
                <RefreshCw className={`h-3.5 w-3.5 ${busy === 'reset' ? 'animate-spin' : ''}`} /> Reset key
              </button>
            </div>
            {ing.error && <p className="text-xs text-rose-300">{ing.error}</p>}

            <SignalLight signal={ing.status} live={!!live} />

            {live ? (
              <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-rose-600/10 border border-rose-600/40" data-testid="obs-live-banner">
                <div className="flex-1 min-w-[180px]">
                  <div className="font-semibold text-white truncate">{live.title || "You're live"}</div>
                  <div className="text-xs text-slate-400">{live.viewers} watching</div>
                </div>
                <button onClick={() => nav(`/watch/${live.id}`)} data-testid="obs-open-stream-btn"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-white/10 text-sm font-semibold hover:bg-white/15 transition-colors">
                  <ExternalLink className="h-4 w-4" /> Open stream & chat
                </button>
                <button onClick={() => window.confirm('End your stream?') && run('end', api.streamEnd)} disabled={!!busy} data-testid="obs-end-btn"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-rose-600 text-white text-sm font-semibold disabled:opacity-50">
                  <Square className="h-3.5 w-3.5" /> {busy === 'end' ? 'Ending…' : 'End stream'}
                </button>
              </div>
            ) : null}
            <StreamInfoForm key={d.settings ? 'ok' : 'x'} initial={d.settings || { title: '', category: 'just_chatting', audience: 'public', auto_live: true }}
              live={!!live} ready={ing.status === 'publishing'} busy={busy === 'start'}
              onStart={b => run('start', async () => { const s = await api.streamStart(b); nav(`/watch/${s.id}`) })} />
          </>
        )}

        {d?.configured && !d.vod_enabled && (
          <p className="text-xs text-amber-300/90 flex items-start gap-1.5" data-testid="obs-vod-disabled">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" /> VOD recording is off: Supabase S3 settings are not configured on the backend.
          </p>
        )}
        {err && <p className="text-sm text-rose-400" data-testid="obs-error">{err}</p>}
      </div>

      <div className="grid md:grid-cols-2 border-t border-edge">
        <StreamMods />
        <StreamVods />
      </div>
    </section>
  )
}
