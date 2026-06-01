import { afterEach, expect, test, vi } from 'vitest'
import { api } from '../client'

afterEach(() => vi.restoreAllMocks())

test('getTags unwraps {data:[...]}', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }] }),
      { headers: { 'content-type': 'application/json' } })))
  const tags = await api.getTags()
  expect(tags[0].label).toBe('主播梗')
})

test('non-2xx throws ApiError with detail', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'rate limit' }), { status: 429,
      headers: { 'content-type': 'application/json' } })))
  await expect(api.copy('barrage', 1)).rejects.toThrow('rate limit')
})
