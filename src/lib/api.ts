import { Capacitor } from '@capacitor/core'

const TOKEN_KEY = 'cc_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) => t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)

// Deployed FastAPI backend on Render. Used as the fallback inside the native app
// (which has no same-origin API) so the APK works out of the box even if the
// REACT_APP_API_URL build var isn't provided.
const NATIVE_API_FALLBACK = 'https://clanchatapp-backend.onrender.com'

// Resolve the backend base URL:
//  - If REACT_APP_API_URL is baked at build time, always use it (web deploy + APK).
//  - Else, inside the native Capacitor shell -> use the deployed Render backend.
//  - Else (sandbox dev / same-origin web) -> "" so requests hit relative "/api"
//    (Vite proxy in dev, same origin in single-host deploys).
function computeApiBase(): string {
  const fromEnv = (((import.meta as any).env.REACT_APP_API_URL || '') as string).replace(/\/$/, '')
  if (fromEnv) return fromEnv
  try { if (Capacitor.isNativePlatform()) return NATIVE_API_FALLBACK } catch { /* not native */ }
  return ''
}

export const API_BASE = computeApiBase()

async function req(path: string, opts: RequestInit = {}) {
  const token = getToken()
  const headers: Record<string, string> = { ...(opts.headers as any) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  // Bounded timeout so a slow/asleep backend (e.g. Render free-tier cold start,
  // which can take ~30-40s) fails with a clear message instead of hanging forever.
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60000)
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api${path}`, { ...opts, headers, signal: controller.signal })
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      const err: any = new Error('The server is taking too long to respond — it may be waking up. Please try again in a moment.')
      err.retryable = true
      throw err
    }
    const err: any = new Error('Could not reach the server. Check your connection and try again.')
    err.retryable = true // network blip / server asleep -> safe to retry
    throw err
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let d = res.statusText
    try { d = (await res.json()).detail || d } catch {}
    const err: any = new Error(d)
    err.status = res.status
    err.retryable = res.status >= 500 || res.status === 429 // transient server states
    throw err
  }
  return res.status === 204 ? null : res.json()
}
const j = (b: any) => JSON.stringify(b)

// Fire-and-forget health ping to wake a sleeping backend early (e.g. on the login
// screen) so the user's actual sign-in lands on an already-warming server.
export async function warmup(): Promise<void> {
  try {
    const c = new AbortController()
    const t = setTimeout(() => c.abort(), 60000)
    await fetch(`${API_BASE}/api/`, { signal: c.signal }).catch(() => {})
    clearTimeout(t)
  } catch { /* ignore */ }
}

// Retry a request through transient failures (server asleep, network blip, 5xx)
// with gentle backoff. Non-retryable errors (401 bad creds, 400) throw immediately.
// `onProgress(attempt)` lets the UI show an escalating "please wait" message.
export async function withRetry<T>(fn: () => Promise<T>, onProgress?: (attempt: number) => void): Promise<T> {
  const backoff = [1200, 2500, 4000, 6000] // 5 attempts total
  let lastErr: any
  for (let i = 0; i <= backoff.length; i++) {
    try { return await fn() }
    catch (e: any) {
      lastErr = e
      if (!e?.retryable) throw e
      if (i === backoff.length) break
      onProgress?.(i + 1)
      await new Promise(r => setTimeout(r, backoff[i]))
    }
  }
  throw lastErr
}

export const api = {
  devLogin: (name: string) => req('/dev/token', { method: 'POST', body: j({ name }) }),
  authRegister: (email: string, password: string, name: string, dob?: string) => req('/auth/register', { method: 'POST', body: j({ email, password, name, dob }) }),
  setDob: (dob: string) => req('/auth/dob', { method: 'POST', body: j({ dob }) }),
  authLogin: (email: string, password: string) => req('/auth/login', { method: 'POST', body: j({ email, password }) }),
  me: () => req('/me'),
  updateProfile: (b: any) => req('/profile', { method: 'PUT', body: j(b) }),
  changeHandle: (handle: string) => req('/profile/handle', { method: 'POST', body: j({ handle }) }),
  setNickname: (handle: string, nickname: string) => req(`/inner/${handle}/nickname`, { method: 'PUT', body: j({ nickname }) }),
  listStickers: () => req('/stickers'),
  addSticker: (url: string) => req('/stickers', { method: 'POST', body: j({ url }) }),
  deleteSticker: (id: string) => req(`/stickers/${id}`, { method: 'DELETE' }),
  deleteAccount: () => req('/account', { method: 'DELETE' }),
  changePassword: (current_password: string, new_password: string) => req('/auth/change-password', { method: 'POST', body: j({ current_password, new_password }) }),
  getUser: (h: string) => req(`/users/${h}`),
  getUserPosts: (h: string) => req(`/users/${h}/posts`),
  follow: (h: string) => req(`/follow/${h}`, { method: 'POST' }),
  unfollow: (h: string) => req(`/follow/${h}`, { method: 'DELETE' }),
  acceptFollow: (h: string) => req(`/follow-requests/${h}/accept`, { method: 'POST' }),
  followRequests: () => req('/follow-requests'),
  inviteInner: (h: string) => req(`/inner/invite/${h}`, { method: 'POST' }),
  acceptInner: (h: string) => req(`/inner/accept/${h}`, { method: 'POST' }),
  getInner: () => req('/inner'),
  setRelation: (handle: string, kind: string) => req(`/relations/${handle}`, { method: 'POST', body: j({ kind }) }),
  clearRelation: (handle: string) => req(`/relations/${handle}`, { method: 'DELETE' }),
  listRelations: () => req('/relations'),
  connections: () => req('/connections'),
  removeFollower: (handle: string) => req(`/followers/${handle}/remove`, { method: 'POST' }),
  removeInner: (handle: string) => req(`/inner/${handle}`, { method: 'DELETE' }),
  feed: (scope: string) => req(`/feed?scope=${scope}`),
  createPost: (b: any) => req('/posts', { method: 'POST', body: j(b) }),
  decideTag: (postId: string, decision: 'approve' | 'reject') => req(`/posts/${postId}/tag/${decision}`, { method: 'POST' }),
  editPost: (id: string, text: string) => req(`/posts/${id}`, { method: 'PUT', body: j({ text }) }),
  editWall: (id: string, text: string) => req(`/wall/${id}`, { method: 'PUT', body: j({ text }) }),
  postHistory: (id: string) => req(`/posts/${id}/history`),
  wallHistory: (id: string) => req(`/wall/${id}/history`),
  pinPost: (id: string) => req(`/posts/${id}/pin`, { method: 'POST' }),
  setInnerPerms: (handle: string, perms: any) => req(`/inner/${handle}/perms`, { method: 'PUT', body: j(perms) }),
  boards: (handle: string) => req(`/boards/${handle}`),
  createBoard: (b: any) => req('/boards', { method: 'POST', body: j(b) }),
  board: (id: string) => req(`/board/${id}`),
  boardPost: (id: string, text: string, parent_id?: string) => req(`/board/${id}/posts`, { method: 'POST', body: j({ text, parent_id }) }),
  deleteBoardPost: (id: string) => req(`/board-posts/${id}`, { method: 'DELETE' }),
  reactBoardPost: (id: string, emoji: string) => req(`/board-posts/${id}/react`, { method: 'POST', body: j({ emoji }) }),
  deleteBoard: (id: string) => req(`/boards/${id}`, { method: 'DELETE' }),
  deletePost: (id: string) => req(`/posts/${id}`, { method: 'DELETE' }),
  likePost: (id: string) => req(`/posts/${id}/like`, { method: 'POST' }),
  reactPost: (id: string, emoji: string) => req(`/posts/${id}/react`, { method: 'POST', body: j({ emoji }) }),
  reels: () => req('/reels'),
  getWall: (handle: string) => req(`/wall/${handle}`),
  postWall: (handle: string, text: string) => req(`/wall/${handle}`, { method: 'POST', body: j({ text }) }),
  deleteWall: (id: string) => req(`/wall/${id}`, { method: 'DELETE' }),
  listComments: (id: string) => req(`/posts/${id}/comments`),
  addComment: (id: string, text: string, parent_id?: string) => req(`/posts/${id}/comments`, { method: 'POST', body: j({ text, parent_id }) }),
  deleteComment: (id: string) => req(`/comments/${id}`, { method: 'DELETE' }),
  deleteDm: (handle: string, id: string) => req(`/dms/${handle}/${id}`, { method: 'DELETE' }),
  pinDm: (handle: string, id: string) => req(`/dms/${handle}/${id}/pin`, { method: 'POST' }),
  giphySearch: (q: string) => req(`/giphy/search?q=${encodeURIComponent(q)}`),
  sendDmMedia: (handle: string, media_url: string, media_type: string, duration?: number, text?: string, view_once?: boolean, allow_save?: boolean) =>
    req(`/dms/${handle}`, { method: 'POST', body: j({ media_url, media_type, duration, text, view_once, allow_save }) }),
  viewOnceDm: (handle: string, id: string) => req(`/dms/${handle}/${id}/view`, { method: 'POST' }),
  trending: () => req('/trending'),
  search: (q: string) => req(`/search?q=${encodeURIComponent(q)}`),
  dmThreads: () => req('/dms'),
  dmHistory: (h: string) => req(`/dms/${h}`),
  dmSend: (h: string, text: string) => req(`/dms/${h}`, { method: 'POST', body: j({ text }) }),
  activity: () => req('/activity'),
  deleteActivity: (id: string) => req(`/activity/${id}`, { method: 'DELETE' }),
  clearActivity: () => req('/activity', { method: 'DELETE' }),
  unread: () => req('/unread'),
  groups: () => req('/groups'),
  createGroup: (name: string, members: string[]) => req('/groups', { method: 'POST', body: j({ name, members }) }),
  group: (id: string) => req(`/groups/${id}`),
  groupSend: (id: string, body: any) => req(`/groups/${id}/messages`, { method: 'POST', body: j(body) }),
  renameGroup: (id: string, name: string) => req(`/groups/${id}`, { method: 'PUT', body: j({ name }) }),
  addGroupMembers: (id: string, handles: string[]) => req(`/groups/${id}/members`, { method: 'POST', body: j({ handles }) }),
  removeGroupMember: (id: string, handle: string) => req(`/groups/${id}/members/${handle}`, { method: 'DELETE' }),
  deleteGroup: (id: string) => req(`/groups/${id}`, { method: 'DELETE' }),
  livekitToken: (room: string, peer?: string) => req('/livekit/token', { method: 'POST', body: j(peer ? { room, peer } : { room }) }),
  callRing: (peer: string, room: string, media: 'audio' | 'video' = 'video') => req('/call/ring', { method: 'POST', body: j({ peer, room, media }) }),
  callCancel: (peer: string, room: string) => req('/call/cancel', { method: 'POST', body: j({ peer, room }) }),
  callDecline: (peer: string, room: string) => req('/call/decline', { method: 'POST', body: j({ peer, room }) }),
  callAccept: (peer: string, room: string) => req('/call/accept', { method: 'POST', body: j({ peer, room }) }),
  registerPush: (token: string, platform = 'android') => req('/push/register', { method: 'POST', body: j({ token, platform }) }),
  unregisterPush: (token: string) => req(`/push/register/${encodeURIComponent(token)}`, { method: 'DELETE' }),
  upload: (file: File) => { const fd = new FormData(); fd.append('file', file); return req('/upload', { method: 'POST', body: fd }) },
  report: (target_type: string, target_id: string, category: string, note = '') =>
    req('/report', { method: 'POST', body: j({ target_type, target_id, category, note }) }),
  adminStats: () => req('/admin/stats'),
  adminReports: (status = 'open') => req(`/admin/reports?status=${status}`),
  adminAction: (id: string, action: string, reason = '', severe = false) => req(`/admin/reports/${id}/action`, { method: 'POST', body: j({ action, reason, severe }) }),
  adminClearStrikes: (handle: string) => req(`/admin/users/${handle}/clear-strikes`, { method: 'POST' }),
  adminCsam: () => req('/admin/csam'),
  adminUsers: (q = '') => req(`/admin/users?q=${encodeURIComponent(q)}`),
  adminStrike: (handle: string, reason: string, stage?: string) => req(`/admin/users/${handle}/strike`, { method: 'POST', body: j({ reason, stage }) }),
  adminUnsuspend: (handle: string) => req(`/admin/users/${handle}/unsuspend`, { method: 'POST' }),
  adminFlag: (handle: string, reason: string) => req(`/admin/users/${handle}/flag`, { method: 'POST', body: j({ reason }) }),
  adminUnflag: (handle: string) => req(`/admin/users/${handle}/unflag`, { method: 'POST' }),
  adminUserDms: (handle: string) => req(`/admin/dms/${handle}`),
  adminInvestigate: (handle: string) => req(`/admin/investigate/${handle}`),
  adminAudit: () => req('/admin/audit'),
  adminPromote: (email: string) => req('/admin/promote', { method: 'POST', body: j({ email }) }),
  adminPurgeDemo: (include_admin: boolean) => req('/admin/purge-demo', { method: 'POST', body: j({ include_admin }) }),
  adminListAdmins: () => req('/admin/admins'),
  adminRoles: () => req('/admin/roles'),
  adminAssignRole: (handle: string, role: string) => req('/admin/roles/assign', { method: 'POST', body: j({ handle, role }) }),
  adminRemoveRole: (handle: string) => req('/admin/roles/remove', { method: 'POST', body: j({ handle }) }),
  adminSetAccountType: (handle: string, account_type: string) => req(`/admin/users/${handle}/account-type`, { method: 'POST', body: j({ account_type }) }),
  setCoadminDms: (enabled: boolean) => req('/admin/settings/coadmin-dms', { method: 'POST', body: j({ enabled }) }),
  dmAccessRequest: (handle: string) => req('/admin/dm-access/request', { method: 'POST', body: j({ handle }) }),
  dmAccessList: () => req('/admin/dm-access'),
  dmAccessDecide: (id: string, decision: 'approve' | 'deny') => req(`/admin/dm-access/${id}/${decision}`, { method: 'POST' }),
  adminAddAdmin: (email: string) => req('/admin/admins', { method: 'POST', body: j({ email }) }),
  adminRemoveAdmin: (email: string) => req('/admin/admins/remove', { method: 'POST', body: j({ email }) }),
  adminNsfw: (status = 'open') => req(`/admin/nsfw?status=${status}`),
  adminNsfwResolve: (id: string, action: string) => req(`/admin/nsfw/${id}/resolve`, { method: 'POST', body: j({ action }) }),
  adminWatchlist: () => req('/admin/watchlist'),
  adminWatch: (handle: string, reason: string) => req(`/admin/users/${handle}/watch`, { method: 'POST', body: j({ reason }) }),
  adminUnwatch: (handle: string) => req(`/admin/users/${handle}/unwatch`, { method: 'POST' }),
  adminNotes: (handle: string) => req(`/admin/users/${handle}/notes`),
  adminAddNote: (handle: string, note: string) => req(`/admin/users/${handle}/note`, { method: 'POST', body: j({ note }) }),
  adminCsamEscalate: (id: string) => req(`/admin/csam/${id}/escalate`, { method: 'POST' }),
  adminCsamResolve: (id: string) => req(`/admin/csam/${id}/resolve`, { method: 'POST' }),
}

export function wsDmUrl(handle: string, token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'
  if (API_BASE) { try { const u = new URL(API_BASE); host = u.host; secure = u.protocol === 'https:' } catch {} }
  const proto = secure ? 'wss' : 'ws'
  return `${proto}://${host}/api/ws/dm/${handle}?token=${encodeURIComponent(token)}`
}

export function wsGroupUrl(id: string, token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'
  if (API_BASE) { try { const u = new URL(API_BASE); host = u.host; secure = u.protocol === 'https:' } catch {} }
  const proto = secure ? 'wss' : 'ws'
  return `${proto}://${host}/api/ws/group/${id}?token=${encodeURIComponent(token)}`
}

export function wsUserUrl(token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'
  if (API_BASE) { try { const u = new URL(API_BASE); host = u.host; secure = u.protocol === 'https:' } catch {} }
  const proto = secure ? 'wss' : 'ws'
  return `${proto}://${host}/api/ws/user?token=${encodeURIComponent(token)}`
}
