import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useAdminStore } from '../admin'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

function okJson(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

test('check() sets authed=true on 200', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => okJson({ authenticated: true })))
  const s = useAdminStore()
  expect(await s.check()).toBe(true)
  expect(s.authed).toBe(true)
  expect(s.checked).toBe(true)
})

test('check() sets authed=false on 401', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => okJson({ detail: 'admin login required' }, 401)))
  const s = useAdminStore()
  expect(await s.check()).toBe(false)
  expect(s.authed).toBe(false)
})

test('login() flips authed and marks checked', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => okJson({ ok: true })))
  const s = useAdminStore()
  await s.login('tok')
  expect(s.authed).toBe(true)
  expect(s.checked).toBe(true)
})
