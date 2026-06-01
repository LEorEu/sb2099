<script setup lang="ts">
import { computed } from 'vue'
import type { Barrage } from '@/api/types'
import TagChips from './TagChips.vue'
import ActionPopover from './ActionPopover.vue'
import { useCopy } from '@/composables/useCopy'
import { useFavoritesStore } from '@/stores/favorites'
import { useToast } from '@/composables/useToast'
import { api } from '@/api/client'

const props = defineProps<{ item: Barrage }>()
const { copy } = useCopy()
const favs = useFavoritesStore()
const toast = useToast()
const faved = computed(() => favs.has(props.item.id))
const date = computed(() => (props.item.submit_time || '').slice(5, 10))

function onCopy() { copy(props.item.content, 'barrage', props.item.id) }
function onFav() {
  if (faved.value) toast.push('已在收藏里了')
  else { favs.add(props.item.id); toast.push('收进默认收藏夹 ⭐') }
}
function onReport() {
  api.report(props.item.id).then(() => toast.push('收到，谢谢反馈 🙏'))
    .catch(() => toast.push('举报失败，稍后再试', 'warn'))
}
function onAddTag() { toast.push('补标签功能马上来（投票/提议）') }
</script>
<template>
  <div class="meme">
    <div class="main">
      <div class="c">{{ item.content }}</div>
      <div class="meta">
        <TagChips :csv="item.tags" />
        <span class="copies">🔥 被复制 {{ item.cnt }} 次<template v-if="date"> · {{ date }} 投</template></span>
        <span v-if="item.submitter" class="sub">· {{ item.submitter.nickname }}</span>
      </div>
    </div>
    <div class="acts">
      <button class="copy" data-test="copy" @click="onCopy">复制</button>
      <button class="ic2" data-test="fav" :class="{ on: faved }" @click="onFav">{{ faved ? '♥' : '♡' }}</button>
      <ActionPopover>
        <button data-test="addtag" @click="onAddTag">🏷️ 补个标签</button>
        <button class="warn" data-test="report" @click="onReport">🚩 这条不合适</button>
      </ActionPopover>
    </div>
  </div>
</template>
<style scoped>
.meme{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 16px;display:flex;align-items:center;gap:16px}
.main{flex:1;min-width:0}
.c{font-size:16px;font-weight:600;line-height:1.5}
.meta{margin-top:9px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.copies{font-size:12px;color:var(--subtle);margin-left:2px}
.sub{font-size:12px;color:var(--subtle)}
.acts{display:flex;align-items:center;gap:6px;flex:0 0 auto}
.copy{background:var(--accent);color:#fff;border:none;border-radius:9px;padding:9px 14px;font-weight:800;font-size:13px;cursor:pointer}
.ic2{background:var(--panel2);color:var(--muted);border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:14px;cursor:pointer}
.ic2.on{color:var(--accent);border-color:var(--accent)}
</style>
