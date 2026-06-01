<script setup lang="ts">
import { computed } from 'vue'
import { useTagsStore } from '@/stores/tags'

const props = defineProps<{ csv: string | null }>()
const tags = useTagsStore()
const values = computed(() => (props.csv || '').split(',').map(v => v.trim()).filter(Boolean))
const PALETTE = 6
function hue(v: string): number {
  let h = 0
  for (const ch of v) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return h % PALETTE
}
</script>
<template>
  <span class="tags">
    <span v-for="v in values" :key="v" class="tagchip" :data-c="hue(v)">{{ tags.labelOf(v) }}</span>
  </span>
</template>
<style scoped>
.tags{display:inline-flex;flex-wrap:wrap;gap:6px}
.tagchip{font-size:11px;font-weight:800;padding:2px 8px;border-radius:6px;white-space:nowrap}
.tagchip[data-c="0"]{background:var(--violet-soft);color:var(--violet)}
.tagchip[data-c="1"]{background:var(--green-soft);color:var(--green)}
.tagchip[data-c="2"]{background:var(--pink-soft);color:var(--pink)}
.tagchip[data-c="3"]{background:var(--accent-soft);color:var(--accent-deep)}
.tagchip[data-c="4"]{background:var(--violet-soft);color:var(--violet)}
.tagchip[data-c="5"]{background:var(--green-soft);color:var(--green)}
</style>
