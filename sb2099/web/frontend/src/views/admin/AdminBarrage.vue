<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminBarrageItem } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { useTagsStore } from '@/stores/tags'
import { cst } from '@/composables/useCst'
import TagChips from '@/components/TagChips.vue'

const toast = useToast()
const tagsStore = useTagsStore()
const items = ref<AdminBarrageItem[]>([])
const total = ref(0)
const page = ref(1)
const lastPage = ref(true)
const q = ref('')
const sort = ref<'new' | 'hot'>('new')
const loading = ref(true)

// 行内编辑（弹窗）
const editing = ref<AdminBarrageItem | null>(null)
const editContent = ref('')
const editTags = ref<string[]>([])
const saving = ref(false)

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

function openEdit(it: AdminBarrageItem) {
  editing.value = it
  editContent.value = it.content
  editTags.value = (it.tags || '').split(',').map(s => s.trim()).filter(Boolean)
}
function closeEdit() { editing.value = null }
function toggleTag(v: string) {
  const i = editTags.value.indexOf(v)
  if (i >= 0) editTags.value.splice(i, 1)
  else editTags.value.push(v)
}
async function saveEdit() {
  if (!editing.value) return
  const content = editContent.value.trim()
  if (!content) { toast.push('正文不能为空', 'warn'); return }
  saving.value = true
  try {
    await api.admin.editBarrage(editing.value.id, { content, tags: editTags.value })
    toast.push('已保存', 'ok')
    editing.value = null
    await load()
  } catch (e) {
    toast.push(e instanceof ApiError ? e.message : '保存失败', 'warn')
  } finally {
    saving.value = false
  }
}

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

onMounted(() => { tagsStore.load(); load() })
</script>
<template>
  <div class="adm-head">
    <h1>全部烂梗</h1>
    <span class="sub">已上架投稿库 · 搜索 / 编辑 / 下架（进回收站）· 共 {{ total }} 条</span>
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
      <thead><tr><th>#</th><th>内容</th><th>标签</th><th>投稿人</th><th>时间</th><th></th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td class="adm-mono">{{ it.id }}</td>
          <td class="content">{{ it.content }}</td>
          <td><TagChips v-if="(it.tags || '').trim()" :csv="it.tags" /><span v-else class="dim">—</span></td>
          <td>{{ it.submitter?.nickname || '匿名' }}</td>
          <td>{{ cst(it.submit_time) }}</td>
          <td class="ops">
            <button class="adm-btn sm" @click="openEdit(it)">编辑</button>
            <button class="adm-btn danger sm" @click="takeDown(it)">下架</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <nav v-if="!loading && items.length" class="pager">
    <button class="adm-btn sm" :disabled="page <= 1" @click="go(-1)">上一页</button>
    <span class="pg">第 {{ page }} 页</span>
    <button class="adm-btn sm" :disabled="lastPage" @click="go(1)">下一页</button>
  </nav>

  <!-- 编辑弹窗 -->
  <Teleport to="body">
    <div v-if="editing" class="adm-modal-wrap">
      <div class="adm-modal-bd" @click="closeEdit"></div>
      <div class="adm-modal" role="dialog" aria-modal="true">
        <div class="modal-head">
          <h3>编辑 <span class="adm-mono">#{{ editing.id }}</span></h3>
          <button class="x" @click="closeEdit">✕</button>
        </div>
        <label class="fld">
          <span class="lbl">正文</span>
          <textarea class="adm-input ta" v-model="editContent" rows="3" placeholder="烂梗正文"></textarea>
        </label>
        <div class="fld">
          <span class="lbl">标签 <span class="dim">（点选，可多选；改完即覆盖原标签）</span></span>
          <div class="tagpick">
            <button v-for="t in tagsStore.list" :key="t.value" type="button"
              class="tp" :class="{ on: editTags.includes(t.value) }" @click="toggleTag(t.value)">{{ t.label }}</button>
            <span v-if="!tagsStore.list.length" class="dim">暂无可用标签，去「标签管理」新建</span>
          </div>
        </div>
        <div class="modal-ops">
          <button class="adm-btn" @click="closeEdit">取消</button>
          <button class="adm-btn primary" :disabled="saving" @click="saveEdit">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.bar .adm-input { max-width: 300px; }
.seg { display: flex; gap: 6px; margin-left: auto; }
.content { max-width: 420px; }
.dim { color: var(--subtle); }
.ops { display: flex; gap: 6px; }
.pager { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; }
.pg { font-size: 13px; color: var(--subtle); }
/* modal */
.adm-modal-wrap { position: fixed; inset: 0; z-index: 80; display: flex; align-items: center; justify-content: center; padding: 20px; }
.adm-modal-bd { position: fixed; inset: 0; background: rgba(20, 18, 12, .42); }
.adm-modal { position: relative; width: 520px; max-width: 100%; background: var(--panel); border: 1px solid var(--line2); border-radius: 16px; box-shadow: 0 24px 60px rgba(0, 0, 0, .28); padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; }
.modal-head { display: flex; align-items: center; justify-content: space-between; }
.modal-head h3 { font-size: 16px; font-weight: 800; }
.modal-head .x { font-size: 18px; color: var(--subtle); background: none; border: none; cursor: pointer; }
.fld { display: flex; flex-direction: column; gap: 7px; }
.fld .lbl { font-size: 13px; font-weight: 700; color: var(--muted); }
.ta { resize: vertical; min-height: 64px; line-height: 1.5; }
.tagpick { display: flex; flex-wrap: wrap; gap: 8px; }
.tp { font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--panel2); color: var(--muted); cursor: pointer; }
.tp.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-deep); }
.modal-ops { display: flex; gap: 10px; justify-content: flex-end; margin-top: 2px; }
</style>
