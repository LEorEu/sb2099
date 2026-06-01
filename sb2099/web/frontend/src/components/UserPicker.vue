<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import type { UserHit } from '@/api/types'

defineProps<{ uid: string | null }>()
const emit = defineEmits<{ (e: 'update:uid', v: string | null): void }>()
const q = ref('')
const hits = ref<UserHit[]>([])
const picked = ref<UserHit | null>(null)

async function onInput() {
  if (q.value.trim().length <= 2) { hits.value = []; return }
  hits.value = await api.searchUsers(q.value.trim()).catch(() => [])
}
function pick(u: UserHit) { picked.value = u; hits.value = []; q.value = ''; emit('update:uid', u.uid) }
function clear() { picked.value = null; emit('update:uid', null) }
</script>
<template>
  <div class="picker">
    <div v-if="picked" class="chip">
      <span>{{ picked.nickname }}</span>
      <button @click="clear">×</button>
    </div>
    <template v-else>
      <input v-model="q" placeholder="选「我是谁」可署名（昵称/UID，≥3 字符；留空匿名）" @input="onInput" />
      <ul v-if="hits.length" class="results">
        <li v-for="u in hits" :key="u.uid" data-test="hit" @click="pick(u)">{{ u.nickname }}</li>
      </ul>
    </template>
  </div>
</template>
<style scoped>
.picker{position:relative}
.chip{display:inline-flex;align-items:center;gap:8px;background:var(--accent-soft);color:var(--accent-deep);padding:6px 10px;border-radius:9px;font-size:13px;font-weight:700}
.chip button{background:none;border:none;color:inherit;cursor:pointer;font-size:15px}
input{width:100%;border:1px solid var(--line2);border-radius:10px;background:var(--panel2);padding:10px 12px;font:inherit;font-size:13px;color:var(--ink);outline:none}
.results{position:absolute;left:0;right:0;top:46px;background:var(--panel);border:1px solid var(--line2);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.16);z-index:20;list-style:none;max-height:200px;overflow:auto}
.results li{padding:9px 12px;font-size:13px;cursor:pointer}
.results li:hover{background:var(--panel2)}
</style>
