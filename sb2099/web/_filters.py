"""Jinja2 模板过滤器:UTC naive datetime / SQLite TEXT → CST 显示字符串。

数据库存的是 UTC naive datetime,SQLite 通过 text() 查询返回的是 str。
统一交给 `cst` filter:截掉微秒,转 +8 时区,输出 `MM-DD HH:MM`(或带年的长格式)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

__all__ = ["register_filters"]


def _to_dt(v) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        head = v.split(".", 1)[0]  # 去微秒
        try:
            return datetime.fromisoformat(head)
        except ValueError:
            return None
    return None


def _cst(v, fmt: str = "%m-%d %H:%M") -> str:
    dt = _to_dt(v)
    if dt is None:
        return ""
    return (dt + timedelta(hours=8)).strftime(fmt)


def _cst_long(v) -> str:
    return _cst(v, "%Y-%m-%d %H:%M")


def register_filters(templates) -> None:
    """注册 cst / cst_long 到 Jinja2Templates.env.filters。"""
    templates.env.filters["cst"] = _cst
    templates.env.filters["cst_long"] = _cst_long
