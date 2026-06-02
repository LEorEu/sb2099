import { ref } from 'vue'

type Theme = 'light' | 'dark'
// 主站与后台视作两个站点，主题各自存储互不影响（后台用 sb2099-theme）
const KEY = 'sb2099-spa-theme'

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
