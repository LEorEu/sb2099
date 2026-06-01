# 团松子烂梗收集站 · 前端改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 sb2099 的三个公开页（首页 / 全部烂梗 / 热榜）重写为浅色+红色、抽象梗文化语气的 Vue3 SPA，FastAPI 退成纯 JSON API，admin 不动。

**Architecture:** Vite + Vue3 + TypeScript SPA，源码在 `sb2099/web/frontend/`，构建产物 `dist/` 由 FastAPI 以 SPA 回退方式托管。`vue-router`(history) 管三条路由，Pinia 管收藏夹/标签缓存，主题用 CSS 变量 + localStorage。后端仅 `/api/live` 补一个 `in_library` 字段；admin/ingest/其余 API 不动。

**Tech Stack:** Vue 3.4+, Vite 5, TypeScript, vue-router 4, Pinia 2, Vitest + @vue/test-utils, jsdom；后端 FastAPI + pytest（既有）。

参考设计：`docs/superpowers/specs/2026-06-01-frontend-redesign-design.md`

---

## 文件结构总览

新增（前端）：
```
sb2099/web/frontend/
  package.json              依赖与脚本
  vite.config.ts            base/proxy/build outDir
  tsconfig.json
  vitest.config.ts          jsdom + setup
  index.html                SPA 入口（含防闪烁主题脚本）
  src/
    main.ts                 创建 app + router + pinia
    router.ts               3 路由 + 404
    api/client.ts           fetch 封装 + 类型
    api/types.ts            DTO 类型
    stores/tags.ts          标签缓存
    stores/favorites.ts     localStorage 收藏夹
    composables/useTheme.ts 主题切换
    composables/useToast.ts toast
    composables/useCopy.ts  复制 + /api/copy + toast
    styles/theme.css        CSS 变量 + base
    components/
      TopBar.vue  FavoritesDrawer.vue  ToastHost.vue
      TagChips.vue  MemeRow.vue  ActionPopover.vue
      SubmitCard.vue  UserPicker.vue  DailyMemeCard.vue
      LatestList.vue  ScriptBanner.vue
      RankRow.vue  WindowToggle.vue
    views/
      HomeView.vue  BarrageView.vue  LiveView.vue  NotFoundView.vue
    App.vue
```

修改（后端）：
- `sb2099/web/routes_api.py`：`/api/live` 增加 `in_library`（+ `barrage_tags`）。
- `sb2099/web/app.py`：挂载 SPA assets + 添加 SPA 回退路由。
- `sb2099/web/routes_public.py`：移除 `/`、`/barrage`、`/live` 三个 SSR 路由，仅保留 `/userscript`。

删除（cutover 末期）：
- `sb2099/web/templates/home.html`、`list.html`、`live.html`、`_layout.html`、`_topbar_tools.html`
- `sb2099/web/static/sb2099.css`、`sb2099.js`（admin 若复用则保留，见 Task 21 校验）

---

## Phase A — 脚手架与 FastAPI 集成

### Task 1: Scaffold Vite + Vue3 + TS 工程

**Files:**
- Create: `sb2099/web/frontend/package.json`
- Create: `sb2099/web/frontend/tsconfig.json`
- Create: `sb2099/web/frontend/index.html`
- Create: `sb2099/web/frontend/src/main.ts`
- Create: `sb2099/web/frontend/src/App.vue`

- [ ] **Step 1: 写 package.json**

```json
{
  "name": "sb2099-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^24.0.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.0.0"
  }
}
```

- [ ] **Step 2: 写 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ESNext", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vitest/globals"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 3: 写 index.html（含防闪烁主题脚本）**

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>团松子烂梗收集站</title>
  <script>
    try {
      var t = localStorage.getItem('sb2099-theme') || 'light';
      document.documentElement.setAttribute('data-theme', t);
    } catch (e) { document.documentElement.setAttribute('data-theme', 'light'); }
  </script>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 4: 写 src/App.vue（占位，后续 Task 10 替换为真实 shell）**

```vue
<template>
  <div>scaffold ok</div>
</template>
```

- [ ] **Step 5: 写 src/main.ts**

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/theme.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

> 注：`./styles/theme.css` 与 router 在后续任务创建；本任务先不引 router，theme.css 在 Task 5 创建前 main.ts 暂时注释该 import 行或先创建空文件。执行时：先 `touch src/styles/theme.css` 建空文件避免 import 报错。

- [ ] **Step 6: 安装依赖并验证**

Run（在 `sb2099/web/frontend/`）：
```bash
npm install
```
Expected: 成功生成 `node_modules` 与 `package-lock.json`，无报错。

- [ ] **Step 7: Commit**

```bash
git add sb2099/web/frontend/package.json sb2099/web/frontend/package-lock.json sb2099/web/frontend/tsconfig.json sb2099/web/frontend/index.html sb2099/web/frontend/src/main.ts sb2099/web/frontend/src/App.vue
git commit -m "chore(frontend): scaffold vite + vue3 + ts project"
```

---

### Task 2: Vite 配置（base / proxy / build 输出）

**Files:**
- Create: `sb2099/web/frontend/vite.config.ts`
- Modify: `sb2099/web/frontend/.gitignore`（create）

- [ ] **Step 1: 写 vite.config.ts**

