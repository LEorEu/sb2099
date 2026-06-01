<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError } from '@/api/client'
import { useTagsStore } from '@/stores/tags'
import { useToast } from '@/composables/useToast'
import UserPicker from './UserPicker.vue'

const emit = defineEmits<{ (e: 'submitted'): void }>()
const tags = useTagsStore()
const content = ref('')
const picked = ref<Set<string>>(new Set())
const uid = ref<string | null>(null)
const busy = ref(false)

function toggle(v: string) { picked.value.has(v) ? picked.value.delete(v) : picked.value.add(v) }

async function submit() {
  const c = content.value.trim()
  if (c.length < 4) { useToast().push('再多写几个字吧', 'warn'); return }
  if (picked.value.size === 0) { useToast().push('至少选一个分类标签', 'warn'); return }
  busy.value = true
  try {
    const row = await api.submit(c, [...picked.value], uid.value)
    content.value = ''; picked.value.clear(); uid.value = null
    useToast().push('投好了！丢进梗库 🎉', 'ok', {
      label: '撤回',
      run: () => api.withdraw(row.id).then(() => useToast().push('已撤回')).catch(() => useToast().push('撤回窗口已过', 'warn')),
    }, 60000)
    emit('submitted')
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) useToast().push('这条已经有人投过啦', 'warn')
    else if (e instanceof ApiError && e.status === 422) useToast().push('内容没通过审核', 'warn')
    else useToast().push('投稿失败，稍后再试', 'warn')
  } finally { busy.value = false }
}
</script>
<template>
  <div class="card">
    <h3>🎤 投个梗 <span class="pill">最多 255 字 · 自动查重</span></h3>
    <textarea v-model="content" maxlength="255" placeholder="听到啥好笑的弹幕，丢进来…"></textarea>
    <div class="tagrow">
      <span v-for="t in tags.list" :key="t.value" :data-test="`tag-${t.value}`"
            class="tagpick" :class="{ on: picked.has(t.value) }" @click="toggle(t.value)">{{ t.label }}</span>
    </div>
    <UserPicker v-model:uid="uid" />
    <div class="submitrow">
      <button class="btn" data-test="submit" :disabled="busy" @click="submit">丢进梗库 →</button>
    </div>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
h3{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:13px}
.pill{margin-left:auto;font-size:12px;color:var(--subtle);font-weight:600}
textarea{width:100%;min-height:88px;resize:vertical;border:1px solid var(--line2);border-radius:12px;background:var(--panel2);padding:12px 13px;font:inherit;font-size:15px;color:var(--ink);outline:none}
.tagrow{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.tagpick{font-size:13px;font-weight:700;padding:6px 12px;border-radius:999px;cursor:pointer;background:var(--panel2);border:1px solid var(--line);color:var(--muted)}
.tagpick.on{background:var(--accent);border-color:var(--accent);color:#fff}
.submitrow{display:flex;justify-content:flex-end;margin-top:12px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 20px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn:disabled{opacity:.5}
</style>
