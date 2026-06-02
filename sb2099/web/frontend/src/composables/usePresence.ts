import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api/client'

// 心跳在线统计：每 ~30s 向 /api/presence 报一次到，服务端按 ip_hash 在 75s 窗口内去重计数。
// HTTP 不会主动告知谁还开着页面，所以必须靠这种周期性心跳（或 WebSocket/SSE 长连接）。
const PING_MS = 30_000

export function usePresence() {
  const online = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  async function ping() {
    try { online.value = (await api.presence()).online } catch { /* 静默 */ }
  }

  onMounted(() => {
    ping()
    timer = setInterval(ping, PING_MS)
    // 标签页重新可见时立即补一次，避免后台节流后显示陈旧
    document.addEventListener('visibilitychange', onVisible)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisible)
  })
  function onVisible() { if (document.visibilityState === 'visible') ping() }

  return { online }
}
