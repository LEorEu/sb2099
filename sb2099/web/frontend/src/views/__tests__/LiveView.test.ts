import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import LiveView from '../LiveView.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => { setActivePinia(createPinia()); const s = useTagsStore(); s.loaded = true; s.list = [] })

test('renders live ranking', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ window: 'day', data: [
      { id: 1, content_sample: '戳手手', send_cnt: 318, unique_senders: 92, last_seen: null, in_library: false, barrage_tags: null }
    ] }), { headers: { 'content-type': 'application/json' } })))
  const w = mount(LiveView)
  await flushPromises()
  expect(w.text()).toContain('戳手手')
  expect(w.text()).toContain('318')
})
