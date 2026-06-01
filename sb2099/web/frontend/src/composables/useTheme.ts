import { ref } from 'vue'

type Theme = 'light' | 'dark'
const KEY = 'sb2099-theme'

function read(): Theme {
  try {
    return (localStorage.getItem(KEY) as Theme) || 'light'
  } catch {
    return 'light'
  }
}

const theme = ref<Theme>(read())

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  try { localStorage.setItem(KEY, t) } catch { /* ignore */ }
}

export function useTheme() {
  function set(t: Theme) { theme.value = t; apply(t) }
  function toggle() { set(theme.value === 'light' ? 'dark' : 'light') }
  return { theme, set, toggle }
}