构建产物输出到 `dist/`；dev 把 `/api`、`/admin`、`/userscript`、`/static` 代理到 uvicorn(8000)。

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/userscript': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
```

- [ ] **Step 2: 写 frontend/.gitignore**

```
node_modules/
dist/
```

> 决策：`dist/` 不入库；部署时在服务器上 `npm run build` 生成（见 Task 21 部署说明）。

- [ ] **Step 3: 验证构建可跑通**

Run：
```bash
npm run build
```
Expected: 生成 `dist/index.html` 与 `dist/assets/*`，无类型错误。

- [ ] **Step 4: Commit**

```bash
git add sb2099/web/frontend/vite.config.ts sb2099/web/frontend/.gitignore
git commit -m "chore(frontend): vite config with dev proxy and dist output"
```

---

### Task 3: Vitest 测试环境 + 冒烟测试

**Files:**
- Create: `sb2099/web/frontend/vitest.config.ts`
- Create: `sb2099/web/frontend/src/components/__tests__/smoke.test.ts`

- [ ] **Step 1: 写 vitest.config.ts**

```ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: { environment: 'jsdom', globals: true },
})
```

- [ ] **Step 2: 写失败的冒烟测试**

```ts
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { expect, test } from 'vitest'

test('vue test utils mounts a component', () => {
  const C = defineComponent({ render: () => h('div', 'hi') })
  const w = mount(C)
  expect(w.text()).toBe('hi')
})
```

- [ ] **Step 3: 跑测试确认通过**

Run：`npm run test`
Expected: 1 passed。（这步本质验证测试环境就绪）

- [ ] **Step 4: Commit**

```bash
git add sb2099/web/frontend/vitest.config.ts sb2099/web/frontend/src/components/__tests__/smoke.test.ts
git commit -m "test(frontend): set up vitest + jsdom smoke test"
```

---

### Task 4: FastAPI SPA 回退 + assets 挂载

**Files:**
- Modify: `sb2099/web/app.py`
- Modify: `sb2099/web/routes_public.py`
- Test: `sb2099/tests/test_spa_fallback.py`（create）

- [ ] **Step 1: 写失败的 pytest**

```python
"""SPA 回退：未知前端路径返回 index.html；/api 与 /admin 不被吞。"""
from pathlib import Path

from fastapi.testclient import TestClient


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app>SPA</div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_spa_fallback_serves_index(tmp_path, monkeypatch):
    dist = _make_dist(tmp_path)
    monkeypatch.setenv("SB2099_FRONTEND_DIST", str(dist))
    from sb2099.web import app as app_mod
    import importlib
    importlib.reload(app_mod)
    client = TestClient(app_mod.app)

    # 未知前端路由 → index.html
    r = client.get("/barrage")
    assert r.status_code == 200
    assert "SPA" in r.text

    # 资源可取
    r2 = client.get("/assets/app.js")
    assert r2.status_code == 200

    # /api 仍是 JSON，不被回退吞掉
    r3 = client.get("/api/tags")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/json")
```

- [ ] **Step 2: 跑测试确认失败**

Run：`cd sb2099 && python -m pytest tests/test_spa_fallback.py -v`
Expected: FAIL（`/barrage` 当前是 SSR 模板或 SPA 逻辑未实现）。

- [ ] **Step 3: 改 routes_public.py — 删三个 SSR 路由，仅留 /userscript**

把 `home`、`barrage_page`、`live_page` 三个路由函数及其辅助 `_enabled_tags`、相关 import（`Jinja2Templates`、`search_barrage`、`text`、`select`、`Tag` 等仅服务这三个路由的）删除，文件收敛为：

```python
"""公开静态资源：仅 /userscript（返回 .user.js 文件）。其余页面交给 SPA。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

_USERSCRIPT_PATH = Path(__file__).parent.parent / "userscript" / "sb2099.user.js"

router = APIRouter()


@router.get("/userscript")
async def userscript() -> FileResponse:
    return FileResponse(
        _USERSCRIPT_PATH,
        media_type="application/javascript",
        filename="sb2099.user.js",
    )
```

- [ ] **Step 4: 改 app.py — 挂载 dist 并加 SPA 回退**

在 `app.py` 末尾（`/static` 挂载之后）追加。注意回退路由必须**最后**注册，且显式排除 `api/admin/static/assets/userscript` 前缀。

```python
import os
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse

_FRONTEND_DIST = Path(
    os.environ.get("SB2099_FRONTEND_DIST", str(Path(__file__).parent / "frontend" / "dist"))
)

if (_FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

_SPA_EXCLUDE = ("api/", "admin", "static/", "assets/", "userscript")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    if full_path.startswith(_SPA_EXCLUDE):
        return JSONResponse(status_code=404, content={"detail": "not found"})
    index = _FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    return JSONResponse(status_code=503, content={"detail": "frontend not built"})
```

> `startswith` 接受 tuple，命中任一前缀即视为非 SPA。`/api/*` 因 `api_router` 在前已匹配，不会落到这里；万一未匹配（错误路径）也返回 404 而非 index.html。

- [ ] **Step 5: 跑测试确认通过**

Run：`cd sb2099 && python -m pytest tests/test_spa_fallback.py -v`
Expected: PASS。

- [ ] **Step 6: 跑既有公开页相关测试，确认没破坏**

Run：`cd sb2099 && python -m pytest tests/ -q -k "public or userscript or api"`
Expected: 无新增失败（若有测试断言旧 SSR HTML，需在本步同改为断言 SPA 回退或删除，逐个修正）。

- [ ] **Step 7: Commit**

```bash
git add sb2099/web/app.py sb2099/web/routes_public.py sb2099/tests/test_spa_fallback.py
git commit -m "feat(web): serve Vue SPA via fallback, drop SSR public routes"
```

---

### Task 5: 主题系统（CSS 变量 + useTheme）

**Files:**
- Create: `sb2099/web/frontend/src/styles/theme.css`
- Create: `sb2099/web/frontend/src/composables/useTheme.ts`
- Test: `sb2099/web/frontend/src/composables/__tests__/useTheme.test.ts`

- [ ] **Step 1: 写 theme.css（浅色默认 + 深色覆盖，红色主色）**

```css
:root, [data-theme="light"] {
  --bg:#f5f4ef; --panel:#ffffff; --panel2:#faf9f5;
  --line:#e8e5dd; --line2:#dad6cb;
  --ink:#1c1a15; --muted:#6f6a5f; --subtle:#9b9588;
  --accent:#e23744; --accent-soft:#fdeaec; --accent-deep:#b3232f;
  --violet:#7c5cff; --violet-soft:#efeaff;
  --green:#1faa6b; --green-soft:#e6f7ef;
  --pink:#e0408f; --pink-soft:#fdeaf4;
}
[data-theme="dark"] {
  --bg:#14130f; --panel:#1c1b16; --panel2:#211f19;
  --line:#2b291f; --line2:#3a372a;
  --ink:#f3f1ea; --muted:#a6a094; --subtle:#7a7568;
  --accent:#ff5a64; --accent-soft:#3a1d20; --accent-deep:#c93a44;
  --violet:#a892ff; --violet-soft:#2a2440;
  --green:#4cd29a; --green-soft:#16302a;
  --pink:#f06fb0; --pink-soft:#3a2030;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--ink);
  font-family: "PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  -webkit-font-smoothing: antialiased; line-height: 1.5;
}
a { color: inherit; text-decoration: none; }
.app-wrap { max-width: 1040px; margin: 0 auto; padding: 0 20px; }
```

- [ ] **Step 2: 写失败的 useTheme 测试**

```ts
import { beforeEach, expect, test } from 'vitest'
import { useTheme } from '../useTheme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

test('defaults to light and toggles + persists', () => {
  const { theme, toggle } = useTheme()
  expect(theme.value).toBe('light')
  toggle()
  expect(theme.value).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(localStorage.getItem('sb2099-theme')).toBe('dark')
})
```

- [ ] **Step 3: 跑测试确认失败**

Run：`npm run test -- useTheme`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: 写 useTheme.ts**

```ts
import { ref } from 'vue'

type Theme = 'light' | 'dark'
const KEY = 'sb2099-theme'

function read(): Theme {
  try {
    return (localStorage.getItem(KEY) as Theme) || 'light'
  } catch {
    return 'light'
  }
}

const theme = ref<Theme>(read())

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  try { localStorage.setItem(KEY, t) } catch { /* ignore */ }
}

export function useTheme() {
  function set(t: Theme) { theme.value = t; apply(t) }
  function toggle() { set(theme.value === 'light' ? 'dark' : 'light') }
  return { theme, set, toggle }
}
```

- [ ] **Step 5: 跑测试确认通过**

Run：`npm run test -- useTheme`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add sb2099/web/frontend/src/styles/theme.css sb2099/web/frontend/src/composables/useTheme.ts sb2099/web/frontend/src/composables/__tests__/useTheme.test.ts
git commit -m "feat(frontend): theme system with css vars + useTheme"
```

---

## Phase B — 后端 API 补字段

### Task 6: `/api/live` 增加 `in_library`

**Files:**
- Modify: `sb2099/web/routes_api.py:99-149`（`_live_rows` + `get_live`）
- Test: `sb2099/tests/test_api_live_in_library.py`（create）

- [ ] **Step 1: 写失败的 pytest**

```python
"""/api/live 每项应含 in_library（content_norm 命中 active barrage 即 True）。"""
from datetime import datetime

from fastapi.testclient import TestClient


def test_live_marks_in_library(seeded_client_with_live):
    # fixture 见下：daily_hot 有两条，其中一条 content_norm 已在 active barrage
    client = seeded_client_with_live
    r = client.get("/api/live?window=day")
    assert r.status_code == 200
    data = r.json()["data"]
    by_in = {item["content_sample"]: item["in_library"] for item in data}
    assert by_in["已入库样本"] is True
    assert by_in["未入库样本"] is False
```

> fixture `seeded_client_with_live`：参照 `tests/conftest.py` 既有 in-memory DB 套路，插入 2 条 `daily_hot`（live_date=当前直播日，is_filtered=0），其中"已入库样本"的 `content_norm` 同时插入一条 `barrage(status='active')`。若 conftest 无现成 helper，在本测试文件内用 `sb2099.db.SessionLocal` 直接建数据。具体插入字段对照 `models.DailyHot` / `models.Barrage`。

- [ ] **Step 2: 跑测试确认失败**

Run：`cd sb2099 && python -m pytest tests/test_api_live_in_library.py -v`
Expected: FAIL（`KeyError: 'in_library'`）。

- [ ] **Step 3: 改 `_live_rows` 的 day 分支 SQL 加 LEFT JOIN**

把 day 分支 SQL（`routes_api.py` 约 105-110 行）替换为带 barrage 关联的版本：

```python
        sql = text(
            "SELECT d.id, d.content_sample, d.send_cnt, "
            "  d.unique_sender_cnt AS unique_senders, d.last_seen, "
            "  b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date = :d AND d.is_filtered = 0 "
            "ORDER BY d.send_cnt DESC, d.last_seen DESC LIMIT 10"
        )
```

week 分支（约 113-124 行）在外层补 barrage 关联——把聚合结果当子查询再 LEFT JOIN：

```python
        sql = text(
            "SELECT t.*, b.id AS barrage_id, b.tags AS barrage_tags FROM ("
            "  SELECT d.content_norm AS content_norm, "
            "    (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "    (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "    SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "    MAX(d.last_seen) AS last_seen "
            "  FROM daily_hot d WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "  GROUP BY d.content_norm "
            "  ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
            ") t LEFT JOIN barrage b ON b.content_norm = t.content_norm AND b.status='active'"
        )
```

- [ ] **Step 4: 改 `get_live` 输出加 `in_library` 与 `barrage_tags`**

把 `get_live`（约 130-149 行）的 dict 推导补两个字段：

```python
            {
                "id": r["id"],
                "content_sample": r["content_sample"],
                "send_cnt": int(r["send_cnt"] or 0),
                "unique_senders": int(r["unique_senders"] or 0),
                "last_seen": (
                    r["last_seen"].isoformat()
                    if hasattr(r["last_seen"], "isoformat")
                    else (str(r["last_seen"]) if r["last_seen"] else None)
                ),
                "in_library": r["barrage_id"] is not None,
                "barrage_tags": r["barrage_tags"],
            }
```

- [ ] **Step 5: 跑测试确认通过**

Run：`cd sb2099 && python -m pytest tests/test_api_live_in_library.py -v`
Expected: PASS。

- [ ] **Step 6: 跑全量后端测试**

Run：`cd sb2099 && python -m pytest tests/ -q`
Expected: 全绿（含既有 live/api 测试）。

- [ ] **Step 7: Commit**

```bash
git add sb2099/web/routes_api.py sb2099/tests/test_api_live_in_library.py
git commit -m "feat(api): /api/live exposes in_library + barrage_tags"
```

---

## Phase C — 前端核心基建

### Task 7: API 类型 + client

**Files:**
- Create: `sb2099/web/frontend/src/api/types.ts`
- Create: `sb2099/web/frontend/src/api/client.ts`
- Test: `sb2099/web/frontend/src/api/__tests__/client.test.ts`

