<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { ApiError } from '@/api/client'

const route = useRoute()
const router = useRouter()
const store = useAdminStore()

const token = ref('')
const err = ref('')
const busy = ref(false)

async function submit() {
  if (!token.value || busy.value) return
  busy.value = true
  err.value = ''
  try {
    await store.login(token.value)
    const next = (route.query.next as string) || '/admin/settings'
    router.replace(next.startsWith('/admin') ? next : '/admin/settings')
  } catch (e) {
    err.value = e instanceof ApiError ? e.message : '登录失败'
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="login-wrap">
    <form class="adm-card box" @submit.prevent="submit">
      <h1>sb2099 <span class="tag">控制台</span></h1>
      <p class="sub">输入管理 Token 登录后台</p>
      <input
        class="adm-input" type="password" v-model="token" placeholder="SB2099_ADMIN_TOKEN"
        autofocus autocomplete="current-password"
      />
      <p v-if="err" class="adm-flash err">{{ err }}</p>
      <button class="adm-btn primary block" type="submit" :disabled="busy || !token">
        {{ busy ? '登录中…' : '登录' }}
      </button>
      <router-link class="back" to="/">← 返回主站</router-link>
    </form>
  </div>
</template>
<style scoped>
.login-wrap { min-height: 100vh; display: grid; place-items: center; background: var(--bg); padding: 20px; }
.box { width: 100%; max-width: 360px; }
.box h1 { font-size: 22px; font-weight: 900; display: flex; align-items: center; gap: 8px; }
.box .tag { font-size: 12px; font-weight: 800; color: var(--accent); background: var(--accent-soft); border-radius: 6px; padding: 2px 8px; }
.box .sub { font-size: 13px; color: var(--subtle); margin: 6px 0 16px; }
.box .adm-input { margin-bottom: 14px; }
.adm-btn.block { width: 100%; justify-content: center; height: 38px; }
.back { display: block; text-align: center; margin-top: 16px; font-size: 13px; color: var(--subtle); }
</style>
