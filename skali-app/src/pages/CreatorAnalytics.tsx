import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, TrendingUp, TrendingDown, Loader2, Download, FileText, Package, HeartPulse, Users, Wallet, Store, LayoutGrid, Leaf, Plus, X, Sparkles } from 'lucide-react'
import { api, getToken } from '../lib/api'

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'subscribers', label: 'Subscribers', icon: Users },
  { id: 'shop', label: 'Shop', icon: Store },
  { id: 'finance', label: 'Finance', icon: Wallet },
  { id: 'health', label: 'Creator Health', icon: HeartPulse },
] as const
type TabId = typeof TABS[number]['id']
const RANGES = [
  { id: 'month', label: 'This month' },
  { id: '3m', label: '3 months' },
  { id: 'all', label: 'All time' },
] as const
type RangeId = typeof RANGES[number]['id']
const RANGE_WORD: Record<RangeId, string> = { month: 'this month', '3m': 'last 3 months', all: 'all time' }

const money = (n: number) => `£${Number(n || 0).toFixed(2)}`
const date = (s?: string) => (s ? new Date(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

async function downloadFile(url: string, filename: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) { alert('Export failed. Please try again.'); return }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await res.blob()); a.download = filename
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 4000)
}

export const SampleTag = ({ show = true }: { show?: boolean }) => show
  ? <span data-testid="sample-tag" className="ml-1.5 text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded-md bg-amber-400/15 text-amber-300 border border-amber-400/30 align-middle">Sample</span>
  : null

const Card = ({ children, className = '', ...rest }: any) => (
  <div className={`bg-panel border border-edge rounded-2xl p-4 animate-pop ${className}`} {...rest}>{children}</div>
)

const Trend = ({ pct, label, testid }: { pct: number | null | undefined; label?: string | null; testid?: string }) => {
  if (!label) return null
  if (pct == null) return <span className="text-xs text-slate-500" data-testid={testid}>no earlier data</span>
  const up = pct >= 0
  return (
    <span data-testid={testid} className={`inline-flex items-center gap-0.5 text-xs font-semibold ${up ? 'text-emerald-400' : 'text-rose-400'}`}>
      {up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}{up ? '+' : ''}{pct}% {label}
    </span>
  )
}

function Milestone({ m, onDismiss }: { m: any; onDismiss: () => void }) {
  return (
    <Card className="border-brand/30 bg-brand/5 flex items-start gap-3" data-testid="milestone-card">
      <Sparkles className="h-5 w-5 text-brand shrink-0 mt-0.5" />
      <p className="flex-1 text-sm text-slate-200" data-testid="milestone-message">{m.message}</p>
      <button onClick={onDismiss} data-testid="milestone-dismiss" aria-label="Dismiss" className="p-1 -m-1 rounded-full text-slate-400 hover:text-slate-200 hover:bg-white/5"><X className="h-4 w-4" /></button>
    </Card>
  )
}