- [ ] **Step 1: 写 types.ts**

```ts
export interface Tag { value: string; label: string; icon_url: string | null; sort: number }
export interface Submitter { nickname: string; avatar: string | null }
export interface Barrage {
  id: number; content: string; tags: string; cnt: number;
  submit_time: string | null; submitter?: Submitter | null
}
export interface BarragePage { list: Barrage[]; total: number; last_page: boolean }
export interface LiveItem {
  id: number; content_sample: string; send_cnt: number; unique_senders: number;
  last_seen: string | null; in_library: boolean; barrage_tags: string | null
}
export interface UserHit { uid: string; nickname: string; avatar: string | null }
```

- [ ] **Step 2: 写失败的 client 测试**

```ts
import { afterEach, expect, test, vi } from 'vitest'
import { api } from '../client'

afterEach(() => vi.restoreAllMocks())

test('getTags unwraps {data:[...]}', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }] }),
      { headers: { 'content-type': 'application/json' } })))
  const tags = await api.getTags()
  expect(tags[0].label).toBe('主播梗')
})

test('non-2xx throws ApiError with detail', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'rate limit' }), { status: 429,
      headers: { 'content-type': 'application/json' } })))
  await expect(api.copy('barrage', 1)).rejects.toThrow('rate limit')
})
```

- [ ] **Step 3: 跑测试确认失败**

Run：`npm run test -- client`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: 写 client.ts**

```ts
import type { Barrage, BarragePage, LiveItem, Tag, UserHit } from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message)
  }
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'content-type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const ct = res.headers.get('content-type') || ''
  const body = ct.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) {
    const detail = (body && (body as any).detail) ?? body
    const msg = typeof detail === 'string' ? detail
      : (detail && (detail as any).message) || `HTTP ${res.status}`
    throw new ApiError(res.status, msg, detail)
  }
  return body as T
}

export const api = {
  getTags: () => req<{ data: Tag[] }>('/api/tags').then(r => r.data),
  getRandom: () => req<{ data: Barrage }>('/api/random').then(r => r.data),
  searchBarrage: (p: { q?: string; tag?: string; sort?: 'new' | 'hot'; page?: number; size?: number }) => {
    const qs = new URLSearchParams()
    if (p.q) qs.set('q', p.q)
    if (p.tag) qs.set('tag', p.tag)
    qs.set('sort', p.sort || 'new')
    qs.set('page', String(p.page || 1))
    if (p.size) qs.set('size', String(p.size))
    return req<{ data: BarragePage }>(`/api/barrage?${qs}`).then(r => r.data)
  },
  getLive: (window: 'day' | 'week') =>
    req<{ window: string; data: LiveItem[] }>(`/api/live?window=${window}`).then(r => r.data),
  searchUsers: (q: string) =>
    req<{ results: UserHit[] }>(`/api/users/search?q=${encodeURIComponent(q)}`).then(r => r.results),
  copy: (source: 'barrage' | 'live_hot', id: number) =>
    req('/api/copy', { method: 'POST', body: JSON.stringify({ source, id }) }),
  submit: (content: string, tags: string[], submitter_uid: string | null) =>
    req<{ data: Barrage }>('/api/barrage', { method: 'POST', body: JSON.stringify({ content, tags, submitter_uid }) }).then(r => r.data),
  promote: (live_hot_id: number, tags: string[], submitter_uid: string | null) =>
    req<{ data: Barrage }>('/api/promote', { method: 'POST', body: JSON.stringify({ live_hot_id, tags, submitter_uid }) }).then(r => r.data),
  report: (id: number) => req('/api/barrage/report', { method: 'POST', body: JSON.stringify({ id }) }),
  voteTag: (barrageId: number, tag_value: string, voter_uid: string | null) =>
    req(`/api/barrage/${barrageId}/vote-tag`, { method: 'POST', body: JSON.stringify({ tag_value, voter_uid }) }),
  withdraw: (id: number) => req(`/api/submission/${id}/withdraw`, { method: 'DELETE' }),
}
```

- [ ] **Step 5: 跑测试确认通过**

Run：`npm run test -- client`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add sb2099/web/frontend/src/api
git commit -m "feat(frontend): typed API client"
```

---

### Task 8: 标签 store（Pinia）

**Files:**
- Create: `sb2099/web/frontend/src/stores/tags.ts`
- Test: `sb2099/web/frontend/src/stores/__tests__/tags.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useTagsStore } from '../tags'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

