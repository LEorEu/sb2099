# sb6657 API 接口快照

> 2026-05-23 Playwright MCP 实测（访问 https://sb6657.cn → /memes/AllBarrage）
> 作为 sb2099 设计文档 §14 字段兼容的事实依据；非 sb6657 官方文档。

## 概要

- **前端**：`https://sb6657.cn/`（Vue SPA，#hash 路由）
- **后端 API host**：`https://hguofichp.cn:10086/machine/`（独立后端，不在主域）
- **响应包络**：`{code: int, msg: str, data: ...}` 统一

## 端点清单

### 1. `GET /machine/dictList` — tag 字典

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": [
    {"dictCode": null, "dictLabel": "喷玩机器", "dictValue": "00",
     "dictType": "machine_tags", "iconUrl": null},
    {"dictCode": null, "dictLabel": "加一", "dictValue": "02",
     "dictType": "machine_tags",
     "iconUrl": "https://pic1.imgdb.cn/item/67d4204f88c538a9b5bdac11.png"},
    ...
  ]
}
```

字段：
- `dictValue`: 两位字符串 ID（`"00"`-`"27"`，跳过 `"04"`）
- `dictLabel`: 显示名
- `iconUrl`: 头像图，可空
- `dictType`: 固定 `"machine_tags"`

实测 sb6657 当前 27 个 tag（强耦合 6657 房间内容，sb2099 不复制）：
`喷玩机器/喷选手/加一/QUQU/木柜子/群魔乱舞/NiKo/ropz/直播间互喷/Donk/伟伟/Zywoo/m0NESY/丰川祥子/device/Twistzz/DOTA/千早爱音/三角初华/Falcons/S1mple/赛事梗/京介/HLTV/Team Spirit/chopper/🗿🗿🗿`

### 2. `GET /machine/Page?pageNum=N&pageSize=K` — 分页投稿库

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": {
    "list": [
      {"id": 20307, "barrage": "...", "cnt": "14",
       "tags": "02,06", "submitTime": "2026-05-22T15:33:57"},
      ...
    ],
    "total": 20274,
    "lastPage": false
  }
}
```

字段：
- `id`: int 数字 ID
- `barrage`: 弹幕原文（sb2099 用 `content`）
- `cnt`: **字符串**数字 `"14"`（sb2099 用 INTEGER）
- `tags`: CSV 字符串 `"02,06"`（sb2099 同形态）
- `submitTime`: ISO datetime 无时区

### 3. `GET /machine/hotBarrageOf24H` — 24 小时热门

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": [
    {"id": null, "barrageId": "19580", "barrage": "...",
     "cnt": "423", "tags": "00", "hotDateTime": "2026-05-23T16:21:02"},
    ...
  ]
}
```

字段：
- `id`: **null**（sb6657 自身反规范）
- `barrageId`: **字符串**形式的 ID（注意类型不同于分页端点的 `id`）
- `hotDateTime`: 进入热门榜的时间，非投稿时间

### 4. `GET /machine/getRandOne` — 随机一条

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": {"id": 1138, "barrage": "...", "cnt": "524",
           "tags": "00", "submitTime": "2024-11-06T01:22:17"}
}
```

字段同分页单条。

## 其它端点（sb2099 不实现）

- `/machine/getShieldWordDict` — 屏蔽词收集（sb2099 不做该板块）
- `/machine/SysMessage/getMsgNum` — 站内消息（sb2099 无用户系统）
- `/machine/InProgressMatch` — 赛事数据（sb2099 不做赛事）
- `/machine/WordCloud` — 词云（sb2099 与"直播热门列表"重合，砍）

## 字段类型差异与互导对照

参见 `设计文档.md` §14。