const Stat = ({ label, value, sample, children, testid }: any) => (
  <Card data-testid={testid}>
    <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${sample ? 'bg-amber-300' : 'bg-emerald-400 shadow-[0_0_8px_rgb(52_211_153)]'}`} />{label}<SampleTag show={!!sample} />
    </div>
    <div className="text-2xl font-bold mt-1.5 tabular-nums holo-glow">{value}</div>
    {children && <div className="mt-1">{children}</div>}
  </Card>
)

const Section = ({ title, sample, children, testid }: any) => (
  <Card data-testid={testid}>
    <div className="text-sm font-semibold mb-3">{title}<SampleTag show={!!sample} /></div>
    {children}
  </Card>
)

const Empty = ({ text }: { text: string }) => <p className="text-xs text-slate-500">{text}</p>

// Holo line chart: glowing neon line + gradient area.
function Bars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1)
  const W = 300, H = 110, n = Math.max(values.length - 1, 1)
  const pts = values.map((v, i) => [(i / n) * W, H - 8 - (v / max) * (H - 20)])
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1] || [0, H]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-28 overflow-visible" data-testid="overview-trend-chart">
      <defs>
        <linearGradient id="holoArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(var(--brand))" stopOpacity=".45" />
          <stop offset="100%" stopColor="rgb(var(--brand))" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="holoLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgb(var(--brand))" />
          <stop offset="100%" stopColor="rgb(var(--neon-pink))" />
        </linearGradient>
        <filter id="holoGlow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      {[0.25, 0.5, 0.75].map(f => <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="rgb(var(--edge))" strokeDasharray="2 4" />)}
      <path d={`${line} L${W},${H} L0,${H} Z`} fill="url(#holoArea)" />
      <path d={line} fill="none" stroke="url(#holoLine)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#holoGlow)" />
      <circle cx={last[0]} cy={last[1]} r="4.5" fill="rgb(var(--neon-pink))" filter="url(#holoGlow)" />
    </svg>
  )
}

// Holo ring gauge (0-100%).
function Ring({ pct, label, sample, testid, color = 'var(--brand)' }: { pct: number; label: string; sample?: boolean; testid?: string; color?: string }) {
  const r = 34, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, Number(pct) || 0))
  return (
    <Card data-testid={testid} className="flex flex-col items-center">
      <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold self-start">{label}<SampleTag show={!!sample} /></div>
      <div className="relative h-24 w-24 mt-1">
      <svg viewBox="0 0 84 84" className="h-24 w-24 -rotate-90">
        <circle cx="42" cy="42" r={r} fill="none" stroke="rgb(var(--edge))" strokeWidth="7" />
        <circle cx="42" cy="42" r={r} fill="none" stroke={`rgb(${color})`} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ filter: `drop-shadow(0 0 6px rgb(${color}))`, transition: 'stroke-dashoffset .8s ease' }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-xl font-bold tabular-nums holo-glow">{v}%</div>
      </div>
    </Card>
  )
}

function Overview({ d, onDismissMilestone }: { d: any; onDismissMilestone: () => void }) {
  const s = (k: string) => d.sample?.includes(k)
  const l = d.compare_label
  return (
    <div className="space-y-3">
      {d.milestone && <Milestone m={d.milestone} onDismiss={onDismissMilestone} />}
      <div className="grid grid-cols-2 gap-3">
        <Stat testid="overview-revenue" label="Revenue" value={money(d.revenue)} sample={s('revenue')}><Trend pct={d.revenue_growth_pct} label={l} testid="overview-revenue-growth" /></Stat>
        <Stat testid="overview-new-subs" label="New subscribers" value={d.new_subs} sample={s('subs')}><Trend pct={d.subs_growth_pct} label={l} testid="overview-subs-growth" /></Stat>
        <Stat testid="overview-tips" label="Tips" value={money(d.tips)} sample={s('tips')}><Trend pct={d.tips_growth_pct} label={l} testid="overview-tips-growth" /></Stat>
        <Stat testid="overview-pending-payout" label="Pending payouts" value={money(d.pending_payout)} sample={s('pending_payout')} />
      </div>
      <Section title={`Revenue · last ${d.trend?.length || 6} months`} sample={s('trend')}><Bars values={d.trend || []} /></Section>
    </div>
  )
}

function PromoForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [pct, setPct] = useState('20')
  const [maxUses, setMaxUses] = useState('')
  const [endsOn, setEndsOn] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      await api.createPromo({ code: code.trim(), percent_off: Number(pct), max_uses: maxUses ? Number(maxUses) : null, expires_on: endsOn || null })
      setCode(''); setMaxUses(''); setEndsOn(''); setOpen(false); onCreated()
    } catch (e: any) { setErr(e?.message || 'Could not create code') } finally { setBusy(false) }
  }
  if (!open) return (
    <button onClick={() => setOpen(true)} data-testid="promo-new-btn" className="mt-3 w-full py-2 rounded-xl border border-dashed border-edge text-sm text-slate-300 flex items-center justify-center gap-1.5 hover:bg-white/5 transition-colors">
      <Plus className="h-4 w-4" /> New promo code
    </button>
  )
  const input = 'bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand'
  return (
    <div className="mt-3 space-y-2 border-t border-edge pt-3" data-testid="promo-form">
      <input value={code} onChange={e => setCode(e.target.value.toUpperCase())} maxLength={20} placeholder="CODE (e.g. WELCOME20)" data-testid="promo-code-input" className={`${input} w-full font-mono`} />
      <div className="flex gap-2">
        <label className="flex-1 text-xs text-slate-500">% off<input value={pct} onChange={e => setPct(e.target.value)} inputMode="numeric" data-testid="promo-percent-input" className={`${input} w-full mt-1`} /></label>
        <label className="flex-1 text-xs text-slate-500">Max uses (optional)<input value={maxUses} onChange={e => setMaxUses(e.target.value)} inputMode="numeric" data-testid="promo-max-uses-input" className={`${input} w-full mt-1`} /></label>
      </div>
      <label className="block text-xs text-slate-500">End date (optional) — the code switches off by itself after this day
        <input type="date" value={endsOn} min={new Date().toISOString().slice(0, 10)} onChange={e => setEndsOn(e.target.value)} data-testid="promo-end-date-input" className={`${input} w-full mt-1 [color-scheme:dark]`} />
      </label>
      {err && <p className="text-xs text-rose-300" data-testid="promo-error">{err}</p>}
      <div className="flex gap-2">
        <button onClick={() => setOpen(false)} data-testid="promo-cancel-btn" className="flex-1 py-2 rounded-xl border border-edge text-sm">Cancel</button>
        <button onClick={submit} disabled={busy || !code.trim()} data-testid="promo-create-btn" className="flex-1 py-2 rounded-xl bg-brand text-white text-sm font-semibold disabled:opacity-50">{busy ? 'Creating…' : 'Create code'}</button>
      </div>
    </div>
  )
}

function Subscribers({ d, onChanged }: { d: any; onChanged: () => void }) {
  const s = (k: string) => d.sample?.includes(k)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Stat testid="subs-active" label="Active memberships" value={d.active} sample={s('active')} />
        <Stat testid="subs-churn" label={`Churn · ${RANGE_WORD[d.range as RangeId]}`} value={d.churn} sample={s('churn')}>
          <span className="text-xs text-slate-500">{d.churn_rate}% cancelled or didn't renew</span>
        </Stat>
      </div>
      <Section testid="subs-renewals" title="Upcoming renewals" sample={s('renewals')}>
        {d.renewals?.length ? d.renewals.map((r: any, i: number) => (
          <div key={i} className="flex items-center justify-between py-2 border-t border-edge first:border-0 text-sm">
            <div><div className="font-medium">{r.name}</div><div className="text-xs text-slate-500">@{r.handle}</div></div>
            <div className="text-right"><div className="text-xs text-slate-400">{date(r.renews_at)}</div><div className="text-xs font-semibold">{money(r.price)}</div></div>
          </div>
        )) : <Empty text="No upcoming renewals." />}
      </Section>
      <Section testid="subs-promos" title="Active discounts & promos">
        {d.promos?.length ? d.promos.map((p: any) => (
          <div key={p.id} className="flex items-center justify-between gap-2 py-2 border-t border-edge first:border-0 text-sm" data-testid={`promo-row-${p.code}`}>
            <div className="min-w-0"><span className="font-mono text-xs px-2 py-0.5 rounded-md bg-brand/15 text-brand">{p.code}</span><span className="ml-2 text-slate-300">{p.label}</span>
              <div className="text-xs text-slate-500 mt-0.5">{p.uses}{p.max_uses ? ` / ${p.max_uses}` : ''} uses{p.expires_at && <span data-testid={`promo-ends-${p.code}`}> · ends {date(p.expires_at)}</span>}</div></div>
            <button onClick={async () => { if (!confirm(`End ${p.code}? Fans won't be able to use it any more.`)) return; await api.endPromo(p.id); onChanged() }}
              data-testid={`promo-end-${p.code}`} className="shrink-0 px-3 py-1 rounded-full border border-edge text-xs hover:bg-white/5">End</button>
          </div>
        )) : <Empty text="No active codes. Fans enter a code when they join your Inner Circle." />}
        <PromoForm onCreated={onChanged} />
        {d.ended_promos?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-edge" data-testid="promos-ended">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Ended</div>
            {d.ended_promos.map((p: any) => <div key={p.id} className="flex justify-between text-xs text-slate-500 py-0.5"><span className="font-mono">{p.code}{p.ended_reason === 'expired' && <span className="font-sans"> · expired</span>}</span><span>{p.uses} uses</span></div>)}
          </div>
        )}
      </Section>
    </div>
  )
}

