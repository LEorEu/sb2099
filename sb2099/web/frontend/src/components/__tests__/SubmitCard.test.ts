import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import SubmitCard from '../SubmitCard.vue'
import { useTagsStore } from '@/stores/tags'
import { useIdentityStore } from '@/stores/identity'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
})

function okFetch() {
  return vi.fn(async () =>
    new Response(JSON.stringify({ data: { id: 9, content: 'x', tags: '00', cnt: 0, submit_time: null } }),
      { status: 201, headers: { 'content-type': 'application/json' } }))
}

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

test('persisted identity signs the submission and survives remount', async () => {
  useIdentityStore().set({ uid: 'u42', nickname: '阿松', avatar: null })
  const fetchSpy = okFetch(); vi.stubGlobal('fetch', fetchSpy)
  // 重新创建 store 应从 localStorage 复原身份
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
  const w = mount(SubmitCard)
  expect(w.text()).toContain('阿松')
  await w.get('textarea').setValue('男厕所在五楼女厕所在四楼')
  await w.get('[data-test=tag-00]').trigger('click')
  await w.get('[data-test=submit]').trigger('click')
  await flushPromises()
  expect(JSON.parse((fetchSpy.mock.calls[0][1] as any).body)).toMatchObject({ submitter_uid: 'u42' })
})

test('本次匿名 overrides identity and sends null uid', async () => {
  useIdentityStore().set({ uid: 'u42', nickname: '阿松', avatar: null })
  const fetchSpy = okFetch(); vi.stubGlobal('fetch', fetchSpy)
  const w = mount(SubmitCard)
  await w.get('[data-test=anon]').setValue(true)
  await w.get('textarea').setValue('男厕所在五楼女厕所在四楼')
  await w.get('[data-test=tag-00]').trigger('click')
  await w.get('[data-test=submit]').trigger('click')
  await flushPromises()
  expect(JSON.parse((fetchSpy.mock.calls[0][1] as any).body)).toMatchObject({ submitter_uid: null })
})
