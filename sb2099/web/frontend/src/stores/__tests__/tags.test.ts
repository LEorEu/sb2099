import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useTagsStore } from '../tags'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

test('loads once and maps value->label', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }] }),
      { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const store = useTagsStore()
  await store.load()
  await store.load()
  expect(fetchSpy).toHaveBeenCalledTimes(1)
  expect(store.labelOf('00')).toBe('主播梗')
  expect(store.labelOf('zz')).toBe('zz')
})