test('loads once and maps value->label', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }] }),
      { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const store = useTagsStore()
  await store.load()
  await store.load()
  expect(fetchSpy).toHaveBeenCalledTimes(1)
  expect(store.labelOf('00')).toBe('主播梗')
  expect(store.labelOf('zz')).toBe('zz') // 未知 value 回退原值
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- tags`
Expected: FAIL。

- [ ] **Step 3: 写 tags.ts**

```ts
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { Tag } from '@/api/types'

export const useTagsStore = defineStore('tags', {
  state: () => ({ list: [] as Tag[], loaded: false }),
  getters: {
    map: (s) => Object.fromEntries(s.list.map(t => [t.value, t.label])) as Record<string, string>,
  },
  actions: {
    async load() {
      if (this.loaded) return
      this.list = await api.getTags()
      this.loaded = true
    },
    labelOf(value: string): string {
      return this.map[value] ?? value
    },
  },
})
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- tags`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/stores/tags.ts sb2099/web/frontend/src/stores/__tests__/tags.test.ts
git commit -m "feat(frontend): tags store with cached load + labelOf"
```

---

### Task 9: 收藏夹 store（localStorage）

**Files:**
- Create: `sb2099/web/frontend/src/stores/favorites.ts`
- Test: `sb2099/web/frontend/src/stores/__tests__/favorites.test.ts`

数据结构与现状/油猴脚本兼容：key `sb2099_favorites_v1`，`{groups: Record<string, number[]>, order: string[]}`。

- [ ] **Step 1: 写失败测试**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import { useFavoritesStore } from '../favorites'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

test('add/remove persists and counts', () => {
  const s = useFavoritesStore()
  s.addGroup('骂战专用')
  s.add(7, '骂战专用')
  s.add(9, '骂战专用')
  expect(s.totalCount).toBe(2)
  expect(JSON.parse(localStorage.getItem('sb2099_favorites_v1')!).groups['骂战专用']).toEqual([7, 9])
  s.remove(7, '骂战专用')
  expect(s.totalCount).toBe(1)
})

test('import replaces and validates', () => {
  const s = useFavoritesStore()
  const ok = s.importJson(JSON.stringify({ groups: { 默认: [1] }, order: ['默认'] }))
  expect(ok).toBe(true)
  expect(s.totalCount).toBe(1)
  expect(s.importJson('not json')).toBe(false)
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- favorites`
Expected: FAIL。

- [ ] **Step 3: 写 favorites.ts**

```ts
import { defineStore } from 'pinia'

const KEY = 'sb2099_favorites_v1'
interface FavState { groups: Record<string, number[]>; order: string[] }

function read(): FavState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { groups: { 默认: [] }, order: ['默认'] }
    const p = JSON.parse(raw)
    if (!p.groups || !p.order) throw new Error('bad')
    return p
  } catch {
    return { groups: { 默认: [] }, order: ['默认'] }
  }
}

export const useFavoritesStore = defineStore('favorites', {
  state: () => read() as FavState,
  getters: {
    totalCount: (s) => Object.values(s.groups).reduce((a, g) => a + g.length, 0),
    has: (s) => (id: number) => Object.values(s.groups).some(g => g.includes(id)),
  },
  actions: {
    persist() { localStorage.setItem(KEY, JSON.stringify({ groups: this.groups, order: this.order })) },
    addGroup(name: string) {
      name = name.trim()
      if (!name || this.groups[name]) return
      this.groups[name] = []; this.order.push(name); this.persist()
    },
    add(id: number, group = '默认') {
      if (!this.groups[group]) this.addGroup(group)
      if (!this.groups[group].includes(id)) { this.groups[group].push(id); this.persist() }
    },
    remove(id: number, group: string) {
      const arr = this.groups[group]; if (!arr) return
      const i = arr.indexOf(id); if (i >= 0) { arr.splice(i, 1); this.persist() }
    },
    exportJson(): string { return JSON.stringify({ groups: this.groups, order: this.order }) },
    importJson(raw: string): boolean {
      try {
        const p = JSON.parse(raw)
        if (!p.groups || !p.order) return false
        this.groups = p.groups; this.order = p.order; this.persist(); return true
      } catch { return false }
    },
  },
})
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- favorites`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/stores/favorites.ts sb2099/web/frontend/src/stores/__tests__/favorites.test.ts
git commit -m "feat(frontend): localStorage favorites store"
```

---

### Task 10: Toast + 复制 composable

**Files:**
- Create: `sb2099/web/frontend/src/composables/useToast.ts`
- Create: `sb2099/web/frontend/src/composables/useCopy.ts`
- Create: `sb2099/web/frontend/src/components/ToastHost.vue`
- Test: `sb2099/web/frontend/src/composables/__tests__/useCopy.test.ts`

- [ ] **Step 1: 写 useToast.ts**

```ts
import { reactive } from 'vue'

export interface ToastItem { id: number; text: string; kind: 'ok' | 'warn'; action?: { label: string; run: () => void } }
const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 1

export function useToast() {
  function push(text: string, kind: 'ok' | 'warn' = 'ok', action?: ToastItem['action'], ttl = 4000) {
    const id = seq++
    state.items.push({ id, text, kind, action })
    if (ttl > 0) setTimeout(() => dismiss(id), ttl)
    return id
  }
  function dismiss(id: number) {
    const i = state.items.findIndex(t => t.id === id)
    if (i >= 0) state.items.splice(i, 1)
  }
  return { items: state.items, push, dismiss }
}
```

- [ ] **Step 2: 写失败的 useCopy 测试**

```ts
import { afterEach, expect, test, vi } from 'vitest'
import { useCopy } from '../useCopy'

afterEach(() => vi.restoreAllMocks())

test('copies text to clipboard and pings /api/copy', async () => {
  const writeText = vi.fn(async () => {})
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  const fetchSpy = vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const { copy } = useCopy()
  await copy('戳手手', 'barrage', 1)
  expect(writeText).toHaveBeenCalledWith('戳手手')
  expect(fetchSpy).toHaveBeenCalledWith('/api/copy', expect.objectContaining({ method: 'POST' }))
})
```

- [ ] **Step 3: 跑测试确认失败**

Run：`npm run test -- useCopy`
Expected: FAIL。

- [ ] **Step 4: 写 useCopy.ts**

```ts
import { api } from '@/api/client'
import { useToast } from './useToast'

export function useCopy() {
  const toast = useToast()
  async function copy(text: string, source: 'barrage' | 'live_hot', id: number) {
    try {
      await navigator.clipboard.writeText(text)
      toast.push('已复制，回直播间粘贴就行 ✌️')
    } catch {
      toast.push('复制失败，长按手动复制吧', 'warn')
    }
    api.copy(source, id).catch(() => { /* 计数失败不打扰用户 */ })
  }
  return { copy }
}
```

- [ ] **Step 5: 跑测试确认通过**

Run：`npm run test -- useCopy`
Expected: PASS。

- [ ] **Step 6: 写 ToastHost.vue**

```vue
<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { items, dismiss } = useToast()
</script>
<template>
  <div class="toast-host">
    <div v-for="t in items" :key="t.id" class="toast" :class="t.kind">
      <span>{{ t.text }}</span>
      <button v-if="t.action" class="ta" @click="t.action.run(); dismiss(t.id)">{{ t.action.label }}</button>
    </div>
  </div>
</template>
<style scoped>
.toast-host{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:99;display:flex;flex-direction:column;gap:8px}
.toast{background:var(--ink);color:var(--bg);padding:11px 16px;border-radius:11px;font-size:14px;font-weight:600;box-shadow:0 8px 24px rgba(0,0,0,.25);display:flex;align-items:center;gap:12px}
.toast.warn{background:var(--accent)}
.ta{background:rgba(255,255,255,.18);color:inherit;border:none;border-radius:7px;padding:5px 11px;font-weight:800;cursor:pointer}
</style>
```

- [ ] **Step 7: Commit**

```bash
git add sb2099/web/frontend/src/composables/useToast.ts sb2099/web/frontend/src/composables/useCopy.ts sb2099/web/frontend/src/composables/__tests__/useCopy.test.ts sb2099/web/frontend/src/components/ToastHost.vue
git commit -m "feat(frontend): toast host + copy composable"
```

---

### Task 11: 路由 + TopBar + App shell

**Files:**
- Create: `sb2099/web/frontend/src/router.ts`
- Create: `sb2099/web/frontend/src/components/TopBar.vue`
- Create: `sb2099/web/frontend/src/views/HomeView.vue`（占位）
- Create: `sb2099/web/frontend/src/views/BarrageView.vue`（占位）
- Create: `sb2099/web/frontend/src/views/LiveView.vue`（占位）
- Create: `sb2099/web/frontend/src/views/NotFoundView.vue`
- Modify: `sb2099/web/frontend/src/App.vue`
- Modify: `sb2099/web/frontend/src/main.ts`
- Test: `sb2099/web/frontend/src/components/__tests__/TopBar.test.ts`

- [ ] **Step 1: 写三个占位 view + NotFound**

每个占位 view：
```vue
<!-- HomeView.vue / BarrageView.vue / LiveView.vue 先各放占位，后续任务替换 -->
<template><section class="app-wrap"><h1>占位</h1></section></template>
```
NotFoundView.vue：
```vue
<template><section class="app-wrap" style="padding:60px 20px;text-align:center">
  <h1 style="font-size:28px">这页没有梗 🤷</h1>
  <p style="margin-top:10px"><router-link to="/" style="color:var(--accent);font-weight:800">回首页 →</router-link></p>
</section></template>
```

- [ ] **Step 2: 写 router.ts**

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/barrage', name: 'barrage', component: () => import('@/views/BarrageView.vue') },
    { path: '/live', name: 'live', component: () => import('@/views/LiveView.vue') },
    { path: '/:pathMatch(.*)*', name: 'notfound', component: () => import('@/views/NotFoundView.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
```

- [ ] **Step 3: 写失败的 TopBar 测试**

```ts
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { expect, test } from 'vitest'
import TopBar from '../TopBar.vue'

test('renders three nav links and favorites count', () => {
  const w = mount(TopBar, {
    props: { favCount: 24 },
    global: { plugins: [createPinia()], stubs: { RouterLink: RouterLinkStub } },
  })
  expect(w.text()).toContain('首页')
  expect(w.text()).toContain('全部烂梗')
  expect(w.text()).toContain('热榜')
  expect(w.text()).toContain('24')
})
```

- [ ] **Step 4: 跑测试确认失败**

Run：`npm run test -- TopBar`
Expected: FAIL。

- [ ] **Step 5: 写 TopBar.vue**

```vue
<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'
defineProps<{ favCount: number }>()
const emit = defineEmits<{ (e: 'open-favorites'): void }>()
const { toggle } = useTheme()
</script>
<template>
  <header class="topbar">
    <div class="inner app-wrap">
      <router-link class="brand" to="/"><span class="blob"></span>sb2099</router-link>
      <nav class="nav">
        <router-link to="/" active-class="on" exact-active-class="on">首页</router-link>
        <router-link to="/barrage" active-class="on">全部烂梗</router-link>
        <router-link to="/live" active-class="on">热榜 🔥</router-link>
        <span class="more">更多 ▾</span>
      </nav>
      <div class="tools">
        <button class="ibtn" title="收藏夹" @click="emit('open-favorites')">⭐<span v-if="favCount" class="dot">{{ favCount }}</span></button>
        <button class="ibtn" title="切换深浅" @click="toggle()">🌓</button>
        <a class="ibtn script" href="/userscript">⚡ 装脚本</a>
      </div>
    </div>
  </header>
</template>
<style scoped>
.topbar{height:60px;border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:20}
.inner{height:100%;display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:900;font-size:20px;display:flex;align-items:center;gap:8px}
.blob{width:21px;height:21px;border-radius:8px 8px 8px 2px;background:var(--accent);transform:rotate(-6deg);box-shadow:2px 2px 0 var(--ink)}
.nav{display:flex;gap:2px}
.nav a,.nav .more{padding:7px 13px;border-radius:9px;color:var(--muted);font-size:14px;font-weight:700}
.nav a.on{color:var(--accent);background:var(--accent-soft)}
.nav .more{color:var(--subtle);cursor:default}
.tools{display:flex;gap:7px;align-items:center}
.ibtn{height:36px;min-width:36px;padding:0 9px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:flex;align-items:center;justify-content:center;font-size:15px;cursor:pointer;position:relative}
.ibtn .dot{position:absolute;top:-5px;right:-5px;background:var(--accent);color:#fff;font-size:10px;font-weight:800;border-radius:999px;padding:1px 5px}
.ibtn.script{gap:6px;font-weight:800;font-size:13px;background:var(--accent);color:#fff;border-color:var(--accent)}
</style>
```

- [ ] **Step 6: 写 App.vue（shell：TopBar + router-view + Drawer 占位 + ToastHost）**

```vue
<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import TopBar from '@/components/TopBar.vue'
import ToastHost from '@/components/ToastHost.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useTagsStore } from '@/stores/tags'

const favs = useFavoritesStore()
const tags = useTagsStore()
const drawerOpen = ref(false)
const favCount = computed(() => favs.totalCount)
onMounted(() => tags.load())
</script>
<template>
  <TopBar :fav-count="favCount" @open-favorites="drawerOpen = true" />
  <main><router-view /></main>
  <!-- FavoritesDrawer 在 Task 15 接入：<FavoritesDrawer v-model:open="drawerOpen" /> -->
  <ToastHost />
</template>
```

- [ ] **Step 7: 改 main.ts 接入 router**

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import './styles/theme.css'

createApp(App).use(createPinia()).use(router).mount('#app')
```

- [ ] **Step 8: 跑测试 + 构建**

Run：`npm run test -- TopBar && npm run build`
Expected: 测试 PASS；构建产物生成无类型错误。

- [ ] **Step 9: Commit**

```bash
git add sb2099/web/frontend/src/router.ts sb2099/web/frontend/src/components/TopBar.vue sb2099/web/frontend/src/views sb2099/web/frontend/src/App.vue sb2099/web/frontend/src/main.ts sb2099/web/frontend/src/components/__tests__/TopBar.test.ts
git commit -m "feat(frontend): router + topbar + app shell"
```

---

## Phase D — 全部烂梗页

### Task 12: TagChips（标签展示，开放词表）

**Files:**
- Create: `sb2099/web/frontend/src/components/TagChips.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/TagChips.test.ts`

把 barrage 的 `tags`（CSV value，如 `"00,02"`）渲染成 label chip；颜色按 value 稳定哈希取一组中性色（不固定每标签配色）。

- [ ] **Step 1: 写失败测试**

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import TagChips from '../TagChips.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore()
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 },
            { value: '02', label: '互动梗', icon_url: null, sort: 2 }]
  s.loaded = true
})

test('renders labels for csv values', () => {
  const w = mount(TagChips, { props: { csv: '00,02' }, global: { plugins: [] } })
  expect(w.text()).toContain('主播梗')
  expect(w.text()).toContain('互动梗')
})

test('empty csv renders nothing', () => {
  const w = mount(TagChips, { props: { csv: '' } })
  expect(w.findAll('.tagchip').length).toBe(0)
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- TagChips`
Expected: FAIL。

- [ ] **Step 3: 写 TagChips.vue**

```vue
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
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- TagChips`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/components/TagChips.vue sb2099/web/frontend/src/components/__tests__/TagChips.test.ts
git commit -m "feat(frontend): TagChips renders open tag vocabulary by label"
```

---

### Task 13: MemeRow + ActionPopover（复制/收藏/补标签/举报）

**Files:**
- Create: `sb2099/web/frontend/src/components/ActionPopover.vue`
- Create: `sb2099/web/frontend/src/components/MemeRow.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/MemeRow.test.ts`

- [ ] **Step 1: 写 ActionPopover.vue（点击切换、外点关闭）**

```vue
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
const open = ref(false)
const root = ref<HTMLElement | null>(null)
function toggle() { open.value = !open.value }
function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
defineExpose({ close: () => (open.value = false) })
</script>
<template>
  <span ref="root" class="pop-root">
    <button class="more" @click.stop="toggle">⋯</button>
    <div v-if="open" class="pop" @click="open = false">
      <slot />
    </div>
  </span>
</template>
<style scoped>
.pop-root{position:relative;display:inline-flex}
.more{background:var(--accent-soft);color:var(--accent);border:none;border-radius:9px;padding:9px 11px;font-weight:800;font-size:13px;cursor:pointer}
.pop{position:absolute;top:46px;right:0;background:var(--panel);border:1px solid var(--line2);border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,.18);padding:6px;width:170px;z-index:30}
.pop :slotted(button){display:flex;align-items:center;gap:9px;width:100%;background:none;border:none;text-align:left;padding:9px 11px;border-radius:8px;font-size:13px;font-weight:700;color:var(--ink);cursor:pointer}
.pop :slotted(button:hover){background:var(--panel2)}
.pop :slotted(button.warn){color:var(--pink)}
</style>
```

- [ ] **Step 2: 写失败的 MemeRow 测试**

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import MemeRow from '../MemeRow.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => {}) } })
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } })))
})