const FULFIL: Record<string, string> = {
  delivered: 'bg-emerald-500/15 text-emerald-300', shipped: 'bg-sky-500/15 text-sky-300',
  in_production: 'bg-amber-500/15 text-amber-300', printful_submitted: 'bg-violet-500/15 text-violet-300',
}
const STOCK: Record<string, [string, string]> = {
  in_stock: ['In stock', 'bg-emerald-500/15 text-emerald-300'], low: ['Low', 'bg-amber-500/15 text-amber-300'], out: ['Out', 'bg-slate-500/20 text-slate-300'],
}
const Pill = ({ cls, children }: any) => <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full capitalize ${cls}`}>{children}</span>

function Shop({ d }: { d: any }) {
  const s = (k: string) => d.sample?.includes(k)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Stat testid="shop-orders-count" label="Orders" value={d.orders_count} sample={s('orders')} />
        <Stat testid="shop-downloads-count" label="Digital downloads" value={d.downloads_count} sample={s('orders')} />
      </div>
      <Section testid="shop-orders" title="Orders · Printful fulfilment" sample={s('orders')}>
        {d.orders?.length ? d.orders.map((o: any) => (
          <div key={o.id} className="flex items-center justify-between py-2 border-t border-edge first:border-0 text-sm">
            <div className="flex items-center gap-2"><Package className="h-4 w-4 text-slate-500" /><div><div className="font-medium">{o.title}</div><div className="text-xs text-slate-500">{o.kind} · {date(o.created_at)}</div></div></div>
            <div className="text-right space-y-1"><div className="text-xs font-semibold">{money(o.gross)}</div><Pill cls={FULFIL[o.fulfilment_status] || 'bg-slate-500/20 text-slate-300'}>{String(o.fulfilment_status || '').replace(/_/g, ' ')}</Pill></div>
          </div>
        )) : <Empty text="No orders yet." />}
      </Section>
      <Section testid="shop-inventory" title="Inventory status" sample={s('inventory')}>
        {d.inventory.map((it: any, i: number) => (
          <div key={i} className="flex items-center justify-between py-2 border-t border-edge first:border-0 text-sm">
            <div><div className="font-medium">{it.title}</div><div className="text-xs text-slate-500">{it.kind}</div></div>
            <Pill cls={STOCK[it.status]?.[1]}>{STOCK[it.status]?.[0]}</Pill>
          </div>
        ))}
      </Section>
    </div>
  )
}

function ExportButton({ range }: { range: RangeId }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const go = async (kind: 'csv' | 'pdf') => {
    setBusy(true); setOpen(false)
    await downloadFile(kind === 'csv' ? api.analyticsCsvUrl(range) : api.analyticsPdfUrl(range), `skali-analytics-finance-${range}.${kind}`)
    setBusy(false)
  }
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)} disabled={busy} data-testid="finance-export-btn"
        className="px-4 py-1.5 rounded-full bg-brand text-white text-sm font-semibold flex items-center gap-1.5 hover:bg-brand-600 transition-colors disabled:opacity-60">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Export
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-36 bg-panel2 border border-edge rounded-xl overflow-hidden z-10 animate-pop" data-testid="finance-export-menu">
          <button onClick={() => go('csv')} data-testid="finance-export-csv" className="w-full text-left px-3 py-2 text-sm hover:bg-white/5">Download CSV</button>
          <button onClick={() => go('pdf')} data-testid="finance-export-pdf" className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 border-t border-edge">Download PDF</button>
        </div>
      )}
    </div>
  )
}

function Finance({ d }: { d: any }) {
  const s = (k: string) => d.sample?.includes(k)
  const f = d.fees
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">Payouts, fees and earnings summaries.</p>
        <ExportButton range={d.range} />
      </div>
      <Section testid="finance-fees" title="Skali fee breakdown" sample={s('fees')}>
        {[['Gross', f.gross], ['VAT', f.vat], ['Processing', f.psp_fee]].map(([l, v]: any) => (
          <div key={l} className="flex justify-between py-1.5 text-sm text-slate-400"><span>{l}</span><span className="tabular-nums">{money(v)}</span></div>
        ))}
        <div className="flex justify-between py-1.5 text-sm text-slate-400"><span>Skali fee ({Math.round(d.fee_rate * 100)}%)<SampleTag show={s('fee_rate')} /></span><span className="tabular-nums">−{money(f.skali_fee)}</span></div>
        <div className="flex justify-between pt-2 mt-1 border-t border-edge text-base font-bold" data-testid="finance-net"><span>Net</span><span className="tabular-nums">{money(f.creator_net)}</span></div>
      </Section>
      <Section testid="finance-payouts" title="Payout history" sample={s('payouts')}>
        {d.payouts?.length ? d.payouts.map((p: any) => (
          <div key={p.id} className="flex items-center justify-between py-2 border-t border-edge first:border-0 text-sm">
            <span className="text-slate-400">{date(p.created_at)}</span>
            <span className="flex items-center gap-2"><Pill cls="bg-emerald-500/15 text-emerald-300">{p.status}</Pill><span className="font-semibold tabular-nums">{money(p.amount)}</span></span>
          </div>
        )) : <Empty text="No payouts yet." />}
      </Section>
      <Section testid="finance-tax-docs" title="Tax documents" sample={s('fees')}>
        <p className="text-[11px] text-slate-500 mb-2">Monthly summaries from your Skali data. These are not official tax forms.</p>
        {d.tax_docs?.length ? d.tax_docs.map((t: any) => (
          <div key={t.month} className="flex items-center justify-between py-2 border-t border-edge first:border-0 text-sm">
            <span className="flex items-center gap-2"><FileText className="h-4 w-4 text-slate-500" />{t.title}</span>
            <span className="text-xs text-slate-400 tabular-nums">Net {money(t.creator_net)}</span>
          </div>
        )) : <Empty text="No summaries yet." />}
      </Section>
    </div>
  )
}

function HealthSwitch({ on, busy, onToggle }: { on: boolean; busy: boolean; onToggle: () => void }) {
  return (
    <Card className="flex items-center justify-between gap-3">
      <div>
        <div className="text-sm font-semibold">Show Creator Health</div>
        <p className="text-xs text-slate-500 mt-0.5">Turn this off any time if the numbers aren't helping you. No penalty.</p>
      </div>
      <button role="switch" aria-checked={on} onClick={onToggle} disabled={busy} data-testid="health-toggle"
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${on ? 'bg-brand' : 'bg-edge'} disabled:opacity-60`}>
        <span className={`absolute top-1 left-1 h-5 w-5 rounded-full bg-white transition-transform ${on ? 'translate-x-5' : ''}`} />
      </button>
    </Card>
  )
}

