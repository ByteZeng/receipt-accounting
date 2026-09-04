"""不联网自检：验证归一化逻辑与依赖安装。

拿到 API Key 之前先跑这个，确认环境没问题：python selftest.py
"""

import sys
from decimal import Decimal

from normalize import normalize_amount, normalize_date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

AMOUNT_CASES = [
    ("1580", Decimal("1580.00")),
    ("1,580.50", Decimal("1580.50")),
    ("￥326.5", Decimal("326.50")),
    ("880元", Decimal("880.00")),
    ("1234。56", Decimal("1234.56")),  # 手写句号常被当小数点
    ("", None),
    (None, None),
    ("看不清", None),
    ("壹仟元", None),  # 中文大写不解析，交人工
]

DATE_CASES = [
    ("2026-08-12", "2026-08-12"),
    ("2026/8/12", "2026-08-12"),
    ("2026.8.12", "2026-08-12"),
    ("20260812", "2026-08-12"),
    ("26-08-12", "2026-08-12"),
    ("8/12", "2026-08-12"),
    ("8月12日", "2026-08-12"),
    ("2026年8月12日", "2026-08-12"),
    ("二〇二六年八月十二日", "2026-08-12"),
    ("八月十二日", "2026-08-12"),
    ("2026-02-30", None),  # 不存在的日期必须拒绝
    ("", None),
    (None, None),
]


def main() -> None:
    failures = []

    for raw, expected in AMOUNT_CASES:
        got, note = normalize_amount(raw)
        if got != expected:
            failures.append(f"金额 {raw!r} 期望 {expected} 实际 {got}（{note}）")

    for raw, expected in DATE_CASES:
        got, note = normalize_date(raw, 2026)
        if got != expected:
            failures.append(f"日期 {raw!r} 期望 {expected} 实际 {got}（{note}）")

    try:
        import openai  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError as exc:
        failures.append(f"依赖缺失：{exc}。执行 pip install -r requirements.txt")

    total = len(AMOUNT_CASES) + len(DATE_CASES)
    if failures:
        print(f"自检失败 {len(failures)} 项（共 {total} 个用例）：")
        for line in failures:
            print(f"  - {line}")
        sys.exit(1)

    print(f"自检通过：{total} 个归一化用例全部正确，依赖已安装。")
    print("下一步：填好 .env 的 API Key，单据放进 samples/，运行 python run_ocr.py --limit 5")


if __name__ == "__main__":
    main()
