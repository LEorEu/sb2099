<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import { useCopy } from '@/composables/useCopy'

const meme = ref<Barrage | null>(null)
const { copy } = useCopy()
async function load() { meme.value = await api.getRandom().catch(() => null) }
function onCopy() { if (meme.value) copy(meme.value.content, 'barrage', meme.value.id) }
onMounted(load)
</script>
<template>
  <div class="card daily">
    <h3>🎲 今日一梗 <span class="pill">手气不错</span></h3>
    <div class="big">{{ meme?.content || '梗库还空着，先投一条吧' }}</div>
    <div class="acts">
      <button class="btn" style="flex:1" @click="onCopy">点我复制</button>
      <button class="btn ghost" @click="load">换一个</button>
    </div>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
.daily{background:linear-gradient(135deg,var(--accent-soft),var(--pink-soft));border:1px solid var(--line2)}
h3{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:13px}
.pill{margin-left:auto;font-size:12px;color:var(--accent);font-weight:700}
.big{font-size:22px;font-weight:900;line-height:1.4;margin:6px 0 14px}
.acts{display:flex;gap:10px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 18px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn.ghost{background:var(--panel);color:var(--ink);box-shadow:0 4px 0 var(--line2);border:1px solid var(--line)}
</style>
