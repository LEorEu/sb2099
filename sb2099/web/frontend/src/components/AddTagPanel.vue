<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Barrage } from '@/api/types'
import { api, ApiError } from '@/api/client'
import { useTagsStore } from '@/stores/tags'
import { useIdentityStore } from '@/stores/identity'
import { useToast } from '@/composables/useToast'

const props = defineProps<{ item: Barrage }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const tags = useTagsStore()
const ident = useIdentityStore()
const toast = useToast()

const busy = ref(false)
const newLabel = ref('')

const have = computed(() => new Set((props.item.tags || '').split(',').map(s => s.trim()).filter(Boolean)))
const candidates = computed(() => tags.list.filter(t => !have.value.has(t.value)))
const uid = () => ident.me?.uid ?? null

async function vote(value: string) {
  if (busy.value) return
  busy.value = true
  try {
    const r = await api.voteTag(props.item.id, value, uid())
    if (r.applied) toast.push('这条标签已生效 ✅', 'ok')
    else if (r.pending_approval) toast.push(`已投票，候选标签待管理员审核（${r.count}/${r.threshold}）`)
    else toast.push(`已投票 ${r.count}/${r.threshold} 票，到票自动生效`)
  } catch (e) {
    toast.push(e instanceof ApiError && e.status === 429 ? '投票太频繁，歇会儿再来' : '投票失败，稍后再试', 'warn')
  } finally { busy.value = false }
}

async function propose() {
  const l = newLabel.value.trim()
  if (!l) { toast.push('给标签起个名字', 'warn'); return }
  if (l.length > 32) { toast.push('标签名太长了（≤32 字）', 'warn'); return }
  busy.value = true
  try {
    const r = await api.proposeTag(props.item.id, l, uid())
    toast.push(`提议「${l}」已提交，达 ${r.threshold} 票后由管理员审核生效 🙌`, 'ok')
    newLabel.value = ''
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) toast.push('这个标签已存在，直接点上面的标签投票即可', 'warn')
    else if (e instanceof ApiError && e.status === 429) toast.push('操作太频繁，歇会儿再来', 'warn')
    else toast.push('提议失败，稍后再试', 'warn')
  } finally { busy.value = false }
}
</script>
<template>
  <div class="mask" @click.self="emit('close')">
    <div class="panel" role="dialog">
      <div class="ph">
        <h4>🏷️ 给这条补标签</h4>
        <button class="x" data-test="close-addtag" @click="emit('close')">✕</button>
      </div>
      <p class="quote">「{{ item.content.slice(0, 40) }}{{ item.content.length > 40 ? '…' : '' }}」</p>

      <div class="sec">
        <div class="lab">投个已有标签（够票自动生效）</div>
        <div v-if="candidates.length" class="chips">
          <button v-for="t in candidates" :key="t.value" class="chip" :disabled="busy"
                  :data-test="`vote-${t.value}`" @click="vote(t.value)">{{ t.label }}</button>
        </div>
        <div v-else class="hint">这条已经挂上所有可用标签啦。</div>
      </div>

      <div class="sec">
        <div class="lab">没有合适的？提议一个新标签</div>
        <div class="proprow">
          <input v-model="newLabel" class="lin" maxlength="32" placeholder="标签名" @keyup.enter="propose" />
          <button class="go" :disabled="busy" data-test="propose" @click="propose">提议</button>
        </div>
        <div class="hint">提议会先投你一票，达阈值后由管理员在后台审核通过。</div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.mask{position:fixed;inset:0;background:rgba(20,18,12,.4);z-index:50;display:flex;align-items:center;justify-content:center;padding:20px}
.panel{width:440px;max-width:94vw;background:var(--panel);border:1px solid var(--line2);border-radius:16px;box-shadow:0 24px 60px rgba(0,0,0,.28);padding:20px}
.ph{display:flex;align-items:center;justify-content:space-between}
.ph h4{font-size:16px;font-weight:900}
.x{font-size:18px;color:var(--subtle);background:none;border:none;cursor:pointer}
.quote{font-size:13px;color:var(--muted);margin:6px 0 14px;line-height:1.5}
.sec{border-top:1px solid var(--line);padding-top:13px;margin-top:13px}
.sec:first-of-type{border-top:none;padding-top:0;margin-top:0}
.lab{font-size:13px;font-weight:800;margin-bottom:9px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:13px;font-weight:700;padding:7px 13px;border-radius:999px;cursor:pointer;background:var(--panel2);border:1px solid var(--line);color:var(--ink)}
.chip:hover:not(:disabled){background:var(--accent);border-color:var(--accent);color:#fff}
.chip:disabled{opacity:.5;cursor:default}
.proprow{display:flex;gap:8px}
.lin{flex:1}
.proprow input{border:1px solid var(--line2);border-radius:9px;background:var(--panel2);padding:9px 11px;font:inherit;font-size:13px;color:var(--ink);outline:none}
.go{background:var(--accent);color:#fff;border:none;border-radius:9px;padding:0 16px;font-weight:800;font-size:13px;cursor:pointer}
.go:disabled{opacity:.5}
.hint{font-size:12px;color:var(--subtle);margin-top:8px;line-height:1.5}
</style>
