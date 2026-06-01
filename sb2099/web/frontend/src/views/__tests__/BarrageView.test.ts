import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import BarrageView from '../BarrageView.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
})

test('loads and renders barrage list', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: { list: [
      { id: 1, content: '戳手手', tags: '00', cnt: 5, submit_time: null, submitter: null }
    ], total: 1, last_page: true } }), { headers: { 'content-type': 'application/json' } })))
  const w = mount(BarrageView, { global: { stubs: { RouterLink: RouterLinkStub } } })
  await flushPromises()
  expect(w.text()).toContain('戳手手')
  expect(w.text()).toContain('共 1 条')
})
