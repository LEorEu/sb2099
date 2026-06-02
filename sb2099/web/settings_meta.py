"""后台「运行时参数设置」的展示元数据 + 解析/渲染工具。

旧 Jinja 后台与新 /api/admin JSON 接口共用同一份元数据，避免两处漂移。
kind:
  "int"   → 单个整数
  "lines" → 每行一条字符串，存为 JSON 数组
"""
from __future__ import annotations

import json

__all__ = [
    "SETTING_META",
    "SETTING_KEYS",
    "SETTING_KIND",
    "render_setting_text",
    "parse_setting_input",
    "typed_setting_value",
]


SETTING_META: list[dict[str, object]] = [
    {
        "key": "live_hot_min_unique_senders_24h",
        "label": "直播热门门槛(24h 不同发送者人数)",
        "desc": "24h 内有多少不同账号刷过同一条弹幕,才允许进入热门榜",
        "kind": "int",
        "default": 3,
        "hint": "整数,建议 3 – 10",
    },
    {
        "key": "live_hot_min_length",
        "label": "直播热门最短字数",
        "desc": "归一化后短于此长度,或全是数字/标点/emoji 的弹幕直接进入「过滤」分组",
        "kind": "int",
        "default": 2,
        "hint": "整数,建议 2 – 4",
    },
    {
        "key": "live_hot_max_length",
        "label": "直播热门最长字数",
        "desc": "归一化后长于此字数直接进入「过滤」分组(防止超长复制刷屏)。设为 0 表示不限",
        "kind": "int",
        "default": 80,
        "hint": "整数,建议 60 – 120;0 = 不限",
    },
    {
        "key": "live_noise_filters",
        "label": "直播降噪关键词",
        "desc": "弹幕全文完全等于其中任一条时,不进入热门榜",
        "kind": "lines",
        "default": [],
        "hint": "每行一条;采用「整句精确匹配」,不会被子串误伤",
    },
    {
        "key": "live_suffix_strips",
        "label": "直播弹幕尾缀剥除",
        "desc": "归一化时,若弹幕结尾命中其中任一条则剥掉(可连剥多个)。"
                "用于 douyuex 等插件给复制弹幕自动追加的自定义尾缀,使去尾缀后相同的弹幕聚合为同一条。",
        "kind": "lines",
        "default": [],
        "hint": "每行一条尾缀词,如 喵 / Oᴗoಣ;仅在「结尾」命中才剥,剥到只剩尾缀本身则停。改后需「重新聚合」让历史 raw 生效",
    },
    {
        "key": "live_cut_markers",
        "label": "直播弹幕截断标记",
        "desc": "弹幕中只要出现标记词,就从该处截到结尾(标记前无内容则不截)。"
                "专治 douyuex 那种「固定前缀 + 千变万化装饰」的尾巴,只配一个前缀(如 Oᴗoಣ)即可全收,"
                "无需穷举尾缀变体。改后需「重新聚合」让历史 raw 生效。",
        "kind": "lines",
        "default": ["Oᴗoಣ"],
        "hint": "每行一个标记前缀;标记应足够独特(避免误伤正常内容)",
    },
    {
        "key": "submission_review_rules",
        "label": "投稿待审关键词",
        "desc": "投稿正文包含任一关键词时,先进入 pending 等管理员审核",
        "kind": "lines",
        "default": [],
        "hint": "每行一条;子串包含即命中(用于违禁词等强风险词)",
    },
    {
        "key": "barrage_min_length",
        "label": "投稿最少字数",
        "desc": "正文短于此字数会被拒收",
        "kind": "int",
        "default": 4,
        "hint": "整数,建议 1 – 50",
    },
    {
        "key": "barrage_max_length",
        "label": "投稿最多字数",
        "desc": "正文长于此字数会被拒收",
        "kind": "int",
        "default": 255,
        "hint": "整数,建议 ≤ 500",
    },
    {
        "key": "ratelimit_submit_per_hour_per_ip",
        "label": "每 IP 每小时投稿次数上限(匿名)",
        "desc": "未选「我是谁」的匿名投稿，每 IP 每小时上限，超过返回 429",
        "kind": "int",
        "default": 5,
        "hint": "整数",
    },
    {
        "key": "ratelimit_submit_signed_per_hour_per_ip",
        "label": "每 IP 每小时投稿次数上限(已署名)",
        "desc": "选了有效用户署名后的投稿，每 IP 每小时上限（独立计数，通常比匿名宽松）",
        "kind": "int",
        "default": 30,
        "hint": "整数，建议 ≥ 匿名上限",
    },
    {
        "key": "ratelimit_report_per_hour_per_ip",
        "label": "每 IP 每小时「不合适」反馈次数",
        "desc": "针对投稿库条目的负反馈频率上限",
        "kind": "int",
        "default": 60,
        "hint": "整数",
    },
    {
        "key": "ratelimit_copy_per_hour_per_ip",
        "label": "每 IP 每小时复制次数",
        "desc": "复制即累加 cnt;到达上限后该 IP 当小时不再计入",
        "kind": "int",
        "default": 200,
        "hint": "整数",
    },
    {
        "key": "ratelimit_promote_per_hour_per_ip",
        "label": "每 IP 每小时「提升入库」次数",
        "desc": "从直播热门往投稿库补 tag 提升的频率上限",
        "kind": "int",
        "default": 5,
        "hint": "整数",
    },
    {
        "key": "raw_retention_days",
        "label": "原始弹幕保留天数",
        "desc": "raw_danmaku 表保留窗口;archive_cron 每日 04:00 删早于该窗口的行",
        "kind": "int",
        "default": 30,
        "hint": "整数",
    },
]

