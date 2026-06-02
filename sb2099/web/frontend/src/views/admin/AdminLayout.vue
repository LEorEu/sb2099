<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useAdminStore } from '@/stores/admin'

const route = useRoute()
const router = useRouter()
const store = useAdminStore()
const { toggle } = useTheme()

type BadgeKey = 'pending' | 'open_reports'
interface NavItem { to: string; icon: string; label: string; exact?: boolean; badge?: BadgeKey }

const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: '日常处理',
    items: [
      { to: '/admin', icon: '🏠', label: '工作台', exact: true },
      { to: '/admin/pending', icon: '📥', label: '待审稿件', badge: 'pending' },
      { to: '/admin/reports', icon: '🚩', label: '举报处理', badge: 'open_reports' },
    ],
  },
  {
    title: '梗库管理',
    items: [
      { to: '/admin/barrage', icon: '😂', label: '全部烂梗' },
      { to: '/admin/tags', icon: '🏷️', label: '标签管理' },
      { to: '/admin/trash', icon: '🗑️', label: '回收站' },
    ],
  },
  {
    title: '运营与设置',
    items: [
      { to: '/admin/live-hot', icon: '🔥', label: '直播热榜' },
      { to: '/admin/stats', icon: '📊', label: '数据概览' },
      { to: '/admin/settings', icon: '⚙️', label: '运行参数' },
    ],
  },
]

const badge = (key?: BadgeKey) => (key ? store.summary[key] || 0 : 0)

const mobileOpen = ref(false)
const isActive = (item: { to: string; exact?: boolean }) =>
  item.exact ? route.path === item.to : route.path.startsWith(item.to)

const title = computed(() => GROUPS.flatMap(g => g.items).find(isActive)?.label || '后台')

onMounted(() => store.loadSummary())
watch(() => route.fullPath, () => { store.loadSummary(); mobileOpen.value = false })

async function logout() {
  await store.logout()
  router.replace('/admin/login')
}
</script>
<template>
  <div class="adm-shell">
    <!-- 移动端顶栏 -->
    <header class="mtop">
      <button class="burger" @click="mobileOpen = !mobileOpen" aria-label="菜单">☰</button>
      <span class="adm-brand">sb2099 <span class="tag">控制台</span></span>
      <span class="mtitle">{{ title }}</span>
    </header>

    <div class="body">
      <aside class="side" :class="{ open: mobileOpen }">
        <div class="brand-row">
          <span class="adm-brand">sb2099 <span class="tag">控制台</span></span>
        </div>

        <nav class="nav">
          <div v-for="g in GROUPS" :key="g.title" class="group">
            <p class="ghead">{{ g.title }}</p>
            <router-link
              v-for="it in g.items" :key="it.to" :to="it.to"
              class="item" :class="{ on: isActive(it) }"
            >
              <span class="ic">{{ it.icon }}</span>
              <span class="lab">{{ it.label }}</span>
              <span v-if="badge(it.badge) > 0" class="badge">{{ badge(it.badge) }}</span>
            </router-link>
          </div>
        </nav>

        <div class="foot">
          <button class="adm-btn ghost sm" title="切换深浅" @click="toggle()">🌓 主题</button>
          <router-link class="adm-btn ghost sm" to="/">↩ 主站</router-link>
          <button class="adm-btn sm" @click="logout">登出</button>
        </div>
      </aside>

      <div v-if="mobileOpen" class="scrim" @click="mobileOpen = false" />

      <main class="adm-main">
        <router-view />
      </main>
    </div>
  </div>
</template>
<style scoped>
.adm-shell { min-height: 100vh; background: var(--bg); }
.body { display: flex; align-items: stretch; }

/* 侧栏 */
.side {
  width: 218px; flex: 0 0 218px; min-height: 100vh; position: sticky; top: 0;
  background: var(--panel); border-right: 1px solid var(--line);
  display: flex; flex-direction: column;
}
.brand-row { padding: 18px 18px 10px; }
.adm-brand { font-weight: 900; font-size: 17px; display: inline-flex; align-items: center; gap: 8px; }
.adm-brand .tag { font-size: 11px; font-weight: 800; color: var(--accent); background: var(--accent-soft); border-radius: 6px; padding: 2px 7px; }

.nav { flex: 1; overflow-y: auto; padding: 6px 10px; }
.group { margin-bottom: 14px; }
.ghead { font-size: 11px; font-weight: 800; color: var(--subtle); letter-spacing: .06em; padding: 6px 10px; }
.item {
  display: flex; align-items: center; gap: 10px; padding: 9px 11px; border-radius: 10px;
  color: var(--muted); font-size: 14px; font-weight: 700; margin-bottom: 2px;
}
.item:hover { background: var(--panel2); color: var(--ink); }
.item.on { background: var(--accent-soft); color: var(--accent); }
.item .ic { width: 20px; text-align: center; font-size: 15px; }
.item .lab { flex: 1; }
.item .badge {
  min-width: 20px; text-align: center; font-size: 11px; font-weight: 800; color: #fff;
  background: var(--accent); border-radius: 999px; padding: 1px 7px;
}

.foot { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px; border-top: 1px solid var(--line); }

.adm-main { flex: 1; min-width: 0; max-width: 1040px; padding: 26px 26px 64px; }

/* 移动端顶栏（默认隐藏） */
.mtop { display: none; }
.scrim { display: none; }

@media (max-width: 820px) {
  .mtop {
    display: flex; align-items: center; gap: 12px; height: 52px; padding: 0 14px;
    border-bottom: 1px solid var(--line); background: var(--panel); position: sticky; top: 0; z-index: 40;
  }
  .burger { font-size: 20px; background: none; border: none; cursor: pointer; color: var(--ink); }
  .mtitle { font-size: 14px; font-weight: 800; color: var(--muted); }
  .side {
    position: fixed; top: 0; left: 0; height: 100vh; z-index: 50;
    transform: translateX(-100%); transition: transform .2s ease;
  }
  .side.open { transform: translateX(0); box-shadow: 0 0 40px rgba(0,0,0,.3); }
  .scrim { display: block; position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 45; }
  .adm-main { padding: 18px 16px 60px; }
}
</style>
