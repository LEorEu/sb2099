<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { LiveItem } from '@/api/types'
import { useTagsStore } from '@/stores/tags'
import WindowToggle from '@/components/WindowToggle.vue'
import RankRow from '@/components/RankRow.vue'

const tags = useTagsStore()
const window = ref<'day' | 'week'>('day')
const items = ref<LiveItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try { items.value = await api.getLive(window.value) } finally { loading.value = false }
}
watch(window, load)
onMounted(async () => { await tags.load(); await load() })
</script>
<template>
  <section class="app-wrap page">
    <div class="head"><h2>弹幕热榜 🔥</h2><span class="cnt">直播中正在刷的弹幕，实时统计</span></div>
    <WindowToggle v-model="window" />
    <p class="hint">看到有想要+1的，点「收录」就进仓库了 · 已在库的标 ✓</p>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">这会儿还没人刷，待会再来 👀</div>
    <div v-else class="ranklist">
      <RankRow v-for="(it, i) in items" :key="it.id ?? i" :item="it" :rank="i + 1" @promoted="load" />
    </div>
  </section>
</template>
<style scoped>
.page{padding:22px 20px 60px}
.head{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.head h2{font-size:22px;font-weight:900}
.cnt{font-size:13px;color:var(--subtle)}
.hint{font-size:12px;color:var(--subtle);margin:14px 0 18px}
.ranklist{display:flex;flex-direction:column;gap:10px}
.empty{padding:40px;text-align:center;color:var(--subtle)}
</style>
