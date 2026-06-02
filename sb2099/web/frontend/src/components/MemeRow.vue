<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Barrage } from '@/api/types'
import TagChips from './TagChips.vue'
import ActionPopover from './ActionPopover.vue'
import AddTagPanel from './AddTagPanel.vue'
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
const hasTags = computed(() => !!(props.item.tags || '').trim())
const addTagOpen = ref(false)

function onCopy() { copy(props.item.content, 'barrage', props.item.id) }
function onFav() {
  if (faved.value) { favs.removeEverywhere(props.item.id); toast.push('已移出收藏夹') }
  else { favs.add(props.item.id); toast.push('收进默认收藏夹 ⭐') }
}
function onReport() {
  if (!window.confirm('确定把这条标记为「不合适」吗？\n会提交给管理员审核，请勿滥用。')) return
  api.report(props.item.id).then(() => toast.push('收到，谢谢反馈 🙏'))
    .catch(() => toast.push('举报失败，稍后再试', 'warn'))
}
</script>
<template>
  <div class="meme">
    <div class="main" data-test="row-copy" title="点这条直接复制" @click="onCopy">
      <div class="c">{{ item.content }}</div>
      <div class="meta">
        <span class="copies">🔥 被复制 {{ item.cnt }} 次</span>
        <span class="hint">点这条复制 · 悬停看标签/投稿人</span>
      </div>
      <div class="hovercard" role="tooltip">
        <div class="hc-row">
          <span class="k">标签</span>
          <TagChips v-if="hasTags" :csv="item.tags" />
          <span v-else class="dim">暂无标签</span>
        </div>
        <div class="hc-row">
          <span class="k">投稿人</span>
          <template v-if="item.submitter">
            <img v-if="item.submitter.avatar" class="av" :src="item.submitter.avatar" alt="" referrerpolicy="no-referrer" />
            <span v-else class="av ph">{{ item.submitter.nickname.slice(0, 1) }}</span>
            <span class="nick">{{ item.submitter.nickname }}</span>
          </template>
          <span v-else class="dim">匿名</span>
          <span v-if="date" class="when">· {{ date }} 投</span>
        </div>
      </div>
    </div>
    <div class="acts">
      <button class="copy" data-test="copy" @click="onCopy">复制</button>
      <button class="ic2" data-test="fav" :class="{ on: faved }" :title="faved ? '点击取消收藏' : '收藏'" @click="onFav">{{ faved ? '♥' : '♡' }}</button>
      <ActionPopover>
        <button data-test="addtag" @click="addTagOpen = true">🏷️ 补个标签</button>
        <button class="warn" data-test="report" @click="onReport">🚩 举报</button>
      </ActionPopover>
    </div>
    <AddTagPanel v-if="addTagOpen" :item="item" @close="addTagOpen = false" />
  </div>
</template>
<style scoped>
.meme{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 16px;display:flex;align-items:center;gap:16px}
.main{flex:1;min-width:0;position:relative;cursor:pointer}
.c{font-size:16px;font-weight:600;line-height:1.5}
.meta{margin-top:7px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.copies{font-size:12px;color:var(--subtle)}
.meta .hint{font-size:11px;color:var(--subtle);opacity:0;transition:opacity .15s}
.meme:hover .meta .hint{opacity:.7}
/* hover 弹层：标签 + 投稿人 */
.hovercard{position:absolute;top:calc(100% + 6px);left:0;z-index:25;min-width:230px;max-width:380px;
  background:var(--panel);border:1px solid var(--line2);border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.18);
  padding:11px 13px;opacity:0;visibility:hidden;transform:translateY(-4px);transition:opacity .16s,transform .16s;pointer-events:none}
.meme:hover .hovercard{opacity:1;visibility:visible;transform:translateY(0)}
.hc-row{display:flex;align-items:center;gap:8px;font-size:13px}
.hc-row + .hc-row{margin-top:9px}
.hc-row .k{font-size:11px;font-weight:800;color:var(--subtle);flex:0 0 36px}
.hc-row .dim{color:var(--subtle)}
.hc-row .av{width:22px;height:22px;border-radius:50%;object-fit:cover;flex:0 0 auto}
.hc-row .av.ph{display:inline-flex;align-items:center;justify-content:center;background:var(--accent-soft);color:var(--accent-deep);font-size:11px;font-weight:800}
.hc-row .nick{font-weight:700}
.hc-row .when{color:var(--subtle);font-size:12px}
.acts{display:flex;align-items:center;gap:6px;flex:0 0 auto}
.copy{background:var(--accent);color:#fff;border:none;border-radius:9px;padding:9px 14px;font-weight:800;font-size:13px;cursor:pointer}
.ic2{background:var(--panel2);color:var(--muted);border:1px solid var(--line);border-radius:9px;width:38px;height:38px;padding:0;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;font-size:16px;line-height:1;cursor:pointer;font-variant-emoji:text}
.ic2.on{color:var(--accent);border-color:var(--accent)}
</style>
