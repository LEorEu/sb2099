<script setup lang="ts">
import { ref } from 'vue'
import InstallGuide from '@/components/InstallGuide.vue'
const showGuide = ref(false)
</script>
<template>
  <div class="scriptbar">
    <div class="ic">⚡</div>
    <div><div class="t">在直播间里直接发梗</div><div class="s">装个浏览器插件，2099 房间右侧就能搜梗一键发</div></div>
    <button class="go" @click="showGuide = true">去装 →</button>
  </div>
  <InstallGuide v-model:open="showGuide" />
</template>
<style scoped>
.scriptbar{margin-top:18px;display:flex;align-items:center;gap:15px;background:var(--accent-soft);border:1px solid var(--line2);border-radius:16px;padding:16px 20px}
.ic{width:42px;height:42px;border-radius:11px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;flex:0 0 auto}
.t{font-weight:800;font-size:15px}
.s{color:var(--muted);font-size:13px;margin-top:2px}
.go{margin-left:auto;background:var(--accent);color:#fff;padding:10px 18px;border-radius:11px;font-weight:800;font-size:14px;white-space:nowrap;box-shadow:0 4px 0 var(--accent-deep);border:none;cursor:pointer}
</style>
