<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { items, dismiss } = useToast()
</script>
<template>
  <div class="toast-host">
    <div v-for="t in items" :key="t.id" class="toast" :class="t.kind">
      <span>{{ t.text }}</span>
      <button v-if="t.action" class="ta" @click="t.action.run(); dismiss(t.id)">{{ t.action.label }}</button>
    </div>
  </div>
</template>
<style scoped>
.toast-host{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:99;display:flex;flex-direction:column;gap:8px}
.toast{background:var(--ink);color:var(--bg);padding:11px 16px;border-radius:11px;font-size:14px;font-weight:600;box-shadow:0 8px 24px rgba(0,0,0,.25);display:flex;align-items:center;gap:12px}
.toast.warn{background:var(--accent)}
.ta{background:rgba(255,255,255,.18);color:inherit;border:none;border-radius:7px;padding:5px 11px;font-weight:800;cursor:pointer}
</style>
