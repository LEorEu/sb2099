import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { expect, test } from 'vitest'

test('vue test utils mounts a component', () => {
  const C = defineComponent({ render: () => h('div', 'hi') })
  const w = mount(C)
  expect(w.text()).toBe('hi')
})
