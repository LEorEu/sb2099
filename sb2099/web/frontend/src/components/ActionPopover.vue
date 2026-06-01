<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
const open = ref(false)
const root = ref<HTMLElement | null>(null)
function toggle() { open.value = !open.value }
function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
defineExpose({ close: () => (open.value = false) })
</script>
<template>
  <span ref="root" class="pop-root">
    <button class="more" @click.stop="toggle">⋯</button>
    <div v-if="open" class="pop" @click="open = false">
      <slot />
    </div>
  </span>
</template>
<style scoped>
.pop-root{position:relative;display:inline-flex}
.more{background:var(--accent-soft);color:var(--accent);border:none;border-radius:9px;padding:9px 11px;font-weight:800;font-size:13px;cursor:pointer}
.pop{position:absolute;top:46px;right:0;background:var(--panel);border:1px solid var(--line2);border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,.18);padding:6px;width:170px;z-index:30}
.pop :slotted(button){display:flex;align-items:center;gap:9px;width:100%;background:none;border:none;text-align:left;padding:9px 11px;border-radius:8px;font-size:13px;font-weight:700;color:var(--ink);cursor:pointer}
.pop :slotted(button:hover){background:var(--panel2)}
.pop :slotted(button.warn){color:var(--pink)}
</style>
