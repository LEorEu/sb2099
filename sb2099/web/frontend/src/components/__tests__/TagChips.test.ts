import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import TagChips from '../TagChips.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore()
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 },
            { value: '02', label: '互动梗', icon_url: null, sort: 2 }]
  s.loaded = true
})

test('renders labels for csv values', () => {
  const w = mount(TagChips, { props: { csv: '00,02' }, global: { plugins: [] } })
  expect(w.text()).toContain('主播梗')
  expect(w.text()).toContain('互动梗')
})

test('empty csv renders nothing', () => {
  const w = mount(TagChips, { props: { csv: '' } })
  expect(w.findAll('.tagchip').length).toBe(0)
})
