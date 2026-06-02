<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useAdminStore } from '@/stores/admin'

const router = useRouter()
const store = useAdminStore()
const { toggle } = useTheme()

const NAV = [
  { to: '/admin/settings', label: '设置' },
  { to: '/admin/tags', label: '标签' },
  { to: '/admin/barrage', label: '全部烂梗' },
  { to: '/admin/pending', label: '待审' },
  { to: '/admin/reports', label: '反馈' },
  { to: '/admin/trash', label: '回收站' },
  { to: '/admin/live-hot', label: '直播热门' },
  { to: '/admin/stats', label: '统计' },
]

async function logout() {
  await store.logout()
  router.replace('/admin/login')
}
</script>
<template>
  <div class="adm-shell">
    <header class="adm-bar">
      <div class="inner">
        <span class="adm-brand">sb2099 <span class="tag">控制台</span></span>
        <nav class="adm-nav">
          <router-link v-for="n in NAV" :key="n.to" :to="n.to" active-class="on">{{ n.label }}</router-link>
        </nav>
        <div class="adm-tools">
          <button class="adm-btn ghost sm" title="切换深浅" @click="toggle()">🌓</button>
          <router-link class="adm-btn ghost sm" to="/">返回主站</router-link>
          <button class="adm-btn sm" @click="logout">登出</button>
        </div>
      </div>
    </header>
    <main class="adm-main">
      <router-view />
    </main>
  </div>
</template>
