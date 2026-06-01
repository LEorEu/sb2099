# 团松子烂梗收集站 · 前端改版设计

- 日期：2026-06-01
- 状态：设计已确认，待出实现计划
- 范围：**面向用户的三个公开页**前端重写；后端 admin、ingest、API 业务逻辑基本不动

---

## 1. 背景与目标

现站（FastAPI + Jinja2 SSR + 模板内联 vanilla JS）的体验问题：页面像"GitHub 开源工具站"，充斥用户不关心的开发名词与说明长文，不像一个给斗鱼 2099 房间观众"刷烂梗"用的工具。

**目标**：把站点重做成一个**找梗 / 抄梗 / 回直播间刷屏**的整活工具。

**成功标准**
- 三个公开页全部去除开发腔，普通观众一眼知道"在哪搜梗、怎么复制、怎么投稿"。
- 视觉统一为浅色为主、红色主色、可切换深色的轻松"抽象梗文化"调性。
- 前端迁移到 Vue3 + Vite，后端退成纯 JSON API（admin 仍走 Jinja2）。

## 2. 非目标（本期不做）

- 不改 `admin/*` 后台（继续 Jinja2，原样保留）。
- 不改 `/userscript`（该路由直接返回 `sb2099.user.js` 文件，无页面）。
- 不改 ingest / 归档 / 审核 / 防伪等后端业务逻辑。
- 不做 SSR / SEO 优化（娱乐工具，首屏打包产物即可）。
- 不改数据库结构（仅一处 API 输出补字段，见 §7）。

## 3. 设计语言

- **主题**：浅色为默认，深色可切换。沿用现有 `localStorage` key `sb2099-theme`（值 `light` / `dark`）。颜色全部走 CSS 变量，切主题 = 切一组变量。
- **主色**：红色（暂定 `--accent:#e23744`，单变量，可后期再调）。
- **语气（抽象梗文化）**：口语化文案、emoji 点缀、不端着；例如按钮「丢进梗库 / 点我复制 / 换一个」，hero 手写小字「没什么用但梗很全」。
- **去开发名词清单**（必须从 UI 消失）：`#编号`、`tags: 02` 这类原始值、`FTS5`、`加密安全哈希`、`正式投稿库 / 长期沉淀区`、`现场发现页 / 降噪榜单`、热榜「分层原则说明」整段、`（直播间没人说话或还没采集到）` 等生硬空态文案。
- **复制数文案**：对外显示为「**被复制 N 次**」（数据来自 barrage.cnt）。
- **标签**：开放词表（后续可达十几个，来自 `/api/tags`，含 `label` + 可选 `icon_url`）。单条烂梗最多 3–4 个标签，**同一行铺开展示**。颜色不重要：用中性 chip 或按 value 稳定哈希自动分配，不做"每标签固定配色"。

## 4. 信息架构（维持三页 + 顶部导航）

顶部导航：`首页` · `全部烂梗` · `热榜 🔥` · `更多 ▾`（下拉，留作后续扩展占位，如赛事/相册/贴吧）。右侧工具区：`⭐ 收藏夹`（带数量角标，点开抽屉）、`🌙 主题切换`、`⚡ 装脚本`（指向 `/userscript`）。

| 页面 | 路由 | 职责 |
|---|---|---|
| 首页 | `/` | 门面 + 投稿 + 今日一梗 + 脚本入口 |
| 全部烂梗 | `/barrage` | 梗仓库：搜索 + 标签筛选 + 单列列表 + 收藏夹抽屉 |
| 热榜 | `/live` | 直播现场实时热门：今日 Top10 / 近7天 Top50 |

## 5. 各页设计

### 5.1 首页 `/`
- **Hero**：大标题「**团松子烂梗收集站**」，副标题点明"斗鱼 2099 · 一团肉松子直播间"，一句人话说明"搜一下就能回房间一键发"。
- **投稿卡**（主行动）：文本域（≤255 字，自动查重提示）+ 标签多选（来自 `/api/tags`）+「我是谁」投稿人选择器（可选，留空即匿名）+ 提交。
  - 提交成功后展示 **60s 撤回** toast（对接 `DELETE /api/submission/{id}/withdraw`，基于 cookie）。
  - 撞库 409 / 内容被拦 422 给出友好提示。
- **刚有人投了这些**：拉 `/api/barrage?sort=new` 前几条，每条可直接复制；底部「看全部烂梗 →」跳 `/barrage`。
- **今日一梗**：`/api/random`，点卡复制、「换一个」再随机。
- **脚本横幅**：浅色卡片（**不要黑底**），引导安装油猴脚本。

### 5.2 全部烂梗 `/barrage`
- **搜索框**（主入口）：关键字搜 → `/api/barrage?q=`。
- **标签筛选**：来自 `/api/tags`。词表大，UI 上展示常用标签 + 折叠"更多"，支持多选；与 `sort=new/hot` 组合。
- **列表：单列整行**（不是双列网格）。每行：
  - 左：烂梗正文（大字）；下方 meta 行 = **多个标签同行铺开** + 「🔥 被复制 N 次 · 投稿日期」+（若有）投稿人。
  - 右：常驻「**复制**」「**♡ 收藏**」；次要操作收进「**⋯ Popover**」=「🏷️ 补个标签」(`vote-tag` / `propose-tag`) +「🚩 这条不合适」(`/api/barrage/report`)。
  - 复制 → `POST /api/copy {source:"barrage"}`。
