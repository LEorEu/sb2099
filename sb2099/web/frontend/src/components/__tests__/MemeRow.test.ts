import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import MemeRow from '../MemeRow.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => {}) } })
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } })))
})

const item = { id: 1, content: '男厕所在五楼', tags: '00', cnt: 128, submit_time: '2026-05-29T00:00:00', submitter: null }

test('shows content, copy count text, and copy button works', async () => {
  const w = mount(MemeRow, { props: { item } })
  expect(w.text()).toContain('男厕所在五楼')
  expect(w.text()).toContain('被复制 128 次')
  await w.get('[data-test=copy]').trigger('click')
  expect((navigator.clipboard.writeText as any)).toHaveBeenCalledWith('男厕所在五楼')
})

test('clicking the row body copies the content', async () => {
  const w = mount(MemeRow, { props: { item } })
  await w.get('[data-test=row-copy]').trigger('click')
  expect((navigator.clipboard.writeText as any)).toHaveBeenCalledWith('男厕所在五楼')
})

test('favorite toggles store', async () => {
  const w = mount(MemeRow, { props: { item } })
  await w.get('[data-test=fav]').trigger('click')
  const { useFavoritesStore } = await import('@/stores/favorites')
  expect(useFavoritesStore().has(1)).toBe(true)
})

test('clicking favorite again removes it', async () => {
  const w = mount(MemeRow, { props: { item } })
  const { useFavoritesStore } = await import('@/stores/favorites')
  await w.get('[data-test=fav]').trigger('click')
  expect(useFavoritesStore().has(1)).toBe(true)
  await w.get('[data-test=fav]').trigger('click')
  expect(useFavoritesStore().has(1)).toBe(false)
})
