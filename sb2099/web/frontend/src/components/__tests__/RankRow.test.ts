import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import RankRow from '../RankRow.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => {}) } })
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } })))
})

const base = { id: 1, content_sample: '戳手手', send_cnt: 318, unique_senders: 92, last_seen: null, barrage_tags: null }

test('in_library shows 已在库 and hides promote', () => {
  const w = mount(RankRow, { props: { item: { ...base, in_library: true }, rank: 1 } })
  expect(w.text()).toContain('已在库')
  expect(w.find('[data-test=promote]').exists()).toBe(false)
})

test('not in library shows promote button', () => {
  const w = mount(RankRow, { props: { item: { ...base, in_library: false }, rank: 2 } })
  expect(w.find('[data-test=promote]').exists()).toBe(true)
})
