<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminTag } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { cst } from '@/composables/useCst'

const toast = useToast()
const tags = ref<AdminTag[]>([])
const threshold = ref(0)
const loading = ref(true)

const enabled = computed(() => tags.value.filter(t => t.enabled))
const pending = computed(() => tags.value.filter(t => !t.enabled))

const draft = ref({ label: '', icon_url: '', sort: 0 })

async function load() {
  loading.value = true
  try {
    const r = await api.admin.getTags()
    tags.value = r.tags
    threshold.value = r.vote_threshold
  } finally {
    loading.value = false
  }
}

function fail(e: unknown, fallback: string) {
  toast.push(e instanceof ApiError ? e.message : fallback, 'warn')
}

async function create() {
  if (!draft.value.label.trim()) return
  try {
    await api.admin.createTag({
      label: draft.value.label.trim(),
      icon_url: draft.value.icon_url, sort: Number(draft.value.sort) || 0,
    })
    draft.value = { label: '', icon_url: '', sort: 0 }
    toast.push('已新增标签', 'ok')
    await load()
  } catch (e) { fail(e, '新增失败') }
}

async function saveRow(t: AdminTag) {
  try {
    await api.admin.updateTag(t.value, {
      label: t.label, icon_url: t.icon_url || '', sort: Number(t.sort) || 0, enabled: t.enabled,
    })
    toast.push(`已保存「${t.label}」`, 'ok')
  } catch (e) { fail(e, '保存失败') }
}

async function remove(t: AdminTag) {
  if (!confirm(`删除标签「${t.label}」？相关投票会一并清除。`)) return
  try {
    await api.admin.deleteTag(t.value)
    toast.push('已删除', 'ok')
    await load()
  } catch (e) { fail(e, '删除失败') }
}

async function approve(t: AdminTag) {
  try {
    await api.admin.approveTag(t.value)
    toast.push(`已批准 ${t.label}`, 'ok')
    await load()
  } catch (e) { fail(e, '批准失败') }
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>标签管理</h1>
    <span class="sub">开放词表 · 候选标签满 {{ threshold }} 票后可批准入库</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <template v-else>
    <!-- 候选标签 -->
    <div v-if="pending.length" class="adm-card">
      <h2 class="sec">观众提议待审 <span class="adm-badge warn">{{ pending.length }}</span></h2>
      <p class="sechint">按标签名去重：同一个名字被多人/多条提议会累加到同一行，票数/关联即真实热度。</p>
      <table class="adm-table">
        <thead><tr><th>标签名</th><th>提议人</th><th class="num">提议票 / 关联弹幕</th><th>首次提议</th><th></th></tr></thead>
        <tbody>
          <tr v-for="t in pending" :key="t.value">
            <td class="name">{{ t.label }}</td>
            <td>{{ t.proposer_nick || t.proposer_uid || '—' }}</td>
            <td class="num">{{ t.pending?.vote_count ?? 0 }} 票 / {{ t.pending?.barrage_count ?? 0 }} 条</td>
            <td>{{ cst(t.proposed_at) }}</td>
            <td class="ops">
              <button class="adm-btn primary sm" @click="approve(t)">批准</button>
              <button class="adm-btn danger sm" @click="remove(t)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 启用中的标签 -->
    <div class="adm-card">
      <h2 class="sec">启用中 <span class="adm-badge muted">{{ enabled.length }}</span></h2>
      <table class="adm-table">
        <thead><tr><th>名称</th><th>图标 URL</th><th class="num">排序</th><th>启用</th><th></th></tr></thead>
        <tbody>
          <tr v-for="t in enabled" :key="t.value">
            <td><input class="adm-input sm" v-model="t.label" /></td>
            <td><input class="adm-input sm" v-model="t.icon_url" placeholder="可空" /></td>
            <td class="num"><input class="adm-input sm w60" v-model.number="t.sort" /></td>
            <td><input type="checkbox" v-model="t.enabled" /></td>
            <td class="ops">
              <button class="adm-btn sm" @click="saveRow(t)">保存</button>
              <button class="adm-btn danger sm" @click="remove(t)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建 -->
    <form class="adm-card" @submit.prevent="create">
      <h2 class="sec">新建标签</h2>
      <div class="new-grid">
        <input class="adm-input" v-model="draft.label" placeholder="标签名称" />
        <input class="adm-input" v-model="draft.icon_url" placeholder="图标 URL（可空）" />
        <input class="adm-input w80" v-model.number="draft.sort" placeholder="排序" />
        <button class="adm-btn primary" type="submit">新增</button>
      </div>
    </form>
  </template>
</template>
<style scoped>
.sec { font-size: 15px; font-weight: 800; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.sechint { font-size: 12px; color: var(--subtle); margin: -6px 0 12px; }
.name { font-weight: 700; }
.adm-input.sm { height: 30px; padding: 4px 8px; }
.w60 { width: 64px; } .w80 { width: 90px; }
.ops { display: flex; gap: 6px; }
.new-grid { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.new-grid .adm-input { flex: 1; min-width: 140px; }
</style>
