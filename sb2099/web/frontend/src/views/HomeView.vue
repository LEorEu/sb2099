<script setup lang="ts">
import { ref } from 'vue'
import SubmitCard from '@/components/SubmitCard.vue'
import LatestList from '@/components/LatestList.vue'
import DailyMemeCard from '@/components/DailyMemeCard.vue'
import ScriptBanner from '@/components/ScriptBanner.vue'

const latest = ref<InstanceType<typeof LatestList> | null>(null)
</script>
<template>
  <section class="app-wrap home">
    <div class="hero">
      <a class="kicker" href="https://www.douyu.com/2099" target="_blank" rel="noopener">斗鱼 2099 · 一团肉松子直播间 ↗</a>
      <h1><span class="mark">团松子</span>烂梗收集站</h1>
      <p class="sub">家人们听到的好笑弹幕都丢这儿 · 回直播间 <b>搜一下就能一键发</b></p>
    </div>
    <div class="cols">
      <SubmitCard @submitted="latest?.load()" />
      <div class="side">
        <DailyMemeCard />
        <ScriptBanner />
      </div>
    </div>
    <LatestList ref="latest" class="latest" />
  </section>
</template>
<style scoped>
.home{padding:40px 20px 60px}
.hero{text-align:center;margin-bottom:30px}
.kicker{display:inline-block;font-size:13px;font-weight:800;color:var(--accent);background:var(--accent-soft);padding:5px 12px;border-radius:999px;text-decoration:none;transition:background .15s}
.kicker:hover{background:var(--accent);color:#fff}
.hero h1{font-size:40px;font-weight:900;margin-top:15px;line-height:1.12}
.mark{background:linear-gradient(transparent 60%,var(--accent-soft) 60%);padding:0 6px}
.sub{color:var(--muted);font-size:15px;margin-top:13px}
.sub b{color:var(--ink)}
.cols{display:grid;grid-template-columns:1.25fr .9fr;gap:18px;align-items:start}
.latest{margin-top:18px}
@media (max-width:820px){.cols{grid-template-columns:1fr}}
</style>
