<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError } from '@/api/client'
import { useTagsStore } from '@/stores/tags'
import { useIdentityStore } from '@/stores/identity'
import { useToast } from '@/composables/useToast'
import UserPicker from './UserPicker.vue'

const emit = defineEmits<{ (e: 'submitted'): void }>()
const tags = useTagsStore()
const ident = useIdentityStore()
const content = ref('')
const picked = ref<Set<string>>(new Set())
const anon = ref(false)
const busy = ref(false)

function toggle(v: string) { picked.value.has(v) ? picked.value.delete(v) : picked.value.add(v) }

async function submit() {
  const c = content.value.trim()
  if (c.length < 4) { useToast().push('再多写几个字吧', 'warn'); return }
  if (picked.value.size === 0) { useToast().push('至少选一个分类标签', 'warn'); return }
  busy.value = true
  try {
    const signUid = anon.value ? null : (ident.me?.uid ?? null)
    const row = await api.submit(c, [...picked.value], signUid)
    content.value = ''; picked.value.clear()
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
    <h3>🎤 投稿 <span class="pill">最少 6 字 · 自动查重</span></h3>
    <textarea v-model="content" maxlength="255" placeholder="你的烂梗比不过我你信吗"></textarea>
    <div class="tagrow">
      <span v-for="t in tags.list" :key="t.value" :data-test="`tag-${t.value}`"
            class="tagpick" :class="{ on: picked.has(t.value) }" @click="toggle(t.value)">{{ t.label }}</span>
    </div>
    <div v-if="ident.me" class="me">
      <img v-if="ident.me.avatar" class="av" :src="ident.me.avatar" alt="" referrerpolicy="no-referrer" />
      <span v-else class="av ph">{{ ident.me.nickname.slice(0, 1) }}</span>
      <span class="who">以 <b>{{ ident.me.nickname }}</b> 署名</span>
      <label class="anon"><input type="checkbox" v-model="anon" data-test="anon" />本次匿名</label>
      <button class="switch" data-test="switch-id" @click="ident.clear()">换 / 退出</button>
    </div>
    <UserPicker v-else @pick="ident.set($event)" />
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
.me{display:flex;align-items:center;gap:10px;background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:9px 12px}
.me .av{width:26px;height:26px;border-radius:50%;object-fit:cover;flex:0 0 auto}
.me .av.ph{display:inline-flex;align-items:center;justify-content:center;background:var(--accent-soft);color:var(--accent-deep);font-size:12px;font-weight:800}
.me .who{font-size:13px;color:var(--muted)}
.me .who b{color:var(--ink);font-weight:800}
.me .anon{margin-left:auto;display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);cursor:pointer;user-select:none}
.me .anon input{accent-color:var(--accent);cursor:pointer}
.me .switch{background:none;border:none;color:var(--subtle);font-size:12px;font-weight:700;cursor:pointer}
.me .switch:hover{color:var(--accent)}
.submitrow{display:flex;justify-content:flex-end;margin-top:12px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 20px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn:disabled{opacity:.5}
</style>
