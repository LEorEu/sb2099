import { reactive } from 'vue'

export interface ToastItem { id: number; text: string; kind: 'ok' | 'warn'; action?: { label: string; run: () => void } }
const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 1

export function useToast() {
  function push(text: string, kind: 'ok' | 'warn' = 'ok', action?: ToastItem['action'], ttl = 4000) {
    const id = seq++
    state.items.push({ id, text, kind, action })
    if (ttl > 0) setTimeout(() => dismiss(id), ttl)
    return id
  }
  function dismiss(id: number) {
    const i = state.items.findIndex(t => t.id === id)
    if (i >= 0) state.items.splice(i, 1)
  }
  return { items: state.items, push, dismiss }
}
