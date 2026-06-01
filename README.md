# sb2099

斗鱼 2099 房间（真实房间号 `12740109`，主播"一团肉松子"）烂梗收集与一键发送站。

> **合规声明**：本项目与上游  `Hyacinth Sentry` 项目的合规声明保持一致：仅服务自有直播间。；仅记录 IP 哈希（`sha256(ip+salt)[:16]`），原始弹幕 30 天后归档；不接广告、不转售数据、不上报第三方。

## 形态

- 三页主站（Vue3 SPA）：首页 `/`、全部烂梗 `/barrage`、热门弹幕 `/live`
- 后台 `/admin/*`：审核、设置、统计
- 油猴脚本：直播间内消费投稿库，单条复制/发送

详见 `设计文档.md` 与 `refs/sb6657-api-snapshot.md`。

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# 复制 .env.example 为 .env 并填入真实 token
copy .env.example .env

alembic upgrade head
uvicorn sb2099.web.app:app --reload
```

## 前端（Vue3 SPA）

面向用户的三页是 Vite + Vue3 + TypeScript 的单页应用，源码在 `sb2099/web/frontend/`；后端 FastAPI 退成纯 JSON API（`/api/*`），admin 后台仍走 Jinja2。

```powershell
cd sb2099/web/frontend
npm install
npm run dev          # Vite dev server，自动 proxy /api、/admin、/userscript、/static 到 127.0.0.1:8000
# 另开一个终端跑后端： uvicorn sb2099.web.app:app --reload
```

构建（部署前必须）：

```powershell
cd sb2099/web/frontend
npm run build        # 产出 dist/，由 FastAPI 以 SPA 回退方式托管
```

- 前端测试：`npm run test`（Vitest）。
- `dist/` 与 `node_modules/` 不入库；部署时在服务器上 `npm run build`。
- 后端通过环境变量 `SB2099_FRONTEND_DIST` 可覆盖 dist 路径（默认 `sb2099/web/frontend/dist`）。

## 工程硬约束

- 单 `.py` 文件 > 300 行视为信号，拆分
- `ingest/` 与 `web/` 只通过 DB 通讯，互不引用代码
- `normalize.py` 纯函数，无外部依赖
- 抓取层不在本地导入 hyacinth_sentry 代码；通过 WebSocket 客户端订阅 `ws://139.196.96.110:8080/ws/live`
- 反滥用规则（`live_noise_filters`、`submission_review_rules`）必须从 `setting` 表读取，禁止硬编码

## 测试

```powershell
pytest -q
```
