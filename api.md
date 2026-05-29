# sb6657.cn 后端接口清单

> 采集时间：2026-05-22
> Base URL：`https://hguofichp.cn:10086/machine`
> 协议：HTTPS（非 443 端口，10086）
> 统一响应壳：`{ "code": 200, "msg": "请求成功", "data": ... }`（RuoYi/Spring Boot 风格）
> 鉴权：以下接口均**无需鉴权**即可在浏览器中直接调用（前端从首页就发起这些请求）

## 接口一览

| # | Path | 方法 | 用途 | data 结构 |
|---|------|------|------|-----------|
| 1 | `/dictList` | GET | 标签字典 | `Array<DictItem>` |
| 2 | `/hotBarrageOf24H` | GET | 24h 热门弹幕 TOP10 | `Array<HotBarrage>` |
| 3 | `/getRandOne` | GET | 随机一条烂梗 | `Barrage` |
| 4 | `/Page` | GET | 烂梗分页列表 | `{ list: Barrage[], total, lastPage }` |
| 5 | `/getShieldWordDict` | GET | 屏蔽词列表 | `Array<string>` |
| 6 | `/SysMessage/getMsgNum` | GET | 站内未读消息数 | number |
| 7 | `/InProgressMatch` | GET | 当前进行中的大型赛事 | `Match \| null` |
| 8 | `/WordCloud` | GET | 词云 TOP-N | `{ [idx]: { name, value } }` |

---

## 1. `GET /dictList` — 标签字典

```http
GET https://hguofichp.cn:10086/machine/dictList
```

**返回字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| dictCode | null | 占位，未使用 |
| dictLabel | string | 标签显示名（"喷玩机器"/"NiKo"…） |
| dictValue | string | 两位字符串编码（`00`、`01`、`27`…） |
| dictType | string | 固定 `machine_tags` |
| iconUrl | string \| null | 标签头像 URL（部分为 imgdb.cn / 5eplay OSS） |

**样本（节选）**

```json
[
  {"dictLabel":"喷玩机器","dictValue":"00","dictType":"machine_tags","iconUrl":null},
  {"dictLabel":"NiKo","dictValue":"07","dictType":"machine_tags",
   "iconUrl":"https://pic1.imgdb.cn/item/67d3ddcb88c538a9b5bd4c86.png"},
  {"dictLabel":"Falcons","dictValue":"20","dictType":"machine_tags",
   "iconUrl":"https://oss.5eplay.com/.../cm0k2q4conkqks63d37g.png?..."}
]
```

**当前全部 27 个标签**

```
00 喷玩机器  01 喷选手   02 加一       03 QUQU      05 木柜子
06 群魔乱舞  07 NiKo     08 ropz       09 直播间互喷 10 Donk
11 伟伟      12 ZywOo    13 m0NESY     14 丰川祥子   15 device
16 Twistzz   17 DOTA     18 千早爱音   19 三角初华   20 Falcons
21 S1mple    22 赛事梗   23 京介       24 HLTV       25 Team Spirit
26 chopper   27 🗿🗿🗿
```

> 注意：`04` 缺失，应是历史删除标签。

---

## 2. `GET /hotBarrageOf24H` — 24h 热门弹幕

```http
GET https://hguofichp.cn:10086/machine/hotBarrageOf24H
```

**返回字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | null | 占位 |
| barrageId | string | 弹幕 ID（与 `Page` 接口里的 `id` 对应） |
| barrage | string | 弹幕内容 |
| cnt | string | 24h 命中数（被复制 / 引用次数） |
| tags | string | 逗号分隔的 dictValue（如 `"06,07,22"` = 群魔乱舞+NiKo+赛事梗） |
| hotDateTime | string | 最近一次命中的时间 ISO8601 |

**样本（TOP1）**

```json
{
  "barrageId":"20220",
  "barrage":"我最讨厌的就是事后道歉😡👊🏻（猛砸桌）...",
  "cnt":"126",
  "tags":"02",
  "hotDateTime":"2026-05-22T09:07:54"
}
```

---

## 3. `GET /getRandOne` — 随机一条

```http
GET https://hguofichp.cn:10086/machine/getRandOne
```

返回结构同分页接口的 `Barrage`：

```json
{
  "id": 9043,
  "barrage": "玉鸟丶ququ:注销注销注销注销注销...",
  "cnt": "47",
  "tags": "03",
  "submitTime": "2025-05-25T02:43:38"
}
```

> 首页右侧「随机一条烂梗 / 换一换」按钮即调用此接口。

---

## 4. `GET /Page` — 弹幕分页

```http
GET https://hguofichp.cn:10086/machine/Page?pageNum=1&pageSize=20
```

**Query 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| pageNum | int | 页码，从 1 开始 |
| pageSize | int | 每页条数 |

未验证但通常会有的过滤参数（前端「全部烂梗」页可筛选）：

