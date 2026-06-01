<script setup lang="ts">
import { ref } from 'vue'
import type { LiveItem } from '@/api/types'
import { useCopy } from '@/composables/useCopy'
import { useTagsStore } from '@/stores/tags'
import { useToast } from '@/composables/useToast'
import { api, ApiError } from '@/api/client'

const props = defineProps<{ item: LiveItem; rank: number }>()
const emit = defineEmits<{ (e: 'promoted'): void }>()
const { copy } = useCopy()
const tags = useTagsStore()
const toast = useToast()
const picking = ref(false)
const chosen = ref<Set<string>>(new Set())

function onCopy() { copy(props.item.content_sample, 'live_hot', props.item.id) }
function toggle(v: string) { chosen.value.has(v) ? chosen.value.delete(v) : chosen.value.add(v) }
async function confirmPromote() {
  if (chosen.value.size === 0) { toast.push('给它选个标签先', 'warn'); return }
  try {
    await api.promote(props.item.id, [...chosen.value], null)
    toast.push('收进梗库啦 ✅'); picking.value = false; emit('promoted')
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) toast.push('这条已经在库里了', 'warn')
    else toast.push('收录失败，稍后再试', 'warn')
  }
}
</script>
<template>
  <div class="rank" :class="`top${rank <= 3 ? rank : 0}`">
    <div class="no">{{ rank }}</div>
    <div class="body">
      <div class="c">{{ item.content_sample }}</div>
      <div class="m">
        <span class="hot">🔥 {{ item.send_cnt }} 次发送</span>
        <span>👥 {{ item.unique_senders }} 人</span>
      </div>
      <div v-if="picking" class="tagpick">
        <span v-for="t in tags.list" :key="t.value" class="tp" :class="{ on: chosen.has(t.value) }" @click="toggle(t.value)">{{ t.label }}</span>
        <button class="confirm" @click="confirmPromote">确认收录</button>
      </div>
    </div>
    <div class="grab">
      <span v-if="item.in_library" class="done">✓ 已在库</span>
      <button v-else data-test="promote" class="save" @click="picking = !picking">收进梗库</button>
      <button class="copy" @click="onCopy">复制</button>
    </div>
  </div>
</template>
<style scoped>
.rank{display:flex;align-items:flex-start;gap:14px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.no{font-size:20px;font-weight:900;color:var(--subtle);width:30px;text-align:center;flex:0 0 auto}
.top1 .no{color:#ff5a1f}.top2 .no{color:#ff9a3d}.top3 .no{color:#ffc24d}
.body{flex:1;min-width:0}
.c{font-size:16px;font-weight:600}
.m{margin-top:6px;display:flex;align-items:center;gap:12px;font-size:12px;color:var(--subtle)}
.hot{color:var(--accent);font-weight:800}
.tagpick{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.tp{font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);cursor:pointer}
.tp.on{background:var(--accent);border-color:var(--accent);color:#fff}
.confirm{font-size:12px;font-weight:800;border:none;border-radius:8px;padding:6px 12px;background:var(--ink);color:var(--bg);cursor:pointer}
.grab{display:flex;gap:6px;flex:0 0 auto}
.grab button{border:none;cursor:pointer;font-weight:800;font-size:12px;border-radius:8px;padding:9px 12px}
.copy{background:var(--accent);color:#fff}
.save{background:var(--accent-soft);color:var(--accent)}
.done{font-size:11px;font-weight:800;color:var(--green);background:var(--green-soft);padding:7px 10px;border-radius:8px;align-self:center}
</style>
