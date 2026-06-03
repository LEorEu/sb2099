import type {
  AdminBarrageItem, AdminLiveHotDetail, AdminLiveHotItem, AdminPendingItem, AdminReportItem,
  AdminSettingItem, AdminStats, AdminTag, AdminTrashItem,
  Barrage, BarragePage, LiveItem, Tag, UserHit,
} from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message)
  }
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'content-type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const ct = res.headers.get('content-type') || ''
  const body = ct.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) {
    const detail = (body && (body as any).detail) ?? body
    const msg = typeof detail === 'string' ? detail
      : (detail && (detail as any).message) || `HTTP ${res.status}`
    throw new ApiError(res.status, msg, detail)
  }
  return body as T
}

export const api = {
  getTags: () => req<{ data: Tag[] }>('/api/tags').then(r => r.data),
  presence: () => req<{ online: number }>('/api/presence'),
  getRandom: () => req<{ data: Barrage }>('/api/random').then(r => r.data),
  getBarragesByIds: (ids: number[]) =>
    req<{ data: Barrage[] }>(`/api/barrage/by-ids?ids=${ids.join(',')}`).then(r => r.data),
  searchBarrage: (p: { q?: string; tag?: string; sort?: 'new' | 'hot'; page?: number; size?: number }) => {
    const qs = new URLSearchParams()
    if (p.q) qs.set('q', p.q)
    if (p.tag) qs.set('tag', p.tag)
    qs.set('sort', p.sort || 'new')
    qs.set('page', String(p.page || 1))
    if (p.size) qs.set('size', String(p.size))
    return req<{ data: BarragePage }>(`/api/barrage?${qs}`).then(r => r.data)
  },
  getLive: (window: 'day' | 'week') =>
    req<{ window: string; data: LiveItem[] }>(`/api/live?window=${window}`).then(r => r.data),
  searchUsers: (q: string) =>
    req<{ results: UserHit[] }>(`/api/users/search?q=${encodeURIComponent(q)}`).then(r => r.results),
  copy: (source: 'barrage' | 'live_hot', id: number) =>
    req('/api/copy', { method: 'POST', body: JSON.stringify({ source, id }) }),
  submit: (content: string, tags: string[], submitter_uid: string | null) =>
    req<{ data: Barrage }>('/api/barrage', { method: 'POST', body: JSON.stringify({ content, tags, submitter_uid }) }).then(r => r.data),
  promote: (live_hot_id: number, tags: string[], submitter_uid: string | null) =>
    req<{ data: Barrage }>('/api/promote', { method: 'POST', body: JSON.stringify({ live_hot_id, tags, submitter_uid }) }).then(r => r.data),
  report: (id: number) => req('/api/barrage/report', { method: 'POST', body: JSON.stringify({ id }) }),
  voteTag: (barrageId: number, tag_value: string, voter_uid: string | null) =>
    req<{ data: { tag: string; count: number; threshold: number; applied: boolean; pending_approval: boolean } }>(
      `/api/barrage/${barrageId}/vote-tag`, { method: 'POST', body: JSON.stringify({ tag_value, voter_uid }) }).then(r => r.data),
  proposeTag: (barrageId: number, label: string, voter_uid: string | null) =>
    req<{ data: { tag: string; label: string; count: number; threshold: number; pending_approval: boolean } }>(
      `/api/barrage/${barrageId}/propose-tag`, { method: 'POST', body: JSON.stringify({ label, voter_uid }) }).then(r => r.data),
  withdraw: (id: number) => req(`/api/submission/${id}/withdraw`, { method: 'DELETE' }),

  admin: {
    me: () => req<{ authenticated: boolean }>('/api/admin/me'),
    login: (token: string) =>
      req<{ ok: boolean }>('/api/admin/login', { method: 'POST', body: JSON.stringify({ token }) }),
    logout: () => req('/api/admin/logout', { method: 'POST' }),

    getSettings: () => req<{ items: AdminSettingItem[] }>('/api/admin/settings').then(r => r.items),
    putSettings: (values: Record<string, number | string | string[]>) =>
      req<{ ok: boolean }>('/api/admin/settings', { method: 'PUT', body: JSON.stringify({ values }) }),

    getTags: () => req<{ vote_threshold: number; tags: AdminTag[] }>('/api/admin/tags'),
    createTag: (t: { label: string; icon_url?: string; sort?: number }) =>
      req<{ ok: boolean; value: string }>('/api/admin/tags', { method: 'POST', body: JSON.stringify(t) }),
    updateTag: (value: string, t: { label: string; icon_url?: string; sort?: number; enabled: boolean }) =>
      req(`/api/admin/tags/${value}`, { method: 'PATCH', body: JSON.stringify(t) }),
    deleteTag: (value: string) => req(`/api/admin/tags/${value}`, { method: 'DELETE' }),
    approveTag: (value: string) => req(`/api/admin/tags/${value}/approve`, { method: 'POST' }),

    getPending: () => req<{ items: AdminPendingItem[] }>('/api/admin/pending').then(r => r.items),
    approvePending: (id: number, tags: string) =>
      req(`/api/admin/pending/${id}/approve`, { method: 'POST', body: JSON.stringify({ tags }) }),
    rejectPending: (id: number) => req(`/api/admin/pending/${id}/reject`, { method: 'POST' }),

    getReports: () => req<{ items: AdminReportItem[] }>('/api/admin/reports').then(r => r.items),
    dismissReport: (id: number) => req(`/api/admin/reports/${id}/dismiss`, { method: 'POST' }),

    getBarrage: (p: { q?: string; sort?: 'new' | 'hot'; page?: number; size?: number }) => {
      const qs = new URLSearchParams()
      if (p.q) qs.set('q', p.q)
      qs.set('sort', p.sort || 'new')
      qs.set('page', String(p.page || 1))
      if (p.size) qs.set('size', String(p.size))
      return req<{ items: AdminBarrageItem[]; total: number; last_page: boolean; page: number }>(`/api/admin/barrage?${qs}`)
    },
    editBarrage: (id: number, body: { content: string; tags: string[] }) =>
      req(`/api/admin/barrage/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteBarrage: (id: number) => req(`/api/admin/barrage/${id}/delete`, { method: 'POST' }),

    getTrash: () => req<{ items: AdminTrashItem[] }>('/api/admin/trash').then(r => r.items),
    restoreTrash: (id: number) => req(`/api/admin/trash/${id}/restore`, { method: 'POST' }),
    purgeTrash: (id: number) => req(`/api/admin/trash/${id}/purge`, { method: 'POST' }),

    getLiveHot: (filtered: boolean) =>
      req<{ filtered: boolean; items: AdminLiveHotItem[] }>(`/api/admin/live-hot?filtered=${filtered}`).then(r => r.items),
    getLiveHotDetail: (id: number) => req<AdminLiveHotDetail>(`/api/admin/live-hot/${id}`),
    recomputeLiveHot: () =>
      req<{ ok: boolean; raw_renormalized: number }>('/api/admin/live-hot/recompute', { method: 'POST' }),
    rescanLiveHot: () => req<{ ok: boolean }>('/api/admin/live-hot/rescan', { method: 'POST' }),

    getStats: () => req<AdminStats>('/api/admin/stats'),
    getSummary: () => req<{ pending: number; open_reports: number; library_total: number }>('/api/admin/summary'),
  },
}
