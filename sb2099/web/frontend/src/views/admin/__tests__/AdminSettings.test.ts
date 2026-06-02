import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import AdminSettings from '../AdminSettings.vue'

beforeEach(() => setActivePinia(createPinia()))

test('renders setting items from /api/admin/settings', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ items: [
      { key: 'barrage_max_length', label: '投稿最多字数', desc: 'x', kind: 'int', default: 255, hint: '整数', value: 255 },
      { key: 'live_noise_filters', label: '降噪关键词', desc: 'y', kind: 'lines', default: [], hint: '每行一条', value: ['晚安'] },
    ] }), { headers: { 'content-type': 'application/json' } })))
  const w = mount(AdminSettings)
  await flushPromises()
  expect(w.text()).toContain('投稿最多字数')
  expect(w.text()).toContain('barrage_max_length')
  // lines 类型渲染为 textarea，值按行展开
  expect(w.find('textarea').element.value).toBe('晚安')
  // int 类型渲染为 input
  expect((w.find('input').element as HTMLInputElement).value).toBe('255')
})
