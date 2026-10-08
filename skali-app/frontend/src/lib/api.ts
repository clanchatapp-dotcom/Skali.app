import { Capacitor } from '@capacitor/core'

const TOKEN_KEY = 'cc_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)

export const setToken = (t: string | null) =>
  t
    ? localStorage.setItem(TOKEN_KEY, t)
    : localStorage.removeItem(TOKEN_KEY)

// Server-side step-up secret for sensitive areas.
// It is never hardcoded or persisted.
let stepUpSecret = ''

export const setStepUp = (s: string) => {
  stepUpSecret = (s || '').trim()
}

export const hasStepUp = () => !!stepUpSecret

const stepUpHeaders = (): Record<string, string> =>
  stepUpSecret ? { 'X-Step-Up': stepUpSecret } : {}

// Render backend fallback for the native app.
const NATIVE_API_FALLBACK =
  'https://clanchatapp-backend.onrender.com'

function computeApiBase(): string {
  const fromEnv = (
    ((import.meta as any).env.REACT_APP_BACKEND_URL || '') as string
  ).replace(/\/$/, '')

  if (fromEnv) return fromEnv

  // Production web builds (skaliapp.com / Render) always talk to the Render backend.
  if (!(import.meta as any).env.DEV) return NATIVE_API_FALLBACK

  try {
    if (Capacitor.isNativePlatform()) {
      return NATIVE_API_FALLBACK
    }
  } catch {
    // Not running natively.
  }

  return ''
}

export const API_BASE = computeApiBase()

