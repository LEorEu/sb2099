import { api } from '@/api/client'
import { useToast } from './useToast'

export function useCopy() {
  const toast = useToast()
  async function copy(text: string, source: 'barrage' | 'live_hot', id: number) {
    try {
      await navigator.clipboard.writeText(text)
      toast.push('已复制，回直播间粘贴就行 ✌️')
    } catch {
      toast.push('复制失败，长按手动复制吧', 'warn')
    }
    api.copy(source, id).catch(() => { /* 计数失败不打扰用户 */ })
  }
  return { copy }
}
