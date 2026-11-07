import StreamersPanel from '../components/StreamersPanel'
import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, setStepUp, hasStepUp } from '../lib/api'
import InvestigationsPanel from '../components/investigations/InvestigationsPanel'
import { useAuth } from '../lib/auth'
import { timeAgo } from '../lib/ui'
import RoleBadge, { ROLE_META } from '../components/RoleBadge'
import AdultBadge from '../components/AdultBadge'
import AuditPanel from '../components/AuditPanel'
import { Shield, Flag, AlertTriangle, Users, ScrollText, Ban, Loader2, Check, Trash2, X, Lock, UserCog, Crown, ScanEye, Bookmark, StickyNote, Star, MessageCircle, Send, Hand } from 'lucide-react'

// `min` = lowest staff level that can see the tab: mod (all staff) · full (Co-admin+) · super.
const LEVEL: Record<string, number> = { moderator: 1, co_admin: 2, super_admin: 3 }
const NEED: Record<string, number> = { mod: 1, full: 2, super: 3 }
const TABS = [
  { key: 'reports', label: 'Reports', icon: Flag, min: 'mod' },
  { key: 'csam', label: 'CSAM', icon: AlertTriangle, min: 'full' },
  { key: 'nsfw', label: 'NSFW', icon: ScanEye, min: 'full' },
  { key: 'support', label: 'Support', icon: MessageCircle, min: 'mod' },
  { key: 'watchlist', label: 'Watchlist', icon: Bookmark, min: 'mod' },
  { key: 'users', label: 'Users', icon: Users, min: 'mod' },
  { key: 'creators', label: 'Creators', icon: Star, min: 'full' },
  { key: 'investigations', label: 'Investigations', icon: Lock, min: 'full' },
  { key: 'audit', label: 'Audit log', icon: ScrollText, min: 'mod' },
  { key: 'roles', label: 'Roles', icon: Crown, min: 'super' },
  { key: 'admins', label: 'Admins', icon: UserCog, min: 'super' },
]

const SENSITIVE = ['csam', 'underage', 'nsfw']

function Stat({ label, value, danger }: { label: string; value: any; danger?: boolean }) {
  return (
    <div className="bg-panel border border-edge rounded-2xl p-4">
      <div className={`text-2xl font-extrabold ${danger && value > 0 ? 'text-rose-400' : ''}`}>{value ?? '—'}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  )
}

