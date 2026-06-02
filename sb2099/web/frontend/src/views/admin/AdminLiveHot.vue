<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminLiveHotItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'

const toast = useToast()
const items = ref<AdminLiveHotItem[]>([])
const filtered = ref(false)
const loading = ref(true)
const busy = ref('')

async function load() {
  loading.value = true
  try { items.value = await api.admin.getLiveHot(filtered.value) } finally { loading.value = false }
}

function setFiltered(v: boolean) { filtered.value = v; load() }

async function rescan() {
  busy.value = 'rescan'
  try {
    await api.admin.rescanLiveHot()
    toast.push('已按当前阈值重建当日榜单', 'ok')
    await load()
  } catch (e) { toast.push(e instanceof ApiError ? e.message : '操作失败', 'warn') }
  finally { busy.value = '' }
}

async function recompute() {
  if (!confirm('重归一化所有历史 raw 并重建榜单？数据量大时可能耗时。')) return
  busy.value = 'recompute'
  try {
    const r = await api.admin.recomputeLiveHot()
    toast.push(`已重归一化 ${r.raw_renormalized} 条 raw 并重建`, 'ok')
    await load()
  } catch (e) { toast.push(e instanceof ApiError ? e.message : '操作失败', 'warn') }
  finally { busy.value = '' }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>直播热榜</h1>
    <span class="sub">由原始弹幕按直播日聚合；可查看明细、重算或重归一化</span>
  </div>

  <div class="bar">
    <div class="seg">
      <button class="adm-btn sm" :class="{ primary: !filtered }" @click="setFiltered(false)">达标榜单</button>
      <button class="adm-btn sm" :class="{ primary: filtered }" @click="setFiltered(true)">被过滤</button>
    </div>
    <div class="spacer" />
    <button class="adm-btn sm" :disabled="!!busy" @click="rescan">{{ busy === 'rescan' ? '重算中…' : '重新聚合' }}</button>
    <button class="adm-btn sm" :disabled="!!busy" @click="recompute">{{ busy === 'recompute' ? '处理中…' : '重归一化 + 重建' }}</button>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="!items.length" class="adm-empty">没有数据</div>
  <div v-else class="adm-card">
    <table class="adm-table">
      <thead><tr><th>#</th><th>样本内容</th><th>直播日</th><th class="num">发送</th><th class="num">人数</th><th>最近</th><th></th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td class="adm-mono">{{ it.id }}</td>
          <td class="content">{{ it.content_sample }}</td>
          <td>{{ it.live_date }}</td>
          <td class="num">{{ it.send_cnt }}</td>
          <td class="num">{{ it.unique_sender_cnt }}</td>
          <td>{{ cst(it.last_seen) }}</td>
          <td><router-link class="adm-btn sm" :to="`/admin/live-hot/${it.id}`">明细</router-link></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; }
.seg { display: flex; gap: 6px; }
.spacer { flex: 1; }
.content { max-width: 380px; }
</style>
