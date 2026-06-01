<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import { useTagsStore } from '@/stores/tags'
import MemeRow from '@/components/MemeRow.vue'

const tags = useTagsStore()
const q = ref('')
const sort = ref<'new' | 'hot'>('hot')
const selected = ref<Set<string>>(new Set())
const page = ref(1)
const list = ref<Barrage[]>([])
const total = ref(0)
const lastPage = ref(true)
const loading = ref(false)
const MAX_INLINE_TAGS = 8

async function load() {
  loading.value = true
  try {
    const tag = [...selected.value].join(',') || undefined
    const r = await api.searchBarrage({ q: q.value || undefined, tag, sort: sort.value, page: page.value, size: 20 })
    list.value = r.list; total.value = r.total; lastPage.value = r.last_page
  } finally { loading.value = false }
}
function doSearch() { page.value = 1; load() }
function toggleTag(v: string) { selected.value.has(v) ? selected.value.delete(v) : selected.value.add(v); doSearch() }
function setSort(s: 'new' | 'hot') { sort.value = s; doSearch() }
function go(d: number) { page.value += d; load() }

onMounted(async () => { await tags.load(); await load() })
</script>
<template>
  <section class="app-wrap page">
    <div class="listhead"><h2>全部烂梗</h2><span class="cnt">共 {{ total }} 条</span></div>

    <div class="search">
      <span class="ic">🔍</span>
      <input v-model="q" placeholder="搜个梗… 比如「蜜雪」「厕所」「这TM是歌」" @keyup.enter="doSearch" />
      <button class="go" @click="doSearch">搜梗</button>
    </div>

    <div class="filters">
      <span class="fchip" :class="{ on: selected.size === 0 }" @click="selected.clear(); doSearch()">全部</span>
      <span v-for="t in tags.list.slice(0, MAX_INLINE_TAGS)" :key="t.value"
            class="fchip" :class="{ on: selected.has(t.value) }" @click="toggleTag(t.value)">{{ t.label }}</span>
      <span class="fspace"></span>
      <span class="fsort">
        <a :class="{ on: sort === 'hot' }" @click="setSort('hot')">🔥 最热</a> ·
        <a :class="{ on: sort === 'new' }" @click="setSort('new')">最新</a>
      </span>
    </div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="list.length === 0" class="empty">没搜到，换个词试试 🤔</div>
    <div v-else class="memelist">
      <MemeRow v-for="b in list" :key="b.id" :item="b" />
    </div>

    <nav v-if="list.length" class="pager">
      <button :disabled="page <= 1" @click="go(-1)">上一页</button>
      <span>第 {{ page }} 页</span>
      <button :disabled="lastPage" @click="go(1)">下一页</button>
    </nav>
  </section>
</template>
<style scoped>
.page{padding:22px 20px 60px}
.listhead{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.listhead h2{font-size:22px;font-weight:900}
.cnt{font-size:13px;color:var(--subtle);font-weight:600}
.search{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line2);border-radius:13px;padding:5px 5px 5px 16px;margin-bottom:14px}
.search .ic{color:var(--subtle)}
.search input{flex:1;border:none;background:none;outline:none;font-size:15px;padding:11px 0;color:var(--ink)}
.search .go{background:var(--accent);color:#fff;border:none;border-radius:9px;padding:10px 18px;font-weight:800;cursor:pointer}
.filters{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.fchip{padding:6px 13px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--muted);font-size:13px;font-weight:700;cursor:pointer}
.fchip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.fspace{flex:1}
.fsort{font-size:13px;color:var(--subtle)}
.fsort a{cursor:pointer}
.fsort a.on{color:var(--ink);font-weight:800}
.memelist{display:flex;flex-direction:column;gap:10px}
.empty{padding:40px;text-align:center;color:var(--subtle)}
.pager{display:flex;align-items:center;justify-content:center;gap:16px;margin-top:20px}
.pager button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:9px;padding:8px 16px;font-weight:700;cursor:pointer}
.pager button:disabled{opacity:.4;cursor:not-allowed}
</style>
