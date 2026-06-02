import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import UserPicker from '../UserPicker.vue'

test('searching >2 chars lists users and selecting emits uid', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ results: [{ uid: '123', nickname: '阿松', avatar: null }] }),
      { headers: { 'content-type': 'application/json' } })))
  const w = mount(UserPicker)
  await w.get('input').setValue('阿松松')
  await flushPromises()
  await w.get('[data-test=hit]').trigger('click')
  expect(w.emitted('pick')![0]).toEqual([{ uid: '123', nickname: '阿松', avatar: null }])
})