- **分页**：沿用 page 翻页（或后续做无限滚动，本期先翻页）。
- **收藏夹抽屉**：见 §6。

### 5.3 热榜 `/live`
- **时间窗切换**：`今日 Top10` / `近7天 Top50`（`/api/live?window=day|week`）。
- 删除"分层原则说明"长文，仅保留**一行小灰字**提示（如"看到想长期留的，点『收进梗库』"）。
- **排名列表**：前三名高亮序号；每行大数字「🔥 N 次发送 · 👥 N 人」+ 最近捕获时间。
- 操作：「**复制**」(`POST /api/copy {source:"live_hot"}`)；未入库项显示「**收进梗库**」(`POST /api/promote`，需选标签 → 弹标签选择小浮层)；已入库项显示「**✓ 已在库**」徽标且不显示收进按钮。
- 空态文案改友好（不暴露采集细节）。

## 6. 收藏夹（右侧抽屉）

- 触发：顶栏 `⭐`（带数量角标）。从右侧滑出抽屉，**不占列表宽度**。
- 存储：纯 `localStorage`（与现状一致，key 沿用 `sb2099_favorites_v1`，结构 `{groups:{name:[id...]}, order:[name...]}`），与油猴脚本互通。
- 功能：分组列表 + 组内条目（复制 / 移出）+ 新建分组 + **导出 / 导入**（JSON）。
- 文案去掉"加密安全哈希"，改人话："只存在你这台浏览器里，跟脚本互通；换设备用导出/导入搬。"
- 收藏动作不调后端，仅写 localStorage。

## 7. 后端改动（最小）

唯一必要改动：**`GET /api/live` 输出补"是否已入库"字段**。
- 现状：JSON 版 `/api/live` 不含 `barrage_id` / 标签；而 SSR `/live` 路由已用 `LEFT JOIN barrage ON content_norm` 拿到 `barrage_id` + `barrage_tags`。
- 改法：把该 LEFT JOIN 逻辑挪进 `/api/live`，每项增加 `in_library: bool`（及可选 `barrage_tags`），供前端渲染「✓ 已在库」并隐藏「收进梗库」。
- 其余端点（`/api/tags`、`/api/barrage`、`/api/random`、`/api/copy`、`/api/promote`、`/api/barrage/report`、`/api/barrage/{id}/vote-tag`、`/api/barrage/{id}/propose-tag`、`/api/users/search`、`DELETE /api/submission/{id}/withdraw`）已满足需求，无需改。

## 8. 技术架构

- **框架**：Vue3 + Vite，`vue-router`（history 模式）管三条路由 + 404；状态用 Pinia（收藏夹 store、主题 composable、tags 缓存）。
- **目录**：前端源码置于 `sb2099/web/frontend/`，构建产物 `sb2099/web/frontend/dist/`。
- **FastAPI 集成**：
  - 保留 `/api`、`/admin`、`/userscript`、`/static`（admin 仍用）。
  - 移除/改写 `routes_public.py` 的三个 SSR HTML 路由，改为 **SPA 回退**：非 `/api`、`/admin`、`/static`、`/userscript` 的 GET 一律返回 `dist/index.html`；`dist/assets` 静态挂载。
  - 路由优先级需保证 `/api`、`/admin` 等前缀不被 SPA catch-all 抢占。
- **开发态**：Vite dev server 跑前端，proxy `/api`、`/admin`、`/userscript` 到 uvicorn。
- **主题**：CSS 变量 + `<html data-theme>`；首屏 inline 脚本读 `localStorage['sb2099-theme']` 防闪烁（沿用现有做法）。
- **组件划分（示意）**：`TopBar` / `FavoritesDrawer` / `MemeRow`（含 `ActionPopover`）/ `TagChips` / `TagPicker` / `UserPicker` / `SubmitCard` / `DailyMemeCard` / `ScriptBanner` / `RankRow` / `WindowToggle` / `Toast`。

## 9. 迁移与回滚

- 旧 Jinja2 模板（`home.html` / `list.html` / `live.html` / `_layout.html` / `_topbar_tools.html`）在 SPA 上线后废弃删除；admin 模板保留。
- 上线需一次构建 + 重启服务（上海 VPS）。回滚 = 切回旧 commit 的 SSR 路由。

## 10. 待确认 / 开放项

- 红色主色为暂定，最终色值上线前可微调。
- 标签自动配色具体策略（中性 vs 哈希取色）实现时定，视觉影响小。
- 全部烂梗分页：本期翻页，无限滚动留作后续。
- 粉丝牌「团松子」目前仅用于标题文案；是否在投稿人署名处再用粉丝牌等级，待定。
