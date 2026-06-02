<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminBarrageItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'

const toast = useToast()
const items = ref<AdminBarrageItem[]>([])
const total = ref(0)
const page = ref(1)
const lastPage = ref(true)
const q = ref('')
const sort = ref<'new' | 'hot'>('new')
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const r = await api.admin.getBarrage({ q: q.value.trim(), sort: sort.value, page: page.value, size: 30 })
    items.value = r.items
    total.value = r.total
    lastPage.value = r.last_page
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }
function setSort(s: 'new' | 'hot') { sort.value = s; page.value = 1; load() }
function go(d: number) { page.value = Math.max(1, page.value + d); load() }

async function takeDown(it: AdminBarrageItem) {
  if (!confirm(`下架 #${it.id}「${it.content.slice(0, 30)}」？会进回收站，可恢复。`)) return
  try {
    await api.admin.deleteBarrage(it.id)
    toast.push('已下架，进回收站', 'ok')
    await load()
  } catch (e) {
    toast.push(e instanceof ApiError ? e.message : '下架失败', 'warn')
  }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>全部烂梗</h1>
    <span class="sub">已上架投稿库 · 搜索 / 下架（进回收站）· 共 {{ total }} 条</span>
  </div>

  <div class="bar">
    <input class="adm-input" v-model="q" placeholder="搜正文关键字…" @keyup.enter="search" />
    <button class="adm-btn" @click="search">搜索</button>
    <div class="seg">
      <button class="adm-btn sm" :class="{ primary: sort === 'new' }" @click="setSort('new')">最新</button>
      <button class="adm-btn sm" :class="{ primary: sort === 'hot' }" @click="setSort('hot')">最热</button>
    </div>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="!items.length" class="adm-empty">没有匹配的烂梗</div>
  <div v-else class="adm-card">
    <table class="adm-table">
      <thead><tr><th>#</th><th>内容</th><th>标签</th><th class="num">复制</th><th class="num">反馈</th><th>投稿人</th><th>时间</th><th></th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td class="adm-mono">{{ it.id }}</td>
          <td class="content">{{ it.content }}</td>
          <td class="adm-mono">{{ it.tags }}</td>
          <td class="num">{{ it.cnt }}</td>
          <td class="num"><span v-if="it.report_cnt" class="adm-badge warn">{{ it.report_cnt }}</span><span v-else>0</span></td>
          <td>{{ it.submitter?.nickname || '匿名' }}</td>
          <td>{{ cst(it.submit_time) }}</td>
          <td><button class="adm-btn danger sm" @click="takeDown(it)">下架</button></td>
        </tr>
      </tbody>
    </table>
  </div>

  <nav v-if="!loading && items.length" class="pager">
    <button class="adm-btn sm" :disabled="page <= 1" @click="go(-1)">上一页</button>
    <span class="pg">第 {{ page }} 页</span>
    <button class="adm-btn sm" :disabled="lastPage" @click="go(1)">下一页</button>
  </nav>
</template>
<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.bar .adm-input { max-width: 300px; }
.seg { display: flex; gap: 6px; margin-left: auto; }
.content { max-width: 420px; }
.pager { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; }
.pg { font-size: 13px; color: var(--subtle); }
</style>
