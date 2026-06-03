<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

const FEEDBACK_URL = 'https://v.wjx.cn/vm/rRSgU2a.aspx#'

function close() { emit('update:open', false) }
function onKey(e: KeyboardEvent) { if (e.key === 'Escape') close() }
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>
<template>
  <Teleport to="body">
    <div v-if="open" class="ig-wrap">
      <div class="ig-backdrop" @click="close"></div>
      <div class="ig-card" role="dialog" aria-modal="true">
        <div class="ig-head">
          <h3>⚡ 装「斗鱼 2099 烂梗发送器」</h3>
          <button class="x" @click="close">✕</button>
        </div>

        <div class="ig-body">
          <p class="lead">这是个浏览器油猴脚本：进 2099 直播间后，右侧会多一个悬浮按钮，点开就能搜梗、一键复制 / 发弹幕。按下面五步走 👇</p>

          <ol class="steps">
            <li>
              <b>① 装油猴扩展（Tampermonkey）</b>
              <p>先给浏览器装管理器扩展（任选其一，按你的浏览器来）：</p>
              <div class="links">
                <a href="https://chromewebstore.google.com/detail/dhdgffkkebhmkfjojejmpbldmpobfkfo" target="_blank" rel="noopener">Chrome 应用商店</a>
                <a href="https://microsoftedge.microsoft.com/addons/detail/iikmkjmpaadaobahmlepeloendndfphd" target="_blank" rel="noopener">Edge 加载项</a>
                <a href="https://addons.mozilla.org/firefox/addon/tampermonkey/" target="_blank" rel="noopener">Firefox 附加组件</a>
              </div>
            </li>
            <li>
              <b>② 导入本脚本（本地文件方式）</b>
              <p>本脚本还没上架脚本市场，先用本地文件导入：</p>
              <p>
                <a class="dl" href="/userscript" download="sb2099.user.js">⬇ 下载脚本文件</a>
                （得到 <code>sb2099.user.js</code>）
              </p>
              <p>然后任选一种装进油猴：</p>
              <ul>
                <li><b>最简单</b>：把下载到的 <code>sb2099.user.js</code> 直接<b>拖进浏览器的油猴管理面板窗口</b>，油猴会弹出安装页，点「安装」即可。</li>
                <li>或：点油猴图标 →「管理面板」→ 顶部「实用工具」→ 最下方「导入」里选这个本地文件。</li>
                <li>或：油猴「管理面板」→「＋」新建脚本，把文件内容全选复制粘进去，Ctrl+S 保存。</li>
              </ul>
            </li>
            <li>
              <b>③ 脚本在哪显示</b>
              <p>打开 <a href="https://www.douyu.com/2099" target="_blank" rel="noopener">douyu.com/2099</a> 直播间，页面<b>右侧偏下</b>会出现竖排「🐹 sb2099」悬浮按钮，<b>点它开 / 关</b>面板（默认是关的）。</p>
            </li>
            <li>
              <b>④ 怎么用</b>
              <ul>
                <li>顶部搜索框输关键词 → 点「搜索」。</li>
                <li><b>点某条烂梗正文 = 直接复制</b>；点右侧「发送」= 自动填进弹幕框并发出（带 5 秒冷却防刷屏）。</li>
                <li>面板可按标题栏拖动挪位置。</li>
              </ul>
            </li>
            <li>
              <b>⑤ 收藏怎么导入导出 / 更新</b>
              <ul>
                <li><b>收藏</b>：在本站右上角「⭐ 收藏夹」里整理好，点「导出」复制 JSON；到脚本「收藏」页点「⬇ 从主站导入」粘上即可（两边同一份本地数据，互通）。增删、建分组、导出都在本站做。</li>
                <li><b>更新脚本</b>：脚本面板标题旁有版本号（如 v0.5.1）。本站「装脚本」弹窗里重新「下载脚本文件」覆盖导入一次，就是最新版。</li>
              </ul>
            </li>
          </ol>

          <p class="feedback">有问题或想加功能？<a :href="FEEDBACK_URL" target="_blank" rel="noopener">点这里提反馈 →</a></p>
        </div>

        <div class="ig-foot">
          <a class="primary" href="/userscript" download="sb2099.user.js">⬇ 下载脚本文件</a>
          <button class="ghost" @click="close">知道了</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<style scoped>
.ig-wrap{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;padding:20px}
.ig-backdrop{position:fixed;inset:0;background:rgba(20,18,12,.42)}
.ig-card{position:relative;width:560px;max-width:100%;max-height:86vh;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line2);border-radius:18px;box-shadow:0 24px 60px rgba(0,0,0,.28);overflow:hidden}
.ig-head{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--line)}
.ig-head h3{font-size:17px;font-weight:900}
.x{font-size:20px;color:var(--subtle);background:none;border:none;cursor:pointer}
.ig-body{padding:18px 22px;overflow:auto}
.lead{font-size:13px;color:var(--muted);line-height:1.7;margin-bottom:14px}
.steps{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:16px}
.steps>li{font-size:13px;line-height:1.7}
.steps>li b{font-size:14px;font-weight:800;color:var(--ink)}
.steps p{margin:5px 0;color:var(--muted)}
.steps ul{margin:5px 0 0;padding-left:18px;color:var(--muted);display:flex;flex-direction:column;gap:4px}
.steps ul b{font-size:13px}
.links{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}
.links a{font-size:12px;font-weight:700;color:var(--accent-deep);background:var(--accent-soft);border:1px solid var(--line2);border-radius:9px;padding:6px 11px;text-decoration:none}
code{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:12px}
a.dl{font-weight:800;color:var(--accent);text-decoration:none}
.feedback{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
.feedback a{color:var(--accent);font-weight:700;text-decoration:none}
.ig-foot{display:flex;gap:10px;padding:14px 22px;border-top:1px solid var(--line);background:var(--panel2)}
.ig-foot .primary{flex:1;text-align:center;background:var(--accent);color:#fff;font-weight:800;font-size:14px;padding:11px 0;border-radius:11px;text-decoration:none;box-shadow:0 4px 0 var(--accent-deep)}
.ig-foot .ghost{font-size:14px;font-weight:700;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:0 18px;cursor:pointer}
</style>
