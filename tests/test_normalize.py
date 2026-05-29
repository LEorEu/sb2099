"""normalize() 单测，覆盖 P1-1 冻结的 6 条规则。"""
from __future__ import annotations

import pytest

from sb2099.normalize import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 1) 全角数字字母 → 半角
        ("ＡＢＣ１２３", "ABC123"),
        # 1) 全角标点 → 半角（汉字不动，不补空格）
        ("好啊，真的！", "好啊,真的!"),
        # 2) 零宽字符清理（U+200B 在"机"和"器"之间）
        ("机​器", "机器"),
        ("打‌rl", "打rl"),
        # 3) 空白合并 + strip
        ("  hello   world  ", "hello world"),
        ("tab\there\nthere", "tab here there"),
        # 3) 全角空格也算空白
        ("好的　很好", "好的 很好"),
        # 4) emoji 保留
        ("哦🐍哦", "哦🐍哦"),
        # 5) 繁简不归一（"鸭" 与 "鴨" 应当保留差异）
        ("打鸭", "打鸭"),
        ("打鴨", "打鴨"),
        # 6) 大小写不归一
        ("GG", "GG"),
        ("gg", "gg"),
        # 综合：全角+零宽+空白
        ("　ＡＢ​cd  ｅｆ　", "ABcd ef"),
        # 空字符串
        ("", ""),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_dedup_targets():
    """零宽剥离 + 全/半角统一 → 应当折叠到同一 content_norm。"""
    a = normalize("打​rl")    # 零宽
    b = normalize("打ｒｌ")    # 全角字母
    c = normalize("打​ｒｌ")  # 零宽 + 全角
    assert a == b == c == "打rl"


def test_normalize_keeps_case_distinct():
    """大小写不归一：去重不应合并。"""
    assert normalize("GG") != normalize("gg")


@pytest.mark.parametrize(
    "raw, suffixes, expected",
    [
        # 不传 suffixes → 行为不变（带尾缀不剥、不折叠）
        ("宝宝你好可爱啊Oᴗoಣ", (), "宝宝你好可爱啊Oᴗoಣ"),
        # 传入对应尾缀 → 剥掉
        ("宝宝你好可爱啊Oᴗoಣ", ("Oᴗoಣ",), "宝宝你好可爱啊"),
        ("好好好喵", ("喵",), "好好好"),
        # 剥尾缀后变成严格周期 → 再折叠
        ("宝宝你好可爱啊宝宝你好可爱啊喵", ("喵",), "宝宝你好可爱啊"),
        # 连续剥多个不同尾缀
        ("内容Oᴗoಣ喵", ("喵", "Oᴗoಣ"), "内容"),
        # 连续剥同一尾缀
        ("内容喵喵", ("喵",), "内容"),
        # 保底：整串就是尾缀本身 → 不剥空
        ("喵", ("喵",), "喵"),
        # 尾缀只在中间/开头 → 不动
        ("喵好好", ("喵",), "喵好好"),
        # 尾缀剥除前先做全/半角与零宽归一，仍能命中
        ("好好好ｍ", ("m",), "好好好"),
    ],
)
def test_normalize_strip_suffixes(raw: str, suffixes, expected: str) -> None:
    assert normalize(raw, suffixes=suffixes) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 整串严格周期 → 折叠到最短 base
        ("晚安晚安晚安", "晚安"),
        ("宝宝你好可爱啊宝宝你好可爱啊", "宝宝你好可爱啊"),
        ("🔇😎🔇享受🔇😎🔇享受", "🔇😎🔇享受"),
        ("天才😲👍天才😲👍天才😲👍", "天才😲👍"),
        # 带尾缀 → 不折叠
        ("宝宝你好可爱啊Oᴗoಣ", "宝宝你好可爱啊Oᴗoಣ"),
        ("晚安晚安宝贝", "晚安晚安宝贝"),
        # 偶数倍单字仍可折叠到 2 字 block(等价于"重复字符自身")
        ("啊啊啊啊", "啊啊"),
        ("8888", "88"),
        # 奇数倍 block 长度 1 无法折叠
        ("aaa", "aaa"),
        # 不是严格周期 不折叠
        ("晚安晚安晚", "晚安晚安晚"),
        ("ABABAB", "AB"),  # block "AB" 长度 2,折叠到 AB
        ("ABAB", "AB"),
    ],
)
def test_collapse_repeat(raw: str, expected: str) -> None:
    assert normalize(raw) == expected
