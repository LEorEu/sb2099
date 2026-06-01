import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import { useFavoritesStore } from '../favorites'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

test('add/remove persists and counts', () => {
  const s = useFavoritesStore()
  s.addGroup('骂战专用')
  s.add(7, '骂战专用')
  s.add(9, '骂战专用')
  expect(s.totalCount).toBe(2)
  expect(JSON.parse(localStorage.getItem('sb2099_favorites_v1')!).groups['骂战专用']).toEqual([7, 9])
  s.remove(7, '骂战专用')
  expect(s.totalCount).toBe(1)
})

test('import replaces and validates', () => {
  const s = useFavoritesStore()
  const ok = s.importJson(JSON.stringify({ groups: { 默认: [1] }, order: ['默认'] }))
  expect(ok).toBe(true)
  expect(s.totalCount).toBe(1)
  expect(s.importJson('not json')).toBe(false)
})
