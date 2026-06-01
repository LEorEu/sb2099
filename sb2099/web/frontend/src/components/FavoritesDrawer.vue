<script setup lang="ts">
import { ref } from 'vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useToast } from '@/composables/useToast'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()
const favs = useFavoritesStore()
const toast = useToast()
const active = ref<string>('默认')

function close() { emit('update:open', false) }
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
}
</script>
<template>
  <div v-if="open">
    <div class="backdrop" @click="close"></div>
    <aside class="drawer">
      <div class="dh"><h4>⭐ 我的收藏夹</h4><button class="x" data-test="close" @click="close">✕</button></div>
      <p class="dnote">只存在你这台浏览器里，跟油猴脚本互通；换设备用下面导出/导入搬。</p>
      <div v-for="g in favs.order" :key="g" class="favgroup" :class="{ on: active === g }" @click="active = g">
        <span>📂 {{ g }}</span><span class="n">{{ favs.groups[g].length }}</span>
      </div>
      <div class="favtools">
        <button @click="newGroup">＋ 新建</button>
        <button @click="doExport">导出</button>
        <button @click="doImport">导入</button>
      </div>
    </aside>
  </div>
</template>
<style scoped>
.backdrop{position:fixed;inset:0;background:rgba(20,18,12,.32);z-index:40}
.drawer{position:fixed;top:0;right:0;bottom:0;width:340px;max-width:86vw;background:var(--panel);z-index:41;border-left:1px solid var(--line2);box-shadow:-16px 0 40px rgba(0,0,0,.18);padding:20px;overflow:auto}
.dh{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.dh h4{font-size:16px;font-weight:900}
.x{font-size:20px;color:var(--subtle);background:none;border:none;cursor:pointer}
.dnote{font-size:12px;color:var(--subtle);line-height:1.6;margin-bottom:14px}
.favgroup{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--panel2);margin-bottom:8px;font-size:14px;font-weight:700;cursor:pointer}
.favgroup.on{border-color:var(--accent);background:var(--accent-soft)}
.favgroup .n{background:var(--panel);color:var(--muted);font-size:11px;font-weight:800;padding:2px 8px;border-radius:6px;border:1px solid var(--line)}
.favtools{display:flex;gap:6px;margin-top:10px}
.favtools button{flex:1;font-size:12px;font-weight:700;border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:9px;padding:9px 0;cursor:pointer}
</style>
