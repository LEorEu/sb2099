<script setup lang="ts">
defineProps<{ modelValue: 'day' | 'week' }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: 'day' | 'week'): void }>()
</script>
<template>
  <div class="wt">
    <a :class="{ on: modelValue === 'day' }" @click="emit('update:modelValue', 'day')">今日 Top 10</a>
    <a :class="{ on: modelValue === 'week' }" @click="emit('update:modelValue', 'week')">近 7 天 Top 50</a>
  </div>
</template>
<style scoped>
.wt{display:inline-flex;background:var(--panel);border:1px solid var(--line2);border-radius:11px;padding:4px;gap:4px}
.wt a{padding:8px 16px;border-radius:8px;font-size:14px;font-weight:700;color:var(--muted);cursor:pointer}
.wt a.on{background:var(--accent);color:#fff}
</style>
