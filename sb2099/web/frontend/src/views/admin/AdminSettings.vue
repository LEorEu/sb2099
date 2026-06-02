<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { AdminSettingItem } from '@/api/types'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const items = ref<AdminSettingItem[]>([])
// 编辑态：int → 字符串数字；lines → 多行文本
const form = ref<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)

function toText(it: AdminSettingItem): string {
  if (it.kind === 'lines') return Array.isArray(it.value) ? it.value.join('\n') : ''
  return it.value === null || it.value === undefined ? '' : String(it.value)
}

async function load() {
  loading.value = true
  try {
    items.value = await api.admin.getSettings()
    const f: Record<string, string> = {}
    for (const it of items.value) f[it.key] = toText(it)
    form.value = f
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const values: Record<string, string | string[]> = {}
    for (const it of items.value) {
      values[it.key] = it.kind === 'lines'
        ? form.value[it.key].split('\n').map(s => s.trim()).filter(Boolean)
        : form.value[it.key]
    }
    await api.admin.putSettings(values)
    toast.push('已保存，运行时缓存已失效，下次访问即生效', 'ok')
    await load()
  } catch (e) {
    const detail = e instanceof ApiError ? e.detail : null
    const errs = (detail as any)?.errors as string[] | undefined
    toast.push(errs?.length ? `保存失败：${errs.join('；')}` : '保存失败', 'warn', undefined, 6000)
  } finally {
    saving.value = false
  }
}

function defaultText(it: AdminSettingItem): string {
  return Array.isArray(it.default) ? JSON.stringify(it.default) : String(it.default)
}

onMounted(load)
</script>
<template>
  <div class="adm-head">
    <h1>运行时参数</h1>
    <span class="sub">阈值 · 关键词 · 限流 —— 保存即热生效，无需重启</span>
  </div>

  <div v-if="loading" class="adm-empty">加载中…</div>
  <template v-else>
    <div class="adm-card hint-card">
      💡 整数类直接填数字；多行类每行一条，前后空白与空行自动忽略。
    </div>

    <form class="adm-card" @submit.prevent="save">
      <div v-for="it in items" :key="it.key" class="row">
        <div class="meta">
          <label :for="`f-${it.key}`">{{ it.label }}</label>
          <p class="desc">{{ it.desc }}</p>
          <p class="adm-mono">{{ it.key }}</p>
        </div>
        <div class="inp">
          <textarea
            v-if="it.kind === 'lines'" :id="`f-${it.key}`" class="adm-textarea"
            v-model="form[it.key]" rows="4" spellcheck="false"
          />
          <input v-else :id="`f-${it.key}`" class="adm-input" v-model="form[it.key]" spellcheck="false" />
          <p class="hint">{{ it.hint }} · 默认 <code>{{ defaultText(it) }}</code></p>
        </div>
      </div>
      <div class="actions">
        <button class="adm-btn primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </form>
  </template>
</template>
<style scoped>
.hint-card { font-size: 13px; color: var(--muted); }
.row { display: grid; grid-template-columns: 280px 1fr; gap: 20px; padding: 16px 0; border-bottom: 1px solid var(--line); }
.row:last-of-type { border-bottom: none; }
.meta label { font-weight: 800; font-size: 14px; }
.meta .desc { font-size: 12px; color: var(--muted); margin: 5px 0; line-height: 1.5; }
.inp .hint { font-size: 12px; color: var(--subtle); margin-top: 6px; }
.inp code { background: var(--panel2); border: 1px solid var(--line); border-radius: 5px; padding: 1px 5px; }
.actions { margin-top: 18px; text-align: right; }
@media (max-width: 720px) { .row { grid-template-columns: 1fr; gap: 10px; } }
</style>
