import { beforeEach, expect, test } from 'vitest'
import { useTheme } from '../useTheme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

test('defaults to light and toggles + persists', () => {
  const { theme, toggle } = useTheme()
  expect(theme.value).toBe('light')
  toggle()
  expect(theme.value).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(localStorage.getItem('sb2099-spa-theme')).toBe('dark')
})