SETTING_KEYS = [m["key"] for m in SETTING_META]
SETTING_KIND = {m["key"]: m["kind"] for m in SETTING_META}


def render_setting_text(raw_db_value: str | None, kind: str) -> str:
    """把数据库里 JSON 序列化后的值反序列化成 textarea 显示文本（旧 Jinja 后台用）。"""
    if raw_db_value is None or raw_db_value == "":
        return ""
    try:
        parsed = json.loads(raw_db_value)
    except (TypeError, json.JSONDecodeError):
        return raw_db_value
    if kind == "lines":
        if isinstance(parsed, list):
            return "\n".join(str(x) for x in parsed)
        return str(parsed)
    return str(parsed)


def typed_setting_value(raw_db_value: str | None, kind: str) -> object:
    """把数据库值反序列化成结构化类型：int → number，lines → list[str]（JSON 接口用）。"""
    if raw_db_value is None or raw_db_value == "":
        return [] if kind == "lines" else None
    try:
        parsed = json.loads(raw_db_value)
    except (TypeError, json.JSONDecodeError):
        return raw_db_value
    if kind == "lines":
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return [str(parsed)]
    return parsed


def parse_setting_input(raw_value: object, kind: str) -> object:
    """把输入(表单字符串或 JSON 类型)按 kind 解析成要落库的 Python 对象;失败抛 ValueError。

    - int：接受 int 或可转 int 的字符串。
    - lines：接受 list（逐项 strip 去空）或多行字符串（按行 split）。
    """
    if kind == "int":
        if isinstance(raw_value, bool):
            raise ValueError("请输入整数")
        if isinstance(raw_value, int):
            return raw_value
        text_value = str(raw_value).strip()
        if text_value == "":
            raise ValueError("不能为空")
        try:
            return int(text_value)
        except ValueError as e:
            raise ValueError(f"请输入整数(收到: {text_value!r})") from e
    if kind == "lines":
        if isinstance(raw_value, list):
            return [str(x).strip() for x in raw_value if str(x).strip()]
        return [line.strip() for line in str(raw_value).splitlines() if line.strip()]
    raise ValueError(f"未知 kind: {kind}")
