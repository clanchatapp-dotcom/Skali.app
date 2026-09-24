import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings as SettingsIcon, ShieldCheck, MessageCircle, LogOut, Trash2, Loader2, Check, Plus, User as UserIcon, AlertTriangle, Lock, Flame, Sparkles, MessageSquare, Swords, Pill, Eye, KeyRound, Sun, Moon, Type, Bell, Users2, ChevronRight, Palette } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Avatar } from '../lib/ui'
import AccountBadge, { ACCOUNT_META } from '../components/AccountBadge'
import RoleBadge, { ROLE_META } from '../components/RoleBadge'
import { applyTheme, ACCENTS } from '../lib/theme'

function Toggle({ on, onChange, disabled, accent = 'brand' }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean; accent?: 'brand' | 'amber' }) {
  const onColor = accent === 'amber' ? 'bg-amber-500' : 'bg-brand'
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${on ? onColor : 'bg-white/15'} ${disabled ? 'opacity-50' : ''}`}
    >
      <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${on ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

const CZ_DEFAULTS: Record<string, boolean> = { nsfw: false, ai: true, language: true, violence: false, drugs: false }
const CZ_ITEMS = [
  { key: 'nsfw', label: 'NSFW', desc: 'Nudity and sexual content.', Icon: Flame },
  { key: 'ai', label: 'AI content', desc: 'Posts made with or about AI tools.', Icon: Sparkles },
  { key: 'language', label: 'Strong language', desc: 'Swearing and crude humour.', Icon: MessageSquare },
  { key: 'violence', label: 'Violence & gore', desc: 'Graphic injury, fights, blood.', Icon: Swords },
  { key: 'drugs', label: 'Drugs & alcohol', desc: 'Recreational substance use.', Icon: Pill },
]

const NP_DEFAULTS: Record<string, boolean> = { follows: true, wall: true, reactions: true, comments: true, dms: true, inner: true }
const NP_ITEMS = [
  { key: 'follows', label: 'Follows', desc: 'New followers and follow requests.' },
  { key: 'inner', label: 'Inner Circle invites', desc: 'When someone invites or joins your circle.' },
  { key: 'wall', label: 'Wall posts', desc: 'When someone posts on your wall.' },
  { key: 'reactions', label: 'Reactions & likes', desc: 'Reactions on your posts.' },
  { key: 'comments', label: 'Comments', desc: 'Replies and comments on your posts.' },
  { key: 'dms', label: 'Direct messages', desc: 'Activity from your conversations.' },
]

const FONT_OPTS = [{ key: 'small', label: 'Small' }, { key: 'normal', label: 'Default' }, { key: 'large', label: 'Large' }]

export default function Settings() {
  const { user, logout, refresh } = useAuth()
  const nav = useNavigate()
  const [p, setP] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [savedName, setSavedName] = useState(false)
  const [realName, setRealName] = useState('')
  const [savedRN, setSavedRN] = useState(false)
  const [uname, setUname] = useState('')
  const [unameBusy, setUnameBusy] = useState(false)
  const [unameErr, setUnameErr] = useState<string | null>(null)
  const [bio, setBio] = useState('')
  const [savedBio, setSavedBio] = useState(false)
  const [links, setLinks] = useState<string[]>([])
  const [savedLinks, setSavedLinks] = useState(false)
  const [curPw, setCurPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confPw, setConfPw] = useState('')
  const [pwMsg, setPwMsg] = useState<{ ok?: boolean; text: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)

  const load = async () => {
    try { const me = await api.me(); setP(me); setName(me.display_name || ''); setRealName(me.real_name || ''); setUname(me.handle || ''); setBio(me.bio || ''); setLinks(Array.isArray(me.links) ? me.links : []) } catch {}
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const setPref = async (key: string, value: any) => {
    setP((prev: any) => ({ ...prev, [key]: value }))
    setSaving(key)
    try { await api.updateProfile({ [key]: value }); await refresh() } catch {}
    setSaving(null)
  }

  const cz = { ...CZ_DEFAULTS, ...(p?.comfort_zone || {}) }
  const setCZ = async (key: string, value: boolean) => {
    const next = { ...cz, [key]: value }
    setP((prev: any) => ({ ...prev, comfort_zone: next }))
    setSaving('cz:' + key)
    try { await api.updateProfile({ comfort_zone: next }) } catch {}
    setSaving(null)
  }

  const setDisplay = async (key: string, value: string) => {
    const next = { ...p, [key]: value }
    setP(next)
    applyTheme({ theme: next.theme, accent: next.accent, font_size: next.font_size })
    setSaving(key)
    try { await api.updateProfile({ [key]: value }); await refresh() } catch {}
    setSaving(null)
  }

  const np = { ...NP_DEFAULTS, ...(p?.notif_prefs || {}) }
  const setNotif = async (key: string, value: boolean) => {
    const next = { ...np, [key]: value }
    setP((prev: any) => ({ ...prev, notif_prefs: next }))
    setSaving('np:' + key)
    try { await api.updateProfile({ notif_prefs: next }) } catch {}
    setSaving(null)
  }

  const saveName = async () => {
    const v = name.trim()
    if (!v || v === p?.display_name) return
    setSaving('display_name')
    try { await api.updateProfile({ display_name: v }); await refresh(); setSavedName(true); setTimeout(() => setSavedName(false), 1500) } catch {}
    setSaving(null)
  }

  const saveRealName = async () => {
    const v = realName.trim()
    if (v === (p?.real_name || '')) return
    setSaving('real_name')
    try { await api.updateProfile({ real_name: v }); setP((prev: any) => ({ ...prev, real_name: v })); setSavedRN(true); setTimeout(() => setSavedRN(false), 1500) } catch {}
    setSaving(null)
  }

  const saveHandle = async () => {
    const h = uname.trim().replace(/^[#@]/, '').toLowerCase()
    setUnameErr(null)
    if (!h || h === p?.handle || h.length < 3) return
    setUnameBusy(true)
    try { await api.changeHandle(h); await refresh(); await load() }
    catch (e: any) { setUnameErr(e?.message || 'Could not change username') }
    finally { setUnameBusy(false) }
  }

  const saveBio = async () => {
    if (bio === (p?.bio || '')) return
    setSaving('bio')
    try { await api.updateProfile({ bio }); await refresh(); setP((prev: any) => ({ ...prev, bio })); setSavedBio(true); setTimeout(() => setSavedBio(false), 1500) }
    catch (e: any) { alert(e?.message || 'Could not save bio') }
    setSaving(null)
  }

  const saveLinks = async () => {
    const clean = links.map(l => l.trim()).filter(Boolean)
    setSaving('links')
    try { await api.updateProfile({ links: clean }); await refresh(); setP((prev: any) => ({ ...prev, links: clean })); setSavedLinks(true); setTimeout(() => setSavedLinks(false), 1500) }
    catch (e: any) { alert(e?.message || 'Could not save links') }
    setSaving(null)
  }

  const doDelete = async () => {
    setDeleting(true)
    try { await api.deleteAccount() } catch {}
    await logout()
    nav('/', { replace: true })
  }

  const changePw = async () => {
    setPwMsg(null)
    if (newPw.length < 6) { setPwMsg({ text: 'New password must be at least 6 characters' }); return }
    if (newPw !== confPw) { setPwMsg({ text: 'New passwords do not match' }); return }
    setSaving('password')
    try { await api.changePassword(curPw, newPw); setPwMsg({ ok: true, text: 'Password updated' }); setCurPw(''); setNewPw(''); setConfPw('') }
    catch (e: any) { setPwMsg({ text: e.message || 'Could not change password' }) }
    setSaving(null)
  }

  type SectionKey = 'profile' | 'email' | 'connections' | 'preferences' | 'notifications' | 'account'
  const [section, setSection] = useState<SectionKey | null>(null)

  if (loading) return <div className="h-full grid place-items-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>

  const SectionPill = ({ id, icon: Icon, title, description }: { id: SectionKey; icon: any; title: string; description: string }) => (
    <button
      type="button"
      onClick={() => setSection(id)}
      className="w-full text-left bg-panel border border-edge rounded-2xl p-4 flex items-center gap-3 hover:bg-white/5 hover:border-brand/30 transition active:scale-[0.99]"
    >
      <span className="h-11 w-11 shrink-0 rounded-xl bg-brand/10 border border-brand/20 grid place-items-center">
        <Icon className="h-5 w-5 text-brand" />
      </span>
      <span className="flex-1 min-w-0">
        <span className="block font-semibold text-white">{title}</span>
        <span className="block text-xs text-slate-500 mt-0.5 truncate">{description}</span>
      </span>
      <ChevronRight className="h-5 w-5 text-slate-500 shrink-0" />
    </button>
  )

  const BackButton = () => (
    <button
      type="button"
      onClick={() => setSection(null)}
      className="flex items-center gap-2 text-slate-300 hover:text-white py-2"
    >
      <span className="text-xl">‹</span>
      <span>Settings</span>
    </button>
  )

  const SectionTitle = ({ title, description }: { title: string; description?: string }) => (
    <div className="mb-5">
      <BackButton />
      <div className="mt-3">
        <h2 className="text-xl font-extrabold">{title}</h2>
        {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
      </div>
    </div>
  )

  const profileSection = (
    <>
      <SectionTitle title="Profile" description="Manage the information shown on your profile." />
      <section className="bg-panel border border-edge rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-5">
          <Avatar id={p?.id || ''} name={p?.display_name || ''} url={p?.avatar_url} size={52} />
          <div className="min-w-0">
            <div className="font-semibold truncate">{p?.display_name}</div>
            <div className="text-xs text-slate-500 truncate">#{p?.handle}</div>
          </div>
        </div>

        <label className="block text-sm text-slate-400 mb-1.5">Username</label>
        <div className="flex gap-2">
          <div className="flex-1 flex items-center bg-black/40 border border-edge rounded-xl px-3 focus-within:border-brand/60">
            <span className="text-slate-500">#</span>
            <input value={uname} onChange={e => { setUname(e.target.value.replace(/[^A-Za-z0-9]/g, '').toLowerCase()); setUnameErr(null) }} maxLength={20} disabled={!!p?.handle_change_available_at} placeholder="username" className="flex-1 bg-transparent py-2.5 outline-none disabled:opacity-60" />
          </div>
          <button onClick={saveHandle} disabled={unameBusy || !!p?.handle_change_available_at || uname === p?.handle || uname.length < 3} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
            {unameBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Change
          </button>
        </div>
        {unameErr ? <p className="text-xs text-rose-400 mt-1.5">{unameErr}</p> : p?.handle_change_available_at ? <p className="text-xs text-amber-400/80 mt-1.5">You can change your username again on {new Date(p.handle_change_available_at).toLocaleDateString()}.</p> : <p className="text-xs text-slate-500 mt-1.5">Once every 60 days. Letters and numbers only.</p>}

        <div className="h-px bg-edge my-4" />

        <label className="block text-sm text-slate-400 mb-1.5">Display name</label>
        <div className="flex gap-2">
          <input value={name} onChange={e => setName(e.target.value)} maxLength={40} className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" placeholder="Your name" />
          <button onClick={saveName} disabled={saving === 'display_name' || !name.trim() || name.trim() === p?.display_name} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
            {saving === 'display_name' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedName ? <Check className="h-4 w-4" /> : null}{savedName ? 'Saved' : 'Save'}
          </button>
        </div>

        <div className="mt-4">
          <label className="block text-sm text-slate-400 mb-1.5">Real name <span className="text-slate-600">(optional)</span></label>
          <div className="flex gap-2">
            <input value={realName} onChange={e => setRealName(e.target.value)} maxLength={60} className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" placeholder="e.g. Alex Morgan" />
            <button onClick={saveRealName} disabled={saving === 'real_name' || realName.trim() === (p?.real_name || '')} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
              {saving === 'real_name' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedRN ? <Check className="h-4 w-4" /> : null}{savedRN ? 'Saved' : 'Save'}
            </button>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <Eye className="h-4 w-4 text-slate-500 shrink-0" />
            <span className="text-xs text-slate-400">Who can see your real name</span>
            <select value={p?.real_name_visibility || 'private'} onChange={e => setPref('real_name_visibility', e.target.value)} className="ml-auto bg-black/40 border border-edge rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-brand/60">
              <option value="private">Only me</option><option value="inner">Inner Circle</option><option value="followers">Followers</option><option value="public">Everyone</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-sm text-slate-400 mb-1.5">Bio <span className="text-slate-600">({(bio || '').length}/{p?.limits?.bio || 150})</span></label>
          <textarea value={bio} onChange={e => setBio(e.target.value)} rows={3} maxLength={p?.limits?.bio || 150} placeholder="Add a bio…" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
          <div className="flex justify-end mt-2"><button onClick={saveBio} disabled={saving === 'bio' || bio === (p?.bio || '')} className="px-4 py-2 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">{saving === 'bio' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedBio ? <Check className="h-4 w-4" /> : null}{savedBio ? 'Saved' : 'Save bio'}</button></div>
        </div>

        <div className="mt-4">
          {(() => { const max = p?.limits?.links || 3; const unlimited = max >= 9999; return (
            <>
              <label className="block text-sm text-slate-400 mb-1.5">Links <span className="text-slate-600">({unlimited ? `${links.length} · unlimited` : `${links.length}/${max}`})</span></label>
              <div className="space-y-2">{links.map((l, i) => <div key={i} className="flex gap-2"><input value={l} onChange={e => setLinks(ls => ls.map((x, j) => j === i ? e.target.value : x))} placeholder="https://your-link.com" className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" /><button onClick={() => setLinks(ls => ls.filter((_, j) => j !== i))} className="h-11 w-11 grid place-items-center rounded-xl bg-white/5 hover:bg-rose-500/15 text-rose-300"><Trash2 className="h-4 w-4" /></button></div>)}</div>
              <div className="flex items-center justify-between mt-2"><button onClick={() => setLinks(ls => [...ls, ''])} disabled={!unlimited && links.length >= max} className="text-sm flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-40"><Plus className="h-4 w-4" /> Add link</button><button onClick={saveLinks} disabled={saving === 'links'} className="px-4 py-2 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">{saving === 'links' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedLinks ? <Check className="h-4 w-4" /> : null}{savedLinks ? 'Saved' : 'Save links'}</button></div>
              {!unlimited && links.length >= max && <p className="text-xs text-amber-400/80 mt-1.5">You’ve reached your plan’s link limit. <button onClick={() => nav('/plans')} className="underline">Upgrade</button> for more.</p>}
            </>
          )})()}
        </div>
      </section>
    </>
  )

  const emailSection = (
    <><SectionTitle title="Email" description="Your account email address." /><section className="bg-panel border border-edge rounded-2xl p-5"><label className="block text-sm text-slate-400 mb-1.5">Email</label><div className="flex items-center gap-2 bg-black/40 border border-edge rounded-xl px-3 py-3 text-slate-400"><UserIcon className="h-4 w-4" /><span className="truncate">{p?.email || 'Not set'}</span></div></section></>
  )

  const connectionsSection = (
    <><SectionTitle title="Connections" description="Control who can follow you and who can message you." /><section className="bg-panel border border-edge rounded-2xl p-5 space-y-1">
      <div className="flex items-center gap-3 py-3 border-b border-edge/60"><ShieldCheck className="h-5 w-5 text-brand shrink-0" /><div className="flex-1 min-w-0"><div className="font-medium">Approve new followers</div><div className="text-xs text-slate-500">Manually approve who can follow you instead of open follows.</div></div>{saving === 'follow_mode' && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}<Toggle on={p?.follow_mode === 'approval'} onChange={v => setPref('follow_mode', v ? 'approval' : 'open')} /></div>
      <div className="flex items-center gap-3 py-3 border-b border-edge/60"><MessageCircle className="h-5 w-5 text-brand shrink-0" /><div className="flex-1 min-w-0"><div className="font-medium">Who can DM you</div><div className="text-xs text-slate-500">Inner Circle can always DM. Turning this on also opens DMs to your followers.</div></div>{saving === 'dm_open' && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}<Toggle on={!!p?.dm_open} onChange={v => setPref('dm_open', v)} /></div>
      <button onClick={() => nav('/connections')} className="w-full mt-2 text-left flex items-center gap-3 px-3 py-3 rounded-xl bg-ink border border-edge hover:border-brand/40 transition"><Users2 className="h-5 w-5 text-brand" /><span className="flex-1"><span className="block font-medium">Manage connections</span><span className="block text-xs text-slate-500">Followers, Inner Circle, blocked and muted people.</span></span><ChevronRight className="h-5 w-5 text-slate-500" /></button>
    </section></>
  )

  const preferencesSection = (
    <><SectionTitle title="Preferences" description="Personalise how Skali looks and what content you see." />
      <section className="bg-panel border border-edge rounded-2xl p-5 mb-4"><h3 className="font-semibold mb-4 text-slate-300 flex items-center gap-2"><Palette className="h-4 w-4 text-brand" /> Appearance</h3><label className="block text-sm text-slate-400 mb-2">Theme</label><div className="grid grid-cols-2 gap-2 mb-5">{[{ k: 'dark', label: 'Dark', Icon: Moon }, { k: 'light', label: 'Light', Icon: Sun }].map(({ k, label, Icon }) => { const active = (p?.theme || 'dark') === k; return <button key={k} onClick={() => setDisplay('theme', k)} className={`flex items-center justify-center gap-2 py-3 rounded-xl border font-medium transition ${active ? 'border-brand bg-brand/15 text-white' : 'border-edge hover:bg-white/5 text-slate-300'}`}><Icon className="h-4 w-4" />{label}{saving === 'theme' && active && <Loader2 className="h-3.5 w-3.5 animate-spin" />}</button> })}</div><label className="block text-sm text-slate-400 mb-2">Accent colour</label><div className="flex flex-wrap gap-3 mb-5">{Object.entries(ACCENTS).map(([key, a]) => { const active = (p?.accent || 'violet') === key; return <button key={key} title={a.label} onClick={() => setDisplay('accent', key)} style={{ backgroundColor: a.hex }} className={`h-9 w-9 rounded-full grid place-items-center ring-2 ring-offset-2 ring-offset-panel transition ${active ? 'ring-white' : 'ring-transparent hover:ring-white/40'}`}>{active && <Check className="h-4 w-4 text-white" />}</button> })}</div><label className="block text-sm text-slate-400 mb-2 flex items-center gap-1.5"><Type className="h-4 w-4" /> Text size</label><div className="grid grid-cols-3 gap-2">{FONT_OPTS.map(o => { const active = (p?.font_size || 'normal') === o.key; return <button key={o.key} onClick={() => setDisplay('font_size', o.key)} className={`py-2.5 rounded-xl border font-medium transition ${active ? 'border-brand bg-brand/15 text-white' : 'border-edge hover:bg-white/5 text-slate-300'}`}>{o.label}</button> })}</div></section>
      <section className="bg-panel border border-edge rounded-2xl p-5"><h3 className="text-lg font-extrabold tracking-wide">Content preferences</h3><p className="text-sm text-slate-400 mt-1 mb-3">Choose what shows up in your feed.</p><div className="inline-flex items-center gap-2 text-[11px] tracking-wider text-slate-500 border border-edge rounded-full px-3 py-1.5 mb-4"><Lock className="h-3.5 w-3.5" /> PRIVATE — ONLY YOU CAN SEE THESE</div><div className="divide-y divide-edge/60">{CZ_ITEMS.map(({ key, label, desc, Icon }) => <div key={key} className="flex items-center gap-3 py-3.5"><Icon className="h-5 w-5 text-amber-500/90 shrink-0" /><div className="flex-1 min-w-0"><div className="font-medium">{label}</div><div className="text-xs text-slate-500">{desc}</div></div>{saving === 'cz:' + key && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}<Toggle on={!!cz[key]} onChange={v => setCZ(key, v)} accent="amber" /></div>)}</div></section>
    </>
  )

  const notificationsSection = (
    <><SectionTitle title="Notifications" description="Choose which activity notifications you receive." /><section className="bg-panel border border-edge rounded-2xl p-5"><div className="divide-y divide-edge/60">{NP_ITEMS.map(({ key, label, desc }) => <div key={key} className="flex items-center gap-3 py-3.5"><div className="flex-1 min-w-0"><div className="font-medium">{label}</div><div className="text-xs text-slate-500">{desc}</div></div>{saving === 'np:' + key && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}<Toggle on={!!np[key]} onChange={v => setNotif(key, v)} /></div>)}</div></section></>
  )

  const accountSection = (
    <><SectionTitle title="Account" description="Password, plan and staff tools." />
      {p?.has_password && <section className="bg-panel border border-edge rounded-2xl p-5 mb-4"><h3 className="font-semibold mb-3 text-slate-300 flex items-center gap-2"><KeyRound className="h-4 w-4" /> Change password</h3><div className="space-y-2"><input type="password" value={curPw} onChange={e => setCurPw(e.target.value)} placeholder="Current password" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" /><input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="New password (min 6 chars)" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" /><input type="password" value={confPw} onChange={e => setConfPw(e.target.value)} placeholder="Confirm new password" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" /></div>{pwMsg && <div className={`text-sm mt-2 ${pwMsg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{pwMsg.text}</div>}<button onClick={changePw} disabled={saving === 'password' || !curPw || !newPw} className="mt-3 px-4 py-2.5 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-2">{saving === 'password' ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} Update password</button></section>}
      <section className="bg-panel border border-edge rounded-2xl p-5 space-y-3"><button onClick={() => nav('/plans')} className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl bg-ink border border-edge hover:border-brand/50 transition"><div className="flex-1 min-w-0"><div className="text-xs text-slate-500">Your plan</div><div className="font-medium flex items-center gap-1.5">{(user as any)?.role ? <><RoleBadge role={(user as any).role} size={18} /><span className={ROLE_META[(user as any).role]?.color}>{ROLE_META[(user as any).role]?.label}</span></> : <><AccountBadge type={(user as any)?.account_type} size={18} /><span className={ACCOUNT_META[(user as any)?.account_type || 'free']?.color}>{ACCOUNT_META[(user as any)?.account_type || 'free']?.label}</span></>}</div></div><span className="text-xs text-brand font-medium">View plans</span></button>{(user?.is_admin || (user as any)?.can_moderate) && <button onClick={() => nav('/admin')} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-brand/20 to-violet-600/10 border border-brand/40 hover:border-brand transition"><ShieldCheck className="h-5 w-5 text-brand" /><span className="font-medium flex-1 text-left">{(user as any)?.can_moderate && !user?.is_admin ? 'Moderation' : 'Admin panel'}</span><ChevronRight className="h-5 w-5 text-slate-500" /></button>}</section>
    </>
  )

  return (
    <div className="h-full min-h-0 flex flex-col max-w-2xl mx-auto w-full overflow-hidden">
      <header className="shrink-0 z-10 bg-ink/95 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-3">
        <button onClick={() => section ? setSection(null) : nav(-1)} className="h-9 w-9 grid place-items-center rounded-xl hover:bg-white/5 text-slate-300" aria-label="Back"><span className="text-2xl leading-none">‹</span></button>
        <SettingsIcon className="h-5 w-5 text-brand" />
        <h1 className="text-lg font-extrabold">{section ? ({ profile: 'Profile', email: 'Email', connections: 'Connections', preferences: 'Preferences', notifications: 'Notifications', account: 'Account' } as any)[section] : 'Settings'}</h1>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 pb-8">
        {!section ? (
          <div className="space-y-3">
            <div className="bg-panel border border-edge rounded-2xl p-4 mb-5 flex items-center gap-3">
              <Avatar id={p?.id || ''} name={p?.display_name || ''} url={p?.avatar_url} size={48} />
              <div className="min-w-0 flex-1"><div className="font-semibold truncate">{p?.display_name}</div><div className="text-xs text-slate-500 truncate">#{p?.handle}</div></div>
            </div>
            <SectionPill id="profile" icon={UserIcon} title="Profile" description="Username, names, visibility, bio and links" />
            <SectionPill id="email" icon={MessageCircle} title="Email" description="Account email address" />
            <SectionPill id="connections" icon={Users2} title="Connections" description="Privacy, follower approval and who can DM you" />
            <SectionPill id="preferences" icon={Palette} title="Preferences" description="Appearance and content preferences" />
            <SectionPill id="notifications" icon={Bell} title="Notifications" description="Follows, Inner Circle, walls, reactions, comments and DMs" />
            <SectionPill id="account" icon={KeyRound} title="Account" description="Password, plan and staff tools" />

            <div className="pt-4 space-y-2">
              <button onClick={logout} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-edge hover:bg-white/5 transition font-medium"><LogOut className="h-5 w-5 text-slate-400" /> Sign out</button>
              <button onClick={() => setConfirmDelete(true)} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition font-medium"><Trash2 className="h-5 w-5" /> Delete account</button>
            </div>
            <p className="text-center text-xs text-slate-600 pt-2">Skali</p>
          </div>
        ) : section === 'profile' ? profileSection
          : section === 'email' ? emailSection
          : section === 'connections' ? connectionsSection
          : section === 'preferences' ? preferencesSection
          : section === 'notifications' ? notificationsSection
          : accountSection}
      </div>

      {confirmDelete && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onClick={() => !deleting && setConfirmDelete(false)}>
          <div className="bg-panel border border-edge rounded-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 text-rose-400 mb-2"><AlertTriangle className="h-5 w-5" /><h3 className="font-bold text-lg">Delete your account?</h3></div>
            <p className="text-sm text-slate-400 mb-4">This permanently deletes your profile, posts, follows, Inner Circle, and messages. This <span className="text-slate-200 font-medium">cannot be undone</span>.</p>
            <label className="block text-xs text-slate-500 mb-1.5">Type <span className="font-mono text-slate-300">DELETE</span> to confirm</label>
            <input value={confirmText} onChange={e => setConfirmText(e.target.value)} className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-rose-500/60 mb-4" placeholder="DELETE" />
            <div className="flex gap-2"><button onClick={() => setConfirmDelete(false)} disabled={deleting} className="flex-1 py-2.5 rounded-xl border border-edge hover:bg-white/5">Cancel</button><button onClick={doDelete} disabled={confirmText !== 'DELETE' || deleting} className="flex-1 py-2.5 rounded-xl bg-rose-600 font-medium disabled:opacity-40 flex items-center justify-center gap-2">{deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}Delete</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