export default function Admin() {
  const { user } = useAuth()
  const supportOnly = !!(user as any)?.is_support_bot && !user?.is_admin && !(user as any)?.can_moderate
  const [tab, setTab] = useState(supportOnly ? 'support' : 'reports')
  const [supportUnread, setSupportUnread] = useState(0)
  const [stats, setStats] = useState<any>({})
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [adminsData, setAdminsData] = useState<any>({ admins: [], pending: [] })
  const [newAdminEmail, setNewAdminEmail] = useState('')
  const [roles, setRoles] = useState<any[]>([])
  const [assignHandle, setAssignHandle] = useState('')
  const [assignRole, setAssignRole] = useState('moderator')
  const [dz, setDz] = useState(false)
  const staffRole: string = (user as any)?.staff_role || ((user as any)?.is_admin ? 'co_admin' : (user as any)?.can_moderate ? 'moderator' : '')
  const level = LEVEL[staffRole] || 0
  const isFull = level >= 2                      // super_admin OR co_admin
  const isSuper = level >= 3
  const visibleTabs = supportOnly ? TABS.filter(t => t.key === 'support') : TABS.filter(t => level >= NEED[t.min])
  const [reportScope, setReportScope] = useState<'open' | 'mine'>('open')
  const loadRoles = async () => { try { setRoles(await api.adminRoles()) } catch {} }
  const doAssign = async () => {
    const h = assignHandle.trim().replace(/^[#@]/, '')
    if (!h) return
    try { await api.adminAssignRole(h, assignRole); setAssignHandle(''); await loadRoles() }
    catch (e: any) { alert(e.message) }
  }
  const doRemoveRole = async (h: string) => {
    if (!confirm(`Remove @${h}'s role?`)) return
    try { await api.adminRemoveRole(h); await loadRoles() } catch (e: any) { alert(e.message) }
  }
  const loadStats = () => api.adminStats().then(setStats).catch(() => {})
  // Creators (manual assignment) + Support inbox state
  const [creators, setCreators] = useState<any[]>([])
  const [creatorSearch, setCreatorSearch] = useState('')
  const [creatorResults, setCreatorResults] = useState<any[]>([])
  const [support, setSupport] = useState<any[]>([])
  const [supportThread, setSupportThread] = useState<any>(null)
  const [supportReplyText, setSupportReplyText] = useState('')
  const loadCreators = async () => { try { setCreators(await api.adminCreators()) } catch {} }
  const searchCreators = async () => { try { setCreatorResults(await api.adminUsers(creatorSearch)) } catch {} }
  const grantCreator = async (h: string) => { try { await api.adminGrantCreator(h); await loadCreators(); await searchCreators() } catch (e: any) { alert(e.message) } }
  const revokeCreator = async (h: string) => { if (!confirm(`Remove creator access from #${h}?`)) return; try { await api.adminRevokeCreator(h); await loadCreators(); await searchCreators() } catch (e: any) { alert(e.message) } }
  const grantAdult = async (h: string) => { if (!confirm(`Make #${h} an ADULT (18+) content creator? This flags the account NSFW everywhere and unlocks adult creator tools.`)) return; try { await api.adminGrantAdultCreator(h); await loadCreators(); await searchCreators(); if (tab === 'users') load() } catch (e: any) { alert(e.message) } }
  const revokeAdult = async (h: string) => { if (!confirm(`Remove the adult (18+) creator status from #${h}?`)) return; try { await api.adminRevokeAdultCreator(h); await loadCreators(); await searchCreators(); if (tab === 'users') load() } catch (e: any) { alert(e.message) } }
  const loadSupport = async () => {
    try { setSupport(await api.supportThreads()) } catch {}
    api.supportUnread().then((r: any) => setSupportUnread(r.unread || 0)).catch(() => {})
  }
  const openSupport = async (h: string) => { try { setSupportThread(await api.supportThread(h)); await loadSupport() } catch (e: any) { alert(e.message) } }
  const claimSupport = async (h: string, claim: boolean, current?: any) => {
    if (claim && current && current.id !== user?.id && !confirm(`#${current.handle} is handling this chat. Take it over?`)) return
    try { await api.supportClaim(h, claim); if (supportThread?.user.handle === h) setSupportThread(await api.supportThread(h)); await loadSupport() }
    catch (e: any) { alert(e.message) }
  }
  const solveSupport = async (h: string, solved: boolean) => {
    try { await api.supportSolve(h, solved); if (supportThread?.user.handle === h) setSupportThread(await api.supportThread(h)); await loadSupport() }
    catch (e: any) { alert(e.message) }
  }
  const sendSupport = async () => {
    const t = supportReplyText.trim()
    if (!t || !supportThread) return
    try { await api.supportReply(supportThread.user.handle, t); setSupportReplyText(''); setSupportThread(await api.supportThread(supportThread.user.handle)); await loadSupport() }
    catch (e: any) { alert(e.message) }
  }
  const loadAdmins = async () => { try { setAdminsData(await api.adminListAdmins()) } catch {} }
  const load = async () => {
    setLoading(true)
    try {
      if (tab === 'reports') setData(await api.adminReports(reportScope))
      else if (tab === 'csam') { if (!ensureStepUp()) { setData([]); setLoading(false); return } setData(await api.adminCsam()) }
      else if (tab === 'nsfw') setData(await api.adminNsfw('open'))
      else if (tab === 'watchlist') setData(await api.adminWatchlist())
      else if (tab === 'users') setData(await api.adminUsers(q))
      else if (tab === 'creators') { await loadCreators(); setData([]) }
      else if (tab === 'support') { await loadSupport(); setData([]) }
      else if (tab === 'admins') { await loadAdmins(); setData([]) }
      else if (tab === 'roles') { await loadRoles(); setData([]) }
      else if (tab === 'audit' || tab === 'investigations') setData([])
    } catch { setData([]) } finally { setLoading(false) }
  }
  useEffect(() => {
    if (!supportOnly) loadStats()
    api.supportUnread().then((r: any) => setSupportUnread(r.unread || 0)).catch(() => {})
  }, [])
  useEffect(() => {
    if (tab !== 'support') return
    const t = setInterval(loadSupport, 20000)
    return () => clearInterval(t)
  }, [tab])
  useEffect(() => { load() }, [tab, reportScope])

  if (user && !user.is_admin && !(user as any).can_moderate && !(user as any).is_support_bot) return <Navigate to="/" replace />

  const act = async (id: string, action: string, severe = false) => {
    let reason = ''
    if (action !== 'dismiss') reason = window.prompt(`Reason for "${action.replace('_', ' ')}"?`, '') || ''
    if (action === 'uphold' && severe && !window.confirm('Zero-tolerance: this permanently terminates the account with NO appeal. Continue?')) return
    try { await api.adminAction(id, action, reason, severe) } catch (e: any) { alert(e.message) }
    await load(); await loadStats()
  }
  const assignReport = async (r: any, assign: boolean) => {
    if (assign && r.assigned && r.assigned.id !== user?.id && !confirm(`#${r.assigned.handle} owns this report. Take it over?`)) return
    try { await api.adminReportAssign(r.id, assign); await load() } catch (e: any) { alert(e.message) }
  }
  const clearRecord = async (handle: string) => {
    if (!window.confirm(`Clear @${handle}'s strikes & upheld reports (12-month rehab)?`)) return
    try { await api.adminClearStrikes(handle); await load(); await loadStats() } catch (e: any) { alert(e.message) }
  }
  const strike = async (handle: string, soft: boolean) => {
    const reason = window.prompt(soft ? 'Soft warning message:' : 'Strike reason:', '') || ''
    if (!reason) return
    try { await api.adminStrike(handle, reason, soft ? 'soft' : undefined) } catch (e: any) { alert(e.message) }
    await load(); await loadStats()
  }
  const unsuspend = async (handle: string) => { await api.adminUnsuspend(handle); await load(); await loadStats() }
  const flag = async (handle: string) => {
    const r = window.prompt('Flag reason (marks account as suspicious):', 'suspicious activity')
    if (r === null) return
    await api.adminFlag(handle, r || 'suspicious activity'); await load(); await loadStats()
  }
  const unflag = async (handle: string) => { await api.adminUnflag(handle); await load(); await loadStats() }
  const watch = async (handle: string) => {
    const r = window.prompt('Add to watchlist — reason:', 'under review')
    if (r === null) return
    await api.adminWatch(handle, r || 'under review'); await load(); await loadStats()
  }
  const unwatch = async (handle: string) => { await api.adminUnwatch(handle); await load(); await loadStats() }
  const setAcct = async (handle: string, t: string) => {
    try { await api.adminSetAccountType(handle, t); await load() } catch (e: any) { alert(e.message) }
  }
  const addNote = async (handle: string) => {
    const n = window.prompt(`Add a private admin note about #${handle}:`, '')
    if (!n) return
    try { await api.adminAddNote(handle, n); alert('Note saved.') } catch (e: any) { alert(e.message) }
  }
  const viewNotes = async (handle: string) => {
    try { const notes = await api.adminNotes(handle)
      alert(notes.length ? notes.map((x: any) => `• ${x.note}\n  — #${x.admin_handle}, ${timeAgo(x.created_at)}`).join('\n\n') : 'No notes yet.')
    } catch (e: any) { alert(e.message) }
  }
  const nsfwResolve = async (id: string, action: string) => { await api.adminNsfwResolve(id, action); await load(); await loadStats() }
  const csamEscalate = async (id: string) => { if (!ensureStepUp()) return; try { const r = await api.adminCsamEscalate(id); alert(`Escalated. Reference: ${r.ceop_ref}`); await load() } catch (e: any) { alert(e.message) } }
  const csamResolve = async (id: string) => { if (!ensureStepUp()) return; await api.adminCsamResolve(id); await load(); await loadStats() }
  const addAdmin = async () => {
    const email = newAdminEmail.trim()
    if (!email) return
    try {
      const r = await api.adminAddAdmin(email)
      setNewAdminEmail(''); await loadAdmins(); await loadStats()
      alert(r.promoted ? `${r.email} is now an admin.` : `${r.email} allowlisted — they'll become admin the moment they sign up.`)
    } catch (e: any) { alert(e.message || 'Could not add admin') }
  }
  const removeAdmin = async (email: string) => {
    if (!window.confirm(`Revoke admin access for ${email}?`)) return
    try { await api.adminRemoveAdmin(email); await loadAdmins(); await loadStats() }
    catch (e: any) { alert(e.message || 'Could not remove admin') }
  }
  const promote = async () => {
    const email = window.prompt('Enter the email address to promote to admin:', '')
    if (!email) return
    setDz(true)
    try { const r = await api.adminPromote(email.trim()); alert(`Promoted #${r.promoted} to admin.`); await loadStats() }
    catch (e: any) { alert(e.message || 'Could not promote that email.') }
    setDz(false)
  }
  const purgeDemo = async (includeAdmin: boolean) => {
    const msg = includeAdmin
      ? 'Purge ALL demo accounts INCLUDING the seeded admin? This permanently deletes alice / bob / teen and the seeded admin and all their data. This cannot be undone.'
      : 'Purge the seeded demo accounts alice / bob / teen and all their data? This cannot be undone.'
    if (!window.confirm(msg)) return
    setDz(true)
    try { const r = await api.adminPurgeDemo(includeAdmin); alert(r.count ? `Purged: ${r.purged.join(', ')}` : 'No demo accounts found to purge.'); await load(); await loadStats() }
    catch (e: any) { alert(e.message || 'Purge failed.') }
    setDz(false)
  }
  const ensureStepUp = (): boolean => {
    if (hasStepUp()) return true
    const s = window.prompt('Sensitive area. Enter the server-side step-up secret to continue:')
    if (!s || !s.trim()) return false
    setStepUp(s.trim())
    return true
  }
  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-2">
        <Shield className="h-5 w-5 text-brand" /><h1 className="text-xl font-extrabold">{supportOnly ? 'Support inbox' : 'Admin'}</h1>
        <span className="text-xs text-slate-500 ml-2 hidden sm:inline">{supportOnly ? 'Skali Team' : 'Trust & Safety'}</span>
        {!supportOnly && ROLE_META[staffRole] && (
          <span data-testid="admin-role-badge" className={`ml-auto inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-white/5 border border-edge ${ROLE_META[staffRole].color}`}>
            <RoleBadge role={staffRole} size={14} />{ROLE_META[staffRole].label}
          </span>
        )}
      </div>

      <div className="p-4 space-y-4">
        {!supportOnly && <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
          <Stat label="Users" value={stats.users} />
          <Stat label="Posts" value={stats.posts} />
          <Stat label="Open reports" value={stats.open_reports} danger />
          {isFull && <Stat label="CSAM queue" value={stats.csam_reports} danger />}
          <Stat label="Suspended" value={stats.suspended} />
          <Stat label="Banned" value={stats.banned} />
          <Stat label="Flagged" value={stats.flagged} danger />
          <Stat label="Watchlist" value={stats.watchlisted} />
          {isFull && <Stat label="NSFW queue" value={stats.nsfw_open} danger />}
          <Stat label="Deleted" value={stats.deleted} />
        </div>}

        <div className="flex lg:flex-wrap gap-1 bg-panel border border-edge rounded-xl p-1 overflow-x-auto max-w-full" data-testid="admin-tabs">
          {visibleTabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} data-testid={`admin-tab-${t.key}`}
              className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg ${tab === t.key ? 'bg-brand text-white' : 'text-slate-400 hover:text-white'}`}>
              <t.icon className="h-4 w-4" />{t.label}
              {t.key === 'support' && supportUnread > 0 && <span data-testid="admin-support-unread-badge" className={`ml-0.5 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] grid place-items-center font-bold ${tab === t.key ? 'bg-white text-brand' : 'bg-rose-500 text-white'}`}>{supportUnread > 99 ? '99+' : supportUnread}</span>}
            </button>
          ))}
        </div>

        {tab === 'reports' && (
          <div className="flex gap-1.5 flex-wrap" data-testid="report-scope">
            {(['open', 'mine'] as const).map(k => (
              <button key={k} onClick={() => setReportScope(k)} data-testid={`report-scope-${k}`}
                className={`px-3 py-1 rounded-full text-xs border ${reportScope === k ? 'bg-brand/20 border-brand text-white' : 'border-edge text-slate-400 hover:text-white'}`}>{k === 'open' ? 'Shared queue' : 'Assigned to me'}</button>
            ))}
            {!isFull && <span className="text-[11px] text-slate-500 self-center ml-1">NSFW &amp; CSAM reports go to Co-admins.</span>}
          </div>
        )}

        {tab === 'users' && (
          <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()}
            placeholder="Search users, press Enter…" className="w-full bg-ink border border-edge rounded-xl px-4 py-2.5 outline-none focus:border-brand" />
        )}

        {loading ? <div className="py-16 grid place-items-center text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div> : (
          <div className="space-y-2">
            {data.length === 0 && !['admins', 'investigations', 'roles', 'creators', 'support', 'audit'].includes(tab) && <p className="text-center text-slate-500 py-10">Nothing here.</p>}

            {tab === 'investigations' && <InvestigationsPanel isSuper={isSuper} />}

            {tab === 'roles' && (
              <div className="space-y-4">
                <StreamersPanel isSuper={isSuper} />
                <div className="bg-panel border border-edge rounded-2xl p-4">
                  <div className="text-sm font-medium mb-2">Assign a staff role</div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input value={assignHandle} onChange={e => setAssignHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && doAssign()}
                      placeholder="@handle" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
                    <select value={assignRole} onChange={e => setAssignRole(e.target.value)}
                      className="bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand">
                      <option value="co_admin">Co-Admin (pink)</option>
                      <option value="moderator">Moderator (red)</option>
                      <option value="first_tester">First Tester (blue)</option>
                    </select>
                    <button onClick={doAssign} className="px-4 py-2.5 rounded-xl bg-brand font-medium">Assign</button>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">Role-holders become verified. Moderators handle general reports, support, watchlist and warnings/strikes. Co-Admins also handle NSFW/CSAM, bans and Investigations. Only a Super Admin can promote or remove staff.</p>
                </div>

                {roles.length === 0 && <p className="text-center text-slate-500 py-6">No staff roles assigned yet.</p>}
                {roles.map((m: any) => (
                  <div key={m.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-white/5 grid place-items-center overflow-hidden shrink-0">
                      {m.avatar_url ? <img src={m.avatar_url} className="h-full w-full object-cover" /> : <RoleBadge role={m.role} size={22} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate flex items-center gap-1.5">
                        {m.display_name || m.handle}
                        <RoleBadge role={m.role} size={16} />
                      </div>
                      <div className="text-xs text-slate-500 truncate">#{m.handle} · <span className={ROLE_META[m.role]?.color}>{ROLE_META[m.role]?.label || m.role}</span></div>
                    </div>
                    {m.protected
                      ? <span className="inline-flex items-center gap-1 text-[10px] bg-amber-500/15 text-amber-300 px-1.5 py-0.5 rounded-full shrink-0"><Crown className="h-3 w-3" />protected</span>
                      : <button onClick={() => doRemoveRole(m.handle)} className="shrink-0 h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-rose-300 hover:bg-white/5"><Trash2 className="h-4 w-4" /></button>}
                  </div>
                ))}
              </div>
            )}

            {tab === 'admins' && (
              <div className="space-y-4">
                <div className="bg-panel border border-edge rounded-2xl p-4">
                  <div className="text-sm font-medium mb-2">Add an admin by email</div>
                  <div className="flex gap-2">
                    <input value={newAdminEmail} onChange={e => setNewAdminEmail(e.target.value)} onKeyDown={e => e.key === 'Enter' && addAdmin()}
                      placeholder="name@email.com" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
                    <button onClick={addAdmin} className="px-4 rounded-xl bg-brand font-medium">Make admin</button>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">If they already have an account they're promoted instantly; otherwise they become admin the moment they sign up.</p>
                </div>

                {adminsData.admins?.map((m: any) => (
                  <div key={m.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-brand/20 grid place-items-center overflow-hidden shrink-0">
                      {m.avatar_url ? <img src={m.avatar_url} className="h-full w-full object-cover" /> : <UserCog className="h-4 w-4 text-brand" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate flex items-center gap-1.5">
                        {m.display_name || m.handle}
                        {m.super && <span className="inline-flex items-center gap-1 text-[10px] bg-amber-500/15 text-amber-300 px-1.5 py-0.5 rounded-full"><Crown className="h-3 w-3" />super</span>}
                      </div>
                      <div className="text-xs text-slate-500 truncate">{m.email || `#${m.handle}`}</div>
                    </div>
                    {m.super
                      ? <span className="text-xs text-slate-600">protected</span>
                      : <button onClick={() => removeAdmin((m.email || '').toLowerCase())} className="text-rose-400 hover:bg-rose-500/10 rounded-lg px-2.5 py-1.5 text-sm flex items-center gap-1"><Trash2 className="h-4 w-4" />Remove</button>}
                  </div>
                ))}

                {adminsData.pending?.length > 0 && (
                  <div className="bg-panel border border-edge rounded-2xl p-3">
                    <div className="text-xs text-slate-500 mb-2">Allowlisted (no account yet — become admin on signup)</div>
                    {adminsData.pending.map((e: string) => (
                      <div key={e} className="flex items-center gap-2 py-1">
                        <span className="text-sm flex-1 truncate">{e}</span>
                        <button onClick={() => removeAdmin(e)} className="text-rose-400 hover:bg-rose-500/10 rounded-lg px-2 py-1 text-xs">Remove</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === 'creators' && (
              <div className="space-y-4" data-testid="creators-panel">
                <div className="bg-panel border border-edge rounded-2xl p-4">
                  <div className="text-sm font-medium mb-1 flex items-center gap-1.5"><Star className="h-4 w-4 text-amber-300" />Assign creator access</div>
                  <p className="text-xs text-slate-500 mb-3">Manually unlock Creator Hub &amp; monetisation tools before Yoti + Stripe are wired up. Use <b className="text-rose-300">Make 18+</b> to designate an adult content creator (flags the account NSFW everywhere and bypasses age-verification as a temporary admin override). Reversible any time.</p>
                  <div className="flex gap-2">
                    <input value={creatorSearch} onChange={e => setCreatorSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchCreators()}
                      placeholder="Search users by name or @handle…" data-testid="creator-search-input"
                      className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
                    <button onClick={searchCreators} data-testid="creator-search-btn" className="px-4 py-2.5 rounded-xl bg-brand font-medium">Search</button>
                  </div>
                  {creatorResults.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {creatorResults.map(u => (
                        <div key={u.id} className="flex items-center gap-2 bg-ink border border-edge rounded-xl p-2.5 flex-wrap">
                          <div className="min-w-0 flex-1">
                            <div className="font-medium truncate flex items-center gap-1.5">{u.display_name}
                              <AdultBadge nsfw={u.account_nsfw} size={15} />
                              {u.is_creator && <span className="text-[10px] bg-amber-500/15 text-amber-300 px-1.5 py-0.5 rounded-full flex items-center gap-1"><Star className="h-3 w-3" />creator</span>}
                            </div>
                            <div className="text-xs text-slate-500">#{u.handle} · {u.account_type}{u.account_nsfw ? ' · 18+ adult' : ''}</div>
                          </div>
                          {u.is_creator
                            ? <button onClick={() => revokeCreator(u.handle)} data-testid={`revoke-creator-${u.handle}`} className="px-3 py-1.5 rounded-lg bg-white/5 text-xs">Remove</button>
                            : <button onClick={() => grantCreator(u.handle)} data-testid={`grant-creator-${u.handle}`} className="px-3 py-1.5 rounded-lg bg-brand/15 text-brand text-xs flex items-center gap-1"><Star className="h-3 w-3" />Make creator</button>}
                          {u.account_nsfw
                            ? <button onClick={() => revokeAdult(u.handle)} data-testid={`revoke-adult-${u.handle}`} className="px-3 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 text-xs flex items-center gap-1"><AdultBadge nsfw size={13} />Remove 18+</button>
                            : <button onClick={() => grantAdult(u.handle)} data-testid={`grant-adult-${u.handle}`} className="px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-300 text-xs">Make 18+</button>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-sm font-medium text-slate-300">Current creators ({creators.length})</div>
                {creators.length === 0 && <p className="text-center text-slate-500 py-6">No creators assigned yet.</p>}
                {creators.map(u => (
                  <div key={u.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3 flex-wrap">
                    <div className="h-9 w-9 rounded-full bg-amber-500/15 grid place-items-center overflow-hidden shrink-0">
                      {u.avatar_url ? <img src={u.avatar_url} className="h-full w-full object-cover" /> : <Star className="h-4 w-4 text-amber-300" />}
                    </div>
                    <div className="flex-1 min-w-0"><div className="font-medium truncate flex items-center gap-1.5">{u.display_name}<AdultBadge nsfw={u.account_nsfw} size={15} /></div><div className="text-xs text-slate-500 truncate">#{u.handle} · {u.email || u.account_type}{u.account_nsfw ? ' · 18+ adult' : ''}</div></div>
                    {u.account_nsfw
                      ? <button onClick={() => revokeAdult(u.handle)} className="px-3 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 text-xs flex items-center gap-1"><AdultBadge nsfw size={13} />Remove 18+</button>
                      : <button onClick={() => grantAdult(u.handle)} className="px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-300 text-xs">Make 18+</button>}
                    <button onClick={() => revokeCreator(u.handle)} className="px-3 py-1.5 rounded-lg bg-white/5 text-xs flex items-center gap-1"><Trash2 className="h-3.5 w-3.5" />Remove</button>
                  </div>
                ))}
              </div>
            )}

            {tab === 'support' && (
              <div className="space-y-2" data-testid="support-panel">
                <div className="bg-brand/5 border border-brand/20 rounded-2xl p-3 text-xs text-slate-300 flex items-start gap-2">
                  <MessageCircle className="h-4 w-4 text-brand shrink-0 mt-0.5" />
                  <span>Every member's chat with the <b>Skali Team</b> account, unread first. Shared by all staff and the Skali Team login; replies are delivered to members as Skali Team.</span>
                </div>
                {support.length === 0 && <p className="text-center text-slate-500 py-10">No support conversations yet.</p>}
                {support.map((t, i) => (<div key={t.user.id}>
                  {i === 0 && t.unread > 0 && <div className="text-xs uppercase tracking-wider text-brand font-semibold px-1 pt-1 pb-2" data-testid="support-unread-heading">Unread · {support.filter(x => x.unread > 0).length}</div>}
                  {t.unread === 0 && !t.solved && (i === 0 || support[i - 1].unread > 0) && <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold px-1 pt-3 pb-2" data-testid="support-earlier-heading">Earlier</div>}
                  {t.solved && (i === 0 || !support[i - 1].solved) && <div className="text-xs uppercase tracking-wider text-emerald-400/80 font-semibold px-1 pt-3 pb-2" data-testid="support-solved-heading">Solved · {support.filter(x => x.solved).length}</div>}
                  <button onClick={() => openSupport(t.user.handle)} data-testid={`support-thread-${t.user.handle}`}
                    className={`w-full text-left bg-panel border rounded-2xl p-3 flex items-center gap-3 hover:bg-white/5 ${t.unread > 0 ? 'border-brand/50' : 'border-edge'} ${t.solved ? 'opacity-70' : ''}`}>
                    <div className="h-10 w-10 rounded-full bg-white/5 grid place-items-center overflow-hidden shrink-0">
                      {t.user.avatar_url ? <img src={t.user.avatar_url} className="h-full w-full object-cover" /> : <Users className="h-4 w-4 text-slate-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate flex items-center gap-2">{t.user.display_name} <span className="text-xs text-slate-500">#{t.user.handle}</span></div>
                      <div className="text-xs text-slate-500 truncate">{t.from_user ? '' : '↩ '}{t.last}</div>
                      {t.assigned && <div className="text-[10px] text-amber-300/90 mt-0.5 flex items-center gap-1" data-testid={`support-assigned-${t.user.handle}`}><UserCog className="h-3 w-3" />{t.assigned.id === user?.id ? 'Handled by you' : `Handled by #${t.assigned.handle}`}</div>}
                      {t.solved && <div className="text-[10px] text-emerald-400/80 mt-0.5 flex items-center gap-1" data-testid={`support-solved-${t.user.handle}`}><Check className="h-3 w-3" />Solved{t.solved.solved_by ? ` by #${t.solved.solved_by}` : ''} · {timeAgo(t.solved.solved_at)}</div>}
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-[10px] text-slate-600">{timeAgo(t.created_at)}</div>
                      {t.unread > 0 && <span className="inline-block mt-1 text-[10px] bg-brand text-white rounded-full px-1.5 py-0.5" data-testid={`support-unread-${t.user.handle}`}>{t.unread}</span>}
                    </div>
                  </button>
                </div>))}
              </div>
            )}

            {tab === 'reports' && data.map(r => (
              <div key={r.id} className="bg-panel border border-edge rounded-2xl p-4" data-testid={`report-card-${r.id}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${SENSITIVE.includes(r.category) ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/15 text-amber-300'}`}>{r.category}</span>
                  <span data-testid={`report-status-${r.id}`} className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${r.assigned ? 'bg-sky-500/15 text-sky-300' : 'bg-white/5 text-slate-400'}`}>{r.assigned ? 'assigned' : 'open'}</span>
                  <span className="text-sm text-slate-400">{r.target_type}</span>
                  {r.target_user && <span className="text-sm">→ #{r.target_user.handle}</span>}
                  <span className="text-xs text-slate-600 ml-auto">reported by #{r.reporter_handle} · {timeAgo(r.created_at)}</span>
                </div>
                {r.preview && <div className="mt-2 text-sm text-slate-300 bg-ink border border-edge rounded-lg p-2">
                  {r.preview.text || '(no text)'} {r.preview.quarantined && <span className="text-rose-400 text-xs">· quarantined</span>}
                </div>}
                {r.note && <p className="mt-1 text-xs text-slate-500">Note: {r.note}</p>}
                <div className="mt-2 flex items-center gap-2 text-xs">
                  {r.assigned
                    ? <span className="text-sky-300 flex items-center gap-1" data-testid={`report-owner-${r.id}`}><UserCog className="h-3.5 w-3.5" />{r.assigned.id === user?.id ? 'Assigned to you' : `Owner: #${r.assigned.handle}`}</span>
                    : <span className="text-slate-500">Unassigned</span>}
                  {r.assigned?.id === user?.id
                    ? <button onClick={() => assignReport(r, false)} data-testid={`report-release-${r.id}`} className="ml-auto px-2.5 py-1 rounded-lg border border-edge text-slate-300">Release</button>
                    : <button onClick={() => assignReport(r, true)} data-testid={`report-assign-${r.id}`} className="ml-auto px-2.5 py-1 rounded-lg bg-sky-500/15 text-sky-300 font-semibold flex items-center gap-1"><Hand className="h-3.5 w-3.5" />{r.assigned ? 'Take over' : 'Assign to me'}</button>}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => act(r.id, 'dismiss')} className="px-3 py-1.5 rounded-lg border border-edge text-sm">Dismiss</button>
                  <button onClick={() => act(r.id, 'remove_content')} className="px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-300 text-sm flex items-center gap-1"><Trash2 className="h-3.5 w-3.5" />Remove content</button>
                  <button onClick={() => act(r.id, 'warn_user')} className="px-3 py-1.5 rounded-lg bg-white/5 text-sm">Soft warn</button>
                  <button onClick={() => act(r.id, 'strike_user')} className="px-3 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-sm flex items-center gap-1"><Ban className="h-3.5 w-3.5" />Strike</button>
                  <button onClick={() => act(r.id, 'uphold')} className="px-3 py-1.5 rounded-lg bg-orange-500/20 text-orange-300 text-sm font-medium">Uphold</button>
                  {isFull && <button onClick={() => act(r.id, 'uphold', true)} className="px-3 py-1.5 rounded-lg bg-red-600/25 text-red-300 text-sm font-medium flex items-center gap-1"><Ban className="h-3.5 w-3.5" />Uphold · terminate</button>}
                </div>
              </div>
            ))}

            {tab === 'csam' && data.map(r => (
              <div key={r.id} className="bg-rose-500/5 border border-rose-500/30 rounded-2xl p-4">
                <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-rose-400" />
                  <span className="font-semibold text-rose-300">{r.category}</span>
                  {r.escalated && <span className="text-xs bg-rose-500/30 text-rose-200 px-1.5 py-0.5 rounded">{r.ceop_ref || 'escalated'}</span>}
                  {r.status === 'resolved' && <span className="text-xs bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded">resolved</span>}
                  <span className="text-xs text-slate-500 ml-auto">{timeAgo(r.created_at)}</span></div>
                <div className="text-sm text-slate-400 mt-1">{r.target_type} · {r.target_id} · reporter #{r.reporter_handle}</div>
                <div className="flex gap-2 mt-3">
                  {!r.escalated && <button onClick={() => csamEscalate(r.id)} className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-sm flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" />Escalate to CEOP</button>}
                  {r.status !== 'resolved' && <button onClick={() => csamResolve(r.id)} className="px-3 py-1.5 rounded-lg border border-edge text-sm flex items-center gap-1"><Check className="h-3.5 w-3.5" />Mark resolved</button>}
                </div>
              </div>
            ))}

            {tab === 'nsfw' && (data.length === 0
              ? <p className="text-center text-slate-500 py-10">No AI-flagged media awaiting review.</p>
              : data.map(r => (
                <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 flex gap-3">
                  <img src={r.signed_url} className="h-20 w-20 rounded-lg object-cover blur-md hover:blur-none transition shrink-0 bg-black/40" title="Hover to reveal" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">#{r.handle} <span className="text-xs text-slate-500 ml-1">{timeAgo(r.created_at)}</span></div>
                    <div className="text-xs text-amber-300 mt-0.5">{r.verdict?.reason}</div>
                    <div className="text-[11px] text-slate-500 mt-1">{Object.entries(r.verdict?.labels || {}).filter(([, v]: any) => v >= 0.3).map(([k, v]: any) => `${k} ${(v * 100).toFixed(0)}%`).join(' · ') || 'low-confidence flags'}</div>
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => nsfwResolve(r.id, 'remove')} className="px-3 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-xs flex items-center gap-1"><Trash2 className="h-3.5 w-3.5" />Remove content</button>
                      <button onClick={() => nsfwResolve(r.id, 'dismiss')} className="px-3 py-1.5 rounded-lg border border-edge text-xs">Dismiss (safe)</button>
                    </div>
                  </div>
                </div>
              )))}

            {tab === 'watchlist' && (data.length === 0
              ? <p className="text-center text-slate-500 py-10">No accounts on the watchlist.</p>
              : data.map(u => (
                <div key={u.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3 flex-wrap">
                  <Bookmark className="h-4 w-4 text-brand shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{u.display_name} <span className="text-xs text-slate-500">#{u.handle}</span></div>
                    <div className="text-xs text-slate-500">{u.watch_reason || 'under review'} · by #{u.watched_by} · {timeAgo(u.watched_at)}</div>
                  </div>
                  <button onClick={() => viewNotes(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs flex items-center gap-1"><StickyNote className="h-3 w-3" />Notes</button>
                  <button onClick={() => unwatch(u.handle)} className="px-2.5 py-1.5 rounded-lg border border-edge text-xs">Remove</button>
                </div>
              )))}

            {tab === 'users' && data.map(u => (
              <div key={u.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate flex items-center gap-2">{u.display_name}
                    <AdultBadge nsfw={u.account_nsfw} size={15} />
                    {u.is_admin && <Shield className="h-3.5 w-3.5 text-brand" />}
                    {u.flagged && <span className="text-xs bg-rose-500/20 text-rose-300 px-1.5 rounded flex items-center gap-1"><Flag className="h-3 w-3" />flagged</span>}
                    {u.watchlisted && <span className="text-xs bg-brand/20 text-brand px-1.5 rounded flex items-center gap-1"><Bookmark className="h-3 w-3" />watch</span>}
                    {u.banned && <span className="text-xs bg-rose-500/20 text-rose-300 px-1.5 rounded">banned</span>}
                    {u.suspended_until && !u.banned && <span className="text-xs bg-amber-500/20 text-amber-300 px-1.5 rounded">suspended</span>}
                    {u.creator_safety_flag && <span className="text-xs bg-orange-500/20 text-orange-300 px-1.5 rounded">creator-safety</span>}
                    {u.no_appeal && <span className="text-xs bg-red-600/25 text-red-300 px-1.5 rounded">no appeal</span>}
                  </div>
                  <div className="text-xs text-slate-500">#{u.handle} · {u.account_type} · strikes: {u.strikes} · upheld: {u.upheld_reports || 0}{u.flag_reason ? ` · ${u.flag_reason}` : ''}</div>
                </div>
                {u.flagged
                  ? <button onClick={() => unflag(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Unflag</button>
                  : <button onClick={() => flag(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 text-rose-300 text-xs flex items-center gap-1"><Flag className="h-3 w-3" />Flag</button>}
                {u.watchlisted
                  ? <button onClick={() => unwatch(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Unwatch</button>
                  : <button onClick={() => watch(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-brand/10 text-brand text-xs flex items-center gap-1"><Bookmark className="h-3 w-3" />Watch</button>}
                <button onClick={() => addNote(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs flex items-center gap-1"><StickyNote className="h-3 w-3" />Note</button>
                {isFull && (u.account_nsfw
                  ? <button onClick={() => revokeAdult(u.handle)} data-testid={`users-revoke-adult-${u.handle}`} className="px-2.5 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 text-xs flex items-center gap-1"><AdultBadge nsfw size={12} />Remove 18+</button>
                  : <button onClick={() => grantAdult(u.handle)} data-testid={`users-grant-adult-${u.handle}`} className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 text-rose-300 text-xs">Make 18+</button>)}
                {isFull && <select value={u.account_type} onChange={e => setAcct(u.handle, e.target.value)} title="Account tier"
                  className="px-2 py-1.5 rounded-lg bg-ink border border-edge text-xs outline-none focus:border-brand">
                  <option value="free">Free</option>
                  <option value="premium">Premium</option>
                  <option value="verified">Verified</option>
                </select>}
                <button onClick={() => strike(u.handle, true)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Warn</button>
                <button onClick={() => strike(u.handle, false)} className="px-2.5 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-xs">Strike</button>
                {isFull && (u.suspended_until || u.banned) && <button onClick={() => unsuspend(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs flex items-center gap-1"><Check className="h-3 w-3" />Restore</button>}
                {isFull && (u.strikes > 0 || u.upheld_reports > 0 || u.creator_safety_flag) && !u.no_appeal &&
                  <button onClick={() => clearRecord(u.handle)} title="12-month rehab: clear record" className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Clear record</button>}
              </div>
            ))}

            {tab === 'audit' && <AuditPanel />}
          </div>
        )}

        {/* Danger zone — production bootstrap tools */}
        {isSuper && <section className="mt-4 border border-rose-500/30 bg-rose-500/5 rounded-2xl p-5" data-testid="admin-danger-zone">
          <div className="flex items-center gap-2 text-rose-400 mb-2">
            <AlertTriangle className="h-5 w-5" />
            <h2 className="font-bold tracking-wide">DANGER ZONE</h2>
          </div>
          <p className="text-sm text-slate-400 mb-4">
            One-off bootstrap for production. Promote your real email to admin, sign in as that account,
            then purge the seeded demo accounts (alice / bob / teen) and optionally the seeded admin too.
          </p>
          <div className="flex flex-col sm:flex-row flex-wrap gap-2">
            <button onClick={promote} disabled={dz}
              className="px-4 py-2.5 rounded-xl border border-edge hover:bg-white/5 font-medium disabled:opacity-50 flex items-center justify-center gap-2">
              {dz ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />} Promote email to admin…
            </button>
            <button onClick={() => purgeDemo(false)} disabled={dz}
              className="px-4 py-2.5 rounded-xl border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 font-medium disabled:opacity-50 flex items-center justify-center gap-2">
              <Trash2 className="h-4 w-4" /> Purge alice / bob / teen
            </button>
            <button onClick={() => purgeDemo(true)} disabled={dz}
              className="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 font-medium disabled:opacity-50 flex items-center justify-center gap-2">
              <Trash2 className="h-4 w-4" /> Purge ALL demo (incl. seeded admin)
            </button>
          </div>
        </section>}
      </div>

      {supportThread && (
        <div className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center p-4" onClick={() => setSupportThread(null)}>
          <div className="bg-panel border border-edge rounded-2xl w-full max-w-lg h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 p-4 border-b border-edge">
              <MessageCircle className="h-5 w-5 text-brand" />
              <div className="flex-1 min-w-0"><div className="font-semibold truncate">{supportThread.user.display_name}</div><div className="text-xs text-slate-500 truncate" data-testid="support-thread-status">#{supportThread.user.handle}{supportThread.assigned ? ` · ${supportThread.assigned.id === user?.id ? 'you are handling this' : `handled by #${supportThread.assigned.handle}`}` : ''} · {supportThread.solved ? `solved${supportThread.solved.solved_by ? ` by #${supportThread.solved.solved_by}` : ''}` : 'replying as Skali Team'}</div></div>
              {supportThread.assigned?.id === user?.id ? (
                <button onClick={() => claimSupport(supportThread.user.handle, false)} data-testid="support-release-btn"
                  className="px-3 h-8 rounded-lg border border-edge text-xs font-semibold text-slate-300 hover:bg-white/5">Release</button>
              ) : (
                <button onClick={() => claimSupport(supportThread.user.handle, true, supportThread.assigned)} data-testid="support-claim-btn"
                  className="px-3 h-8 rounded-lg border border-amber-500/40 bg-amber-500/10 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 flex items-center gap-1"><UserCog className="h-3.5 w-3.5" />{supportThread.assigned ? 'Take over' : 'Assign to me'}</button>
              )}
              {supportThread.solved ? (
                <button onClick={() => solveSupport(supportThread.user.handle, false)} data-testid="support-reopen-btn"
                  className="px-3 h-8 rounded-lg border border-edge text-xs font-semibold text-slate-300 hover:bg-white/5">Reopen</button>
              ) : (
                <button onClick={() => solveSupport(supportThread.user.handle, true)} data-testid="support-solve-btn"
                  className="px-3 h-8 rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20 flex items-center gap-1"><Check className="h-3.5 w-3.5" />Mark solved</button>
              )}
              <button onClick={() => setSupportThread(null)} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-4 w-4" /></button>
            </div>
            <div className="p-4 overflow-y-auto space-y-2 flex-1">
              {supportThread.messages.length === 0 ? <p className="text-center text-slate-500 py-8">No messages.</p> : supportThread.messages.map((m: any) => (
                <div key={m.id} className={`flex ${m.from_bot ? 'justify-end' : ''}`}>
                  <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${m.from_bot ? 'bg-brand/20' : 'bg-white/5 border border-edge'}`}>
                    {m.text}
                    {m.media_url && <img src={m.media_url} className="mt-1 rounded-lg max-h-48" />}
                    <div className="text-[10px] text-slate-500 mt-1">{m.from_bot ? (m.replied_by ? `#${m.replied_by}` : 'Skali Team') : `#${supportThread.user.handle}`} · {timeAgo(m.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="p-3 border-t border-edge flex gap-2">
              <input value={supportReplyText} onChange={e => setSupportReplyText(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendSupport()}
                placeholder="Reply as Skali Team…" data-testid="support-reply-input"
                className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
              <button onClick={sendSupport} data-testid="support-reply-send" className="px-4 rounded-xl bg-brand font-medium flex items-center gap-1"><Send className="h-4 w-4" /></button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