function Health({ d, onChanged }: { d: any; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const on = !d.settings?.hidden
  const toggle = async () => {
    setBusy(true)
    try { await api.setHealthSettings({ hidden: on }); await onChanged() } finally { setBusy(false) }
  }
  if (!on) return (
    <div className="space-y-3">
      <HealthSwitch on={on} busy={busy} onToggle={toggle} />
      <Card className="text-center py-8" data-testid="health-hidden-message">
        <Leaf className="h-6 w-6 text-brand mx-auto mb-2" />
        <p className="text-sm text-slate-300">Creator Health is hidden.</p>
        <p className="text-xs text-slate-500 mt-1">Take the time you need. Switch it back on whenever you like.</p>
      </Card>
    </div>
  )
  const m = d.metrics, s = (k: string) => d.sample?.includes(k)
  return (
    <div className="space-y-3">
      <HealthSwitch on={on} busy={busy} onToggle={toggle} />
      <div className="grid grid-cols-2 gap-3" data-testid="health-metrics">
        <Stat testid="health-returning" label="Returning subscribers" value={m.returning_subscribers} sample={s('returning_subscribers')} />
        <Ring testid="health-renewal-rate" label="Renewal rate" pct={m.renewal_rate} sample={s('renewal_rate')} />
        <Stat testid="health-watch-time" label="Avg watch time" value={m.avg_watch_time == null ? '—' : `${m.avg_watch_time} min`}>
          <span className="text-xs text-slate-500">{m.watch_sessions ? `${m.watch_sessions} Inner Circle views` : 'No Inner Circle views yet'}</span>
        </Stat>
        <Ring testid="health-retention" label="Retention" pct={m.retention} sample={s('retention')} color="var(--neon-cyan)" />
      </div>
      <Stat testid="health-ic-messages" label="Messages from Inner Circle" value={m.inner_circle_messages} sample={s('inner_circle_messages')}>
        <span className="text-xs text-slate-500">{RANGE_WORD[d.range as RangeId]}</span>
      </Stat>
      <p className="text-[11px] text-slate-500 text-center">Just for you. This is never a score and never affects your account.</p>
    </div>
  )
}

export default function CreatorAnalytics() {
  const nav = useNavigate()
  const [tab, setTab] = useState<TabId>('overview')
  const [range, setRange] = useState<RangeId>('month')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const touch = useRef<number | null>(null)
  const load = () => api.creatorAnalytics(range).then(setData).catch((e: any) => setError(e?.message || 'Could not load analytics'))
  useEffect(() => { load() }, [range])
  const dismissMilestone = async () => {
    const m = data?.overview?.milestone
    if (m) { await api.dismissMilestone(m.kind, m.value).catch(() => {}); load() }
  }

  const swipe = (dx: number) => {
    if (Math.abs(dx) < 60) return
    const i = TABS.findIndex(t => t.id === tab) + (dx < 0 ? 1 : -1)
    if (i >= 0 && i < TABS.length) setTab(TABS[i].id)
  }

  return (
    <div className="min-h-screen bg-ink text-slate-100" data-testid="creator-analytics-page">
      <div className="sticky top-0 z-20 bg-ink/95 backdrop-blur border-b border-edge">
        <div className="max-w-2xl mx-auto px-4 pb-2 flex items-center gap-3">
          <button onClick={() => nav(-1)} data-testid="analytics-back" className="p-1.5 -ml-1.5 rounded-full hover:bg-white/5"><ArrowLeft className="h-5 w-5" /></button>
          <h1 className="flyer-title text-2xl">Analytics</h1>
        </div>
        <div className="max-w-2xl mx-auto px-4 pb-2">
          <div className="flex bg-panel border border-edge rounded-full p-0.5" data-testid="analytics-range-picker">
            {RANGES.map(r => (
              <button key={r.id} onClick={() => setRange(r.id)} data-testid={`analytics-range-${r.id}`}
                className={`flex-1 py-1 rounded-full text-xs font-semibold transition-colors ${range === r.id ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200'}`}>{r.label}</button>
            ))}
          </div>
        </div>
        <div className="max-w-2xl mx-auto flex gap-1 overflow-x-auto no-scrollbar px-3 pb-2">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`analytics-tab-${t.id}`}
              className={`shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold transition-colors ${tab === t.id ? 'synth-nav-active text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}>
              <t.icon className="h-4 w-4" />{t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="max-w-2xl mx-auto px-4 py-5 pb-24"
        onTouchStart={e => { touch.current = e.touches[0].clientX }}
        onTouchEnd={e => { if (touch.current != null) swipe(e.changedTouches[0].clientX - touch.current); touch.current = null }}>
        {error ? <Card data-testid="analytics-error"><p className="text-sm text-slate-300">{error}</p></Card>
          : !data ? <div className="grid place-items-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
          : <div key={tab} data-testid={`analytics-panel-${tab}`}>
              {tab === 'overview' && <Overview d={data.overview} onDismissMilestone={dismissMilestone} />}
              {tab === 'subscribers' && <Subscribers d={data.subscribers} onChanged={load} />}
              {tab === 'shop' && <Shop d={data.shop} />}
              {tab === 'finance' && <Finance d={data.finance} />}
              {tab === 'health' && <Health d={data.health} onChanged={load} />}
            </div>}
      </div>
    </div>
  )
}
