<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import MemeRow from './MemeRow.vue'

const list = ref<Barrage[]>([])
async function load() {
  const r = await api.searchBarrage({ sort: 'new', page: 1, size: 5 }).catch(() => null)
  if (r) list.value = r.list
}
defineExpose({ load })
onMounted(load)
</script>
<template>
  <div class="card">
    <h3>🆕 刚有人投了这些</h3>
    <div class="memelist"><MemeRow v-for="b in list" :key="b.id" :item="b" /></div>
    <router-link class="seeall" to="/barrage">看全部烂梗 →</router-link>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
h3{font-size:15px;font-weight:800;margin-bottom:13px}
.memelist{display:flex;flex-direction:column;gap:10px}
.seeall{display:block;text-align:center;margin-top:13px;font-size:14px;font-weight:800;color:var(--accent)}
</style>
