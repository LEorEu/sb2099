"""sb2099.users 纯逻辑单测：ic 解码、头像 URL、名册聚合(含改名/缺头像场景)。"""
from __future__ import annotations

from sb2099.users import avatar_url, build_roster, decode_ic, extract_ic

# 取自真实 dgb raw 的片段
_GIFT_RAW = (
    "type@=dgb/rid@=12740109/uid@=289960812/nn@=FAZECLAN的小春本人/"
    "ic@=avatar_v3@S202605@Sae210238499746029399fc6c82c7f70a/level@=36/gfn@=陪伴印章/"
)


def test_decode_ic_unescapes_path():
    assert decode_ic("avatar_v3@S202605@Sae21abc") == "avatar_v3/202605/ae21abc"
    assert decode_ic("") is None
    assert decode_ic(None) is None


def test_extract_ic_from_raw():
    assert extract_ic(_GIFT_RAW) == "avatar_v3/202605/ae210238499746029399fc6c82c7f70a"
    assert extract_ic("type@=dgb/uid@=1/nn@=x/") is None  # 没有 ic 字段
    assert extract_ic(None) is None


def test_avatar_url_sizes():
    p = "avatar_v3/202605/ae21"
    assert avatar_url(p) == "https://apic.douyucdn.cn/upload/avatar_v3/202605/ae21_middle.jpg"
    assert avatar_url(p, "small").endswith("_small.jpg")
    assert avatar_url(p, "big").endswith("_big.jpg")
    assert avatar_url(None) is None


def test_build_roster_takes_latest_nickname():
    # uid=1 改名：旧名 ts=100，新名 ts=300（乱序喂入）
    rows = [
        ("1", "旧名", None, 100),
        ("1", "新名", None, 300),
        ("1", "中间名", None, 200),
    ]
    roster = build_roster(rows)
    assert roster["1"]["nickname"] == "新名"
    assert roster["1"]["first_seen_ms"] == 100
    assert roster["1"]["last_seen_ms"] == 300


def test_build_roster_avatar_from_gift_raw():
    rows = [("289960812", "小春", _GIFT_RAW, 500)]
    roster = build_roster(rows)
    assert roster["289960812"]["avatar"] == "avatar_v3/202605/ae210238499746029399fc6c82c7f70a"


def test_build_roster_keeps_avatar_when_newer_event_lacks_ic():
    # 先一条带头像的礼物(ts=100)，再一条没 ic 的订阅(ts=200)：头像不应被覆盖成空
    rows = [
        ("7", "甲", _GIFT_RAW, 100),
        ("7", "甲", "type@=dfobc/uid@=7/nick@=甲/", 200),
    ]
    roster = build_roster(rows)
    assert roster["7"]["avatar"] == "avatar_v3/202605/ae210238499746029399fc6c82c7f70a"
    assert roster["7"]["last_seen_ms"] == 200


def test_build_roster_skips_empty_uid():
    rows = [("", "x", None, 1), (None, "y", None, 2), ("3", "z", None, 3)]
    roster = build_roster(rows)
    assert set(roster) == {"3"}
