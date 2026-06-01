import { afterEach, expect, test, vi } from 'vitest'
import { useCopy } from '../useCopy'

afterEach(() => vi.restoreAllMocks())

test('copies text to clipboard and pings /api/copy', async () => {
  const writeText = vi.fn(async () => {})
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  const fetchSpy = vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const { copy } = useCopy()
  await copy('戳手手', 'barrage', 1)
  expect(writeText).toHaveBeenCalledWith('戳手手')
  expect(fetchSpy).toHaveBeenCalledWith('/api/copy', expect.objectContaining({ method: 'POST' }))
})
