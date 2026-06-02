<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminPendingItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'

const toast = useToast()
const items = ref<AdminPendingItem[]>([])
const loading = ref(true)
const tagEdits = reactive<Record<number, string>>({})

async function load() {
  loading.value = true
  try {
    items.value = await api.admin.getPending()
    for (const it of items.value) tagEdits[it.id] = it.tags
  } finally {
    loading.value = false
  }
}

function fail(e: unknown, f: string) { toast.push(e instanceof ApiError ? e.message : f, 'warn') }

async function approve(it: AdminPendingItem) {
  try {
    await api.admin.approvePending(it.id, tagEdits[it.id] ?? it.tags)
    toast.push('已通过', 'ok')
    await load()
  } catch (e) { fail(e, '操作失败') }
}

async function reject(it: AdminPendingItem) {
  try {
    await api.admin.rejectPending(it.id)
    toast.push('已打回', 'ok')
    await load()
  } catch (e) { fail(e, '操作失败') }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>投稿待审</h1>
    <span class="sub">命中违禁词或反作弊规则的投稿在此人工复核</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <div v-else-if="!items.length" class="adm-empty">没有待审投稿 🎉</div>
  <div v-else class="list">
    <div v-for="it in items" :key="it.id" class="adm-card item">
      <div class="main">
        <p class="content">{{ it.content }}</p>
        <div class="meta">
          <span v-if="it.review_reason" class="adm-badge warn">{{ it.review_reason }}</span>
          <span class="adm-mono">#{{ it.id }}</span>
          <span>{{ cst(it.submit_time) }}</span>
        </div>
        <div v-if="it.submitter" class="submitter">
          <img v-if="it.submitter.avatar" :src="it.submitter.avatar" alt="" />
          <span>{{ it.submitter.nickname || it.submitter.uid }}</span>
          <span class="adm-mono">最后活跃 {{ cst(it.submitter.last_seen) }}</span>
        </div>
        <div v-if="it.recent_danmaku.length" class="recent">
          <p class="recent-h">该 uid 最近弹幕</p>
          <ul>
            <li v-for="(r, i) in it.recent_danmaku" :key="i">
              <span class="adm-mono">{{ cst(r.ts) }}</span> {{ r.content }}
            </li>
          </ul>
        </div>
      </div>
      <div class="ops">
        <input class="adm-input sm" v-model="tagEdits[it.id]" placeholder="标签 CSV，如 00,02" />
        <button class="adm-btn primary sm" @click="approve(it)">通过</button>
        <button class="adm-btn danger sm" @click="reject(it)">打回</button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.list { display: flex; flex-direction: column; gap: 12px; }
.item { display: flex; gap: 18px; justify-content: space-between; align-items: flex-start; }
.content { font-size: 15px; font-weight: 600; }
.meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: var(--subtle); margin-top: 8px; flex-wrap: wrap; }
.submitter { display: flex; gap: 8px; align-items: center; margin-top: 10px; font-size: 13px; }
.submitter img { width: 22px; height: 22px; border-radius: 50%; object-fit: cover; }
.recent { margin-top: 10px; border-top: 1px dashed var(--line); padding-top: 8px; }
.recent-h { font-size: 11px; color: var(--subtle); margin-bottom: 4px; }
.recent ul { list-style: none; }
.recent li { font-size: 12px; color: var(--muted); padding: 2px 0; }
.ops { display: flex; flex-direction: column; gap: 7px; min-width: 180px; }
.adm-input.sm { height: 30px; padding: 4px 8px; }
@media (max-width: 640px) { .item { flex-direction: column; } .ops { min-width: 0; flex-direction: row; flex-wrap: wrap; } }
</style>
