import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { Users2, ArrowLeft, Loader2, UserMinus, Lock, Check, Ban, VolumeX, ShieldOff, UserPlus } from 'lucide-react'

const TABS = [
  { key: 'requests', label: 'Requests' },
  { key: 'followers', label: 'Followers' },
  { key: 'following', label: 'Following' },
  { key: 'inner', label: 'Inner Circle' },
  { key: 'blocked', label: 'Blocked & Muted' },
] as const
type TabKey = typeof TABS[number]['key']

export default function Connections() {
  const nav = useNavigate()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabKey>('followers')
  const [busy, setBusy] = useState<string | null>(null)

  const load = async () => {
    try { setData(await api.connections()) } catch {}
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const act = async (key: string, fn: () => Promise<any>) => {
    setBusy(key)
    try { await fn(); await load() } catch (e: any) { alert(e.message || 'Something went wrong') }
    setBusy(null)
  }

  if (loading) return <div className="py-24 grid place-items-center text-slate-500"><Loader2 className="h-6 w-6 animate-spin" /></div>

  const c = data?.counts || {}
  const rel = data?.relations || { block: [], mute: [], restrict: [] }
  const blockedTotal = rel.block.length + rel.mute.length + rel.restrict.length

  const Row = ({ p, children }: { p: any; children?: React.ReactNode }) => (
    <div className="flex items-center gap-3 py-3 border-b border-edge/60 last:border-0">
      <Link to={`/u/${p.handle}`}><Avatar id={p.id} name={p.display_name} url={p.avatar_url} size={42} /></Link>
      <Link to={`/u/${p.handle}`} className="flex-1 min-w-0">
        <div className="font-medium truncate">{p.display_name}</div>
        <div className="text-xs text-slate-500 truncate">#{p.handle}</div>
      </Link>
      <div className="flex items-center gap-2 shrink-0">{children}</div>
    </div>
  )

  const badge = (n: number) => n > 0 ? <span className="ml-1.5 text-[11px] px-1.5 py-0.5 rounded-full bg-brand/20 text-brand">{n}</span> : null
  const count = (k: TabKey) => k === 'blocked' ? blockedTotal : (c[k] || 0)

  return (
    <div className="max-w-2xl mx-auto w-full">
      <div className="sticky top-0 z-30 bg-ink/80 backdrop-blur border-b border-edge px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center gap-3">
        <button onClick={() => nav(-1)} className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10 text-slate-300"><ArrowLeft className="h-5 w-5" /></button>
        <Users2 className="h-5 w-5 text-brand" />
        <h1 className="text-lg font-extrabold">Connections</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-edge overflow-x-auto">
        <div className="flex items-center px-2 w-max">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`relative shrink-0 whitespace-nowrap px-3.5 py-3 text-sm font-semibold transition ${tab === t.key ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}>
              {t.label}{badge(count(t.key))}
              {tab === t.key && <span className="absolute -bottom-px left-2 right-2 h-0.5 bg-brand rounded-full" />}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        {tab === 'requests' && (
          data.requests.length === 0
            ? <Empty text="No pending follow requests." />
            : data.requests.map((p: any) => (
              <Row key={p.id} p={p}>
                <button disabled={busy === 'req' + p.id} onClick={() => act('req' + p.id, () => api.acceptFollow(p.handle))}
                  className="px-3 py-1.5 rounded-lg bg-brand text-sm font-medium flex items-center gap-1">
                  {busy === 'req' + p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Accept
                </button>
              </Row>
            ))
        )}

        {tab === 'followers' && (
          data.followers.length === 0
            ? <Empty text="No followers yet." />
            : data.followers.map((p: any) => (
              <Row key={p.id} p={p}>
                {!p.in_my_inner && (
                  <button disabled={busy === 'inv' + p.id} onClick={() => act('inv' + p.id, () => api.inviteInner(p.handle))}
                    className="px-3 py-1.5 rounded-lg border border-violet-500/30 bg-violet-500/10 text-violet-300 text-sm flex items-center gap-1 hover:bg-violet-500/20">
                    <Lock className="h-3.5 w-3.5" /> Invite
                  </button>
                )}
                <IconBtn busy={busy === 'rf' + p.id} title="Remove follower" onClick={() => act('rf' + p.id, () => api.removeFollower(p.handle))}><UserMinus className="h-4 w-4" /></IconBtn>
              </Row>
            ))
        )}

        {tab === 'following' && (
          data.following.length === 0
            ? <Empty text="You're not following anyone yet." />
            : data.following.map((p: any) => (
              <Row key={p.id} p={p}>
                {p.status === 'pending' && <span className="text-xs text-amber-300 border border-amber-500/40 rounded-full px-2 py-0.5">Requested</span>}
                {p.in_my_inner && <span className="text-xs text-violet-300 flex items-center gap-1"><Lock className="h-3.5 w-3.5" />Inner</span>}
                <button disabled={busy === 'unf' + p.id} onClick={() => act('unf' + p.id, () => api.unfollow(p.handle))}
                  className="px-3 py-1.5 rounded-lg border border-edge text-sm hover:bg-white/5">
                  {p.status === 'pending' ? 'Cancel' : 'Unfollow'}
                </button>
              </Row>
            ))
        )}

        {tab === 'inner' && (
          data.inner.length === 0
            ? <Empty text="Your Inner Circle is empty. Invite trusted people from their profile." />
            : data.inner.map((p: any) => (
              <div key={p.id} className="py-3 border-b border-edge/60 last:border-0">
                <div className="flex items-center gap-3">
                  <Link to={`/u/${p.handle}`}><Avatar id={p.id} name={p.display_name} url={p.avatar_url} size={42} /></Link>
                  <Link to={`/u/${p.handle}`} className="flex-1 min-w-0"><div className="font-medium truncate">{p.display_name}</div><div className="text-xs text-slate-500 truncate">#{p.handle}</div></Link>
                  <button disabled={busy === 'ri' + p.id} onClick={() => act('ri' + p.id, () => api.removeInner(p.handle))}
                    className="px-3 py-1.5 rounded-lg border border-edge text-sm hover:bg-white/5">Remove</button>
                </div>
                <div className="flex items-center gap-2 mt-2 pl-[54px]">
                  <span className="text-xs text-slate-500">Can:</span>
                  {[['dm', 'DM'], ['voice', 'Voice note'], ['call', 'Call']].map(([k, lbl]) => {
                    const on = (p.perms || {})[k] !== false
                    return (
                      <button key={k} disabled={busy === 'pm' + p.id + k}
                        onClick={() => act('pm' + p.id + k, () => api.setInnerPerms(p.handle, { [k]: !on }))}
                        className={`text-xs px-2.5 py-1 rounded-full border transition ${on ? 'bg-brand/20 text-brand border-brand/40' : 'border-edge text-slate-500'}`}>
                        {lbl}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))
        )}

        {tab === 'blocked' && (
          blockedTotal === 0
            ? <Empty text="You haven't blocked, muted, or restricted anyone." />
            : (
              <div className="space-y-6">
                <RelGroup title="Blocked" Icon={Ban} tint="text-rose-400" items={rel.block} busy={busy} onClear={(h: string, id: string) => act('cl' + id, () => api.clearRelation(h))} label="Unblock" RowComp={Row} />
                <RelGroup title="Muted" Icon={VolumeX} tint="text-amber-400" items={rel.mute} busy={busy} onClear={(h: string, id: string) => act('cl' + id, () => api.clearRelation(h))} label="Unmute" RowComp={Row} />
                <RelGroup title="Restricted" Icon={ShieldOff} tint="text-sky-400" items={rel.restrict} busy={busy} onClear={(h: string, id: string) => act('cl' + id, () => api.clearRelation(h))} label="Remove" RowComp={Row} />
              </div>
            )
        )}
      </div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="py-14 text-center text-slate-500 flex flex-col items-center gap-2"><UserPlus className="h-8 w-8 opacity-40" />{text}</div>
}

function IconBtn({ children, onClick, title, busy }: any) {
  return (
    <button title={title} disabled={busy} onClick={onClick}
      className="h-9 w-9 grid place-items-center rounded-lg border border-edge text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-40">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : children}
    </button>
  )
}

function RelGroup({ title, Icon, tint, items, onClear, label, RowComp }: any) {
  if (!items.length) return null
  return (
    <div>
      <div className={`flex items-center gap-2 font-semibold mb-1 ${tint}`}><Icon className="h-4 w-4" />{title} <span className="text-slate-500 font-normal">· {items.length}</span></div>
      <div className="bg-panel border border-edge rounded-2xl px-4">
        {items.map((p: any) => (
          <RowComp key={p.id} p={p}>
            <button onClick={() => onClear(p.handle, p.id)} className="px-3 py-1.5 rounded-lg border border-edge text-sm hover:bg-white/5">{label}</button>
          </RowComp>
        ))}
      </div>
    </div>
  )
}
