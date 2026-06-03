<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminTrashItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'
import TagChips from '@/components/TagChips.vue'

const toast = useToast()
const items = ref<AdminTrashItem[]>([])
const loading = ref(true)

async function load() {
  loading.value = true
  try { items.value = await api.admin.getTrash() } finally { loading.value = false }
}

function fail(e: unknown, f: string) { toast.push(e instanceof ApiError ? e.message : f, 'warn') }

async function restore(it: AdminTrashItem) {
  try { await api.admin.restoreTrash(it.id); toast.push('已恢复上架', 'ok'); await load() }
  catch (e) { fail(e, '恢复失败') }
}

async function purge(it: AdminTrashItem) {
  if (!confirm(`彻底删除 #${it.id}？不可恢复。`)) return
  try { await api.admin.purgeTrash(it.id); toast.push('已彻底删除', 'ok'); await load() }
  catch (e) { fail(e, '删除失败') }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>回收站</h1>
    <span class="sub">已下架（deleted）的投稿，可恢复或彻底清除</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="!items.length" class="adm-empty">回收站是空的</div>
  <div v-else class="adm-card">
    <table class="adm-table">
      <thead><tr><th>#</th><th>内容</th><th>标签</th><th class="num">复制</th><th>投稿时间</th><th></th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td class="adm-mono">{{ it.id }}</td>
          <td class="content">{{ it.content }}</td>
          <td><TagChips :csv="it.tags" /></td>
          <td class="num">{{ it.cnt }}</td>
          <td>{{ cst(it.submit_time) }}</td>
          <td class="ops">
            <button class="adm-btn sm" @click="restore(it)">恢复</button>
            <button class="adm-btn danger sm" @click="purge(it)">彻底删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped>
.content { max-width: 420px; }
.ops { display: flex; gap: 6px; }
</style>
