<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminReportItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'

const toast = useToast()
const items = ref<AdminReportItem[]>([])
const loading = ref(true)

async function load() {
  loading.value = true
  try { items.value = await api.admin.getReports() } finally { loading.value = false }
}

async function dismiss(it: AdminReportItem) {
  if (!confirm(`确认「这条没问题」？将清空 #${it.id} 的反馈记录，投稿保持上架。`)) return
  try {
    await api.admin.dismissReport(it.id)
    toast.push('已忽略反馈', 'ok')
    await load()
  } catch (e) { toast.push(e instanceof ApiError ? e.message : '操作失败', 'warn') }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>被反馈的投稿</h1>
    <span class="sub">观众点了「这条不合适」的条目，按反馈数排序</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="!items.length" class="adm-empty">暂无被反馈的条目 ✨</div>
  <div v-else class="adm-card">
    <table class="adm-table">
      <thead><tr><th>#</th><th>内容</th><th>标签</th><th class="num">复制</th><th class="num">反馈</th><th>状态</th><th>最近反馈</th><th></th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td class="adm-mono">{{ it.id }}</td>
          <td class="content">{{ it.content }}</td>
          <td class="adm-mono">{{ it.tags }}</td>
          <td class="num">{{ it.cnt }}</td>
          <td class="num"><span class="adm-badge warn">{{ it.report_cnt }}</span></td>
          <td>{{ it.status }}</td>
          <td>{{ cst(it.last_report) }}</td>
          <td><button class="adm-btn sm" @click="dismiss(it)">没问题</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped>
.content { max-width: 360px; }
</style>
