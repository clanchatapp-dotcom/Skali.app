import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { timeAgo } from '../lib/ui'
import RoleBadge, { ROLE_META } from '../components/RoleBadge'
import { Shield, Flag, AlertTriangle, Users, ScrollText, Ban, Loader2, Check, Trash2, Eye, X, Lock, UserCog, Crown, ScanEye, Bookmark, StickyNote } from 'lucide-react'

// `full: true` tabs are visible ONLY to full admins (super_admin / co_admin).
// The rest are also visible to moderators.
const TABS = [
  { key: 'reports', label: 'Reports', icon: Flag },
  { key: 'csam', label: 'CSAM', icon: AlertTriangle, full: true },
  { key: 'nsfw', label: 'NSFW', icon: ScanEye },
  { key: 'watchlist', label: 'Watchlist', icon: Bookmark },
  { key: 'investigate', label: 'Investigate', icon: Eye, full: true },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'dmaccess', label: 'DM Access', icon: Lock, full: true },
  { key: 'roles', label: 'Roles', icon: Crown, full: true },
  { key: 'admins', label: 'Admins', icon: UserCog, full: true },
  { key: 'audit', label: 'Audit log', icon: ScrollText, full: true },
]

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
  const [tab, setTab] = useState('reports')
  const [stats, setStats] = useState<any>({})
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [dm, setDm] = useState<any>(null)
  const [dmLoading, setDmLoading] = useState(false)
  const [adminsData, setAdminsData] = useState<any>({ admins: [], pending: [] })
  const [newAdminEmail, setNewAdminEmail] = useState('')
  const [invHandle, setInvHandle] = useState('')
  const [inv, setInv] = useState<any>(null)
  const [invLoading, setInvLoading] = useState(false)
  const [roles, setRoles] = useState<any[]>([])
  const [assignHandle, setAssignHandle] = useState('')
  const [assignRole, setAssignRole] = useState('moderator')
  const isFull = !!user?.is_admin                      // super_admin OR co_admin
  const isSuper = (user as any)?.role === 'super_admin'
  const visibleTabs = TABS.filter(t => isFull || !t.full)
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
  const [dmAccess, setDmAccess] = useState<any>({ as_super: false, allow_coadmin_dms: false, requests: [] })
  const [reqHandle, setReqHandle] = useState('')
  const loadDmAccess = async () => { try { setDmAccess(await api.dmAccessList()) } catch {} }
  const toggleCoDms = async (enabled: boolean) => {
    try { await api.setCoadminDms(enabled); await loadDmAccess() } catch (e: any) { alert(e.message) }
  }
  const requestDmAccess = async () => {
    const h = reqHandle.trim().replace(/^[#@]/, '')
    if (!h) return
    try { await api.dmAccessRequest(h); setReqHandle(''); await loadDmAccess(); alert('Request sent to the Super Admin.') }
    catch (e: any) { alert(e.message) }
  }
  const decideDmAccess = async (id: string, decision: 'approve' | 'deny') => {
    try { await api.dmAccessDecide(id, decision); await loadDmAccess() } catch (e: any) { alert(e.message) }
  }
  const runInvestigation = async () => {
    const h = invHandle.trim().replace(/^@/, '')
    if (!h) return
    setInvLoading(true); setInv(null)
    try { setInv(await api.adminInvestigate(h)) } catch (e: any) { alert(e.message) } finally { setInvLoading(false) }
  }

  const loadStats = () => api.adminStats().then(setStats).catch(() => {})
  const loadAdmins = async () => { try { setAdminsData(await api.adminListAdmins()) } catch {} }
  const load = async () => {
    setLoading(true)
    try {
      if (tab === 'reports') setData(await api.adminReports('open'))
      else if (tab === 'csam') setData(await api.adminCsam())
      else if (tab === 'nsfw') setData(await api.adminNsfw('open'))
      else if (tab === 'watchlist') setData(await api.adminWatchlist())
      else if (tab === 'users') setData(await api.adminUsers(q))
      else if (tab === 'admins') { await loadAdmins(); setData([]) }
      else if (tab === 'roles') { await loadRoles(); setData([]) }
      else if (tab === 'dmaccess') { await loadDmAccess(); setData([]) }
      else if (tab === 'audit') setData(await api.adminAudit())
    } catch { setData([]) } finally { setLoading(false) }
  }
  useEffect(() => { loadStats() }, [])
  useEffect(() => { load() }, [tab])

  if (user && !user.is_admin && !(user as any).can_moderate) return <Navigate to="/" replace />

  const act = async (id: string, action: string, severe = false) => {
    let reason = ''
    if (action !== 'dismiss') reason = window.prompt(`Reason for "${action.replace('_', ' ')}"?`, '') || ''
    if (action === 'uphold' && severe && !window.confirm('Zero-tolerance: this permanently terminates the account with NO appeal. Continue?')) return
    await api.adminAction(id, action, reason, severe); await load(); await loadStats()
  }
  const clearRecord = async (handle: string) => {
    if (!window.confirm(`Clear @${handle}'s strikes & upheld reports (12-month rehab)?`)) return
    try { await api.adminClearStrikes(handle); await load(); await loadStats() } catch (e: any) { alert(e.message) }
  }
  const strike = async (handle: string, soft: boolean) => {
    const reason = window.prompt(soft ? 'Soft warning message:' : 'Strike reason:', '') || ''
    if (!reason) return
    await api.adminStrike(handle, reason, soft ? 'soft' : undefined); await load(); await loadStats()
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
  const csamEscalate = async (id: string) => { try { const r = await api.adminCsamEscalate(id); alert(`Escalated. Reference: ${r.ceop_ref}`); await load() } catch (e: any) { alert(e.message) } }
  const csamResolve = async (id: string) => { await api.adminCsamResolve(id); await load(); await loadStats() }
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
  const [dz, setDz] = useState(false)
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
  const viewDms = async (handle: string) => {
    setDm({ loading: true }); setDmLoading(true)
    try { setDm(await api.adminUserDms(handle)) } catch (e: any) { alert(e.message); setDm(null) } finally { setDmLoading(false) }
  }

  return (
    <div>
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-2">
        <Shield className="h-5 w-5 text-brand" /><h1 className="text-xl font-extrabold">Admin</h1>
        <span className="text-xs text-slate-500 ml-2">Reports · CSAM · Trust &amp; Safety</span>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
          <Stat label="Users" value={stats.users} />
          <Stat label="Posts" value={stats.posts} />
          <Stat label="Open reports" value={stats.open_reports} danger />
          <Stat label="CSAM queue" value={stats.csam_reports} danger />
          <Stat label="Suspended" value={stats.suspended} />
          <Stat label="Banned" value={stats.banned} />
          <Stat label="Flagged" value={stats.flagged} danger />
          <Stat label="Watchlist" value={stats.watchlisted} />
          <Stat label="NSFW queue" value={stats.nsfw_open} danger />
          <Stat label="Deleted" value={stats.deleted} />
        </div>

        <div className="flex gap-1 bg-panel border border-edge rounded-xl p-1 overflow-x-auto max-w-full">
          {visibleTabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg ${tab === t.key ? 'bg-brand text-white' : 'text-slate-400 hover:text-white'}`}>
              <t.icon className="h-4 w-4" />{t.label}
            </button>
          ))}
        </div>

        {tab === 'users' && (
          <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()}
            placeholder="Search users, press Enter…" className="w-full bg-ink border border-edge rounded-xl px-4 py-2.5 outline-none focus:border-brand" />
        )}

        {loading ? <div className="py-16 grid place-items-center text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div> : (
          <div className="space-y-2">
            {data.length === 0 && tab !== 'admins' && tab !== 'investigate' && tab !== 'roles' && tab !== 'dmaccess' && <p className="text-center text-slate-500 py-10">Nothing here.</p>}

            {tab === 'dmaccess' && (
              <div className="space-y-4">
                {dmAccess.as_super ? (
                  <>
                    <div className="bg-panel border border-edge rounded-2xl p-4 flex items-center gap-3">
                      <Lock className="h-5 w-5 text-brand shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium">Allow Co-Admins to view my DMs</div>
                        <div className="text-xs text-slate-500">When off, a Co-Admin must request one-time permission each time.</div>
                      </div>
                      <button onClick={() => toggleCoDms(!dmAccess.allow_coadmin_dms)}
                        className={`h-7 w-12 rounded-full p-0.5 transition shrink-0 ${dmAccess.allow_coadmin_dms ? 'bg-emerald-500' : 'bg-white/15'}`}>
                        <span className={`block h-6 w-6 rounded-full bg-white transition ${dmAccess.allow_coadmin_dms ? 'translate-x-5' : ''}`} />
                      </button>
                    </div>
                    <div className="text-sm font-medium text-slate-300">Requests to view your DMs</div>
                    {dmAccess.requests.length === 0 && <p className="text-center text-slate-500 py-6">No requests.</p>}
                    {dmAccess.requests.map((r: any) => (
                      <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{r.requester_name || r.requester_handle} <span className="text-slate-500 text-sm">#{r.requester_handle}</span></div>
                          <div className="text-xs text-slate-500">{timeAgo(r.created_at)} · <span className={r.status === 'approved' ? 'text-emerald-400' : r.status === 'denied' ? 'text-rose-400' : 'text-amber-400'}>{r.status}</span>{r.status === 'approved' && (r.used ? ' · used' : ' · unused (one-time)')}</div>
                        </div>
                        {r.status === 'pending' && <>
                          <button onClick={() => decideDmAccess(r.id, 'approve')} className="px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs flex items-center gap-1"><Check className="h-3 w-3" />Approve</button>
                          <button onClick={() => decideDmAccess(r.id, 'deny')} className="px-2.5 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-xs flex items-center gap-1"><X className="h-3 w-3" />Deny</button>
                        </>}
                      </div>
                    ))}
                  </>
                ) : (
                  <>
                    <div className="bg-panel border border-edge rounded-2xl p-4">
                      <div className="text-sm font-medium mb-2">Request permission to view a Super Admin's DMs</div>
                      <div className="flex gap-2">
                        <input value={reqHandle} onChange={e => setReqHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && requestDmAccess()}
                          placeholder="@super-admin-handle" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
                        <button onClick={requestDmAccess} className="px-4 py-2.5 rounded-xl bg-brand font-medium">Request</button>
                      </div>
                      <p className="text-xs text-slate-500 mt-2">Approved requests grant one-time access. The Super Admin is notified and can approve or deny.</p>
                    </div>
                    <div className="text-sm font-medium text-slate-300">Your requests</div>
                    {dmAccess.requests.length === 0 && <p className="text-center text-slate-500 py-6">No requests yet.</p>}
                    {dmAccess.requests.map((r: any) => (
                      <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">#{r.target_handle}</div>
                          <div className="text-xs text-slate-500">{timeAgo(r.created_at)} · <span className={r.status === 'approved' ? 'text-emerald-400' : r.status === 'denied' ? 'text-rose-400' : 'text-amber-400'}>{r.status}</span>{r.status === 'approved' && (r.used ? ' · used' : ' · ready (one-time)')}</div>
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {tab === 'roles' && (
              <div className="space-y-4">
                <div className="bg-panel border border-edge rounded-2xl p-4">
                  <div className="text-sm font-medium mb-2">Assign a staff role</div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input value={assignHandle} onChange={e => setAssignHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && doAssign()}
                      placeholder="@handle" className="flex-1 bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand" />
                    <select value={assignRole} onChange={e => setAssignRole(e.target.value)}
                      className="bg-ink border border-edge rounded-xl px-3 py-2.5 outline-none focus:border-brand">
                      {isSuper && <option value="co_admin">Co-Admin (pink)</option>}
                      <option value="moderator">Moderator (red)</option>
                      <option value="first_tester">First Tester (blue)</option>
                    </select>
                    <button onClick={doAssign} className="px-4 py-2.5 rounded-xl bg-brand font-medium">Assign</button>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">Role-holders become verified. Co-Admins have full admin access; only a Super Admin can add or remove Co-Admins.{!isSuper && ' (You are a Co-Admin — you can assign Moderators and First Testers.)'}</p>
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
                      : (m.role === 'co_admin' && !isSuper)
                        ? <span className="text-[10px] text-slate-600 shrink-0">super only</span>
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

            {tab === 'reports' && data.map(r => (
              <div key={r.id} className="bg-panel border border-edge rounded-2xl p-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${['csam', 'underage'].includes(r.category) ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/15 text-amber-300'}`}>{r.category}</span>
                  <span className="text-sm text-slate-400">{r.target_type}</span>
                  {r.target_user && <span className="text-sm">→ #{r.target_user.handle}</span>}
                  <span className="text-xs text-slate-600 ml-auto">reported by #{r.reporter_handle} · {timeAgo(r.created_at)}</span>
                </div>
                {r.preview && <div className="mt-2 text-sm text-slate-300 bg-ink border border-edge rounded-lg p-2">
                  {r.preview.text || '(no text)'} {r.preview.quarantined && <span className="text-rose-400 text-xs">· quarantined</span>}
                </div>}
                {r.note && <p className="mt-1 text-xs text-slate-500">Note: {r.note}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => act(r.id, 'dismiss')} className="px-3 py-1.5 rounded-lg border border-edge text-sm">Dismiss</button>
                  <button onClick={() => act(r.id, 'remove_content')} className="px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-300 text-sm flex items-center gap-1"><Trash2 className="h-3.5 w-3.5" />Remove content</button>
                  <button onClick={() => act(r.id, 'warn_user')} className="px-3 py-1.5 rounded-lg bg-white/5 text-sm">Soft warn</button>
                  <button onClick={() => act(r.id, 'strike_user')} className="px-3 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-sm flex items-center gap-1"><Ban className="h-3.5 w-3.5" />Strike</button>
                  <button onClick={() => act(r.id, 'uphold')} className="px-3 py-1.5 rounded-lg bg-orange-500/20 text-orange-300 text-sm font-medium">Uphold</button>
                  <button onClick={() => act(r.id, 'uphold', true)} className="px-3 py-1.5 rounded-lg bg-red-600/25 text-red-300 text-sm font-medium flex items-center gap-1"><Ban className="h-3.5 w-3.5" />Uphold · terminate</button>
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

            {tab === 'investigate' && (
              <div className="space-y-4">
                <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-3 text-xs text-rose-200 flex items-start gap-2">
                  <Lock className="h-4 w-4 shrink-0 mt-0.5" />
                  <span><b>Silent investigation.</b> Lawful, warrant-based inspection (UK IPA / court order). The subject is <b>not</b> notified. Every access is written to the audit log. Only Watchlisted or Flagged accounts can be inspected.</span>
                </div>
                <div className="flex gap-2">
                  <input value={invHandle} onChange={e => setInvHandle(e.target.value)} onKeyDown={e => e.key === 'Enter' && runInvestigation()}
                    placeholder="@handle to inspect" className="flex-1 bg-panel border border-edge rounded-xl px-4 py-2.5 outline-none focus:border-brand" />
                  <button onClick={runInvestigation} disabled={invLoading} className="px-4 py-2.5 rounded-xl bg-brand font-semibold disabled:opacity-50 flex items-center gap-2">
                    {invLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}Inspect
                  </button>
                </div>
                {inv && (
                  <div className="space-y-4">
                    <div className="bg-panel border border-edge rounded-2xl p-3">
                      <div className="font-semibold">{inv.subject.display_name} <span className="text-xs text-slate-500">#{inv.subject.handle}</span></div>
                      <div className="text-xs text-slate-500">{inv.subject.email} {inv.subject.is_minor && '· MINOR'} {inv.subject.flagged && '· flagged'} {inv.subject.watchlisted && '· watchlisted'}</div>
                    </div>
                    <div>
                      <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Posts ({inv.posts.length})</h3>
                      <div className="space-y-2">
                        {inv.posts.map((p: any) => (
                          <div key={p.id} className="bg-panel border border-edge rounded-xl p-3 text-sm">
                            <div className="text-[10px] uppercase text-slate-500 mb-1">{p.tier} · {timeAgo(p.created_at)}{p.ai_label !== 'none' ? ` · AI:${p.ai_label}` : ''}</div>
                            {p.text && <p className="whitespace-pre-wrap break-words">{p.text}</p>}
                            {p.media_url && <img src={p.media_url} className="mt-1 rounded-lg max-h-48" />}
                          </div>
                        ))}
                        {inv.posts.length === 0 && <p className="text-slate-500 text-sm">No posts.</p>}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">DM threads ({inv.dms.length})</h3>
                      <div className="space-y-3">
                        {inv.dms.map((t: any, i: number) => (
                          <div key={i} className="bg-panel border border-edge rounded-xl p-3">
                            <div className="text-xs font-medium mb-2">with {t.peer.display_name} <span className="text-slate-500">#{t.peer.handle}</span></div>
                            <div className="space-y-1.5">
                              {t.messages.map((m: any, j: number) => (
                                <div key={j} className={`text-sm ${m.from_subject ? 'text-white' : 'text-slate-400'}`}>
                                  <span className="text-[10px] text-slate-600 mr-1">{m.from_subject ? '→' : '←'}</span>
                                  {m.deleted ? <em className="text-slate-600">(deleted)</em> : <>
                                    {m.text}
                                    {m.media_url && <img src={m.media_url} className="mt-1 rounded max-h-40" />}
                                    {m.view_once && !m.media_url && <em className="text-slate-600"> (one-time media, already viewed)</em>}
                                  </>}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                        {inv.dms.length === 0 && <p className="text-slate-500 text-sm">No DMs.</p>}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Groups ({inv.groups.length})</h3>
                      <div className="space-y-2">
                        {inv.groups.map((g: any) => (
                          <div key={g.id} className="bg-panel border border-edge rounded-xl p-3 text-sm flex items-center gap-2">
                            <Users className="h-4 w-4 text-slate-500" />{g.name} <span className="text-xs text-slate-500">· {g.member_count} members {g.is_owner && '· owner'}</span>
                          </div>
                        ))}
                        {inv.groups.length === 0 && <p className="text-slate-500 text-sm">No groups.</p>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {tab === 'users' && data.map(u => (
              <div key={u.id} className="bg-panel border border-edge rounded-2xl p-3 flex items-center gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate flex items-center gap-2">{u.display_name}
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
                <select value={u.account_type} onChange={e => setAcct(u.handle, e.target.value)} title="Account tier"
                  className="px-2 py-1.5 rounded-lg bg-ink border border-edge text-xs outline-none focus:border-brand">
                  <option value="free">Free</option>
                  <option value="premium">Premium</option>
                  <option value="verified">Verified</option>
                </select>
                {u.flagged && <button onClick={() => viewDms(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-brand/15 text-brand text-xs flex items-center gap-1"><Eye className="h-3 w-3" />View DMs</button>}
                <button onClick={() => strike(u.handle, true)} className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Warn</button>
                <button onClick={() => strike(u.handle, false)} className="px-2.5 py-1.5 rounded-lg bg-rose-500/15 text-rose-300 text-xs">Strike</button>
                {(u.suspended_until || u.banned) && <button onClick={() => unsuspend(u.handle)} className="px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs flex items-center gap-1"><Check className="h-3 w-3" />Restore</button>}
                {isFull && (u.strikes > 0 || u.upheld_reports > 0 || u.creator_safety_flag) && !u.no_appeal &&
                  <button onClick={() => clearRecord(u.handle)} title="12-month rehab: clear record" className="px-2.5 py-1.5 rounded-lg bg-white/5 text-xs">Clear record</button>}
              </div>
            ))}

            {tab === 'audit' && data.map(r => (
              <div key={r.id} className="bg-panel border border-edge rounded-2xl p-3 text-sm flex items-center gap-3">
                <ScrollText className="h-4 w-4 text-slate-500" />
                <div className="flex-1"><span className="font-medium">#{r.admin_handle}</span> <span className="text-brand">{r.action}</span> <span className="text-slate-400">{r.target}</span>
                  {r.detail && <span className="text-slate-500"> — {r.detail}</span>}</div>
                <span className="text-xs text-slate-600">{timeAgo(r.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Danger zone — production bootstrap tools */}
        <section className="mt-4 border border-rose-500/30 bg-rose-500/5 rounded-2xl p-5">
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
        </section>
      </div>

      {dm && (
        <div className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center p-4" onClick={() => setDm(null)}>
          <div className="bg-panel border border-edge rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 p-4 border-b border-edge">
              <Eye className="h-5 w-5 text-brand" />
              <div className="flex-1 min-w-0">
                <div className="font-semibold">Discreet DM review</div>
                <div className="text-xs text-slate-500 truncate">
                  {dm.loading ? 'Loading…' : <>#{dm.user?.handle} · reason: {dm.user?.flag_reason || '—'} · access logged to audit</>}
                </div>
              </div>
              <button onClick={() => setDm(null)} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"><X className="h-4 w-4" /></button>
            </div>
            <div className="p-4 overflow-y-auto space-y-4">
              {(dmLoading || dm.loading) ? <div className="py-10 grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>
                : (dm.threads?.length ? dm.threads.map((t: any, i: number) => (
                  <div key={i} className="border border-edge rounded-xl overflow-hidden">
                    <div className="px-3 py-2 bg-white/5 text-sm font-medium flex items-center gap-2"><Lock className="h-3.5 w-3.5 text-emerald-400" />with #{t.peer.handle}</div>
                    <div className="p-3 space-y-1.5">
                      {t.messages.map((m: any, k: number) => (
                        <div key={k} className={`flex ${m.from_flagged ? 'justify-end' : ''}`}>
                          <div className={`max-w-[80%] rounded-xl px-3 py-1.5 text-sm ${m.from_flagged ? 'bg-brand/20' : 'bg-white/5 border border-edge'}`}>
                            <div className="text-[10px] text-slate-500 mb-0.5">{m.from_flagged ? `#${dm.user.handle}` : `#${t.peer.handle}`} · {timeAgo(m.created_at)}</div>
                            {m.text}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )) : <p className="text-center text-slate-500 py-10">No DMs found for this account.</p>)}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