const item = { id: 1, content: '男厕所在五楼', tags: '00', cnt: 128, submit_time: '2026-05-29T00:00:00', submitter: null }

test('shows content, copy count text, and copy button works', async () => {
  const w = mount(MemeRow, { props: { item } })
  expect(w.text()).toContain('男厕所在五楼')
  expect(w.text()).toContain('被复制 128 次')
  await w.get('[data-test=copy]').trigger('click')
  expect((navigator.clipboard.writeText as any)).toHaveBeenCalledWith('男厕所在五楼')
})

test('favorite toggles store', async () => {
  const w = mount(MemeRow, { props: { item } })
  await w.get('[data-test=fav]').trigger('click')
  const { useFavoritesStore } = await import('@/stores/favorites')
  expect(useFavoritesStore().has(1)).toBe(true)
})
```

- [ ] **Step 3: 跑测试确认失败**

Run：`npm run test -- MemeRow`
Expected: FAIL。

- [ ] **Step 4: 写 MemeRow.vue**

```vue
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
function onAddTag() { toast.push('补标签功能马上来（投票/提议）') } // 完整接 vote-tag 在 Task 14 之外迭代
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
```

- [ ] **Step 5: 跑测试确认通过**

Run：`npm run test -- MemeRow`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add sb2099/web/frontend/src/components/ActionPopover.vue sb2099/web/frontend/src/components/MemeRow.vue sb2099/web/frontend/src/components/__tests__/MemeRow.test.ts
git commit -m "feat(frontend): MemeRow + ActionPopover (copy/fav/report/addtag)"
```

---

### Task 14: BarrageView（搜索 + 筛选 + 列表 + 翻页）

**Files:**
- Modify: `sb2099/web/frontend/src/views/BarrageView.vue`
- Test: `sb2099/web/frontend/src/views/__tests__/BarrageView.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import BarrageView from '../BarrageView.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
})

test('loads and renders barrage list', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: { list: [
      { id: 1, content: '戳手手', tags: '00', cnt: 5, submit_time: null, submitter: null }
    ], total: 1, last_page: true } }), { headers: { 'content-type': 'application/json' } })))
  const w = mount(BarrageView, { global: { stubs: { RouterLink: RouterLinkStub } } })
  await flushPromises()
  expect(w.text()).toContain('戳手手')
  expect(w.text()).toContain('共 1 条')
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- BarrageView`
Expected: FAIL。

- [ ] **Step 3: 写 BarrageView.vue**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import { useTagsStore } from '@/stores/tags'
import MemeRow from '@/components/MemeRow.vue'

const tags = useTagsStore()
const q = ref('')
const sort = ref<'new' | 'hot'>('hot')
const selected = ref<Set<string>>(new Set())
const page = ref(1)
const list = ref<Barrage[]>([])
const total = ref(0)
const lastPage = ref(true)
const loading = ref(false)
const MAX_INLINE_TAGS = 8

async function load() {
  loading.value = true
  try {
    const tag = [...selected.value].join(',') || undefined
    const r = await api.searchBarrage({ q: q.value || undefined, tag, sort: sort.value, page: page.value, size: 20 })
    list.value = r.list; total.value = r.total; lastPage.value = r.last_page
  } finally { loading.value = false }
}
function doSearch() { page.value = 1; load() }
function toggleTag(v: string) { selected.value.has(v) ? selected.value.delete(v) : selected.value.add(v); doSearch() }
function setSort(s: 'new' | 'hot') { sort.value = s; doSearch() }
function go(d: number) { page.value += d; load() }

onMounted(async () => { await tags.load(); await load() })
</script>
<template>
  <section class="app-wrap page">
    <div class="listhead"><h2>全部烂梗</h2><span class="cnt">共 {{ total }} 条</span></div>

    <div class="search">
      <span class="ic">🔍</span>
      <input v-model="q" placeholder="搜个梗… 比如「蜜雪」「厕所」「这TM是歌」" @keyup.enter="doSearch" />
      <button class="go" @click="doSearch">搜梗</button>
    </div>

    <div class="filters">
      <span class="fchip" :class="{ on: selected.size === 0 }" @click="selected.clear(); doSearch()">全部</span>
      <span v-for="t in tags.list.slice(0, MAX_INLINE_TAGS)" :key="t.value"
            class="fchip" :class="{ on: selected.has(t.value) }" @click="toggleTag(t.value)">{{ t.label }}</span>
      <span class="fspace"></span>
      <span class="fsort">
        <a :class="{ on: sort === 'hot' }" @click="setSort('hot')">🔥 最热</a> ·
        <a :class="{ on: sort === 'new' }" @click="setSort('new')">最新</a>
      </span>
    </div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="list.length === 0" class="empty">没搜到，换个词试试 🤔</div>
    <div v-else class="memelist">
      <MemeRow v-for="b in list" :key="b.id" :item="b" />
    </div>

    <nav v-if="list.length" class="pager">
      <button :disabled="page <= 1" @click="go(-1)">上一页</button>
      <span>第 {{ page }} 页</span>
      <button :disabled="lastPage" @click="go(1)">下一页</button>
    </nav>
  </section>
