import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, TrendingUp, TrendingDown, Users, Store, Wallet, Lock, Plus, Trash2, Download, FileText, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

const TABS = ['overview', 'subscribers', 'shop', 'finance'] as const
type Tab = typeof TABS[number]
const money = (n: number, ccy = 'GBP') => `${ccy === 'GBP' ? '£' : ''}${Number(n || 0).toFixed(2)}`

export default function CreatorHub() {
  const nav = useNavigate()
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('overview')
  const unlocked = !!(user as any)?.monetisation_enabled

  if (!unlocked) {
    return (
      <div className="min-h-screen bg-ink text-slate-100">
        <div className="max-w-lg mx-auto px-4 py-6">
          <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-6" data-testid="hub-back"><ArrowLeft size={18} /> Back</button>
          <div className="bg-panel border border-edge rounded-2xl p-8 text-center" data-testid="hub-locked">
            <Lock className="mx-auto text-slate-400 mb-3" size={32} />
            <h1 className="text-xl font-bold mb-1">Creator Hub is locked</h1>
            <p className="text-sm text-slate-400 mb-5">Verify your identity and age to unlock subscriptions, tips, your shop and payouts.</p>
            <button onClick={() => nav('/verify')} className="px-5 py-2.5 rounded-xl bg-brand text-white font-semibold" data-testid="hub-go-verify">Get verified</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-ink text-slate-100">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-4" data-testid="hub-back"><ArrowLeft size={18} /> Back</button>
        <h1 className="text-2xl font-bold mb-4">Creator Hub</h1>
        <div className="flex gap-1 mb-5 bg-panel border border-edge rounded-xl p-1 overflow-x-auto no-scrollbar">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} data-testid={`hub-tab-${t}`}
              className={`flex-1 min-w-[84px] capitalize text-sm font-semibold py-2 rounded-lg transition ${tab === t ? 'bg-brand text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              {t}
            </button>
          ))}
        </div>
        {tab === 'overview' && <Overview />}
        {tab === 'subscribers' && <Subscribers />}
        {tab === 'shop' && <Shop />}
        {tab === 'finance' && <Finance />}
      </div>
    </div>
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
              <div className="text-xs text-slate-400">Tier {s.tier} · {money(s.price)} · {s.psp}</div>
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
  const load = () => { api.creatorFinance().then(setD).catch(() => setD({ totals: {}, transactions: [] })); api.creatorPayouts().then(setPay).catch(() => setPay({})); api.creatorTaxDocs().then(setDocs).catch(() => setDocs({ tax_documents: [] })) }
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
  if (!d || !pay) return <Loading />
  const t = d.totals || {}
  return (
    <div data-testid="hub-finance" className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Gross" value={money(t.gross)} />
        <Stat label="VAT (Skali remits)" value={money(t.vat)} />
        <Stat label="Processing (PSP)" value={money(t.psp_fee)} />
        <Stat label="Skali fee" value={money(t.skali_fee)} />
      </div>
      <div className="bg-panel border border-edge rounded-2xl p-4">
        <div className="text-xs text-slate-400">Your net earnings</div>
        <div className="text-2xl font-bold text-emerald-400">{money(t.creator_net)}</div>
        <div className="text-xs text-slate-500 mt-1">{d.note}</div>
      </div>

      <div className="bg-panel border border-edge rounded-2xl p-4" data-testid="hub-payouts">
        <div className="flex items-center gap-2 mb-3"><Wallet size={16} className="text-brand" /><span className="font-semibold">Payouts</span>
          <span className="ml-auto text-xs text-slate-400 capitalize">{pay.schedule}</span></div>
        <div className="grid grid-cols-3 gap-2 mb-3 text-center">
          <div><div className="text-xs text-slate-400">Pending</div><div className="font-bold text-amber-400">{money(pay.pending, pay.currency)}</div></div>
          <div><div className="text-xs text-slate-400">Available</div><div className="font-bold">{money(pay.available, pay.currency)}</div></div>
          <div><div className="text-xs text-slate-400">Paid</div><div className="font-bold text-emerald-400">{money(pay.paid, pay.currency)}</div></div>
        </div>
        {pay.payout_review_flag && <div className="text-xs text-rose-400 mb-2">Payouts paused — account under review after repeated chargebacks.</div>}
        {pay.payout_kyc?.status !== 'verified' && <div className="text-xs text-amber-400 mb-2">Payout KYC: {pay.payout_kyc?.status || 'unverified'} — required before your first payout.</div>}
        <button onClick={requestPayout} disabled={busy} className="w-full py-2.5 rounded-xl bg-brand text-white font-semibold text-sm disabled:opacity-50" data-testid="hub-request-payout">{busy ? 'Working…' : 'Request payout'}</button>
      </div>

      <div className="flex gap-2">
        <a href={api.financeCsvUrl()} target="_blank" rel="noreferrer" className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-edge text-sm font-semibold hover:bg-white/5" data-testid="hub-export-csv"><Download size={16} /> Export CSV</a>
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
