import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import AddTagPanel from '../AddTagPanel.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [
    { value: '00', label: '主播', icon_url: null, sort: 0 },
    { value: '01', label: '选手', icon_url: null, sort: 1 },
  ]
})

const item = { id: 5, content: '某条烂梗', tags: '00', cnt: 1, submit_time: null, submitter: null }

test('only shows tags not already on the barrage', () => {
  const w = mount(AddTagPanel, { props: { item } })
  expect(w.find('[data-test=vote-01]').exists()).toBe(true)
  expect(w.find('[data-test=vote-00]').exists()).toBe(false) // 已有 00
})

test('voting an existing tag POSTs to vote-tag', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: { tag: '01', count: 1, threshold: 5, applied: false, pending_approval: false } }),
      { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const w = mount(AddTagPanel, { props: { item } })
  await w.get('[data-test=vote-01]').trigger('click')
  await flushPromises()
  expect(fetchSpy.mock.calls[0][0]).toBe('/api/barrage/5/vote-tag')
  expect(JSON.parse((fetchSpy.mock.calls[0][1] as any).body)).toMatchObject({ tag_value: '01' })
})

test('proposing a new tag POSTs to propose-tag', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: { tag: 'cp', label: 'CP', count: 1, threshold: 5, pending_approval: true } }),
      { status: 201, headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const w = mount(AddTagPanel, { props: { item } })
  await w.get('.vin').setValue('cp')
  await w.get('.lin').setValue('CP 名场面')
  await w.get('[data-test=propose]').trigger('click')
  await flushPromises()
  expect(fetchSpy.mock.calls[0][0]).toBe('/api/barrage/5/propose-tag')
  expect(JSON.parse((fetchSpy.mock.calls[0][1] as any).body)).toMatchObject({ value: 'cp', label: 'CP 名场面' })
})
