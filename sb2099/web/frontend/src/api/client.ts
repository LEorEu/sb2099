import type { Barrage, BarragePage, LiveItem, Tag, UserHit } from './types'

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
  proposeTag: (barrageId: number, value: string, label: string, voter_uid: string | null) =>
    req<{ data: { tag: string; label: string; count: number; threshold: number; pending_approval: boolean } }>(
      `/api/barrage/${barrageId}/propose-tag`, { method: 'POST', body: JSON.stringify({ value, label, voter_uid }) }).then(r => r.data),
  withdraw: (id: number) => req(`/api/submission/${id}/withdraw`, { method: 'DELETE' }),
}
