"""用户名册的纯逻辑：从斗鱼 raw 弹幕/礼物消息里提取 uid→昵称+头像。

头像在斗鱼协议里是 `ic` 字段，存的是一段路径(如 avatar_v3/202605/xxx)，
完整图片地址要套 CDN 模板 + 尺寸。本模块只做解析与名册聚合，不碰 DB，
方便 seed 导入脚本与将来自有弹幕回填共用、也方便单测。
"""
from __future__ import annotations

from typing import Iterable

# 斗鱼头像 CDN；size ∈ {small, middle, big}
_AVATAR_CDN = "https://apic.douyucdn.cn/upload/{path}_{size}.jpg"


def decode_ic(ic: str | None) -> str | None:
    """斗鱼 ic 字段还原成头像路径。

    斗鱼对字段值里的特殊字符做了一级转义：`@S`→`/`、`@A`→`@`。
    头像路径形如 avatar_v3@S202605@Sxxx → avatar_v3/202605/xxx。空值返回 None。
    """
    if not ic:
        return None
    return ic.replace("@S", "/").replace("@A", "@") or None


def extract_ic(raw: str | None) -> str | None:
    """从一条 raw 弹幕/礼物消息里取头像路径(已解码)，无则 None。

    raw 用 `/` 分隔字段、`@=` 分隔键值；ic 值里真正的 `/` 已被转义成 `@S`，
    所以按 `/` 切分不会切碎头像路径。
    """
    if not raw:
        return None
    for part in raw.split("/"):
        if part.startswith("ic@="):
            return decode_ic(part[4:])
    return None


def avatar_url(path: str | None, size: str = "middle") -> str | None:
    """头像路径 → 完整 URL。size ∈ {small, middle, big}。path 为空返回 None。"""
    if not path:
        return None
    return _AVATAR_CDN.format(path=path, size=size)


def build_roster(
    rows: Iterable[tuple[str | None, str | None, str | None, int]],
) -> dict[str, dict]:
    """把事件行聚合成 uid → 名册条目。

    rows: (uid, nickname, raw, ts_ms)，顺序任意。
    返回 {uid: {nickname, avatar, first_seen_ms, last_seen_ms}}，其中
    nickname / avatar 取「时间最新且非空」的那条——用户改名后只要再出现过，
    名字/头像就是新的；某类事件缺 ic(如订阅)也不会把已有头像覆盖成空。
    """
    roster: dict[str, dict] = {}
    for uid, nickname, raw, ts in rows:
        if not uid:
            continue
        ic = extract_ic(raw)
        cur = roster.get(uid)
        if cur is None:
            roster[uid] = {
                "nickname": nickname,
                "avatar": ic,
                "first_seen_ms": ts,
                "last_seen_ms": ts,
            }
            continue
        cur["first_seen_ms"] = min(cur["first_seen_ms"], ts)
        if ts >= cur["last_seen_ms"]:
            cur["last_seen_ms"] = ts
            if nickname:
                cur["nickname"] = nickname
            if ic:
                cur["avatar"] = ic
        else:
            # 更早的事件：仅在当前为空时回填，不覆盖较新的值
            if cur["nickname"] is None and nickname:
                cur["nickname"] = nickname
            if cur["avatar"] is None and ic:
                cur["avatar"] = ic
    return roster