async function req(path: string, opts: RequestInit = {}) {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(opts.headers as any),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  // Tell the backend when we're the native mobile app so it can withhold NSFW
  // content (NSFW is web-only). Web browsers omit this header.
  try {
    if (Capacitor.isNativePlatform()) {
      headers['X-Client-Platform'] = 'native'
    }
  } catch {
    // Not running natively.
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60000)

  let res: Response

  try {
    res = await fetch(`${API_BASE}/api${path}`, {
      ...opts,
      headers,
      signal: controller.signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      const err: any = new Error(
        'The server is taking too long to respond. It may be waking up. Please try again in a moment.'
      )
      err.retryable = true
      throw err
    }

    const err: any = new Error(
      'Could not reach the server. Check your connection and try again.'
    )
    err.retryable = true
    throw err
  } finally {
    clearTimeout(timer)
  }

  if (!res.ok) {
    let d = res.statusText

    try {
      d = (await res.json()).detail || d
    } catch {
      // Keep the status text.
    }

    const err: any = new Error(d)
    err.status = res.status
    err.retryable = res.status >= 500 || res.status === 429

    throw err
  }

  return res.status === 204 ? null : res.json()
}

const j = (b: any) => JSON.stringify(b)

export async function warmup(): Promise<void> {
  try {
    const c = new AbortController()
    const t = setTimeout(() => c.abort(), 60000)

    await fetch(`${API_BASE}/api/`, {
      signal: c.signal,
    }).catch(() => {})

    clearTimeout(t)
  } catch {
    // Ignore warmup errors.
  }
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  onProgress?: (attempt: number) => void
): Promise<T> {
  const backoff = [1200, 2500, 4000, 6000]
  let lastErr: any

  for (let i = 0; i <= backoff.length; i++) {
    try {
      return await fn()
    } catch (e: any) {
      lastErr = e

      if (!e?.retryable) throw e
      if (i === backoff.length) break

      onProgress?.(i + 1)

      await new Promise((r) => setTimeout(r, backoff[i]))
    }
  }

  throw lastErr
}

export const api = {
  devLogin: (name: string) =>
    req('/dev/token', {
      method: 'POST',
      body: j({ name }),
    }),

  authRegister: (
    email: string,
    password: string,
    name: string,
    dob?: string
  ) =>
    req('/auth/register', {
      method: 'POST',
      body: j({ email, password, name, dob }),
    }),

  setDob: (dob: string) =>
    req('/auth/dob', {
      method: 'POST',
      body: j({ dob }),
    }),

  authLogin: (email: string, password: string) =>
    req('/auth/login', {
      method: 'POST',
      body: j({ email, password }),
    }),

  me: () => req('/me'),

  // Admin — manual creator access (restored) + adult-content-creator designation
  adminCreators: () => req('/admin/creators'),
  adminGrantCreator: (handle: string) =>
    req(`/admin/users/${handle}/creator`, { method: 'POST' }),
  adminRevokeCreator: (handle: string) =>
    req(`/admin/users/${handle}/creator`, { method: 'DELETE' }),
  adminGrantAdultCreator: (handle: string) =>
    req(`/admin/users/${handle}/adult-creator`, { method: 'POST' }),
  adminRevokeAdultCreator: (handle: string) =>
    req(`/admin/users/${handle}/adult-creator`, { method: 'DELETE' }),

  // Admin — Skali Team support inbox (restored)
  supportThreads: () => req('/admin/support/threads'),
  supportThread: (handle: string) => req(`/admin/support/threads/${handle}`),
  supportReply: (handle: string, text: string) =>
    req(`/admin/support/reply/${handle}`, { method: 'POST', body: j({ text }) }),

  // Live streaming — Twitch-style public discovery + private tiers
  liveStart: (b: { audience: string; category?: string; save: boolean; title?: string; group_id?: string }) =>
    req('/live/start', { method: 'POST', body: j(b) }),
  liveList: (category?: string) => req(`/live${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  liveCategories: () => req('/live/categories'),
  livePast: (handle: string) => req(`/live/past/${handle}`),
  liveJoin: (id: string) => req(`/live/${id}/join`, { method: 'POST' }),
  liveEnd: (id: string) => req(`/live/${id}/end`, { method: 'POST' }),

  // Verification
  verificationStatus: () => req('/verification/status'),

  verificationStart: (
    type: 'identity' | 'age',
    provider: 'yoti' | 'oneid'
  ) =>
    req('/verification/start', {
      method: 'POST',
      body: j({ type, provider }),
    }),

  // Entitlements and creator finance
  entitlements: () => req('/entitlements'),

  creatorFinance: () => req('/creator/finance'),

  // Creator Hub
  creatorOverview: () => req('/creator/overview'),

  creatorSubscribers: () => req('/creator/subscribers'),

  creatorShop: () => req('/creator/shop'),

  shopCreateProduct: (b: any) =>
    req('/creator/shop/products', {
      method: 'POST',
      body: j(b),
    }),

  shopDeleteProduct: (id: string) =>
    req(`/creator/shop/products/${id}`, {
      method: 'DELETE',
    }),

  creatorTaxDocs: () => req('/creator/finance/tax-docs'),

  creatorPayouts: () => req('/creator/payouts'),

  setPayoutSettings: (b: any) =>
    req('/creator/payout-settings', {
      method: 'PUT',
      body: j(b),
    }),

  requestPayout: () =>
    req('/creator/payouts/request', {
      method: 'POST',
    }),

  financeCsvUrl: () =>
    `${API_BASE}/api/creator/finance/export.csv`,

  financePdfUrl: () =>
    `${API_BASE}/api/creator/finance/export.pdf`,

  // Creator Hub v2 — creator account status, enable/type, wellbeing analytics
  creatorMe: () => req('/creator/me'),

  creatorEnable: (b: { enabled?: boolean; creator_type?: string }) =>
    req('/creator/enable', {
      method: 'POST',
      body: j(b),
    }),

  creatorHealth: () => req('/creator/health'),

  setHealthSettings: (b: {
    collection_enabled?: boolean
    hidden?: boolean
  }) =>
    req('/creator/health/settings', {
      method: 'PUT',
      body: j(b),
    }),

  accountNsfwFlip: () =>
    req('/account/nsfw-flip', {
      method: 'POST',
    }),

  // Discovery, offers, storefront, subscriptions and tips
  choices: () => req('/choices'),

  choicesOptIn: () =>
    req('/choices/opt-in', {
      method: 'POST',
    }),

  tagsSimilar: (q: string) =>
    req(`/tags/similar?q=${encodeURIComponent(q)}`),

  tagsTrending: () => req('/tags/trending'),

  nsfwTags: () => req('/nsfw-tags'),

  createSponsored: (post_id: string, topics?: string[]) =>
    req('/sponsored', {
      method: 'POST',
      body: j({ post_id, topics }),
    }),

  creatorOffers: (handle: string) =>
    req(`/creators/${handle}/offers`),

  setCreatorOffers: (b: any) =>
    req('/creator/offers', {
      method: 'PUT',
      body: j(b),
    }),

  creatorPublicShop: (handle: string) =>
    req(`/creators/${handle}/shop`),

  checkoutSession: (b: any) =>
    req('/checkout/session', {
      method: 'POST',
      body: j(b),
    }),

  shopOrder: (productId: string) =>
    req(`/shop/order/${productId}`, {
      method: 'POST',
    }),

  updateProfile: (b: any) =>
    req('/profile', {
      method: 'PUT',
      body: j(b),
    }),

  changeHandle: (handle: string) =>
    req('/profile/handle', {
      method: 'POST',
      body: j({ handle }),
    }),

  setNickname: (handle: string, nickname: string) =>
    req(`/inner/${handle}/nickname`, {
      method: 'PUT',
      body: j({ nickname }),
    }),

  listStickers: () => req('/stickers'),

  addSticker: (url: string) =>
    req('/stickers', {
      method: 'POST',
      body: j({ url }),
    }),

  deleteSticker: (id: string) =>
    req(`/stickers/${id}`, {
      method: 'DELETE',
    }),

  deleteAccount: () =>
    req('/account', {
      method: 'DELETE',
    }),

  changePassword: (
    current_password: string,
    new_password: string
  ) =>
    req('/auth/change-password', {
      method: 'POST',
      body: j({ current_password, new_password }),
    }),

  getUser: (h: string) => req(`/users/${h}`),

  getUserPosts: (h: string) => req(`/users/${h}/posts`),

  follow: (h: string) =>
    req(`/follow/${h}`, {
      method: 'POST',
    }),

  unfollow: (h: string) =>
    req(`/follow/${h}`, {
      method: 'DELETE',
    }),

  acceptFollow: (h: string) =>
    req(`/follow-requests/${h}/accept`, {
      method: 'POST',
    }),

  followRequests: () => req('/follow-requests'),

  inviteInner: (h: string) =>
    req(`/inner/invite/${h}`, {
      method: 'POST',
    }),

  acceptInner: (h: string) =>
    req(`/inner/accept/${h}`, {
      method: 'POST',
    }),

  getInner: () => req('/inner'),

  setRelation: (handle: string, kind: string) =>
    req(`/relations/${handle}`, {
      method: 'POST',
      body: j({ kind }),
    }),

  clearRelation: (handle: string) =>
    req(`/relations/${handle}`, {
      method: 'DELETE',
    }),

  listRelations: () => req('/relations'),

  connections: () => req('/connections'),

  removeFollower: (handle: string) =>
    req(`/followers/${handle}/remove`, {
      method: 'POST',
    }),

  removeInner: (handle: string) =>
    req(`/inner/${handle}`, {
      method: 'DELETE',
    }),

  feed: (scope: string) =>
    req(`/feed?scope=${scope}`),

  createPost: (b: any) =>
    req('/posts', {
      method: 'POST',
      body: j(b),
    }),

  decideTag: (
    postId: string,
    decision: 'approve' | 'reject'
  ) =>
    req(`/posts/${postId}/tag/${decision}`, {
      method: 'POST',
    }),

  editPost: (id: string, text: string) =>
    req(`/posts/${id}`, {
      method: 'PUT',
      body: j({ text }),
    }),

  editWall: (id: string, text: string) =>
    req(`/wall/${id}`, {
      method: 'PUT',
      body: j({ text }),
    }),

  postHistory: (id: string) =>
    req(`/posts/${id}/history`),

  wallHistory: (id: string) =>
    req(`/wall/${id}/history`),

  pinPost: (id: string) =>
    req(`/posts/${id}/pin`, {
      method: 'POST',
    }),

  setInnerPerms: (handle: string, perms: any) =>
    req(`/inner/${handle}/perms`, {
      method: 'PUT',
      body: j(perms),
    }),

  boards: (handle: string) =>
    req(`/boards/${handle}`),

  createBoard: (b: any) =>
    req('/boards', {
      method: 'POST',
      body: j(b),
    }),

  board: (id: string) =>
    req(`/board/${id}`),

  boardPost: (
    id: string,
    text: string,
    parent_id?: string
  ) =>
    req(`/board/${id}/posts`, {
      method: 'POST',
      body: j({ text, parent_id }),
    }),

  deleteBoardPost: (id: string) =>
    req(`/board-posts/${id}`, {
      method: 'DELETE',
    }),

  reactBoardPost: (id: string, emoji: string) =>
    req(`/board-posts/${id}/react`, {
      method: 'POST',
      body: j({ emoji }),
    }),

  deleteBoard: (id: string) =>
    req(`/boards/${id}`, {
      method: 'DELETE',
    }),

  deletePost: (id: string) =>
    req(`/posts/${id}`, {
      method: 'DELETE',
    }),

  likePost: (id: string) =>
    req(`/posts/${id}/like`, {
      method: 'POST',
    }),

  reactPost: (id: string, emoji: string) =>
    req(`/posts/${id}/react`, {
      method: 'POST',
      body: j({ emoji }),
    }),

  reels: () => req('/reels'),

  getWall: (handle: string) =>
    req(`/wall/${handle}`),

  postWall: (handle: string, text: string) =>
    req(`/wall/${handle}`, {
      method: 'POST',
      body: j({ text }),
    }),

  deleteWall: (id: string) =>
    req(`/wall/${id}`, {
      method: 'DELETE',
    }),

  listComments: (id: string) =>
    req(`/posts/${id}/comments`),

  addComment: (
    id: string,
    text: string,
    parent_id?: string
  ) =>
    req(`/posts/${id}/comments`, {
      method: 'POST',
      body: j({ text, parent_id }),
    }),

  deleteComment: (id: string) =>
    req(`/comments/${id}`, {
      method: 'DELETE',
    }),

  deleteDm: (handle: string, id: string) =>
    req(`/dms/${handle}/${id}`, {
      method: 'DELETE',
    }),

  pinDm: (handle: string, id: string) =>
    req(`/dms/${handle}/${id}/pin`, {
      method: 'POST',
    }),

  giphySearch: (q: string) =>
    req(`/giphy/search?q=${encodeURIComponent(q)}`),

  sendDmMedia: (
    handle: string,
    media_url: string,
    media_type: string,
    duration?: number,
    text?: string,
    view_once?: boolean,
    allow_save?: boolean
  ) =>
    req(`/dms/${handle}`, {
      method: 'POST',
      body: j({
        media_url,
        media_type,
        duration,
        text,
        view_once,
        allow_save,
      }),
    }),

  viewOnceDm: (handle: string, id: string) =>
    req(`/dms/${handle}/${id}/view`, {
      method: 'POST',
    }),

  trending: () => req('/trending'),

  search: (q: string) =>
    req(`/search?q=${encodeURIComponent(q)}`),

  myInterests: () => req('/interests'),

  interestsFeed: () => req('/interests/feed'),

  followInterest: (name: string) =>
    req(`/interests/${encodeURIComponent(name)}`, {
      method: 'POST',
    }),

  unfollowInterest: (name: string) =>
    req(`/interests/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  interestPeople: (name: string) =>
    req(`/interests/${encodeURIComponent(name)}/people`),

  dmThreads: () => req('/dms'),

  dmHistory: (h: string) =>
    req(`/dms/${h}`),

  dmSend: (h: string, text: string) =>
    req(`/dms/${h}`, {
      method: 'POST',
      body: j({ text }),
    }),

  activity: () => req('/activity'),

  deleteActivity: (id: string) =>
    req(`/activity/${id}`, {
      method: 'DELETE',
    }),

  clearActivity: () =>
    req('/activity', {
      method: 'DELETE',
    }),

  unread: () => req('/unread'),

  groups: () => req('/groups'),

  createGroup: (name: string, members: string[]) =>
    req('/groups', {
      method: 'POST',
      body: j({ name, members }),
    }),

  group: (id: string) =>
    req(`/groups/${id}`),

  groupSend: (id: string, body: any) =>
    req(`/groups/${id}/messages`, {
      method: 'POST',
      body: j(body),
    }),

  renameGroup: (id: string, name: string) =>
    req(`/groups/${id}`, {
      method: 'PUT',
      body: j({ name }),
    }),

  addGroupMembers: (id: string, handles: string[]) =>
    req(`/groups/${id}/members`, {
      method: 'POST',
      body: j({ handles }),
    }),

  removeGroupMember: (id: string, handle: string) =>
    req(`/groups/${id}/members/${handle}`, {
      method: 'DELETE',
    }),

  deleteGroup: (id: string) =>
    req(`/groups/${id}`, {
      method: 'DELETE',
    }),

  // IMPORTANT: This line is syntactically correct.
  livekitToken: (room: string, peer?: string) =>
    req('/livekit/token', {
      method: 'POST',
      body: j(peer ? { room, peer } : { room }),
    }),

  callRing: (
    peer: string,
    room: string,
    media: 'audio' | 'video' = 'video'
  ) =>
    req('/call/ring', {
      method: 'POST',
      body: j({ peer, room, media }),
    }),

  callCancel: (peer: string, room: string) =>
    req('/call/cancel', {
      method: 'POST',
      body: j({ peer, room }),
    }),

  callDecline: (peer: string, room: string) =>
    req('/call/decline', {
      method: 'POST',
      body: j({ peer, room }),
    }),

  callAccept: (peer: string, room: string) =>
    req('/call/accept', {
      method: 'POST',
      body: j({ peer, room }),
    }),

  registerPush: (
    token: string,
    platform = 'android'
  ) =>
    req('/push/register', {
      method: 'POST',
      body: j({ token, platform }),
    }),

  unregisterPush: (token: string) =>
    req(`/push/register/${encodeURIComponent(token)}`, {
      method: 'DELETE',
    }),

  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)

    return req('/upload', {
      method: 'POST',
      body: fd,
    })
  },

  report: (
    target_type: string,
    target_id: string,
    category: string,
    note = ''
  ) =>
    req('/report', {
      method: 'POST',
      body: j({ target_type, target_id, category, note }),
    }),

  adminStats: () => req('/admin/stats'),

  adminReports: (status = 'open') =>
    req(`/admin/reports?status=${status}`),

  adminAction: (
    id: string,
    action: string,
    reason = '',
    severe = false
  ) =>
    req(`/admin/reports/${id}/action`, {
      method: 'POST',
      body: j({ action, reason, severe }),
    }),

  adminClearStrikes: (handle: string) =>
    req(`/admin/users/${handle}/clear-strikes`, {
      method: 'POST',
    }),

  adminCsam: () =>
    req('/admin/csam', {
      headers: stepUpHeaders(),
    }),

  adminUsers: (q = '') =>
    req(`/admin/users?q=${encodeURIComponent(q)}`),

  adminStrike: (
    handle: string,
    reason: string,
    stage?: string
  ) =>
    req(`/admin/users/${handle}/strike`, {
      method: 'POST',
      body: j({ reason, stage }),
    }),

  adminUnsuspend: (handle: string) =>
    req(`/admin/users/${handle}/unsuspend`, {
      method: 'POST',
    }),

  adminFlag: (handle: string, reason: string) =>
    req(`/admin/users/${handle}/flag`, {
      method: 'POST',
      body: j({ reason }),
    }),

  adminUnflag: (handle: string) =>
    req(`/admin/users/${handle}/unflag`, {
      method: 'POST',
    }),

  adminUserDms: (
    handle: string,
    legal_basis: string
  ) =>
    req(
      `/admin/dms/${handle}?legal_basis=${encodeURIComponent(legal_basis)}`,
      { headers: stepUpHeaders() }
    ),

  adminInvestigate: (
    handle: string,
    legal_basis: string
  ) =>
    req(
      `/admin/investigate/${handle}?legal_basis=${encodeURIComponent(legal_basis)}`,
      { headers: stepUpHeaders() }
    ),

  adminAudit: (log?: string) => req(`/admin/audit${log ? `?log=${encodeURIComponent(log)}` : ''}`),
  adminAuditAccess: () => req('/admin/audit/access'),
  adminAuditRequest: (log: string) => req('/admin/audit/access/request', { method: 'POST', body: JSON.stringify({ log }) }),
  adminAuditDecide: (id: string, decision: 'approve' | 'deny') => req(`/admin/audit/access/${id}/${decision}`, { method: 'POST' }),

  adminPromote: (email: string) =>
    req('/admin/promote', {
      method: 'POST',
      body: j({ email }),
    }),

  adminPurgeDemo: (include_admin: boolean) =>
    req('/admin/purge-demo', {
      method: 'POST',
      body: j({ include_admin }),
    }),

  adminListAdmins: () => req('/admin/admins'),

  adminRoles: () => req('/admin/roles'),

  adminAssignRole: (handle: string, role: string) =>
    req('/admin/roles/assign', {
      method: 'POST',
      body: j({ handle, role }),
    }),

  adminRemoveRole: (handle: string) =>
    req('/admin/roles/remove', {
      method: 'POST',
      body: j({ handle }),
    }),

  adminSetAccountType: (
    handle: string,
    account_type: string
  ) =>
    req(`/admin/users/${handle}/account-type`, {
      method: 'POST',
      body: j({ account_type }),
    }),

  setCoadminDms: (enabled: boolean) =>
    req('/admin/settings/coadmin-dms', {
      method: 'POST',
      body: j({ enabled }),
    }),

  dmAccessRequest: (handle: string) =>
    req('/admin/dm-access/request', {
      method: 'POST',
      body: j({ handle }),
    }),

  dmAccessList: () => req('/admin/dm-access'),

  dmAccessDecide: (
    id: string,
    decision: 'approve' | 'deny'
  ) =>
    req(`/admin/dm-access/${id}/${decision}`, {
      method: 'POST',
    }),

  adminAddAdmin: (email: string) =>
    req('/admin/admins', {
      method: 'POST',
      body: j({ email }),
    }),

  adminRemoveAdmin: (email: string) =>
    req('/admin/admins/remove', {
      method: 'POST',
      body: j({ email }),
    }),

  adminNsfw: (status = 'open') =>
    req(`/admin/nsfw?status=${status}`),

  adminNsfwResolve: (id: string, action: string) =>
    req(`/admin/nsfw/${id}/resolve`, {
      method: 'POST',
      body: j({ action }),
    }),

  adminWatchlist: () => req('/admin/watchlist'),

  adminWatch: (handle: string, reason: string) =>
    req(`/admin/users/${handle}/watch`, {
      method: 'POST',
      body: j({ reason }),
    }),

  adminUnwatch: (handle: string) =>
    req(`/admin/users/${handle}/unwatch`, {
      method: 'POST',
    }),

  adminNotes: (handle: string) =>
    req(`/admin/users/${handle}/notes`),

  adminAddNote: (handle: string, note: string) =>
    req(`/admin/users/${handle}/note`, {
      method: 'POST',
      body: j({ note }),
    }),

  adminCsamEscalate: (id: string) =>
    req(`/admin/csam/${id}/escalate`, {
      method: 'POST',
      headers: stepUpHeaders(),
    }),

  adminCsamResolve: (id: string) =>
    req(`/admin/csam/${id}/resolve`, {
      method: 'POST',
      headers: stepUpHeaders(),
    }),

  // Stories — Instagram-style, 24h expiry
  stories: () => req('/stories'),

  storiesOfUser: (handle: string) =>
    req(`/stories/${handle}`),

  createStory: (
    media_url: string,
    media_type: 'image' | 'video' = 'image',
    caption = ''
  ) =>
    req('/stories', {
      method: 'POST',
      body: j({ media_url, media_type, caption }),
    }),

  viewStory: (id: string) =>
    req(`/stories/${id}/view`, {
      method: 'POST',
    }),

  storyViewers: (id: string) =>
    req(`/stories/${id}/viewers`),

  deleteStory: (id: string) =>
    req(`/stories/${id}`, {
      method: 'DELETE',
    }),
}

