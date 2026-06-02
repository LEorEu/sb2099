<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'
defineProps<{ favCount: number }>()
const emit = defineEmits<{ (e: 'open-favorites'): void }>()
const { toggle } = useTheme()
</script>
<template>
  <header class="topbar">
    <div class="inner app-wrap">
      <router-link class="brand" to="/"><span class="blob"></span>sb2099</router-link>
      <nav class="nav">
        <router-link to="/" active-class="on" exact-active-class="on">首页</router-link>
        <router-link to="/barrage" active-class="on">全部烂梗</router-link>
        <router-link to="/live" active-class="on">热榜 🔥</router-link>
        <span class="more">更多 ▾</span>
      </nav>
      <div class="tools">
        <button class="ibtn" title="收藏夹" @click="emit('open-favorites')">⭐<span v-if="favCount" class="dot">{{ favCount }}</span></button>
        <button class="ibtn" title="切换深浅" @click="toggle()">🌓</button>
        <a class="ibtn script" href="/userscript">⚡ 装脚本</a>
      </div>
    </div>
  </header>
</template>
<style scoped>
.topbar{height:60px;border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:20}
.inner{height:100%;display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:900;font-size:20px;display:flex;align-items:center;gap:8px;flex:1}
.blob{width:21px;height:21px;border-radius:8px 8px 8px 2px;background:var(--accent);transform:rotate(-6deg);box-shadow:2px 2px 0 var(--ink)}
.nav{display:flex;gap:2px}
.nav a,.nav .more{padding:7px 13px;border-radius:9px;color:var(--muted);font-size:14px;font-weight:700}
.nav a.on{color:var(--accent);background:var(--accent-soft)}
.nav .more{color:var(--subtle);cursor:default}
.tools{display:flex;gap:7px;align-items:center;flex:1;justify-content:flex-end}
.ibtn{height:36px;min-width:36px;padding:0 9px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:flex;align-items:center;justify-content:center;font-size:15px;cursor:pointer;position:relative}
.ibtn .dot{position:absolute;top:-5px;right:-5px;background:var(--accent);color:#fff;font-size:10px;font-weight:800;border-radius:999px;padding:1px 5px}
.ibtn.script{gap:6px;font-weight:800;font-size:13px;background:var(--accent);color:#fff;border-color:var(--accent)}
</style>
