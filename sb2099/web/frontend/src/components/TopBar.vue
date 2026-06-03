<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/composables/useTheme'
import { usePresence } from '@/composables/usePresence'
import InstallGuide from '@/components/InstallGuide.vue'
defineProps<{ favCount: number }>()
const emit = defineEmits<{ (e: 'open-favorites'): void }>()
const { toggle } = useTheme()
const { online } = usePresence()
const REPO = 'https://github.com/LEorEu/sb2099'
const FEEDBACK = 'https://v.wjx.cn/vm/rRSgU2a.aspx#'
const showGuide = ref(false)
</script>
<template>
  <header class="topbar">
    <div class="inner app-wrap">
      <div class="left">
        <router-link class="brand" to="/"><img class="logo" src="/logo.jpg" alt="" />SB2099</router-link>
        <span v-if="online > 0" class="online" title="近 1 分钟在线人数（心跳统计）"><span class="dotlive"></span>{{ online }} 在线</span>
      </div>
      <nav class="nav">
        <router-link to="/" active-class="on" exact-active-class="on">首页</router-link>
        <router-link to="/barrage" active-class="on">全部烂梗</router-link>
        <router-link to="/live" active-class="on">弹幕热榜</router-link>
        <!-- <span class="more">更多 ▾</span> -->
      </nav>
      <div class="tools">
        <button class="ibtn" title="收藏夹" @click="emit('open-favorites')">⭐<span v-if="favCount" class="dot">{{ favCount }}</span></button>
        <button class="ibtn" title="切换深浅" @click="toggle()">🌓</button>
        <a class="ibtn gh" :href="REPO" target="_blank" rel="noopener" title="GitHub 项目">
          <svg viewBox="0 0 16 16" width="17" height="17" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
        </a>
        <a class="ibtn fb" :href="FEEDBACK" target="_blank" rel="noopener" title="意见反馈">💬</a>
        <button class="ibtn script" @click="showGuide = true">⚡ 装脚本</button>
      </div>
    </div>
  </header>
  <InstallGuide v-model:open="showGuide" />
</template>
<style scoped>
.topbar{height:60px;border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:20}
.inner{height:100%;display:flex;align-items:center;justify-content:space-between}
.left{flex:1;display:flex;align-items:center;gap:11px;min-width:0}
.brand{font-weight:900;font-size:20px;display:flex;align-items:center;gap:9px}
.logo{width:30px;height:30px;border-radius:9px;object-fit:cover;box-shadow:0 2px 6px rgba(0,0,0,.18)}
.nav{display:flex;gap:2px}
.nav a,.nav .more{padding:7px 13px;border-radius:9px;color:var(--muted);font-size:14px;font-weight:700}
.nav a.on{color:var(--accent);background:var(--accent-soft)}
.nav .more{color:var(--subtle);cursor:default}
.tools{display:flex;gap:7px;align-items:center;flex:1;justify-content:flex-end}
.online{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:var(--muted);background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:6px 11px;white-space:nowrap}
.dotlive{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(31,170,107,.5)}70%{box-shadow:0 0 0 5px rgba(31,170,107,0)}100%{box-shadow:0 0 0 0 rgba(31,170,107,0)}}
@media (max-width:640px){.online{display:none}}
/* 移动端：中间导航移到底部 Tab 栏，顶栏只留 Logo + 工具 */
@media (max-width:720px){.nav{display:none}.left{flex:0 1 auto}.tools{gap:6px}}
@media (max-width:430px){.tools .ibtn.gh,.tools .ibtn.fb{display:none}.ibtn.script{white-space:nowrap}}
.ibtn{height:36px;min-width:36px;padding:0 9px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:flex;align-items:center;justify-content:center;font-size:15px;cursor:pointer;position:relative}
.ibtn .dot{position:absolute;top:-5px;right:-5px;background:var(--accent);color:#fff;font-size:10px;font-weight:800;border-radius:999px;padding:1px 5px}
.ibtn.script{gap:6px;font-weight:800;font-size:13px;background:var(--accent);color:#fff;border-color:var(--accent)}
</style>