export function wsDmUrl(handle: string, token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'

  if (API_BASE) {
    try {
      const u = new URL(API_BASE)
      host = u.host
      secure = u.protocol === 'https:'
    } catch {
      // Keep the current host.
    }
  }

  const proto = secure ? 'wss' : 'ws'

  return `${proto}://${host}/api/ws/dm/${handle}?token=${encodeURIComponent(token)}`
}

export function wsGroupUrl(id: string, token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'

  if (API_BASE) {
    try {
      const u = new URL(API_BASE)
      host = u.host
      secure = u.protocol === 'https:'
    } catch {
      // Keep the current host.
    }
  }

  const proto = secure ? 'wss' : 'ws'

  return `${proto}://${host}/api/ws/group/${id}?token=${encodeURIComponent(token)}`
}

export function wsUserUrl(token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'

  if (API_BASE) {
    try {
      const u = new URL(API_BASE)
      host = u.host
      secure = u.protocol === 'https:'
    } catch {
      // Keep the current host.
    }
  }

  const proto = secure ? 'wss' : 'ws'

  return `${proto}://${host}/api/ws/user?token=${encodeURIComponent(token)}`
}

export function wsLiveUrl(id: string, token: string) {
  let host = window.location.host
  let secure = window.location.protocol === 'https:'

  if (API_BASE) {
    try {
      const u = new URL(API_BASE)
      host = u.host
      secure = u.protocol === 'https:'
    } catch {
      // Keep the current host.
    }
  }

  const proto = secure ? 'wss' : 'ws'

  return `${proto}://${host}/api/ws/live/${id}?token=${encodeURIComponent(token)}`
}
