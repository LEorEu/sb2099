<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import type { AdminLiveHotDetail } from '@/api/types'
import { cst } from '@/composables/useCst'

const route = useRoute()
const data = ref<AdminLiveHotDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)

onMounted(async () => {
  try {
    data.value = await api.admin.getLiveHotDetail(Number(route.params.id))
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
})
</script>
<template>
  <div class="adm-head">
    <h1>热门明细</h1>
    <router-link class="adm-btn ghost sm" to="/admin/live-hot">← 返回列表</router-link>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="notFound" class="adm-empty">未找到该记录</div>
  <template v-else-if="data">
    <div class="adm-card">
      <p class="sample">{{ data.hot.content_sample }}</p>
      <div class="kv">
        <span>直播日 <b>{{ data.hot.live_date }}</b></span>
        <span>发送 <b>{{ data.hot.send_cnt }}</b></span>
        <span>去重人数 <b>{{ data.hot.unique_sender_cnt }}</b></span>
        <span>首次 <b>{{ cst(data.hot.first_seen) }}</b></span>
        <span>最近 <b>{{ cst(data.hot.last_seen) }}</b></span>
        <span v-if="data.hot.is_filtered" class="adm-badge warn">已过滤</span>
      </div>
      <p class="adm-mono norm">归一化：{{ data.hot.content_norm }}</p>
    </div>

    <div class="cols">
      <div class="adm-card">
        <h2 class="sec">高频发送者 TOP（识别刷子）</h2>
        <div v-if="!data.top_uids.length" class="adm-empty">无</div>
        <table v-else class="adm-table">
          <thead><tr><th>uid</th><th class="num">次数</th></tr></thead>
          <tbody>
            <tr v-for="u in data.top_uids" :key="u.uid">
              <td class="adm-mono">{{ u.uid }}</td>
              <td class="num">{{ u.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="adm-card">
        <h2 class="sec">原始弹幕（最多 500 条）</h2>
        <div v-if="!data.raws.length" class="adm-empty">raw 已被留存策略清理</div>
        <table v-else class="adm-table">
          <thead><tr><th>时间</th><th>昵称</th><th>内容</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in data.raws" :key="i">
              <td class="adm-mono">{{ cst(r.ts) }}</td>
              <td>{{ r.nickname || '—' }}</td>
              <td>{{ r.content }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
</template>
<style scoped>
.sample { font-size: 17px; font-weight: 700; }
.kv { display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0; font-size: 13px; color: var(--muted); }
.kv b { color: var(--ink); }
.norm { margin-top: 4px; }
.sec { font-size: 14px; font-weight: 800; margin-bottom: 10px; }
.cols { display: grid; grid-template-columns: 320px 1fr; gap: 16px; align-items: start; }
@media (max-width: 820px) { .cols { grid-template-columns: 1fr; } }
</style>
