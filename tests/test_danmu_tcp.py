"""sb2099/ingest/danmu_tcp.py 的纯函数测试（不真连斗鱼）。"""
from __future__ import annotations

import struct

from sb2099.ingest import danmu_tcp


def test_encode_frame_structure():
    body = "type@=mrkl/"
    frame = danmu_tcp._encode(body)
    # 头 12 字节 + body + \x00
    assert len(frame) == 12 + len(body.encode("utf-8")) + 1
    total_len, total_len_dup, msg_type, enc, res = struct.unpack_from("<IIHBB", frame, 0)
    assert total_len == total_len_dup
    assert total_len == 4 + 2 + 1 + 1 + len(body.encode("utf-8")) + 1
    assert msg_type == 689
    assert enc == 0 and res == 0
    assert frame.endswith(b"\x00")


def test_iter_frames_split_partial_and_multi():
    """缓冲跨界 + 多包应能正确切分。"""
    f1 = danmu_tcp._encode("type@=chatmsg/uid@=1/")
    f2 = danmu_tcp._encode("type@=mrkl/")
    buf = bytearray(f1 + f2[:5])  # 第二个 frame 只到一半
    bodies = list(danmu_tcp._iter_frames(buf))
    assert len(bodies) == 1
    assert "chatmsg" in bodies[0]
    # 剩余应是 f2 的前 5 字节
    assert len(buf) == 5
    buf.extend(f2[5:])
    bodies2 = list(danmu_tcp._iter_frames(buf))
    assert len(bodies2) == 1
    assert "mrkl" in bodies2[0]
    assert len(buf) == 0


def test_parse_kv_basic_and_escape():
    body = "type@=chatmsg/uid@=986064247/nn@=昵称带@S/ic@=avatar_v3@S202605@Sxxx/"
    kv = danmu_tcp._parse_kv(body)
    assert kv["type"] == "chatmsg"
    assert kv["uid"] == "986064247"
    # @S → /
    assert kv["nn"] == "昵称带/"
    assert kv["ic"] == "avatar_v3/202605/xxx"


def test_chatmsg_to_event_full_fields():
    kv = {
        "type": "chatmsg",
        "uid": "12345",
        "nn": "测试昵称",
        "txt": "测试弹幕",
        "col": "7",
        "ic": "avatar_v3/202604/abc",
        "level": "37",
        "bnn": "一团肉松子",
        "brid": "12740109",
        "bl": "17",
        "dms": "8",
    }
    evt = danmu_tcp._chatmsg_to_event(kv, 12740109)
    assert evt is not None
    assert evt["uid"] == "12345"
    assert evt["nickname"] == "测试昵称"
    assert evt["content"] == "测试弹幕"
    assert evt["color"] == 7
    assert evt["ic"] == "avatar_v3/202604/abc"
    assert evt["level"] == 37
    assert evt["bnn"] == "一团肉松子"
    assert evt["bl"] == 17
    assert evt["kind"] == "chat"
    assert evt["room_id"] == 12740109


def test_chatmsg_to_event_drops_missing():
    """uid 或 txt 缺失应返回 None。"""
    assert danmu_tcp._chatmsg_to_event({"type": "chatmsg", "uid": "1"}, 100) is None
    assert danmu_tcp._chatmsg_to_event({"type": "chatmsg", "txt": "hi"}, 100) is None


def test_to_int_handles_blank_and_invalid():
    assert danmu_tcp._to_int(None) is None
    assert danmu_tcp._to_int("") is None
    assert danmu_tcp._to_int("abc") is None
    assert danmu_tcp._to_int("42") == 42