</template>
<style scoped>
.page{padding:22px 20px 60px}
.listhead{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.listhead h2{font-size:22px;font-weight:900}
.cnt{font-size:13px;color:var(--subtle);font-weight:600}
.search{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line2);border-radius:13px;padding:5px 5px 5px 16px;margin-bottom:14px}
.search .ic{color:var(--subtle)}
.search input{flex:1;border:none;background:none;outline:none;font-size:15px;padding:11px 0;color:var(--ink)}
.search .go{background:var(--accent);color:#fff;border:none;border-radius:9px;padding:10px 18px;font-weight:800;cursor:pointer}
.filters{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.fchip{padding:6px 13px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--muted);font-size:13px;font-weight:700;cursor:pointer}
.fchip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.fspace{flex:1}
.fsort{font-size:13px;color:var(--subtle)}
.fsort a{cursor:pointer}
.fsort a.on{color:var(--ink);font-weight:800}
.memelist{display:flex;flex-direction:column;gap:10px}
.empty{padding:40px;text-align:center;color:var(--subtle)}
.pager{display:flex;align-items:center;justify-content:center;gap:16px;margin-top:20px}
.pager button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:9px;padding:8px 16px;font-weight:700;cursor:pointer}
.pager button:disabled{opacity:.4;cursor:not-allowed}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- BarrageView`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/views/BarrageView.vue sb2099/web/frontend/src/views/__tests__/BarrageView.test.ts
git commit -m "feat(frontend): BarrageView with search/filter/list/pager"
```

---

### Task 15: FavoritesDrawer + 接入 App

**Files:**
- Create: `sb2099/web/frontend/src/components/FavoritesDrawer.vue`
- Modify: `sb2099/web/frontend/src/App.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/FavoritesDrawer.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test } from 'vitest'
import FavoritesDrawer from '../FavoritesDrawer.vue'
import { useFavoritesStore } from '@/stores/favorites'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

test('open shows groups, close emits update:open=false', async () => {
  const s = useFavoritesStore(); s.add(7, '默认')
  const w = mount(FavoritesDrawer, { props: { open: true } })
  expect(w.text()).toContain('默认')
  await w.get('[data-test=close]').trigger('click')
  expect(w.emitted('update:open')![0]).toEqual([false])
})

test('closed renders no panel', () => {
  const w = mount(FavoritesDrawer, { props: { open: false } })
  expect(w.find('.drawer').exists()).toBe(false)
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- FavoritesDrawer`
Expected: FAIL。

- [ ] **Step 3: 写 FavoritesDrawer.vue**

```vue
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
  toast.push(favs.importJson(raw) ? '导入成功 ✅' : '格式不对，导入失败', favs.importJson(raw) ? 'ok' : 'warn')
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
```

> 注：`doImport` 当前调用了两次 `importJson`，第二次会重复导入——修正为先存结果：`const ok = favs.importJson(raw); toast.push(ok ? '导入成功 ✅' : '格式不对，导入失败', ok ? 'ok' : 'warn')`。实现时按此单次调用版本写。

- [ ] **Step 4: 接入 App.vue**

在 `App.vue` 引入并替换占位注释：
```vue
<script setup lang="ts">
// ...原有 import...
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'
</script>
<template>
  <TopBar :fav-count="favCount" @open-favorites="drawerOpen = true" />
  <main><router-view /></main>
  <FavoritesDrawer v-model:open="drawerOpen" />
  <ToastHost />
</template>
```

- [ ] **Step 5: 跑测试 + 构建**

Run：`npm run test -- FavoritesDrawer && npm run build`
Expected: 测试 PASS（按单次 importJson 实现），构建无错。

- [ ] **Step 6: Commit**

```bash
git add sb2099/web/frontend/src/components/FavoritesDrawer.vue sb2099/web/frontend/src/App.vue sb2099/web/frontend/src/components/__tests__/FavoritesDrawer.test.ts
git commit -m "feat(frontend): favorites drawer wired into shell"
```

---

## Phase E — 首页

### Task 16: UserPicker（投稿人搜索）

**Files:**
- Create: `sb2099/web/frontend/src/components/UserPicker.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/UserPicker.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import UserPicker from '../UserPicker.vue'

test('searching >2 chars lists users and selecting emits uid', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ results: [{ uid: '123', nickname: '阿松', avatar: null }] }),
      { headers: { 'content-type': 'application/json' } })))
  const w = mount(UserPicker)
  await w.get('input').setValue('阿松松')
  await flushPromises()
  await w.get('[data-test=hit]').trigger('click')
  expect(w.emitted('update:uid')![0]).toEqual(['123'])
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- UserPicker`
Expected: FAIL。

- [ ] **Step 3: 写 UserPicker.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import type { UserHit } from '@/api/types'

defineProps<{ uid: string | null }>()
const emit = defineEmits<{ (e: 'update:uid', v: string | null): void }>()
const q = ref('')
const hits = ref<UserHit[]>([])
const picked = ref<UserHit | null>(null)
let timer: number | undefined

function onInput() {
  window.clearTimeout(timer)
  timer = window.setTimeout(async () => {
    if (q.value.trim().length <= 2) { hits.value = []; return }
    hits.value = await api.searchUsers(q.value.trim()).catch(() => [])
  }, 250)
}
function pick(u: UserHit) { picked.value = u; hits.value = []; q.value = ''; emit('update:uid', u.uid) }
function clear() { picked.value = null; emit('update:uid', null) }
</script>
<template>
  <div class="picker">
    <div v-if="picked" class="chip">
      <span>{{ picked.nickname }}</span>
      <button @click="clear">×</button>
    </div>
    <template v-else>
      <input v-model="q" placeholder="选「我是谁」可署名（昵称/UID，≥3 字符；留空匿名）" @input="onInput" />
      <ul v-if="hits.length" class="results">
        <li v-for="u in hits" :key="u.uid" data-test="hit" @click="pick(u)">{{ u.nickname }}</li>
      </ul>
    </template>
  </div>
</template>
<style scoped>
.picker{position:relative}
.chip{display:inline-flex;align-items:center;gap:8px;background:var(--accent-soft);color:var(--accent-deep);padding:6px 10px;border-radius:9px;font-size:13px;font-weight:700}
.chip button{background:none;border:none;color:inherit;cursor:pointer;font-size:15px}
input{width:100%;border:1px solid var(--line2);border-radius:10px;background:var(--panel2);padding:10px 12px;font:inherit;font-size:13px;color:var(--ink);outline:none}
.results{position:absolute;left:0;right:0;top:46px;background:var(--panel);border:1px solid var(--line2);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.16);z-index:20;list-style:none;max-height:200px;overflow:auto}
.results li{padding:9px 12px;font-size:13px;cursor:pointer}
.results li:hover{background:var(--panel2)}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- UserPicker`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/components/UserPicker.vue sb2099/web/frontend/src/components/__tests__/UserPicker.test.ts
git commit -m "feat(frontend): UserPicker with debounced search"
```

---

### Task 17: SubmitCard（投稿 + 60s 撤回）

**Files:**
- Create: `sb2099/web/frontend/src/components/SubmitCard.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/SubmitCard.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import SubmitCard from '../SubmitCard.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => {
  setActivePinia(createPinia())
  const s = useTagsStore(); s.loaded = true
  s.list = [{ value: '00', label: '主播梗', icon_url: null, sort: 1 }]
})

test('submit posts content+tags and emits submitted', async () => {
  const fetchSpy = vi.fn(async () =>
    new Response(JSON.stringify({ data: { id: 9, content: 'x', tags: '00', cnt: 0, submit_time: null } }),
      { status: 201, headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchSpy)
  const w = mount(SubmitCard)
  await w.get('textarea').setValue('男厕所在五楼女厕所在四楼')
  await w.get('[data-test=tag-00]').trigger('click')
  await w.get('[data-test=submit]').trigger('click')
  await flushPromises()
  const [url, init] = fetchSpy.mock.calls[0]
  expect(url).toBe('/api/barrage')
  expect(JSON.parse((init as any).body)).toMatchObject({ content: '男厕所在五楼女厕所在四楼', tags: ['00'] })
  expect(w.emitted('submitted')).toBeTruthy()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- SubmitCard`
Expected: FAIL。

- [ ] **Step 3: 写 SubmitCard.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError } from '@/api/client'
import { useTagsStore } from '@/stores/tags'
import { useToast } from '@/composables/useToast'
import UserPicker from './UserPicker.vue'

const emit = defineEmits<{ (e: 'submitted'): void }>()
const tags = useTagsStore()
const content = ref('')
const picked = ref<Set<string>>(new Set())
const uid = ref<string | null>(null)
const busy = ref(false)

function toggle(v: string) { picked.value.has(v) ? picked.value.delete(v) : picked.value.add(v) }

async function submit() {
  const c = content.value.trim()
  if (c.length < 4) { useToast().push('再多写几个字吧', 'warn'); return }
  if (picked.value.size === 0) { useToast().push('至少选一个分类标签', 'warn'); return }
  busy.value = true
  try {
    const row = await api.submit(c, [...picked.value], uid.value)
    content.value = ''; picked.value.clear(); uid.value = null
    useToast().push('投好了！丢进梗库 🎉', 'ok', {
      label: '撤回',
      run: () => api.withdraw(row.id).then(() => useToast().push('已撤回')).catch(() => useToast().push('撤回窗口已过', 'warn')),
    }, 60000)
    emit('submitted')
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) useToast().push('这条已经有人投过啦', 'warn')
    else if (e instanceof ApiError && e.status === 422) useToast().push('内容没通过审核', 'warn')
    else useToast().push('投稿失败，稍后再试', 'warn')
  } finally { busy.value = false }
}
</script>
<template>
  <div class="card">
    <h3>🎤 投个梗 <span class="pill">最多 255 字 · 自动查重</span></h3>
    <textarea v-model="content" maxlength="255" placeholder="听到啥好笑的弹幕，丢进来…"></textarea>
    <div class="tagrow">
      <span v-for="t in tags.list" :key="t.value" :data-test="`tag-${t.value}`"
            class="tagpick" :class="{ on: picked.has(t.value) }" @click="toggle(t.value)">{{ t.label }}</span>
    </div>
    <UserPicker v-model:uid="uid" />
    <div class="submitrow">
      <button class="btn" data-test="submit" :disabled="busy" @click="submit">丢进梗库 →</button>
    </div>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
