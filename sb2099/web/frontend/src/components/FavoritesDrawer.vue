<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Barrage } from '@/api/types'
import { api } from '@/api/client'
import { useFavoritesStore } from '@/stores/favorites'
import { useToast } from '@/composables/useToast'
import { useCopy } from '@/composables/useCopy'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()
const favs = useFavoritesStore()
const toast = useToast()
const { copy } = useCopy()
const active = ref<string>('默认')
const rows = ref<Barrage[]>([])
const loading = ref(false)

const ids = computed(() => favs.groups[active.value] || [])
const others = computed(() => favs.order.filter(g => g !== active.value))
const staleCount = computed(() => ids.value.length - rows.value.length)

async function loadActive() {
  if (!props.open) return
  if (!favs.order.includes(active.value)) active.value = favs.order[0] || '默认'
  const list = favs.groups[active.value] || []
  if (list.length === 0) { rows.value = []; return }
  loading.value = true
  try {
    rows.value = await api.getBarragesByIds([...list]).catch(() => [])
  } finally { loading.value = false }
}
watch(() => [props.open, active.value], loadActive, { immediate: true })

function close() { emit('update:open', false) }
function pickGroup(g: string) { active.value = g }
function moveTo(id: number, to: string) {
  favs.move(id, active.value, to)
  rows.value = rows.value.filter(r => r.id !== id)
  toast.push(`已移到「${to}」`)
}
function removeOne(id: number) {
  favs.remove(id, active.value)
  rows.value = rows.value.filter(r => r.id !== id)
  toast.push('已移除')
}
function copyOne(b: Barrage) { copy(b.content, 'barrage', b.id) }

function newGroup() {
  const name = prompt('新建收藏夹分组名：')?.trim()
  if (name) { favs.addGroup(name); active.value = name }
}
function doExport() {
  navigator.clipboard.writeText(favs.exportJson())
    .then(() => toast.push('收藏配置已复制，粘到别处即可导入'))
    .catch(() => toast.push('复制失败', 'warn'))
}
function doImport() {
  const raw = prompt('粘贴收藏 JSON：')
  if (raw == null) return
  const ok = favs.importJson(raw)
  toast.push(ok ? '导入成功 ✅' : '格式不对，导入失败', ok ? 'ok' : 'warn')
  if (ok) loadActive()
}
</script>
<template>
  <div v-if="open">
    <div class="backdrop" @click="close"></div>
    <aside class="drawer">
      <div class="dh"><h4>⭐ 我的收藏夹</h4><button class="x" data-test="close" @click="close">✕</button></div>
      <p class="dnote">只存在你这台浏览器里，跟油猴脚本互通；换设备用下面导出/导入搬。</p>

      <div class="tabs">
        <button v-for="g in favs.order" :key="g" class="tab" :class="{ on: active === g }" @click="pickGroup(g)">
          {{ g }}<span class="n">{{ (favs.groups[g] || []).length }}</span>
        </button>
        <button class="tab add" @click="newGroup">＋</button>
      </div>

      <div class="items">
        <div v-if="loading" class="ph">加载中…</div>
        <div v-else-if="rows.length === 0" class="ph">这个分组还没有收藏，去烂梗页点 ♡ 收起来吧。</div>
        <template v-else>
          <div v-for="b in rows" :key="b.id" class="fitem" data-test="fitem">
            <div class="ftext">{{ b.content }}</div>
            <div class="fbtns">
              <button class="mini primary" data-test="fav-copy" @click="copyOne(b)">复制</button>
              <select v-if="others.length" class="mini sel" data-test="move-sel"
                      @change="moveTo(b.id, ($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).selectedIndex = 0">
                <option value="" disabled selected>移到 ▾</option>
                <option v-for="g in others" :key="g" :value="g">{{ g }}</option>
              </select>
              <button class="mini" data-test="fav-remove" @click="removeOne(b.id)">移除</button>
            </div>
          </div>
          <p v-if="staleCount > 0" class="stale">另有 {{ staleCount }} 条已被下架/删除，不再展示。</p>
        </template>
      </div>

      <div class="favtools">
        <button @click="doExport">导出</button>
        <button @click="doImport">导入</button>
      </div>
    </aside>
  </div>
</template>
<style scoped>
.backdrop{position:fixed;inset:0;background:rgba(20,18,12,.32);z-index:40}
.drawer{position:fixed;top:0;right:0;bottom:0;width:380px;max-width:90vw;background:var(--panel);z-index:41;border-left:1px solid var(--line2);box-shadow:-16px 0 40px rgba(0,0,0,.18);padding:20px;overflow:auto;display:flex;flex-direction:column}
.dh{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.dh h4{font-size:16px;font-weight:900}
.x{font-size:20px;color:var(--subtle);background:none;border:none;cursor:pointer}
.dnote{font-size:12px;color:var(--subtle);line-height:1.6;margin-bottom:14px}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.tab{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);color:var(--muted);font-size:13px;font-weight:700;cursor:pointer}
.tab.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-deep)}
.tab .n{font-size:11px;font-weight:800;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:0 6px}
.tab.add{color:var(--subtle)}
.items{flex:1;display:flex;flex-direction:column;gap:9px}
.ph{padding:34px 10px;text-align:center;color:var(--subtle);font-size:13px;line-height:1.6}
.fitem{border:1px solid var(--line);border-radius:11px;background:var(--panel2);padding:11px 12px}
.ftext{font-size:14px;font-weight:600;line-height:1.45;word-break:break-word}
.fbtns{margin-top:9px;display:flex;align-items:center;gap:6px}
.mini{font-size:12px;font-weight:700;border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:8px;padding:6px 11px;cursor:pointer}
.mini.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.mini.sel{padding:6px 8px;color:var(--ink)}
.stale{font-size:12px;color:var(--subtle);margin-top:4px}
.favtools{display:flex;gap:6px;margin-top:14px}
.favtools button{flex:1;font-size:12px;font-weight:700;border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:9px;padding:9px 0;cursor:pointer}
</style>
