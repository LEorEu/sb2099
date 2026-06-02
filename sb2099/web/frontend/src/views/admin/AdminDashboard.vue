<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { AdminStats } from '@/api/types'
import { useAdminStore } from '@/stores/admin'

const router = useRouter()
const store = useAdminStore()
const stats = ref<AdminStats | null>(null)
const loading = ref(true)

const todo = computed(() => store.summary.pending + store.summary.open_reports)

onMounted(async () => {
  await Promise.all([store.loadSummary(), api.admin.getStats().then(s => (stats.value = s))])
    .catch(() => {})
  loading.value = false
})

const overview = computed(() => {
  const s = stats.value
  return [
    { label: '烂梗库总数', value: store.summary.library_total },
    { label: '今日新投稿', value: s?.submit_24h ?? '—' },
    { label: '今日复制', value: s?.copy_total ?? '—' },
    { label: '回收站', value: s?.deleted_total ?? '—' },
  ]
})
</script>
<template>
  <div class="dash">
    <header class="hero">
      <h1>👋 梗站工作台</h1>
      <p class="sub">登录后先看这里——有没有需要你处理的，处理完就可以下班啦。</p>
    </header>

    <section class="todo">
      <h2 class="lbl">需要你处理</h2>

      <div v-if="loading" class="adm-empty">加载中…</div>

      <div v-else-if="todo === 0" class="clean">
        <span class="emoji">🎉</span>
        <div>
          <strong>都处理完啦</strong>
          <p>没有待审稿件、也没有待处理的举报，喝口水休息下。</p>
        </div>
      </div>

      <div v-else class="cards">
        <button
          class="todo-card" :class="{ urgent: store.summary.pending > 0, calm: store.summary.pending === 0 }"
          @click="router.push('/admin/pending')"
        >
          <span class="ic">📥</span>
          <span class="big">{{ store.summary.pending }}</span>
          <span class="name">待审稿件</span>
          <span class="hint">新投稿里需要你点头的 →</span>
        </button>

        <button
          class="todo-card" :class="{ urgent: store.summary.open_reports > 0, calm: store.summary.open_reports === 0 }"
          @click="router.push('/admin/reports')"
        >
          <span class="ic">🚩</span>
          <span class="big">{{ store.summary.open_reports }}</span>
          <span class="name">用户举报</span>
          <span class="hint">观众点了「不合适」的内容 →</span>
        </button>
      </div>
    </section>

    <section class="overview">
      <h2 class="lbl">梗站概况</h2>
      <div class="nums">
        <div v-for="o in overview" :key="o.label" class="num-card">
          <span class="v">{{ o.value }}</span>
          <span class="l">{{ o.label }}</span>
        </div>
      </div>
    </section>

    <section class="quick">
      <h2 class="lbl">常用入口</h2>
      <div class="links">
        <router-link class="ql" to="/admin/barrage"><span>😂</span> 管理全部烂梗</router-link>
        <router-link class="ql" to="/admin/tags"><span>🏷️</span> 标签 / 批准提议</router-link>
        <router-link class="ql" to="/admin/live-hot"><span>🔥</span> 直播热榜</router-link>
        <router-link class="ql" to="/admin/settings"><span>⚙️</span> 运行参数</router-link>
      </div>
    </section>
  </div>
</template>
<style scoped>
.dash { max-width: 860px; }
.hero h1 { font-size: 24px; font-weight: 900; }
.hero .sub { font-size: 14px; color: var(--muted); margin-top: 6px; }
.lbl { font-size: 13px; font-weight: 800; color: var(--subtle); letter-spacing: .04em; margin: 26px 0 12px; }

.clean { display: flex; gap: 14px; align-items: center; background: var(--green-soft); border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px; }
.clean .emoji { font-size: 30px; }
.clean strong { font-size: 16px; }
.clean p { font-size: 13px; color: var(--muted); margin-top: 3px; }

.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.todo-card {
  display: grid; grid-template-columns: auto 1fr; grid-template-rows: auto auto;
  column-gap: 14px; text-align: left; cursor: pointer;
  border: 1px solid var(--line); border-radius: 16px; padding: 20px 22px; background: var(--panel);
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
}
.todo-card:hover { transform: translateY(-2px); box-shadow: 0 10px 26px rgba(0,0,0,.10); }
.todo-card.urgent { border-color: var(--accent); background: var(--accent-soft); }
.todo-card .ic { grid-row: 1 / 3; font-size: 30px; align-self: center; }
.todo-card .big { font-size: 34px; font-weight: 900; line-height: 1; font-variant-numeric: tabular-nums; }
.todo-card.urgent .big { color: var(--accent); }
.todo-card .name { font-weight: 800; font-size: 15px; }
.todo-card .hint { grid-column: 2; font-size: 12px; color: var(--subtle); margin-top: 4px; }

.nums { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.num-card { display: flex; flex-direction: column; gap: 5px; background: var(--panel); border: 1px solid var(--line); border-radius: 13px; padding: 15px 18px; }
.num-card .v { font-size: 24px; font-weight: 900; font-variant-numeric: tabular-nums; }
.num-card .l { font-size: 12px; color: var(--subtle); }

.links { display: flex; flex-wrap: wrap; gap: 10px; }
.ql { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; padding: 10px 15px; border-radius: 11px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); }
.ql:hover { border-color: var(--accent); color: var(--accent); }

@media (max-width: 560px) { .cards { grid-template-columns: 1fr; } }
</style>
