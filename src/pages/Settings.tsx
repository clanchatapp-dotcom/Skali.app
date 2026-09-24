import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings as SettingsIcon, ShieldCheck, MessageCircle, LogOut, Trash2, Loader2, Check, Plus, User as UserIcon, AlertTriangle, Lock, Flame, Sparkles, MessageSquare, Swords, Pill, Eye, KeyRound, Bell, Users2, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Avatar } from '../lib/ui'
import AccountBadge, { ACCOUNT_META } from '../components/AccountBadge'
import RoleBadge, { ROLE_META } from '../components/RoleBadge'

function Toggle({ on, onChange, disabled, accent = 'brand' }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean; accent?: 'brand' | 'amber' }) {
  const onColor = accent === 'amber' ? 'bg-amber-500' : 'bg-brand'
  return (
    <button type="button" disabled={disabled} onClick={() => onChange(!on)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${on ? onColor : 'bg-white/15'} ${disabled ? 'opacity-50' : ''}`}>
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

type TabKey = 'profile' | 'connections' | 'preferences' | 'notifications' | 'account'
const TAB_LIST: { key: TabKey; label: string }[] = [
  { key: 'profile', label: 'Profile' },
  { key: 'connections', label: 'Connections' },
  { key: 'preferences', label: 'Preferences' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'account', label: 'Account' },
]

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
  const [tab, setTab] = useState<TabKey>('profile')

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

  const np = { ...NP_DEFAULTS, ...(p?.notif_prefs || {}) }
  const setNotif = async (key: string, value: boolean) => {
    const next = { ...np, [key]: value }
    setP((prev: any) => ({ ...prev, notif_prefs: next }))
    setSaving('np:' + key)
    try { await api.updateProfile({ notif_prefs: next }) } catch {}
    setSaving(null)
  }

  const saveName = async () => {
    const v = name.trim(); if (!v || v === p?.display_name) return
    setSaving('display_name')
    try { await api.updateProfile({ display_name: v }); await refresh(); setSavedName(true); setTimeout(() => setSavedName(false), 1500) } catch {}
    setSaving(null)
  }

  const saveRealName = async () => {
    const v = realName.trim(); if (v === (p?.real_name || '')) return
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

  if (loading) return <div className="h-full grid place-items-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>

  const isStaff = !!(user?.is_admin || (user as any)?.can_moderate)
  const adminLabel = user?.is_admin ? 'Admin panel' : 'Moderation'

  return (
    <div className="max-w-2xl mx-auto w-full h-full min-h-0 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="shrink-0 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-2">
        <SettingsIcon className="h-5 w-5 text-brand" />
        <h1 className="text-lg font-extrabold">Settings</h1>
      </div>

      {/* Pill tabs */}
      <div className="shrink-0 bg-ink/80 backdrop-blur border-b border-edge px-3 py-2">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          {TAB_LIST.map(t => {
            const active = tab === t.key
            return (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide transition ${active ? 'bg-brand text-white shadow-sm shadow-violet-900/30' : 'bg-panel/60 border border-edge text-slate-400 hover:text-slate-200'}`}>
                {t.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 space-y-6 pb-[calc(5.5rem+env(safe-area-inset-bottom))]">
        {/* PROFILE TAB */}
        {tab === 'profile' && (
          <section className="bg-panel border border-edge rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-4">
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
                <input value={uname} onChange={e => { setUname(e.target.value.replace(/[^A-Za-z0-9]/g, '').toLowerCase()); setUnameErr(null) }}
                  maxLength={20} disabled={!!p?.handle_change_available_at} placeholder="username"
                  className="flex-1 bg-transparent py-2.5 outline-none disabled:opacity-60" />
              </div>
              <button onClick={saveHandle}
                disabled={unameBusy || !!p?.handle_change_available_at || uname === p?.handle || uname.length < 3}
                className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
                {unameBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Change
              </button>
            </div>
            {unameErr
              ? <p className="text-xs text-rose-400 mt-1.5">{unameErr}</p>
              : p?.handle_change_available_at
                ? <p className="text-xs text-amber-400/80 mt-1.5">You can change your username again on {new Date(p.handle_change_available_at).toLocaleDateString()}.</p>
                : <p className="text-xs text-slate-500 mt-1.5">Once every 60 days. Letters and numbers only.</p>}

            <div className="h-px bg-edge my-4" />

            <label className="block text-sm text-slate-400 mb-1.5">Display name</label>
            <div className="flex gap-2">
              <input value={name} onChange={e => setName(e.target.value)} maxLength={40} className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" placeholder="Your name" />
              <button onClick={saveName} disabled={saving === 'display_name' || !name.trim() || name.trim() === p?.display_name} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
                {saving === 'display_name' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedName ? <Check className="h-4 w-4" /> : null}
                {savedName ? 'Saved' : 'Save'}
              </button>
            </div>

            <div className="mt-4">
              <label className="block text-sm text-slate-400 mb-1.5">Real name <span className="text-slate-600">(optional)</span></label>
              <div className="flex gap-2">
                <input value={realName} onChange={e => setRealName(e.target.value)} maxLength={60} className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" placeholder="e.g. Alex Morgan" />
                <button onClick={saveRealName} disabled={saving === 'real_name' || realName.trim() === (p?.real_name || '')} className="px-4 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
                  {saving === 'real_name' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedRN ? <Check className="h-4 w-4" /> : null}
                  {savedRN ? 'Saved' : 'Save'}
                </button>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Eye className="h-4 w-4 text-slate-500 shrink-0" />
                <span className="text-xs text-slate-400">Who can see your real name</span>
                <select value={p?.real_name_visibility || 'private'} onChange={e => setPref('real_name_visibility', e.target.value)} className="ml-auto bg-black/40 border border-edge rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-brand/60">
                  <option value="private">Only me</option>
                  <option value="inner">Inner Circle</option>
                  <option value="followers">Followers</option>
                  <option value="public">Everyone</option>
                </select>
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-sm text-slate-400 mb-1.5">Bio <span className="text-slate-600">({(bio || '').length}/{p?.limits?.bio || 150})</span></label>
              <textarea value={bio} onChange={e => setBio(e.target.value)} rows={3} maxLength={p?.limits?.bio || 150} placeholder="Add a bio…" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
              <div className="flex justify-end mt-2">
                <button onClick={saveBio} disabled={saving === 'bio' || bio === (p?.bio || '')} className="px-4 py-2 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
                  {saving === 'bio' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedBio ? <Check className="h-4 w-4" /> : null}{savedBio ? 'Saved' : 'Save bio'}
                </button>
              </div>
            </div>

            <div className="mt-4">
              {(() => { const max = p?.limits?.links || 3; const unlimited = max >= 9999; return (
                <>
                  <label className="block text-sm text-slate-400 mb-1.5">Links <span className="text-slate-600">({unlimited ? `${links.length} · unlimited` : `${links.length}/${max}`})</span></label>
                  <div className="space-y-2">
                    {links.map((l, i) => (
                      <div key={i} className="flex gap-2">
                        <input value={l} onChange={e => setLinks(ls => ls.map((x, j) => j === i ? e.target.value : x))} placeholder="https://your-link.com" className="flex-1 bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
                        <button onClick={() => setLinks(ls => ls.filter((_, j) => j !== i))} className="h-11 w-11 grid place-items-center rounded-xl bg-white/5 hover:bg-rose-500/15 text-rose-300"><Trash2 className="h-4 w-4" /></button>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <button onClick={() => setLinks(ls => [...ls, ''])} disabled={!unlimited && links.length >= max} className="text-sm flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-40">
                      <Plus className="h-4 w-4" /> Add link
                    </button>
                    <button onClick={saveLinks} disabled={saving === 'links'} className="px-4 py-2 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-1.5">
                      {saving === 'links' ? <Loader2 className="h-4 w-4 animate-spin" /> : savedLinks ? <Check className="h-4 w-4" /> : null}{savedLinks ? 'Saved' : 'Save links'}
                    </button>
                  </div>
                  {!unlimited && links.length >= max && <p className="text-xs text-amber-400/80 mt-1.5">You've reached your plan's link limit. <button onClick={() => nav('/plans')} className="underline">Upgrade</button> for more.</p>}
                </>
              )})()}
            </div>

            <div className="mt-4">
              <label className="block text-sm text-slate-400 mb-1.5">Email</label>
              <div className="flex items-center gap-2 bg-black/40 border border-edge rounded-xl px-3 py-2.5 text-slate-400">
                <UserIcon className="h-4 w-4" />
                <span className="truncate">{p?.email || 'Not set'}</span>
              </div>
            </div>
          </section>
        )}

        {/* CONNECTIONS TAB */}
        {tab === 'connections' && (
          <>
            <section className="bg-panel border border-edge rounded-2xl p-5 space-y-1">
              <h2 className="font-semibold mb-2 text-slate-300">Privacy settings</h2>

              <div className="flex items-center gap-3 py-3 border-b border-edge/60">
                <ShieldCheck className="h-5 w-5 text-brand shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">Follower approval</div>
                  <div className="text-xs text-slate-500">Manually approve who can follow you instead of open follows.</div>
                </div>
                {saving === 'follow_mode' && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
                <Toggle on={p?.follow_mode === 'approval'} onChange={v => setPref('follow_mode', v ? 'approval' : 'open')} />
              </div>

              <div className="flex items-center gap-3 py-3">
                <MessageCircle className="h-5 w-5 text-brand shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">Who can DM you</div>
                  <div className="text-xs text-slate-500">Inner Circle can always DM. Turn this on to also let followers message you.</div>
                </div>
                {saving === 'dm_open' && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
                <Toggle on={!!p?.dm_open} onChange={v => setPref('dm_open', v)} />
              </div>
            </section>

            <button onClick={() => nav('/connections')} className="w-full bg-panel border border-edge rounded-2xl p-5 flex items-center gap-3 hover:bg-white/5 transition text-left">
              <Users2 className="h-5 w-5 text-brand shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium">Manage connections</div>
                <div className="text-xs text-slate-500">Followers, Inner Circle, blocked & muted people.</div>
              </div>
              <ChevronRight className="h-5 w-5 text-slate-500" />
            </button>
          </>
        )}

        {/* PREFERENCES TAB — Comfort Zone */}
        {tab === 'preferences' && (
          <section className="bg-panel border border-edge rounded-2xl p-5">
            <h2 className="text-lg font-extrabold tracking-wide">Comfort Zone</h2>
            <p className="text-sm text-slate-400 mt-1 mb-3">Choose what shows up in your feed. We'll soften or hide anything you turn off.</p>
            <div className="inline-flex items-center gap-2 text-[11px] tracking-wider text-slate-500 border border-edge rounded-full px-3 py-1.5 mb-4">
              <Lock className="h-3.5 w-3.5" /> PRIVATE — ONLY YOU CAN SEE THESE
            </div>
            <div className="divide-y divide-edge/60">
              {CZ_ITEMS.map(({ key, label, desc, Icon }) => (
                <div key={key} className="flex items-center gap-3 py-3.5">
                  <Icon className="h-5 w-5 text-amber-500/90 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{label}</div>
                    <div className="text-xs text-slate-500">{desc}</div>
                  </div>
                  {saving === 'cz:' + key && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
                  <Toggle on={!!cz[key]} onChange={v => setCZ(key, v)} accent="amber" />
                </div>
              ))}
            </div>
          </section>
        )}

        {/* NOTIFICATIONS TAB */}
        {tab === 'notifications' && (
          <section className="bg-panel border border-edge rounded-2xl p-5">
            <h2 className="font-semibold mb-1 text-slate-300 flex items-center gap-2"><Bell className="h-4 w-4 text-brand" /> Notifications</h2>
            <p className="text-sm text-slate-500 mb-2">Choose what shows up on your Activity page.</p>
            <div className="divide-y divide-edge/60">
              {NP_ITEMS.map(({ key, label, desc }) => (
                <div key={key} className="flex items-center gap-3 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{label}</div>
                    <div className="text-xs text-slate-500">{desc}</div>
                  </div>
                  {saving === 'np:' + key && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
                  <Toggle on={!!np[key]} onChange={v => setNotif(key, v)} />
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ACCOUNT TAB */}
        {tab === 'account' && (
          <>
            {p?.has_password && (
              <section className="bg-panel border border-edge rounded-2xl p-5">
                <h2 className="font-semibold mb-3 text-slate-300 flex items-center gap-2"><KeyRound className="h-4 w-4" /> Change password</h2>
                <div className="space-y-2">
                  <input type="password" value={curPw} onChange={e => setCurPw(e.target.value)} placeholder="Current password" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
                  <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="New password (min 6 chars)" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
                  <input type="password" value={confPw} onChange={e => setConfPw(e.target.value)} placeholder="Confirm new password" className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand/60" />
                </div>
                {pwMsg && <div className={`text-sm mt-2 ${pwMsg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{pwMsg.text}</div>}
                <button onClick={changePw} disabled={saving === 'password' || !curPw || !newPw} className="mt-3 px-4 py-2.5 rounded-xl bg-brand font-medium disabled:opacity-40 flex items-center gap-2">
                  {saving === 'password' ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} Update password
                </button>
              </section>
            )}

            <section className="bg-panel border border-edge rounded-2xl p-5 space-y-3">
              <h2 className="font-semibold text-slate-300">Plan</h2>
              <button onClick={() => nav('/plans')} className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl bg-ink border border-edge hover:border-brand/50 transition">
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-slate-500">Your plan</div>
                  <div className="font-medium flex items-center gap-1.5">
                    {(user as any)?.role
                      ? <><RoleBadge role={(user as any).role} size={18} /><span className={ROLE_META[(user as any).role]?.color}>{ROLE_META[(user as any).role]?.label}</span></>
                      : <><AccountBadge type={(user as any)?.account_type} size={18} /><span className={ACCOUNT_META[(user as any)?.account_type || 'free']?.color}>{ACCOUNT_META[(user as any)?.account_type || 'free']?.label}</span></>}
                  </div>
                </div>
                <span className="text-xs text-brand font-medium">View plans</span>
              </button>
              {isStaff && (
                <button onClick={() => nav('/admin')} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-brand/20 to-violet-600/10 border border-brand/40 hover:border-brand transition">
                  <ShieldCheck className="h-5 w-5 text-brand" />
                  <span className="font-medium flex-1 text-left">{adminLabel}</span>
                  <ChevronRight className="h-5 w-5 text-slate-500" />
                </button>
              )}
            </section>
          </>
        )}

        {/* Always-visible: Legal & policies */}
        <section className="bg-panel border border-edge rounded-2xl p-5" data-testid="settings-legal">
          <h2 className="font-semibold mb-3 text-slate-300">Legal & policies</h2>
          <div className="grid grid-cols-2 gap-2">
            <button data-testid="settings-legal-terms" onClick={() => nav('/legal/terms')} className="text-left px-3 py-2.5 rounded-xl border border-edge hover:bg-white/5 transition text-sm">Terms of Service</button>
            <button data-testid="settings-legal-privacy" onClick={() => nav('/legal/privacy')} className="text-left px-3 py-2.5 rounded-xl border border-edge hover:bg-white/5 transition text-sm">Privacy Policy</button>
            <button data-testid="settings-legal-content" onClick={() => nav('/legal/content')} className="text-left px-3 py-2.5 rounded-xl border border-edge hover:bg-white/5 transition text-sm">Content Policy</button>
            <button data-testid="settings-legal-cookies" onClick={() => nav('/legal/cookies')} className="text-left px-3 py-2.5 rounded-xl border border-edge hover:bg-white/5 transition text-sm">Cookie Policy</button>
          </div>
        </section>

        {/* Always-visible actions (no pill): Sign out + Delete */}
        <section className="bg-panel border border-edge rounded-2xl p-5 space-y-3">
          <button onClick={logout} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-edge hover:bg-white/5 transition">
            <LogOut className="h-5 w-5 text-slate-400" />
            <span className="font-medium">Sign out</span>
          </button>
          <button onClick={() => setConfirmDelete(true)} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition">
            <Trash2 className="h-5 w-5" />
            <span className="font-medium">Delete account</span>
          </button>
        </section>

        <p className="text-center text-xs text-slate-600 pb-4">Skali</p>
      </div>

      {/* Delete confirm modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onClick={() => !deleting && setConfirmDelete(false)}>
          <div className="bg-panel border border-edge rounded-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 text-rose-400 mb-2">
              <AlertTriangle className="h-5 w-5" />
              <h3 className="font-bold text-lg">Delete your account?</h3>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              This permanently deletes your profile, posts, follows, Inner Circle, and messages. This <span className="text-slate-200 font-medium">cannot be undone</span>.
            </p>
            <label className="block text-xs text-slate-500 mb-1.5">Type <span className="font-mono text-slate-300">DELETE</span> to confirm</label>
            <input value={confirmText} onChange={e => setConfirmText(e.target.value)} className="w-full bg-black/40 border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-rose-500/60 mb-4" placeholder="DELETE" />
            <div className="flex gap-2">
              <button onClick={() => setConfirmDelete(false)} disabled={deleting} className="flex-1 py-2.5 rounded-xl border border-edge hover:bg-white/5">Cancel</button>
              <button onClick={doDelete} disabled={confirmText !== 'DELETE' || deleting} className="flex-1 py-2.5 rounded-xl bg-rose-600 font-medium disabled:opacity-40 flex items-center justify-center gap-2">
                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}