h3{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:13px}
.pill{margin-left:auto;font-size:12px;color:var(--subtle);font-weight:600}
textarea{width:100%;min-height:88px;resize:vertical;border:1px solid var(--line2);border-radius:12px;background:var(--panel2);padding:12px 13px;font:inherit;font-size:15px;color:var(--ink);outline:none}
.tagrow{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.tagpick{font-size:13px;font-weight:700;padding:6px 12px;border-radius:999px;cursor:pointer;background:var(--panel2);border:1px solid var(--line);color:var(--muted)}
.tagpick.on{background:var(--accent);border-color:var(--accent);color:#fff}
.submitrow{display:flex;justify-content:flex-end;margin-top:12px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 20px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn:disabled{opacity:.5}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- SubmitCard`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/components/SubmitCard.vue sb2099/web/frontend/src/components/__tests__/SubmitCard.test.ts
git commit -m "feat(frontend): SubmitCard with tags + user picker + 60s withdraw"
```

---

### Task 18: DailyMemeCard + LatestList + ScriptBanner + HomeView

**Files:**
- Create: `sb2099/web/frontend/src/components/DailyMemeCard.vue`
- Create: `sb2099/web/frontend/src/components/LatestList.vue`
- Create: `sb2099/web/frontend/src/components/ScriptBanner.vue`
- Modify: `sb2099/web/frontend/src/views/HomeView.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/DailyMemeCard.test.ts`

- [ ] **Step 1: 写失败的 DailyMemeCard 测试**

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import DailyMemeCard from '../DailyMemeCard.vue'

beforeEach(() => setActivePinia(createPinia()))

test('loads a random meme on mount', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ data: { id: 1, content: '戳手手 👉👈', tags: '', cnt: 0, submit_time: null } }),
      { headers: { 'content-type': 'application/json' } })))
  const w = mount(DailyMemeCard)
  await flushPromises()
  expect(w.text()).toContain('戳手手')
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- DailyMemeCard`
Expected: FAIL。

- [ ] **Step 3: 写 DailyMemeCard.vue**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import { useCopy } from '@/composables/useCopy'

const meme = ref<Barrage | null>(null)
const { copy } = useCopy()
async function load() { meme.value = await api.getRandom().catch(() => null) }
function onCopy() { if (meme.value) copy(meme.value.content, 'barrage', meme.value.id) }
onMounted(load)
</script>
<template>
  <div class="card daily">
    <h3>🎲 今日一梗 <span class="pill">手气不错</span></h3>
    <div class="big">{{ meme?.content || '梗库还空着，先投一条吧' }}</div>
    <div class="acts">
      <button class="btn" style="flex:1" @click="onCopy">点我复制</button>
      <button class="btn ghost" @click="load">换一个</button>
    </div>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
.daily{background:linear-gradient(135deg,var(--accent-soft),var(--pink-soft));border:1px solid var(--line2)}
h3{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:13px}
.pill{margin-left:auto;font-size:12px;color:var(--accent);font-weight:700}
.big{font-size:22px;font-weight:900;line-height:1.4;margin:6px 0 14px}
.acts{display:flex;gap:10px}
.btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:11px 18px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 4px 0 var(--accent-deep)}
.btn.ghost{background:var(--panel);color:var(--ink);box-shadow:0 4px 0 var(--line2);border:1px solid var(--line)}
</style>
```

- [ ] **Step 4: 写 LatestList.vue（拉 sort=new 前几条，复用 MemeRow）**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Barrage } from '@/api/types'
import MemeRow from './MemeRow.vue'

const list = ref<Barrage[]>([])
async function load() {
  const r = await api.searchBarrage({ sort: 'new', page: 1, size: 5 }).catch(() => null)
  if (r) list.value = r.list
}
defineExpose({ load })
onMounted(load)
</script>
<template>
  <div class="card">
    <h3>🆕 刚有人投了这些</h3>
    <div class="memelist"><MemeRow v-for="b in list" :key="b.id" :item="b" /></div>
    <router-link class="seeall" to="/barrage">看全部烂梗 →</router-link>
  </div>
</template>
<style scoped>
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
h3{font-size:15px;font-weight:800;margin-bottom:13px}
.memelist{display:flex;flex-direction:column;gap:10px}
.seeall{display:block;text-align:center;margin-top:13px;font-size:14px;font-weight:800;color:var(--accent)}
</style>
```

- [ ] **Step 5: 写 ScriptBanner.vue**

```vue
<template>
  <div class="scriptbar">
    <div class="ic">⚡</div>
    <div><div class="t">在直播间里直接发梗</div><div class="s">装个浏览器插件，2099 房间左侧就能搜梗一键发</div></div>
    <a href="/userscript">去装 →</a>
  </div>
</template>
<style scoped>
.scriptbar{margin-top:18px;display:flex;align-items:center;gap:15px;background:var(--accent-soft);border:1px solid var(--line2);border-radius:16px;padding:16px 20px}
.ic{width:42px;height:42px;border-radius:11px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;flex:0 0 auto}
.t{font-weight:800;font-size:15px}
.s{color:var(--muted);font-size:13px;margin-top:2px}
a{margin-left:auto;background:var(--accent);color:#fff;padding:10px 18px;border-radius:11px;font-weight:800;font-size:14px;white-space:nowrap;box-shadow:0 4px 0 var(--accent-deep)}
</style>
```

- [ ] **Step 6: 写 HomeView.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import SubmitCard from '@/components/SubmitCard.vue'
import LatestList from '@/components/LatestList.vue'
import DailyMemeCard from '@/components/DailyMemeCard.vue'
import ScriptBanner from '@/components/ScriptBanner.vue'

const latest = ref<InstanceType<typeof LatestList> | null>(null)
</script>
<template>
  <section class="app-wrap home">
    <div class="hero">
      <span class="kicker">斗鱼 2099 · 一团肉松子直播间</span>
      <h1><span class="mark">团松子</span>烂梗收集站</h1>
      <p class="sub">家人们听到的好笑弹幕都丢这儿 · 回直播间 <b>搜一下就能一键发</b></p>
    </div>
    <div class="cols">
      <div>
        <SubmitCard @submitted="latest?.load()" />
        <div style="height:18px"></div>
        <LatestList ref="latest" />
      </div>
      <div>
        <DailyMemeCard />
        <ScriptBanner />
      </div>
    </div>
  </section>
</template>
<style scoped>
.home{padding:40px 20px 60px}
.hero{text-align:center;margin-bottom:30px}
.kicker{display:inline-block;font-size:13px;font-weight:800;color:var(--accent);background:var(--accent-soft);padding:5px 12px;border-radius:999px}
.hero h1{font-size:40px;font-weight:900;margin-top:15px;line-height:1.12}
.mark{background:linear-gradient(transparent 60%,var(--accent-soft) 60%);padding:0 6px}
.sub{color:var(--muted);font-size:15px;margin-top:13px}
.sub b{color:var(--ink)}
.cols{display:grid;grid-template-columns:1.25fr .9fr;gap:18px;align-items:start}
@media (max-width:820px){.cols{grid-template-columns:1fr}}
</style>
```

- [ ] **Step 7: 跑测试 + 构建**

Run：`npm run test -- DailyMemeCard && npm run build`
Expected: 测试 PASS，构建无错。

- [ ] **Step 8: Commit**

```bash
git add sb2099/web/frontend/src/components/DailyMemeCard.vue sb2099/web/frontend/src/components/LatestList.vue sb2099/web/frontend/src/components/ScriptBanner.vue sb2099/web/frontend/src/views/HomeView.vue sb2099/web/frontend/src/components/__tests__/DailyMemeCard.test.ts
git commit -m "feat(frontend): home view (submit + latest + daily + script)"
```

---

## Phase F — 热榜页

### Task 19: WindowToggle + RankRow（含 收进梗库）

**Files:**
- Create: `sb2099/web/frontend/src/components/WindowToggle.vue`
- Create: `sb2099/web/frontend/src/components/RankRow.vue`
- Test: `sb2099/web/frontend/src/components/__tests__/RankRow.test.ts`

- [ ] **Step 1: 写 WindowToggle.vue**

```vue
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
```

- [ ] **Step 2: 写失败的 RankRow 测试**

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import RankRow from '../RankRow.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => {}) } })
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { headers: { 'content-type': 'application/json' } })))
})

const base = { id: 1, content_sample: '戳手手', send_cnt: 318, unique_senders: 92, last_seen: null, barrage_tags: null }

test('in_library shows 已在库 and hides promote', () => {
  const w = mount(RankRow, { props: { item: { ...base, in_library: true }, rank: 1 } })
  expect(w.text()).toContain('已在库')
  expect(w.find('[data-test=promote]').exists()).toBe(false)
})