- `tags` —— dictValue，例如 `tags=07` 只看 NiKo
- `keyword` —— 内容关键字
- `orderBy` —— `submitTime` / `cnt`

**返回字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| data.list | Barrage[] | 当前页内容 |
| data.total | int | 总条数（当前 20194） |
| data.lastPage | bool | 是否最后一页 |

**Barrage 结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 弹幕 ID |
| barrage | string | 内容（≤255 字，前端投稿框限制） |
| cnt | string | 累计命中数 |
| tags | string | 逗号分隔的 dictValue |
| submitTime | string | 投稿时间 ISO8601 |

**样本**

```json
{
  "list":[{
    "id":20227,
    "barrage":"给不熟悉的解释一下，玩神的同事里枫哥是枫花恋...",
    "cnt":"43",
    "tags":"00",
    "submitTime":"2026-05-20T21:20:23"
  }],
  "total":20194,
  "lastPage":false
}
```

---

## 5. `GET /getShieldWordDict` — 屏蔽词

```http
GET https://hguofichp.cn:10086/machine/getShieldWordDict
```

**返回**：`string[]`，17 条（截至采集时刻），样本前 5 条：

```json
["sb","navi","av","博彩","485"]
```

> 用途：用户投稿前前端可比对，提示哪些词在斗鱼直播间会被屏蔽。

---

## 6. `GET /SysMessage/getMsgNum` — 未读消息数

```http
GET https://hguofichp.cn:10086/machine/SysMessage/getMsgNum
```

返回当前用户的站内未读消息数（未登录时通常为 `0`）。
首页右上角「消息 N」徽标驱动它。

---

## 7. `GET /InProgressMatch` — 进行中赛事

```http
GET https://hguofichp.cn:10086/machine/InProgressMatch
```

**用途**：决定首页投稿框「关联赛事库」复选框是否可用。
- 无赛事时：`data: null`，前端显示「当前无正在进行的大型赛事」，复选框 disabled。
- 有赛事时：返回赛事元数据（队伍、阶段等），投稿会被同时归档到对应赛事库。

---

## 8. `GET /WordCloud` — 词云

```http
GET https://hguofichp.cn:10086/machine/WordCloud
```

**返回**：以索引为 key 的对象（不是数组，注意），每个 value 是 `{ name, value }`，按权重降序：

```json
{
  "0":{"name":"中国队","value":"50.0"},
  "1":{"name":"不愧是主播的父亲,57也是66哒","value":"48.0"},
  "2":{"name":"松子","value":"39.0"}
}
```

约返回 TOP100 词。
首页右下角「搜索词云」按钮驱动它。

---

## 配套静态资源 / 第三方依赖

| 用途 | URL |
|------|-----|
| 油猴脚本下载 | `https://cdn.hguofichp.cn/sb6657.cn%E6%96%97%E9%B1%BC%E7%8E%A9%E6%9C%BA%E5%99%A8%E7%83%82%E6%A2%97%E6%94%B6%E9%9B%86.user.js` |
| 标签头像图床 | `pic.imgdb.cn` / `pic1.imgdb.cn` |
| 选手 / 战队头像 | `oss.5eplay.com`（复用 5EPlay CDN） |
| 用户行为埋点 | `e.clarity.ms/collect`（Microsoft Clarity） |
| 第三方统计（503） | `api.tongjiniao.com/c` |
| Cloudflare 防护 | `sb6657.cn/cdn-cgi/challenge-platform`、`cdn-cgi/rum` |

---

## 用 curl 一次性试一遍

```bash
BASE="https://hguofichp.cn:10086/machine"
curl -s "$BASE/dictList"          | jq '.data | length'           # → 27
curl -s "$BASE/Page?pageNum=1&pageSize=1" | jq '.data.total'      # → 20194
curl -s "$BASE/hotBarrageOf24H"   | jq '.data | length'           # → 10
curl -s "$BASE/getRandOne"        | jq '.data'
curl -s "$BASE/getShieldWordDict" | jq '.data'
curl -s "$BASE/WordCloud"         | jq 'keys | length'            # → ~101
curl -s "$BASE/InProgressMatch"   | jq '.data'                    # → null
```

---

## 风险提示

1. 这些接口**完全开放无鉴权**，便于扒库，但如果作为同类站点参考，公开部署前建议加：
   - Referer / Origin 白名单
   - 投稿接口的人机验证（图形验证码 / Turnstile）
   - 每 IP 速率限制
2. **未观察到的接口**（推测存在，前端走交互才触发）：
   - `POST /submit`（投稿）
   - `POST /copy` 或 `POST /addCnt`（点击复制时累加 cnt）
   - `POST /login` / `POST /register` / `GET /captcha`
   - `POST /ai/chat`（AI 造梗）
   - `GET /comment`、`POST /comment`（贴吧）
   - `GET /tampermonkey/version`（油猴脚本版本检查）
   如需补全，再走一遍 Network Tab 抓即可。
