import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Capacitor } from '@capacitor/core'
import { ArrowLeft, TrendingUp, TrendingDown, Users, Store, Wallet, Lock, Plus, Trash2, Download, FileText, Loader2, Settings as SettingsIcon, Sparkles, ShieldAlert, Check, HeartPulse, Eye, EyeOff, Power, CalendarClock, Repeat, MessageCircle } from 'lucide-react'
import { api, getToken } from '../lib/api'

const TABS = ['overview', 'subscribers', 'shop', 'finance', 'health', 'settings'] as const
type Tab = typeof TABS[number]
const money = (n: number, ccy = 'GBP') => `${ccy === 'GBP' ? '£' : ''}${Number(n || 0).toFixed(2)}`
const pct = (n: number | null | undefined) => (n == null ? '—' : `${n}%`)
const isNative = (() => { try { return Capacitor.isNativePlatform() } catch { return false } })()

// Authenticated file download (CSV/PDF exports need the Bearer token, so a plain
// <a href> won't work — fetch as a blob and trigger a download).
async function downloadFile(url: string, filename: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) { alert('Export failed. Please try again.'); return }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = filename
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 4000)
}

const CREATOR_TYPE_META: Record<string, { label: string; icon: string }> = {
  gaming: { label: 'Gaming', icon: '🎮' },
  music: { label: 'Music', icon: '🎵' },
  influencer: { label: 'Influencer', icon: '⭐' },
  art: { label: 'Art', icon: '🎨' },
  fitness: { label: 'Fitness', icon: '💪' },
  education: { label: 'Education', icon: '📚' },
  adult: { label: 'Adult', icon: '🔞' },
  other: { label: 'Other', icon: '✨' },
}