test('not in library shows promote button', () => {
  const w = mount(RankRow, { props: { item: { ...base, in_library: false }, rank: 2 } })
  expect(w.find('[data-test=promote]').exists()).toBe(true)
})
```

- [ ] **Step 3: 跑测试确认失败**

Run：`npm run test -- RankRow`
Expected: FAIL。

- [ ] **Step 4: 写 RankRow.vue**

促进入库需要选标签：点「收进梗库」展开一个 tag 多选小浮层，确认后调 `api.promote`。

```vue
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
```

- [ ] **Step 5: 跑测试确认通过**

Run：`npm run test -- RankRow`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add sb2099/web/frontend/src/components/WindowToggle.vue sb2099/web/frontend/src/components/RankRow.vue sb2099/web/frontend/src/components/__tests__/RankRow.test.ts
git commit -m "feat(frontend): RankRow with promote + WindowToggle"
```

---

### Task 20: LiveView

**Files:**
- Modify: `sb2099/web/frontend/src/views/LiveView.vue`
- Test: `sb2099/web/frontend/src/views/__tests__/LiveView.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import LiveView from '../LiveView.vue'
import { useTagsStore } from '@/stores/tags'

beforeEach(() => { setActivePinia(createPinia()); const s = useTagsStore(); s.loaded = true; s.list = [] })

test('renders live ranking', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ window: 'day', data: [
      { id: 1, content_sample: '戳手手', send_cnt: 318, unique_senders: 92, last_seen: null, in_library: false, barrage_tags: null }
    ] }), { headers: { 'content-type': 'application/json' } })))
  const w = mount(LiveView)
  await flushPromises()
  expect(w.text()).toContain('戳手手')
  expect(w.text()).toContain('318')
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npm run test -- LiveView`
Expected: FAIL。

- [ ] **Step 3: 写 LiveView.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { LiveItem } from '@/api/types'
import { useTagsStore } from '@/stores/tags'
import WindowToggle from '@/components/WindowToggle.vue'
import RankRow from '@/components/RankRow.vue'

const tags = useTagsStore()
const window = ref<'day' | 'week'>('day')
const items = ref<LiveItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try { items.value = await api.getLive(window.value) } finally { loading.value = false }
}
watch(window, load)
onMounted(async () => { await tags.load(); await load() })
</script>
<template>
  <section class="app-wrap page">
    <div class="head"><h2>现场热榜 🔥</h2><span class="cnt">刚刚还在刷的弹幕，实时统计</span></div>
    <WindowToggle v-model="window" />
    <p class="hint">看到想长期留着的，点「收进梗库」就进仓库了 · 已在库的标 ✓</p>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">这会儿还没人刷，待会再来 👀</div>
    <div v-else class="ranklist">
      <RankRow v-for="(it, i) in items" :key="it.id ?? i" :item="it" :rank="i + 1" @promoted="load" />
    </div>
  </section>
</template>
<style scoped>
.page{padding:22px 20px 60px}
.head{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.head h2{font-size:22px;font-weight:900}
.cnt{font-size:13px;color:var(--subtle)}
.hint{font-size:12px;color:var(--subtle);margin:14px 0 18px}
.ranklist{display:flex;flex-direction:column;gap:10px}
.empty{padding:40px;text-align:center;color:var(--subtle)}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npm run test -- LiveView`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add sb2099/web/frontend/src/views/LiveView.vue sb2099/web/frontend/src/views/__tests__/LiveView.test.ts
git commit -m "feat(frontend): LiveView ranking with window toggle"
```

---

## Phase G — Cutover、构建集成、验收

### Task 21: 删除旧模板/静态、构建脚本、文档

**Files:**
- Delete: `sb2099/web/templates/home.html`, `list.html`, `live.html`, `_layout.html`, `_topbar_tools.html`
- Delete（确认无 admin 复用后）: `sb2099/web/static/sb2099.css`, `sb2099/web/static/sb2099.js`
- Modify: `sb2099/README.md`（追加前端构建/开发说明）

- [ ] **Step 1: 确认 admin 模板是否引用待删资源**

Run：`grep -rn "sb2099.css\|sb2099.js\|_topbar_tools\|_layout.html" sb2099/web/templates/admin/`
Expected: 若 admin 的 `_layout.html` 独立（admin 目录下自有 `_layout.html`），公开版资源可删；若 admin 引用了 `/static/sb2099.css`，则**保留** static 文件，仅删模板。按结果决定删除范围。

- [ ] **Step 2: 删除公开页旧模板**

Run：
```bash
git rm sb2099/web/templates/home.html sb2099/web/templates/list.html sb2099/web/templates/live.html sb2099/web/templates/_layout.html sb2099/web/templates/_topbar_tools.html
```
（若 Step 1 显示 admin 复用了 `_layout.html`/`_topbar_tools.html`，则从删除列表移除对应文件。）

- [ ] **Step 3: 跑后端全量测试确认无引用断裂**

Run：`cd sb2099 && python -m pytest tests/ -q`
Expected: 全绿。若有测试断言旧公开页 HTML，改为断言 SPA 回退（200 + 含 `id=app` 或 index 内容）或删除该断言。

- [ ] **Step 4: README 追加前端说明**

在 `sb2099/README.md` 适当位置追加：

```markdown
## 前端（Vue3 SPA）

源码在 `sb2099/web/frontend/`。

开发：
```bash
cd sb2099/web/frontend
npm install
npm run dev          # Vite dev server，proxy /api 等到 :8000
# 另开一个终端跑后端： uvicorn sb2099.web.app:app --reload
```

构建（部署前）：
```bash
cd sb2099/web/frontend
npm run build        # 产出 dist/，由 FastAPI 以 SPA 回退托管
```

测试：`npm run test`。
后端通过 `SB2099_FRONTEND_DIST` 环境变量可覆盖 dist 路径（默认 `sb2099/web/frontend/dist`）。
```

- [ ] **Step 5: Commit**

```bash
git add -A sb2099/web/templates sb2099/README.md
git commit -m "chore(web): remove legacy SSR templates; document frontend build"
```

---

### Task 22: 端到端人工验收

**Files:** 无（验证步骤）

- [ ] **Step 1: 构建前端**

Run：`cd sb2099/web/frontend && npm run build`
Expected: `dist/index.html` + `dist/assets/*` 生成。

- [ ] **Step 2: 起后端**

Run：`cd sb2099 && uvicorn sb2099.web.app:app --port 8000`
Expected: 启动无错。

- [ ] **Step 3: 逐页人工核对**

浏览器开 `http://127.0.0.1:8000/`：
- 首页：标题「团松子烂梗收集站」、投稿、今日一梗、脚本横幅（浅色非黑底）。
- `/barrage`：搜索、标签筛选、单列整行、⋯ Popover（补标签/不合适）、复制提示 toast、⭐ 抽屉开合、收藏计数角标。
- `/live`：今日/7天切换、排名、🔥发送数、收进梗库（选标签）、✓已在库。
- 顶栏 🌓 切换深浅色，刷新不闪烁、保持。
- 任意未知路径（如 `/zzz`）显示 NotFound；`/api/tags` 仍返回 JSON。

Expected: 全部符合设计文档 `2026-06-01-frontend-redesign-design.md`。逐条记录，有偏差回对应任务修。

- [ ] **Step 4: 全量测试收尾**

Run：
```bash
cd sb2099/web/frontend && npm run test
cd sb2099 && python -m pytest tests/ -q
```
Expected: 前端 + 后端测试全绿。

- [ ] **Step 5: Commit（如有验收期修正）**

```bash
git add -A
git commit -m "test(frontend): e2e verification fixes"
```

---

## 自查清单结论（写计划者已核对）

- **spec §3 设计语言**：主题 Task 5；去开发名词体现在各 view 文案；「被复制 N 次」Task 13；标签开放词表 Task 12/14。✓
- **spec §4 三页 + 更多▾ + 顶栏工具**：Task 11 TopBar。✓
- **spec §5.1 首页**：Task 16/17/18（投稿/撤回/今日一梗/最新/脚本）。✓
- **spec §5.2 全部烂梗**：Task 12/13/14（单列/多标签/⋯Popover/搜索筛选翻页）。✓
- **spec §5.3 热榜**：Task 19/20（窗口切换/排名/收进梗库/已在库/去长文）。✓
- **spec §6 收藏夹抽屉**：Task 9（store）+ Task 15（drawer）。✓
- **spec §7 后端 /api/live in_library**：Task 6。✓
- **spec §8 技术架构**：Task 1-5（脚手架/Vite/Vitest/SPA 回退/主题）+ Task 11（router）。✓
- **spec §2 非目标**：admin 不动（Task 21 Step 1 显式确认不误删 admin 依赖）。✓

已知需执行时注意的点（已在正文标注）：
- Task 1 Step 5：先建空 `theme.css` 以免 import 报错。
- Task 15 Step 3：`doImport` 按"单次 importJson"实现（正文已注明）。
- Task 13 `onAddTag`：本期先 toast 占位，完整 vote-tag/propose-tag 交互为后续迭代（spec §10 开放项，未承诺本期完成完整投票 UI）。
