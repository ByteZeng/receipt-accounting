"""金额与日期归一化。

财务金额一律用 Decimal，不用 float——0.1 + 0.2 那类误差在对账表里会变成客户投诉。
每个函数都返回 (值, 备注)，备注非空说明有需要人工留意的地方，会一路带到输出表格里。
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

CN_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5,
    "陆": 6, "柒": 7, "捌": 8, "玖": 9, "两": 2,
}

_AMOUNT_STRIP = re.compile(r"[¥￥$\s,，元圆RMBrmb]")
_AMOUNT_VALID = re.compile(r"^-?\d+(\.\d+)?$")


def normalize_amount(raw) -> Tuple[Optional[Decimal], str]:
    """把模型输出的金额字符串转成 Decimal，保留两位小数。"""
    if raw is None:
        return None, "金额缺失"

    text = str(raw).strip()
    if not text:
        return None, "金额缺失"

    cleaned = _AMOUNT_STRIP.sub("", text)
    cleaned = cleaned.replace("。", ".")  # 手写单据里句号常被当小数点

    if not _AMOUNT_VALID.match(cleaned):
        return None, f"金额格式无法解析：{text}"

    try:
        value = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, f"金额格式无法解析：{text}"

    if value < 0:
        return value, "金额为负，请确认是否为退货或红冲"
    return value, ""


def _cn_year(text: str) -> Optional[int]:
    digits = [CN_NUM[c] for c in text if c in CN_NUM]
    if len(digits) == 4:
        return int("".join(str(d) for d in digits))
    return None


def _cn_number(text: str) -> Optional[int]:
    """解析「十二」「二十」「三十一」这类月份日期写法。"""
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CN_NUM.get(left, 1) if left else 1
        ones = CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    return CN_NUM.get(text)


_DATE_PATTERNS = [
    # 2026-08-12 / 2026/8/12 / 2026.8.12
    re.compile(r"(?P<y>\d{4})\s*[-/.年]\s*(?P<m>\d{1,2})\s*[-/.月]\s*(?P<d>\d{1,2})"),
    # 20260812
    re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})$"),
    # 26-08-12 两位年份
    re.compile(r"^(?P<y2>\d{2})\s*[-/.]\s*(?P<m>\d{1,2})\s*[-/.]\s*(?P<d>\d{1,2})$"),
    # 8/12 缺年份
    re.compile(r"^(?P<m>\d{1,2})\s*[-/.月]\s*(?P<d>\d{1,2})\s*日?$"),
]

_CN_DATE = re.compile(
    r"(?P<y>[零一二三四五六七八九〇]{4})?\s*年?\s*"
    r"(?P<m>[一二三四五六七八九十]{1,3})\s*月\s*"
    r"(?P<d>[一二三四五六七八九十]{1,3})\s*日"
)


def normalize_date(raw, fallback_year: int) -> Tuple[Optional[str], str]:
    """转成 ISO 格式 YYYY-MM-DD。缺年份时用 fallback_year 补，并在备注里说明。"""
    if raw is None:
        return None, "日期缺失"

    text = str(raw).strip()
    if not text:
        return None, "日期缺失"

    note = ""
    year = month = day = None

    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = match.groupdict()
        month, day = int(parts["m"]), int(parts["d"])
        if parts.get("y"):
            year = int(parts["y"])
        elif parts.get("y2"):
            year = 2000 + int(parts["y2"])
        else:
            year = fallback_year
            note = f"单据未写年份，按 {fallback_year} 补全，请确认"
        break

    if year is None:
        match = _CN_DATE.search(text)
        if match:
            month = _cn_number(match.group("m"))
            day = _cn_number(match.group("d"))
            year = _cn_year(match.group("y") or "") or fallback_year
            if not match.group("y"):
                note = f"单据未写年份，按 {fallback_year} 补全，请确认"

    if year is None or month is None or day is None:
        return None, f"日期格式无法解析：{text}"

    try:
        return date(year, month, day).isoformat(), note
    except ValueError:
        return None, f"日期不合法：{text}"
