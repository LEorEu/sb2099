# sb2099 · 团松子烂梗收集站

> 一个给斗鱼 **2099 房间（主播"一团肉松子"）** 观众自娱自乐的小工具 —— 把直播间里好笑的烂梗收进仓库，回头搜一下、点一下复制，再回直播间一键刷屏。

直播间的烂梗稍纵即逝，好不容易刷起来的活儿过会儿就忘了、想再发又想不起原文。本项目不是再做一个弹幕窗口，而是替家人们 **攒梗 + 找梗 + 发梗**：投稿入库、按热度/标签检索、本地收藏夹同步到油猴脚本，在直播间网页里直接一键发送。

线上：<https://www.sb2099.cn/>

---

## 目录

- [免责声明](#免责声明)
- [界面预览](#界面预览)
- [核心能力](#核心能力)
- [快速开始](#快速开始)
- [配置项](#配置项)
- [使用说明](#使用说明)
- [维护命令](#维护命令)
- [技术栈](#技术栈)
- [Roadmap](#roadmap)
- [已知问题](#已知问题)
- [致谢](#致谢)
- [License](#license)

---

## 免责声明

> [!WARNING]
> 本项目仅供 **一团肉松子** 直播间观众自娱自乐：收集、检索、复用 **本房间** 的烂梗弹幕。请勿用于其他直播间的数据采集、二次分发或商业用途。

> [!IMPORTANT]
> 抓取层匿名直连 `danmuproxy.douyu.com:8601`，只入指定房间的公开广播组。落库前对来访 IP 做 `sha256(ip + salt)[:16]` 匿名化；原始弹幕仅短期留存（默认 2 天）后聚合归档；不接广告、不转售数据、不上报第三方。

> [!CAUTION]
> 部署到公网前，**必须设置 `SB2099_ADMIN_TOKEN` 与 `SB2099_IP_SALT`** 两个环境变量。二者无默认值，未设置时服务启动即报错退出，以免后台被任意访问。

---

## 界面预览

线上体验入口：<https://www.sb2099.cn/>（浅色为主，右上角可切深色）。

- **首页** —— 门面 + 投稿 + 今日一梗 + 油猴脚本入口
- **全部烂梗** —— 梗仓库：关键字搜索 + 标签筛选 + 单列列表 + 本地收藏夹抽屉
- **热榜** —— 直播现场实时热门弹幕：今日 Top 10 / 近 7 天 Top 50

---

## 核心能力

### 全部烂梗 —— 梗仓库

- 关键字 **子串搜索**（FTS5 trigram，中文友好），按 **最热 / 最新** 排序。
- 标签为开放词表（主播 / 选手 / 互动 / 其他 + 观众投票新增），单条烂梗可挂多个标签、同行铺开。
- 每条显示 **被复制次数** 做热度参考；一键复制即记一次。
- 次要操作（补标签 / 举报不合适）收进 `⋯` 浮层，不抢主操作。

### 热榜 —— 现场实时热门

- 抓取层实时统计当前直播间在刷的弹幕，自动合并复读、降噪过滤。
- 今日 / 近 7 天两个时间窗；前三名高亮，显示 **发送次数 + 去重人数**。
- 看到值得长期留着的，点「**收进梗库**」补标签即可提升入正式库；已入库的标 `✓`。

### 投稿与审核 —— 防刷不防玩

- 任何人可投稿（≤ 255 字，自动查重 + 违禁词校验）；可选「我是谁」按 **斗鱼粉丝牌** 署名，留空即匿名。
- 投稿成功后 **60 秒内可撤回**（HMAC cookie + IP 一致校验）。
- 内置反作弊探测器（房间未见 / 30 天不活跃 / 多 IP 命中）命中转人工 **待审**；阈值与开关全走 `setting` 表，可后台热调。
- 后台 `/admin/*`：审核、设置、统计、标签管理、回收站。

### 收藏夹 —— 跨设备搬家

- 纯浏览器 `localStorage`，分组管理，**与油猴脚本互通**；换设备用导出 / 导入 JSON 搬。

### 油猴脚本 —— 直播间里一键发

- 在斗鱼 2099 房间网页左侧嵌入烂梗弹窗，关键字模糊搜索 + 本地收藏 + 单条一键发送。

---

## 快速开始

### 环境要求

- Python ≥ 3.11
- Node ≥ 18（仅构建前端时需要）
- 一台可访问公网的服务器或本机（出站连接 `danmuproxy.douyu.com:8601` 与 `www.douyu.com`）

### 1. 拉代码并装后端依赖

```powershell
git clone https://github.com/LEorEu/sb2099.git
cd sb2099
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Linux / macOS 用户把激活命令换成 `source .venv/bin/activate`。

### 2. 配置环境变量

```powershell
copy .env.example .env
# 编辑 .env，至少填入 SB2099_ADMIN_TOKEN 与 SB2099_IP_SALT
# 生成随机值： python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. 建库

```powershell
alembic upgrade head
```

### 4. 构建前端（Vue3 SPA）

面向用户的三页是 Vite + Vue3 + TypeScript 单页应用，构建产物由后端直接托管。

```powershell
cd sb2099/web/frontend
npm install
npm run build      # 产出 dist/，FastAPI 以 SPA 回退方式托管
cd ../../..
```

### 5. 启动服务

```powershell
python -m uvicorn sb2099.web.app:app --host 0.0.0.0 --port 8090
```

浏览器访问 `http://localhost:8090/` 即可。后端在同一端口同时提供 SPA 与 `/api/*`，无需另配 nginx 静态目录。

> [!NOTE]
> **本地开发**可前后端分离：`npm run dev` 起 Vite（自动 proxy `/api`、`/userscript` 到 8090），另开一个终端跑 uvicorn。改前端热更新，不必每次 build。后台 `/admin/*` 现在也是同一套 SPA 的路由（数据走 `/api/admin`），由 Vite 直接接管。

---

## 配置项

| 变量 | 必填 | 默认 | 说明 |
|---|:---:|---|---|
| `SB2099_ADMIN_TOKEN` | ✅ | — | 后台登录 Token；无默认值，未设置启动报错退出 |
| `SB2099_IP_SALT` | ✅ | — | IP 哈希盐，用于 `sha256(ip + salt)[:16]` 落库前匿名化 |
| `DOUYU_ROOM_ID` | 否 | `12740109` | 直播间号（短号 2099 对应真实房间 12740109） |
| `SB2099_DB_PATH` | 否 | `./sb2099.db` | SQLite 文件路径 |
| `SB2099_FRONTEND_DIST` | 否 | `sb2099/web/frontend/dist` | 前端构建产物目录，后端据此托管 SPA |

> 运行期的阈值、降噪词、留存天数、限流、反作弊开关等均以 `setting` 表为准（首次启动由 `config.py` 的 `DEFAULTS` 种子化），可在后台热调，不必改代码。

---

## 使用说明

### 观众 vs 后台

| 能力 | 观众（默认） | 后台（登录后） |
|---|:---:|:---:|
| 搜索 / 复制 / 收藏烂梗 | ✅ | ✅ |
| 投稿 / 给热榜条目「收进梗库」 | ✅ | ✅ |
| 给烂梗投票补标签 / 举报 | ✅ | ✅ |
| 审核待审稿 / 改设置 / 看统计 / 管标签 | ❌ | ✅ |

> [!NOTE]
> 后台在 `/admin/`，用 `SB2099_ADMIN_TOKEN` 登录。普通观众无需任何账号，全部数据匿名（仅存 IP 哈希）。

### 油猴脚本

1. 浏览器先装 **Tampermonkey**。
2. 打开站点右上角「装脚本」（即 `/userscript`），在弹出页点「安装」。
3. 刷新斗鱼 2099 房间页，左侧出现烂梗弹窗，搜词 → 一键发送。

---

## 维护命令

运维脚本放在 `tools/`。

```powershell
# daily_hot 回填 / 重归一化（改了 normalize 规则或留存策略后用；建议先停服务）
python -m tools.renorm_raw
```

> [!NOTE]
> daily_hot 由原始弹幕按直播日（**凌晨 4 点切分**）滚动重算；归档会清理 2 天前的 raw 与 7 天前的 daily_hot，控制库体积。相关脚本与参数见 `tools/` 与 `docs/`。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · [FastAPI](https://fastapi.tiangolo.com/)（纯 JSON API，含 `/api` 公开端点与 `/api/admin` 后台端点）· SQLite（WAL + FTS5 trigram）· Alembic |
| 前端 | [Vue 3](https://vuejs.org/) · [Vite](https://vitejs.dev/) · TypeScript · Pinia · vue-router（公开三页 **+ `/admin` 后台**同属一套 SPA，由后端回退托管） |
| 抓取 | asyncio TCP，直连 `danmuproxy.douyu.com:8601`，匿名多 gid 入组 |
| 反滥用 | `setting` 表驱动的降噪 / 审核 / 限流 / 反作弊规则，禁止硬编码 |
| 脚本 | Tampermonkey 用户脚本，直播间内消费投稿库 |

---

## Roadmap

- [x] 三页主站（首页 / 全部烂梗 / 热榜）+ 后台审核
- [x] FTS5 trigram 中文子串搜索 + 标签多选筛选
- [x] daily_hot 留存机制（raw 2 天 / daily_hot 7 天，控库体积）
- [x] 投稿 60s 撤回 + 反作弊待审 + 标签投票 / 提议
- [x] 用户名册 + 粉丝牌署名
- [x] **前端 Vue3 + Vite 重写**（浅色 / 深色，FastAPI 退纯 API）
- [x] **后台并入 Vue SPA**（`/admin` 同栈复用主题/组件，旧 Jinja2 后台与 `/static` 资源已下线，全部走 `/api/admin`）
- [x] 标签投票 / 提议的完整前端交互（`MemeRow` 的「补个标签」→ `AddTagPanel`，对接 `vote-tag` / `propose-tag`）
- [ ] 全部烂梗无限滚动（当前翻页）

> 设计文档与实现计划保留在 `docs/superpowers/`，不随发布对外承诺。

---

## 已知问题

- **本地库为空时**首页「今日一梗」与「刚有人投了这些」为空态、`/api/random` 返回 404（前端已兜底文案），需投稿或抓取积累后才有数据。
- **热榜依赖实时抓取**：直播间没人说话或刚启动还没采到时为空。
- **收藏夹仅存浏览器本地**：清缓存即丢，跨设备需手动导出 / 导入。

---

## 致谢

抓取协议层参考了以下对斗鱼弹幕协议的逆向工程开源项目：

- [qianjiachun/douyu-monitor](https://github.com/qianjiachun/douyu-monitor)
- [qianjiachun/douyuEx](https://github.com/qianjiachun/douyuEx)

姊妹项目（主播自用第二屏）：[LEorEu/hyacinth-sentry-douyu](https://github.com/LEorEu/hyacinth-sentry-douyu)

---

## License

[MIT](./LICENSE)
