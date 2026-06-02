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

test('move shifts id between groups', () => {
  const s = useFavoritesStore()
  s.add(7, '默认')
  s.addGroup('骂战')
  s.move(7, '默认', '骂战')
  expect(s.groups['默认']).toEqual([])
  expect(s.groups['骂战']).toEqual([7])
  // 移到不存在的分组会自动建
  s.move(7, '骂战', '新组')
  expect(s.order).toContain('新组')
  expect(s.groups['新组']).toEqual([7])
})

test('removeGroup drops custom group but never 默认', () => {
  const s = useFavoritesStore()
  s.addGroup('临时')
  s.add(3, '临时')
  s.removeGroup('临时')
  expect(s.order).not.toContain('临时')
  expect(s.groups['临时']).toBeUndefined()
  // 默认不可删
  s.add(9, '默认')
  s.removeGroup('默认')
  expect(s.order).toContain('默认')
  expect(s.groups['默认']).toEqual([9])
})

test('import replaces and validates', () => {
  const s = useFavoritesStore()
  const ok = s.importJson(JSON.stringify({ groups: { 默认: [1] }, order: ['默认'] }))
  expect(ok).toBe(true)
  expect(s.totalCount).toBe(1)
  expect(s.importJson('not json')).toBe(false)
})