export default function CreatorHub() {
  const nav = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [status, setStatus] = useState<any>(null)
  const load = () => api.creatorMe().then(setStatus).catch(() => setStatus({}))
  useEffect(() => { load() }, [])

  if (!status) return <div className="min-h-screen bg-ink grid place-items-center"><Loader2 className="animate-spin text-slate-500" /></div>

  // Any account can become a creator — show onboarding until they switch it on.
  if (!status.is_creator) return <BecomeCreator status={status} onDone={load} nav={nav} />

  const canSell = !!status.can_sell

  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-4" data-testid="hub-back"><ArrowLeft size={18} /> Back</button>
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-2xl font-bold">Creator Hub</h1>
          {status.creator_type && <span className="text-xs px-2 py-0.5 rounded-full bg-brand/20 text-brand font-semibold" data-testid="hub-creator-type">{CREATOR_TYPE_META[status.creator_type]?.icon} {CREATOR_TYPE_META[status.creator_type]?.label || status.creator_type}</span>}
          {status.account_nsfw && <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-semibold">18+ Adult</span>}
        </div>

        {!canSell && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 my-4 flex items-start gap-3" data-testid="hub-verify-banner">
            <ShieldAlert className="text-amber-400 shrink-0 mt-0.5" size={20} />
            <div className="flex-1">
              <div className="font-semibold text-amber-200 text-sm">Verify to start selling</div>
              <p className="text-xs text-slate-400 mt-0.5">Set up your Inner Circle now. To actually receive payments, prove your identity and age (18+).</p>
              <button onClick={() => nav('/verify')} className="mt-2 px-4 py-1.5 rounded-lg bg-amber-500 text-black font-semibold text-xs" data-testid="hub-go-verify">Get verified</button>
            </div>
          </div>
        )}

        <div className="flex gap-1 mb-5 bg-panel border border-edge rounded-xl p-1 overflow-x-auto no-scrollbar mt-4">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} data-testid={`hub-tab-${t}`}
              className={`flex-1 min-w-[80px] capitalize text-sm font-semibold py-2 rounded-lg transition ${tab === t ? 'bg-brand text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              {t}
            </button>
          ))}
        </div>
        {tab === 'settings'
          ? <CreatorSettings status={status} onChange={load} nav={nav} />
          : tab === 'health'
            ? <CreatorHealth />
            : !canSell
              ? <LockedSell nav={nav} />
              : (<>
                  {tab === 'overview' && <Overview />}
                  {tab === 'subscribers' && <Subscribers />}
                  {tab === 'shop' && <Shop />}
                  {tab === 'finance' && <Finance />}
                </>)}
      </div>
    </div>
  )
}

function LockedSell({ nav }: { nav: any }) {
  return (
    <div className="bg-panel border border-edge rounded-2xl p-8 text-center" data-testid="hub-locked">
      <Lock className="mx-auto text-slate-400 mb-3" size={32} />
      <h2 className="text-lg font-bold mb-1">Verify to unlock this</h2>
      <p className="text-sm text-slate-400 mb-5">Earnings, subscribers, shop and payouts unlock once your identity and age are verified.</p>
      <button onClick={() => nav('/verify')} className="px-5 py-2.5 rounded-xl bg-brand text-white font-semibold" data-testid="locked-go-verify">Get verified</button>
    </div>
  )
}

function BecomeCreator({ status, onDone, nav }: { status: any; onDone: () => void; nav: any }) {
  const [type, setType] = useState<string>('')
  const [busy, setBusy] = useState(false)
  // The adult category is hidden inside the native app (adult content is web-only).
  // On web it's always listed; age verification (18+) is enforced by the backend on enable.
  const types = (status.creator_types || Object.keys(CREATOR_TYPE_META)).filter((t: string) => t !== 'adult' || !isNative)
  const enable = async () => {
    setBusy(true)
    try { await api.creatorEnable({ enabled: true, creator_type: type || undefined }); onDone() }
    catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <div className="max-w-lg mx-auto px-4 py-6">
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-6" data-testid="hub-back"><ArrowLeft size={18} /> Back</button>
        <div className="bg-panel border border-edge rounded-2xl p-6" data-testid="become-creator">
          <Sparkles className="text-brand mb-3" size={30} />
          <h1 className="text-xl font-bold mb-1">Become a creator</h1>
          <p className="text-sm text-slate-400 mb-5">Open a creator account to sell an Inner Circle membership, tips and a shop. Anyone can set up — you'll verify before you can get paid.</p>
          <div className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">Pick your category</div>
          <div className="grid grid-cols-2 gap-2 mb-5">
            {types.map((t: string) => (
              <button key={t} onClick={() => setType(t)} data-testid={`creator-type-${t}`}
                className={`flex items-center gap-2 px-3 py-3 rounded-xl border text-sm font-medium transition ${type === t ? 'border-brand bg-brand/10 text-white' : 'border-edge text-slate-300 hover:border-brand/40'}`}>
                <span className="text-lg">{CREATOR_TYPE_META[t]?.icon}</span>{CREATOR_TYPE_META[t]?.label || t}
                {type === t && <Check size={16} className="ml-auto text-brand" />}
              </button>
            ))}
          </div>
          <button onClick={enable} disabled={busy || !type} className="w-full py-3 rounded-xl bg-brand text-white font-semibold disabled:opacity-50" data-testid="become-creator-btn">{busy ? 'Setting up…' : 'Open creator account'}</button>
        </div>
      </div>
    </div>
  )
}

function CreatorSettings({ status, onChange, nav }: { status: any; onChange: () => void; nav: any }) {
  const [price, setPrice] = useState<number>(status.inner_circle_price ?? 15)
  const [icEnabled, setIcEnabled] = useState<boolean>(status.inner_circle_enabled ?? true)
  const [tips, setTips] = useState<boolean>(status.accepts_tips ?? true)
  const [type, setType] = useState<string>(status.creator_type || '')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const min = status.inner_circle_min ?? 10, max = status.inner_circle_max ?? 50
  const types = (status.creator_types || Object.keys(CREATOR_TYPE_META)).filter((t: string) => t !== 'adult' || !isNative)

  const save = async () => {
    setBusy(true); setSaved(false)
    try {
      if (type && type !== status.creator_type) await api.creatorEnable({ creator_type: type })
      await api.setCreatorOffers({ inner_circle_enabled: icEnabled, inner_circle_price: price, accepts_tips: tips })
      setSaved(true); onChange()
    } catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }

  const goAdult = async () => {
    if (!confirm('Label your account as Adult (18+/NSFW)? Adult content is web-only and never shown in the mobile app. This routes payments through an adult-friendly processor.')) return
    try { await api.accountNsfwFlip(); onChange() }
    catch (e: any) { alert(e.message) }
  }

  return (
    <div className="space-y-4" data-testid="hub-settings">
      {/* Category */}
      <div className="bg-panel border border-edge rounded-2xl p-4">
        <div className="font-semibold mb-3">Creator category</div>
        <div className="grid grid-cols-2 gap-2">
          {types.map((t: string) => (
            <button key={t} onClick={() => setType(t)} data-testid={`settings-type-${t}`}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm font-medium transition ${type === t ? 'border-brand bg-brand/10 text-white' : 'border-edge text-slate-300 hover:border-brand/40'}`}>
              <span>{CREATOR_TYPE_META[t]?.icon}</span>{CREATOR_TYPE_META[t]?.label || t}
            </button>
          ))}
        </div>
      </div>

      {/* Inner Circle single price */}
      <div className="bg-panel border border-edge rounded-2xl p-4">
        <div className="flex items-center justify-between mb-1">
          <div className="font-semibold">Inner Circle membership</div>
          <Toggle on={icEnabled} onChange={setIcEnabled} testid="settings-ic-enabled" />
        </div>
        <p className="text-xs text-slate-500 mb-3">One monthly price you set — anywhere from £{min} to £{max}. No tiers.</p>
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-brand w-20">£{Number(price).toFixed(2)}</span>
          <input type="range" min={min} max={max} step={1} value={price} disabled={!icEnabled}
            onChange={e => setPrice(parseFloat(e.target.value))} className="flex-1 accent-brand" data-testid="settings-ic-price" />
        </div>
        <div className="flex items-center gap-2 mt-3">
          <span className="text-xs text-slate-400">Exact £</span>
          <input inputMode="decimal" value={price} disabled={!icEnabled}
            onChange={e => setPrice(Math.min(max, Math.max(min, parseFloat(e.target.value) || min)))}
            className="w-24 bg-ink border border-edge rounded-lg px-2 py-1 text-sm outline-none focus:border-brand" />
          <span className="text-xs text-slate-500">/ month</span>
        </div>
      </div>

      {/* Tips */}
      <div className="bg-panel border border-edge rounded-2xl p-4 flex items-center justify-between">
        <div><div className="font-semibold">Accept tips</div><div className="text-xs text-slate-500">Let fans send one-off tips.</div></div>
        <Toggle on={tips} onChange={setTips} testid="settings-tips" />
      </div>

      <button onClick={save} disabled={busy} className="w-full py-3 rounded-xl bg-brand text-white font-semibold disabled:opacity-50" data-testid="settings-save">
        {busy ? 'Saving…' : saved ? 'Saved ✓' : 'Save changes'}
      </button>

      {/* Adult content — WEB ONLY. Never rendered inside the native app. */}
      {!isNative && (
        <div className="bg-panel border border-rose-500/30 rounded-2xl p-4" data-testid="hub-adult-section">
          <div className="flex items-center gap-2 mb-1"><ShieldAlert className="text-rose-400" size={18} /><span className="font-semibold text-rose-200">Adult content (18+)</span></div>
          {status.account_nsfw ? (
            <p className="text-xs text-slate-400">Your account is labelled <span className="text-rose-300 font-semibold">Adult / NSFW</span>. NSFW content is shown on the web only — never in the mobile app — and is hidden from minors. Label individual posts as NSFW when you create them.</p>
          ) : (
            <>
              <p className="text-xs text-slate-400 mb-3">Creators of adult content must label their account. NSFW stays web-only and hidden from minors. Fans can still see your SFW content in the app. Requires age verification (18+).</p>
              {status.is_age_verified_adult
                ? <button onClick={goAdult} className="px-4 py-2 rounded-lg bg-rose-500/20 text-rose-200 font-semibold text-sm border border-rose-500/40" data-testid="hub-go-adult">Label my account Adult (18+)</button>
                : <button onClick={() => nav('/verify')} className="px-4 py-2 rounded-lg border border-edge text-slate-300 font-semibold text-sm" data-testid="hub-adult-verify">Verify age to enable</button>}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Toggle({ on, onChange, testid }: { on: boolean; onChange: (v: boolean) => void; testid?: string }) {
  return (
    <button onClick={() => onChange(!on)} data-testid={testid}
      className={`w-11 h-6 rounded-full transition relative shrink-0 ${on ? 'bg-brand' : 'bg-edge'}`}>
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${on ? 'left-[22px]' : 'left-0.5'}`} />
    </button>
  )
}

function Loading() { return <div className="grid place-items-center py-16"><Loader2 className="animate-spin text-slate-500" /></div> }

function Stat({ label, value, sub }: { label: string; value: string; sub?: React.ReactNode }) {
  return (
    <div className="bg-panel border border-edge rounded-2xl p-4">
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className="text-xl font-bold">{value}</div>
      {sub && <div className="text-xs mt-0.5">{sub}</div>}
    </div>
  )
}

function Overview() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.creatorOverview().then(setD).catch(() => setD({})) }, [])
  if (!d) return <Loading />
  const g = d.growth_pct
  return (
    <div className="grid grid-cols-2 gap-3" data-testid="hub-overview">
      <Stat label="Revenue this month" value={money(d.revenue_this_month, d.currency)}
        sub={g != null && <span className={`inline-flex items-center gap-1 ${g >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{g >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}{Math.abs(g)}% vs last month</span>} />
      <Stat label="Pending payout" value={money(d.pending_payout, d.currency)} />
      <Stat label="New subscriptions" value={String(d.new_subs_this_month)} />
      <Stat label="Tips this month" value={money(d.tips_this_month, d.currency)} />
      <Stat label="Active subscribers" value={String(d.active_subscribers)} />
      <Stat label="Last month" value={money(d.revenue_last_month, d.currency)} />
    </div>
  )
}

function Subscribers() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.creatorSubscribers().then(setD).catch(() => setD({ subscribers: [] })) }, [])
  if (!d) return <Loading />
  return (
    <div data-testid="hub-subscribers">
      <div className="grid grid-cols-3 gap-3 mb-4">
        <Stat label="Active" value={String(d.active)} />
        <Stat label="Churn (mo)" value={String(d.churn_this_month)} />
        <Stat label="Renewals (mo)" value={String(d.renewals_this_month)} />
      </div>
      <div className="bg-panel border border-edge rounded-2xl divide-y divide-edge">
        {(d.subscribers || []).length === 0 && <div className="p-5 text-sm text-slate-400 text-center">No subscribers yet.</div>}
        {(d.subscribers || []).map((s: any, i: number) => (
          <div key={i} className="p-3 flex items-center gap-3">
            <Users size={16} className="text-slate-400" />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">{s.buyer_name} <span className="text-slate-500">#{s.buyer_handle}</span></div>
              <div className="text-xs text-slate-400">Inner Circle · {money(s.price)}/mo · {s.psp}</div>
            </div>
            <span className={`text-xs font-medium ${s.status === 'active' ? 'text-emerald-400' : 'text-slate-500'}`}>{s.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Shop() {
  const [d, setD] = useState<any>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<any>({ title: '', kind: 'digital', price: '', download_url: '' })
  const [busy, setBusy] = useState(false)
  const load = () => api.creatorShop().then(setD).catch(() => setD({ products: [], orders: [] }))
  useEffect(() => { load() }, [])
  const add = async () => {
    setBusy(true)
    try { await api.shopCreateProduct({ ...form, price: parseFloat(form.price) }); setAdding(false); setForm({ title: '', kind: 'digital', price: '', download_url: '' }); await load() }
    catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }
  const del = async (id: string) => { try { await api.shopDeleteProduct(id); await load() } catch (e: any) { alert(e.message) } }
  if (!d) return <Loading />
  return (
    <div data-testid="hub-shop">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Products</h2>
        <button onClick={() => setAdding(a => !a)} className="flex items-center gap-1 text-sm text-brand font-semibold" data-testid="hub-add-product"><Plus size={16} /> Add</button>
      </div>
      {adding && (
        <div className="bg-panel border border-edge rounded-2xl p-4 mb-3 space-y-2" data-testid="hub-product-form">
          <input placeholder="Title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
          <div className="flex gap-2">
            {['digital', 'physical'].map(k => (
              <button key={k} onClick={() => setForm({ ...form, kind: k })} className={`flex-1 text-xs py-2 rounded-lg border capitalize ${form.kind === k ? 'bg-brand/20 border-brand/40 text-brand' : 'border-edge text-slate-400'}`}>{k}{k === 'physical' ? ' (Printful)' : ''}</button>
            ))}
          </div>
          <input placeholder="Price (£, VAT-inclusive)" inputMode="decimal" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
          {form.kind === 'digital'
            ? <input placeholder="Download URL" value={form.download_url} onChange={e => setForm({ ...form, download_url: e.target.value })} className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />
            : <input placeholder="Printful variant ID" value={form.printful_variant_id || ''} onChange={e => setForm({ ...form, printful_variant_id: e.target.value })} className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand" />}
          <button onClick={add} disabled={busy || !form.title || !form.price} className="w-full py-2 rounded-xl bg-brand text-white font-semibold text-sm disabled:opacity-50">{busy ? 'Saving…' : 'Save product'}</button>
        </div>
      )}
      <div className="space-y-2 mb-5">
        {(d.products || []).length === 0 && <div className="text-sm text-slate-400 text-center py-4">No products yet.</div>}
        {(d.products || []).map((p: any) => (
          <div key={p.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3">
            <Store size={16} className="text-slate-400" />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">{p.title}</div>
              <div className="text-xs text-slate-400 capitalize">{p.kind} · {money(p.price)}</div>
            </div>
            <button onClick={() => del(p.id)} className="text-slate-500 hover:text-rose-400"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      <h2 className="font-semibold mb-2">Orders</h2>
      <div className="bg-panel border border-edge rounded-2xl divide-y divide-edge">
        {(d.orders || []).length === 0 && <div className="p-5 text-sm text-slate-400 text-center">No orders yet.</div>}
        {(d.orders || []).map((o: any) => (
          <div key={o.id} className="p-3 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">{o.title || 'Order'}</div>
              <div className="text-xs text-slate-400">{money(o.gross)} · {o.kind}</div>
            </div>
            <span className="text-xs text-sky-400">{o.fulfilment_status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Finance() {
  const [d, setD] = useState<any>(null)
  const [pay, setPay] = useState<any>(null)
  const [docs, setDocs] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [savingSched, setSavingSched] = useState(false)
  const load = () => { api.creatorFinance().then(setD).catch(() => setD({ totals: {}, by_stream: {}, transactions: [] })); api.creatorPayouts().then(setPay).catch(() => setPay({})); api.creatorTaxDocs().then(setDocs).catch(() => setDocs({ tax_documents: [] })) }
  useEffect(() => { load() }, [])
  const requestPayout = async () => {
    setBusy(true)
    try {
      const r = await api.requestPayout()
      if (r.kyc_required) { if (r.kyc_url) window.open(r.kyc_url, '_blank'); alert('Complete payout KYC with the processor to receive your first payout.') }
      else alert('Payout requested.')
      await load()
    } catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }
  const setSchedule = async (schedule: string, threshold?: number) => {
    setSavingSched(true)
    try { await api.setPayoutSettings({ schedule, ...(threshold != null ? { threshold } : {}) }); await load() }
    catch (e: any) { alert(e.message) } finally { setSavingSched(false) }
  }
  if (!d || !pay) return <Loading />
  const t = d.totals || {}
  const streams = d.by_stream || {}
  const STREAM_META: Record<string, { label: string; icon: any }> = {
    inner_circle: { label: 'Inner Circle', icon: Users }, tip: { label: 'Tips', icon: Sparkles },
    shop: { label: 'Shop', icon: Store }, sponsored: { label: 'Sponsored', icon: TrendingUp },
  }
  const schedules: string[] = pay.schedules || ['weekly', 'monthly', 'threshold']
  const thMin = pay.threshold_min ?? 25
  return (
    <div data-testid="hub-finance" className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Gross" value={money(t.gross, d.currency)} />
        <Stat label="VAT (Skali remits)" value={money(t.vat, d.currency)} />
        <Stat label="Processing (PSP)" value={money(t.psp_fee, d.currency)} />
        <Stat label="Skali fee" value={money(t.skali_fee, d.currency)} />
      </div>
      <div className="bg-panel border border-edge rounded-2xl p-4">
        <div className="text-xs text-slate-400">Your net earnings</div>
        <div className="text-2xl font-bold text-emerald-400">{money(t.creator_net, d.currency)}</div>
        <div className="text-xs text-slate-500 mt-1">{d.note}</div>
      </div>

      {/* Earnings by revenue stream — platform fee vs creator net, per PDF §7 */}
      <div className="bg-panel border border-edge rounded-2xl p-4" data-testid="hub-earnings-streams">
        <div className="font-semibold text-sm mb-3">Earnings by stream</div>
        <div className="space-y-2">
          {Object.keys(STREAM_META).map(k => {
            const s = streams[k] || {}; const M = STREAM_META[k]; const Icon = M.icon
            return (
              <div key={k} className="flex items-center gap-3 text-sm" data-testid={`stream-${k}`}>
                <Icon size={15} className="text-slate-400 shrink-0" />
                <div className="flex-1 min-w-0"><span className="font-medium">{M.label}</span></div>
                <div className="text-right">
                  <div className="text-slate-300">{money(s.gross || 0, d.currency)} <span className="text-slate-500 text-xs">gross</span></div>
                  <div className="text-xs"><span className="text-slate-500">fee {money((s.skali_fee || 0) + (s.psp_fee || 0), d.currency)}</span> · <span className="text-emerald-400">net {money(s.creator_net || 0, d.currency)}</span></div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-panel border border-edge rounded-2xl p-4" data-testid="hub-payouts">
        <div className="flex items-center gap-2 mb-3"><Wallet size={16} className="text-brand" /><span className="font-semibold">Payouts</span>
          <span className="ml-auto text-xs text-slate-400 capitalize">{pay.schedule}</span></div>
        <div className="grid grid-cols-3 gap-2 mb-3 text-center">
          <div><div className="text-xs text-slate-400">Pending</div><div className="font-bold text-amber-400">{money(pay.pending, pay.currency)}</div></div>
          <div><div className="text-xs text-slate-400">Available</div><div className="font-bold">{money(pay.available, pay.currency)}</div></div>
          <div><div className="text-xs text-slate-400">Paid</div><div className="font-bold text-emerald-400">{money(pay.paid, pay.currency)}</div></div>
        </div>

        {/* Payout schedule controls — weekly / monthly / threshold (min £25) */}
        <div className="mb-3">
          <div className="text-xs text-slate-400 mb-1.5 flex items-center gap-1"><CalendarClock size={13} /> Payout schedule</div>
          <div className="grid grid-cols-3 gap-1.5">
            {schedules.map(s => (
              <button key={s} disabled={savingSched}
                onClick={() => setSchedule(s, s === 'threshold' ? (pay.threshold || thMin) : undefined)}
                data-testid={`payout-schedule-${s}`}
                className={`text-xs font-semibold py-2 rounded-lg border capitalize transition ${pay.schedule === s ? 'bg-brand text-white border-brand' : 'border-edge text-slate-400 hover:border-brand/40'}`}>
                {s}
              </button>
            ))}
          </div>
          {pay.schedule === 'threshold' && (
            <div className="flex items-center gap-2 mt-2" data-testid="payout-threshold-row">
              <span className="text-xs text-slate-400">Pay out at</span>
              <span className="text-sm font-bold text-brand">{money(pay.threshold || thMin, pay.currency)}</span>
              <input type="range" min={thMin} max={thMin * 20} step={5} value={pay.threshold || thMin} disabled={savingSched}
                onChange={e => setPay({ ...pay, threshold: parseFloat(e.target.value) })}
                onMouseUp={e => setSchedule('threshold', parseFloat((e.target as HTMLInputElement).value))}
                onTouchEnd={e => setSchedule('threshold', parseFloat((e.target as HTMLInputElement).value))}
                className="flex-1 accent-brand" data-testid="payout-threshold" />
              <span className="text-[10px] text-slate-500">min {money(thMin, pay.currency)}</span>
            </div>
          )}
        </div>

        {pay.payout_review_flag && <div className="text-xs text-rose-400 mb-2">Payouts paused — account under review after repeated chargebacks.</div>}
        {pay.payout_kyc?.status !== 'verified' && <div className="text-xs text-amber-400 mb-2">Payout KYC: {pay.payout_kyc?.status || 'unverified'} — required before your first payout.</div>}
        <button onClick={requestPayout} disabled={busy} className="w-full py-2.5 rounded-xl bg-brand text-white font-semibold text-sm disabled:opacity-50" data-testid="hub-request-payout">{busy ? 'Working…' : 'Request payout'}</button>
      </div>

      {/* Payout history */}
      <div data-testid="hub-payout-history">
        <div className="font-semibold text-sm mb-2">Payout history</div>
        <div className="bg-panel border border-edge rounded-2xl divide-y divide-edge">
          {(pay.history || []).length === 0 && <div className="p-4 text-sm text-slate-400 text-center">No payouts yet.</div>}
          {(pay.history || []).map((p: any) => (
            <div key={p.id} className="p-3 flex items-center gap-3 text-sm">
              <Wallet size={15} className="text-slate-400" />
              <div className="flex-1 min-w-0"><div className="font-medium">{money(p.amount, p.currency)}</div><div className="text-xs text-slate-500">{(p.created_at || '').slice(0, 10)} · {p.psp}</div></div>
              <span className={`text-xs font-medium ${p.status === 'paid' ? 'text-emerald-400' : 'text-amber-400'}`}>{p.status}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={() => downloadFile(api.financeCsvUrl(), 'skali-earnings.csv')} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-edge text-sm font-semibold hover:bg-white/5" data-testid="hub-export-csv"><Download size={16} /> Export CSV</button>
        <button onClick={() => downloadFile(api.financePdfUrl(), 'skali-earnings.pdf')} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-edge text-sm font-semibold hover:bg-white/5" data-testid="hub-export-pdf"><FileText size={16} /> Export PDF</button>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-2"><FileText size={16} className="text-slate-400" /><span className="font-semibold text-sm">Tax statements (issued by Skali)</span></div>
        <div className="bg-panel border border-edge rounded-2xl divide-y divide-edge">
          {(docs?.tax_documents || []).length === 0 && <div className="p-4 text-sm text-slate-400 text-center">No statements yet.</div>}
          {(docs?.tax_documents || []).map((m: any) => (
            <div key={m.month} className="p-3 flex items-center gap-3 text-sm">
              <div className="flex-1"><div className="font-medium">{m.month}</div><div className="text-xs text-slate-500">{m.statement_id}</div></div>
              <div className="text-right text-xs text-slate-400">Net {money(m.creator_net)}<br />VAT {money(m.vat)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function CreatorHealth() {
  const [d, setD] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const load = () => api.creatorHealth().then(setD).catch(() => setD({ settings: { collection_enabled: true, hidden: false }, collecting: true, metrics: {} }))
  useEffect(() => { load() }, [])
  const setSetting = async (patch: any) => {
    setBusy(true)
    try { await api.setHealthSettings(patch); await load() }
    catch (e: any) { alert(e.message) } finally { setBusy(false) }
  }
  if (!d) return <Loading />
  const s = d.settings || {}
  const m = d.metrics || {}
  const collecting = !!d.collecting
  const hidden = !!s.hidden

  return (
    <div className="space-y-4" data-testid="hub-health">
      <div className="bg-panel border border-edge rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-1"><HeartPulse className="text-brand" size={18} /><span className="font-semibold">Creator Health</span></div>
        <p className="text-xs text-slate-500">Optional analytics to help you understand retention and engagement. This is a support tool — <span className="text-slate-300">never a score</span> and it never affects your account standing.</p>
      </div>

      {/* Wellbeing controls */}
      <div className="bg-panel border border-edge rounded-2xl p-4 space-y-3" data-testid="health-controls">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2"><Power size={15} className="text-slate-400" /><div><div className="font-medium text-sm">Collect metrics</div><div className="text-xs text-slate-500">Turning off stops future collection. Past data is kept.</div></div></div>
          <Toggle on={collecting} onChange={(v) => setSetting({ collection_enabled: v })} testid="health-collection-toggle" />
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">{hidden ? <EyeOff size={15} className="text-slate-400" /> : <Eye size={15} className="text-slate-400" />}<div><div className="font-medium text-sm">Show metrics in the Hub</div><div className="text-xs text-slate-500">Hide the numbers without stopping collection.</div></div></div>
          <Toggle on={!hidden} onChange={(v) => setSetting({ hidden: !v })} testid="health-hidden-toggle" />
        </div>
      </div>

      {!collecting ? (
        <div className="bg-panel border border-edge rounded-2xl p-6 text-center text-sm text-slate-400" data-testid="health-off">
          <Power className="mx-auto mb-2 text-slate-500" size={26} />
          {d.note || 'Collection is off. Turn it back on any time — no penalty.'}
        </div>
      ) : hidden ? (
        <div className="bg-panel border border-edge rounded-2xl p-6 text-center text-sm text-slate-400" data-testid="health-hidden">
          <EyeOff className="mx-auto mb-2 text-slate-500" size={26} />
          Metrics are hidden. Toggle "Show metrics" to view them.
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3" data-testid="health-metrics">
          <HealthStat icon={Repeat} label="Returning subscribers" value={String(m.returning_subscribers ?? 0)} />
          <HealthStat icon={TrendingUp} label="Renewal rate" value={pct(m.renewal_rate)} />
          <HealthStat icon={Users} label="Retention" value={pct(m.retention)} />
          <HealthStat icon={MessageCircle} label="Inner Circle messages" value={String(m.inner_circle_messages ?? 0)} />
          <HealthStat icon={Users} label="Active subscribers" value={String(m.active_subscribers ?? 0)} />
          <HealthStat icon={TrendingDown} label="Churn (this month)" value={String(m.churn_this_month ?? 0)} />
          <div className="col-span-2 bg-panel border border-edge rounded-2xl p-4 flex items-center gap-3">
            <div className="flex-1"><div className="text-xs text-slate-400">Average watch time</div><div className="text-sm text-slate-500 mt-0.5">Available once viewing data is collected.</div></div>
            <span className="text-slate-500 font-bold">—</span>
          </div>
        </div>
      )}
      <p className="text-[11px] text-slate-600 text-center px-4">{d.note}</p>
    </div>
  )
}

function HealthStat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="bg-panel border border-edge rounded-2xl p-4">
      <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1"><Icon size={13} />{label}</div>
      <div className="text-xl font-bold">{value}</div>
    </div>
  )
}
