<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import type { UserHit } from '@/api/types'

const emit = defineEmits<{ (e: 'pick', u: UserHit): void }>()
const q = ref('')
const hits = ref<UserHit[]>([])

async function onInput() {
  if (q.value.trim().length <= 2) { hits.value = []; return }
  hits.value = await api.searchUsers(q.value.trim()).catch(() => [])
}
function pick(u: UserHit) { hits.value = []; q.value = ''; emit('pick', u) }
</script>
<template>
  <div class="picker">
    <input v-model="q" placeholder="输入自己的斗鱼昵称/UID即可署名（≥3 字符；留空匿名）" @input="onInput" />
    <ul v-if="hits.length" class="results">
      <li v-for="u in hits" :key="u.uid" data-test="hit" @click="pick(u)">
        <img v-if="u.avatar" class="av" :src="u.avatar" alt="" referrerpolicy="no-referrer" />
        <span v-else class="av ph">{{ u.nickname.slice(0, 1) }}</span>
        <span>{{ u.nickname }}</span>
      </li>
    </ul>
  </div>
</template>
<style scoped>
.picker{position:relative}
input{width:100%;border:1px solid var(--line2);border-radius:10px;background:var(--panel2);padding:10px 12px;font:inherit;font-size:13px;color:var(--ink);outline:none}
.results{position:absolute;left:0;right:0;top:46px;background:var(--panel);border:1px solid var(--line2);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.16);z-index:20;list-style:none;max-height:200px;overflow:auto}
.results li{padding:8px 12px;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:8px}
.results li:hover{background:var(--panel2)}
.av{width:22px;height:22px;border-radius:50%;object-fit:cover;flex:0 0 auto}
.av.ph{display:inline-flex;align-items:center;justify-content:center;background:var(--accent-soft);color:var(--accent-deep);font-size:12px;font-weight:800}
</style>
