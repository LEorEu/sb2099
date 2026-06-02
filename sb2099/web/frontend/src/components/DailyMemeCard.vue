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
    <div class="bigwrap">
      <Transition name="slide" mode="out-in">
        <div class="big" :key="meme?.id ?? 'empty'">{{ meme?.content || '梗库还空着，先投一条吧' }}</div>
      </Transition>
    </div>
    <div class="acts">
      <button class="btn" style="flex:1" @click="onCopy">点我复制</button>
      <button class="btn ghost" @click="load">换一个</button>
    </div>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
.daily{background:linear-gradient(135deg,var(--violet-soft),var(--pink-soft));border:1px solid var(--line2)}
h3{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:13px}
.pill{margin-left:auto;font-size:12px;color:var(--violet);font-weight:700}
.bigwrap{position:relative;overflow:hidden;min-height:62px;margin:6px 0 14px}
.big{font-size:22px;font-weight:900;line-height:1.4}
.slide-enter-active,.slide-leave-active{transition:transform .28s cubic-bezier(.4,0,.2,1),opacity .28s}
.slide-enter-from{transform:translateX(40px);opacity:0}
.slide-leave-to{transform:translateX(-40px);opacity:0}
.slide-leave-active{position:absolute;left:0;right:0;top:0}
.acts{display:flex;gap:10px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 18px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn.ghost{background:var(--panel);color:var(--ink);box-shadow:0 4px 0 var(--line2);border:1px solid var(--line)}
</style>
