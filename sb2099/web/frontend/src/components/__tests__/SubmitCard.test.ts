import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import SubmitCard from '../SubmitCard.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
})

test('submit posts content+tags and emits submitted', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: { id: 9, content: 'x', tags: '00', cnt: 0, submit_time: null } }),
      { status: 201, headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const w = mount(SubmitCard)
  await w.get('textarea').setValue('男厕所在五楼女厕所在四楼')
  await w.get('[data-test=tag-00]').trigger('click')
  await w.get('[data-test=submit]').trigger('click')
  await flushPromises()
  const [url, init] = fetchSpy.mock.calls[0]
  expect(url).toBe('/api/barrage')
  expect(JSON.parse((init as any).body)).toMatchObject({ content: '男厕所在五楼女厕所在四楼', tags: ['00'] })
  expect(w.emitted('submitted')).toBeTruthy()
})
