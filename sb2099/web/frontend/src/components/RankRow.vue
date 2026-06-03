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
        <span class="hint">悬停看首个发送者</span>
      </div>
      <div class="hovercard" role="tooltip">
        <div class="hc-row">
          <span class="k">首发</span>
          <template v-if="item.first_sender">
            <img v-if="item.first_sender.avatar" class="av" :src="item.first_sender.avatar" alt="" referrerpolicy="no-referrer" />
            <span v-else class="av ph">{{ item.first_sender.nickname.slice(0, 1) }}</span>
            <span class="nick">{{ item.first_sender.nickname }}</span>
            <span class="tip">第一个刷这条的人</span>
          </template>
          <span v-else class="dim">没记录到（可能已超出留存）</span>
        </div>
      </div>
      <div v-if="picking" class="tagpick">
        <span v-for="t in tags.list" :key="t.value" class="tp" :class="{ on: chosen.has(t.value) }" @click="toggle(t.value)">{{ t.label }}</span>
        <button class="confirm" @click="confirmPromote">确认收录</button>
      </div>
    </div>
    <div class="grab">
      <span v-if="item.in_library" class="done">✓ 已在库</span>
      <button v-else data-test="promote" class="save" @click="picking = !picking">收录</button>
      <button class="copy" @click="onCopy">复制</button>
    </div>
  </div>
</template>
<style scoped>
.rank{display:flex;align-items:flex-start;gap:14px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.no{font-size:20px;font-weight:900;color:var(--subtle);width:30px;text-align:center;flex:0 0 auto}
.top1 .no{color:#ff5a1f}.top2 .no{color:#ff9a3d}.top3 .no{color:#ffc24d}
.body{flex:1;min-width:0;position:relative}
.c{font-size:16px;font-weight:600}
.m{margin-top:6px;display:flex;align-items:center;gap:12px;font-size:12px;color:var(--subtle)}
.hot{color:var(--accent);font-weight:800}
.m .hint{opacity:0;transition:opacity .15s}
.rank:hover .m .hint{opacity:.7}
.hovercard{position:absolute;top:calc(100% + 6px);left:0;z-index:25;min-width:230px;max-width:360px;
  background:var(--panel);border:1px solid var(--line2);border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.18);
  padding:11px 13px;opacity:0;visibility:hidden;transform:translateY(-4px);transition:opacity .16s,transform .16s;pointer-events:none}
.rank:hover .hovercard{opacity:1;visibility:visible;transform:translateY(0)}
.hc-row{display:flex;align-items:center;gap:8px;font-size:13px}
.hc-row .k{font-size:11px;font-weight:800;color:var(--subtle);flex:0 0 30px}
.hc-row .dim{color:var(--subtle)}
.hc-row .av{width:24px;height:24px;border-radius:50%;object-fit:cover;flex:0 0 auto}
.hc-row .av.ph{display:inline-flex;align-items:center;justify-content:center;background:var(--accent-soft);color:var(--accent-deep);font-size:11px;font-weight:800}
.hc-row .nick{font-weight:800}
.hc-row .tip{color:var(--subtle);font-size:11px}
.tagpick{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.tp{font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);cursor:pointer}
.tp.on{background:var(--accent);border-color:var(--accent);color:#fff}
.confirm{font-size:12px;font-weight:800;border:none;border-radius:8px;padding:6px 12px;background:var(--ink);color:var(--bg);cursor:pointer}
.grab{display:flex;gap:6px;flex:0 0 auto}
.grab button{border:none;cursor:pointer;font-weight:800;font-size:12px;border-radius:8px;padding:9px 12px}
.copy{background:var(--accent);color:#fff}
.save{background:var(--accent-soft);color:var(--accent)}
.done{font-size:11px;font-weight:800;color:var(--green);background:var(--green-soft);padding:7px 10px;border-radius:8px;align-self:center}
/* 移动端：无 hover，「首发」改为常驻内嵌 */
@media (max-width:720px){
  .rank{padding:13px 14px;gap:10px}
  .no{width:22px;font-size:18px}
  .m .hint{display:none}
  .hovercard{position:static;opacity:1;visibility:visible;transform:none;pointer-events:auto;
    min-width:0;max-width:none;box-shadow:none;background:var(--panel2);margin-top:10px}
}
</style>
