import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import DailyMemeCard from '../DailyMemeCard.vue'

beforeEach(() => setActivePinia(createPinia()))

test('loads a random meme on mount', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: { id: 1, content: '戳手手 👉👈', tags: '', cnt: 0, submit_time: null } }),
      { headers: { 'content-type': 'application/json' } })))
  const w = mount(DailyMemeCard)
  await flushPromises()
  expect(w.text()).toContain('戳手手')
})
