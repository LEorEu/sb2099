<script setup lang="ts">
// 移动端底部 Tab 导航：仅在窄屏显示（CSS 控制），桌面端隐藏。
</script>
<template>
  <nav class="bottomnav" aria-label="主导航">
    <router-link class="tab" to="/" exact-active-class="on">
      <span class="ic">🏠</span><span class="lb">首页</span>
    </router-link>
    <router-link class="tab" to="/barrage" active-class="on">
      <span class="ic">😆</span><span class="lb">全部烂梗</span>
    </router-link>
    <router-link class="tab" to="/live" active-class="on">
      <span class="ic">🔥</span><span class="lb">弹幕热榜</span>
    </router-link>
  </nav>
</template>
<style scoped>
.bottomnav{display:none}
@media (max-width:720px){
  .bottomnav{
    display:flex;position:fixed;left:0;right:0;bottom:0;z-index:30;
    background:var(--panel);border-top:1px solid var(--line);
    padding-bottom:env(safe-area-inset-bottom,0);
    box-shadow:0 -4px 16px rgba(0,0,0,.06);
  }
  .tab{
    flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
    padding:8px 0 7px;color:var(--muted);font-size:11px;font-weight:700;
    -webkit-tap-highlight-color:transparent;
  }
  .tab .ic{font-size:20px;line-height:1;font-variant-emoji:text}
  .tab.on{color:var(--accent)}
}
</style>
