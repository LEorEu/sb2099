import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import FavoritesDrawer from '../FavoritesDrawer.vue'
import { useFavoritesStore } from '@/stores/favorites'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

test('open shows groups, close emits update:open=false', async () => {
  const s = useFavoritesStore(); s.add(7, '默认')
  const w = mount(FavoritesDrawer, { props: { open: true } })
  expect(w.text()).toContain('默认')
  await w.get('[data-test=close]').trigger('click')
  expect(w.emitted('update:open')![0]).toEqual([false])
})

test('closed renders no panel', () => {
  const w = mount(FavoritesDrawer, { props: { open: false } })
  expect(w.find('.drawer').exists()).toBe(false)
})
