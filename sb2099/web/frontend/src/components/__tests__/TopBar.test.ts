import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { expect, test } from 'vitest'
import TopBar from '../TopBar.vue'

test('renders three nav links and favorites count', () => {
  const w = mount(TopBar, {
    props: { favCount: 24 },
    global: { plugins: [createPinia()], stubs: { RouterLink: RouterLinkStub } },
  })
  expect(w.text()).toContain('首页')
  expect(w.text()).toContain('全部烂梗')
  expect(w.text()).toContain('热榜')
  expect(w.text()).toContain('24')
})
