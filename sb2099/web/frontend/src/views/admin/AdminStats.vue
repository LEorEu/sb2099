<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { AdminStats } from '@/api/types'

const data = ref<AdminStats | null>(null)
const loading = ref(true)

onMounted(async () => {
  try { data.value = await api.admin.getStats() } finally { loading.value = false }
})

const cards = (d: AdminStats) => [
  { label: '24h 原始弹幕', value: d.raw_24h },
  { label: '24h 投稿', value: d.submit_24h },
  { label: '累计复制', value: d.copy_total },
  { label: '直播热门总数', value: d.live_hot_total },
  { label: '待审', value: d.pending_total },
  { label: '回收站', value: d.deleted_total },
  { label: '24h 反馈', value: d.report_24h },
]
</script>
<template>
  <div class="adm-head">
    <h1>数据概览</h1>
    <span class="sub">近 24 小时运营数据</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <template v-else-if="data">
    <div class="grid">
      <div v-for="c in cards(data)" :key="c.label" class="adm-card stat">
        <span class="v">{{ c.value }}</span>
        <span class="l">{{ c.label }}</span>
      </div>
    </div>

    <div class="adm-card">
      <h2 class="sec">24h 投稿 IP TOP（哈希）</h2>
      <div v-if="!data.top_ip.length" class="adm-empty">无</div>
      <table v-else class="adm-table">
        <thead><tr><th>ip_hash</th><th class="num">投稿数</th></tr></thead>
        <tbody>
          <tr v-for="r in data.top_ip" :key="r.ip_hash">
            <td class="adm-mono">{{ r.ip_hash }}</td>
            <td class="num">{{ r.count }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.stat { display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; }
.stat .v { font-size: 26px; font-weight: 900; font-variant-numeric: tabular-nums; }
.stat .l { font-size: 12px; color: var(--subtle); }
.sec { font-size: 14px; font-weight: 800; margin-bottom: 10px; }
</style>
