"""对比人工标注与识别结果，产出可直接进合同的准确率数字。

三个关键指标：
  字段级准确率   - 决定验收标准写多少
  静默出错率     - 模型答错却给了高置信度的比例，这是真正的风险敞口
  需复核比例     - 换算成客户每月还要花多少时间，谈判时最好懂的数字

用法：python eval_accuracy.py
"""

import csv
import json
import sys
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import config
from normalize import normalize_amount, normalize_date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FIELDS = [("date", "日期"), ("supplier", "供应商"), ("amount", "金额")]
_PUNCT = " \t（）()·、,，.。-_/"


def load_truth() -> Dict[str, Dict[str, str]]:
    if not config.GROUND_TRUTH_CSV.exists():
        raise SystemExit(
            f"缺少人工标注文件 {config.GROUND_TRUTH_CSV}\n"
            "请先照抄单据原值填写，格式见 ground_truth.csv 模板。"
        )
    with config.GROUND_TRUTH_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    truth: Dict[str, Dict[str, str]] = {}
    for row in rows:
        name = (row.get("file") or "").strip()
        if not name:
            continue
        truth[name] = {key: (row.get(key) or "").strip() for key, _ in FIELDS}
    if not truth:
        raise SystemExit("ground_truth.csv 里没有有效行")
    return truth


def load_results() -> List[Dict[str, Any]]:
    if not config.RESULTS_JSON.exists():
        raise SystemExit(f"缺少识别结果 {config.RESULTS_JSON}，请先运行 run_ocr.py")
    return json.loads(config.RESULTS_JSON.read_text(encoding="utf-8"))


def clean(text: str) -> str:
    return "".join(c for c in text if c not in _PUNCT).lower()


def same_supplier(predicted: Optional[str], expected: str) -> bool:
    if not predicted:
        return False
    left, right = clean(predicted), clean(expected)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    return SequenceMatcher(None, left, right).ratio() >= config.SUPPLIER_MATCH_RATIO


def same_amount(predicted: Optional[str], expected: str) -> bool:
    if not predicted:
        return False
    want, _ = normalize_amount(expected)
    try:
        got = Decimal(predicted)
    except Exception:
        return False
    return want is not None and got == want


def same_date(predicted: Optional[str], expected: str) -> bool:
    if not predicted:
        return False
    want, _ = normalize_date(expected, config.FALLBACK_YEAR)
    return want is not None and predicted == want


COMPARE = {"date": same_date, "supplier": same_supplier, "amount": same_amount}
CONFIDENCE_KEY = {
    "date": "date_confidence",
    "supplier": "supplier_confidence",
    "amount": "amount_confidence",
}


def evaluate() -> Tuple[Dict[str, Any], List[str]]:
    truth = load_truth()
    results = {row["file"]: row for row in load_results()}
    # 标注一般只写文件名，识别结果带相对路径，这里按文件名兜底匹配
    by_name = {row["file"].replace("\\", "/").split("/")[-1]: row for row in results.values()}

    stats = {
        key: {"total": 0, "correct": 0, "silent_error": 0, "flagged": 0}
        for key, _ in FIELDS
    }
    guessed_illegible = 0
    illegible_total = 0
    matched = 0
    missing: List[str] = []
    lines: List[str] = []

    for name, expected in truth.items():
        row = results.get(name) or by_name.get(name.replace("\\", "/").split("/")[-1])
        if row is None:
            missing.append(name)
            continue
        matched += 1

        problems = []
        for key, label in FIELDS:
            want = expected[key]
            got = row.get(key)
            confidence = float(row.get(CONFIDENCE_KEY[key]) or 0.0)
            flagged = confidence < config.CONFIDENCE_THRESHOLD

            if not want:
                # 人都认不出：不计入准确率，但要看模型有没有硬猜
                illegible_total += 1
                if got and not flagged:
                    guessed_illegible += 1
                    problems.append(f"{label} 人工无法辨认，模型却给出 {got}（置信度 {confidence:.2f}）")
                continue

            stats[key]["total"] += 1
            if flagged:
                stats[key]["flagged"] += 1

            if COMPARE[key](got, want):
                stats[key]["correct"] += 1
            else:
                if not flagged:
                    stats[key]["silent_error"] += 1
                    problems.append(
                        f"{label} 应为 {want}，识别为 {got}，置信度 {confidence:.2f} 未预警"
                    )
                else:
                    problems.append(f"{label} 应为 {want}，识别为 {got}（已标黄）")

        if problems:
            lines.append(f"{name}\n    " + "\n    ".join(problems))

    review = sum(1 for row in results.values() if row.get("needs_review"))
    return (
        {
            "matched": matched,
            "missing": missing,
            "stats": stats,
            "review": review,
            "result_total": len(results),
            "illegible_total": illegible_total,
            "guessed_illegible": guessed_illegible,
        },
        lines,
    )


def main() -> None:
    summary, problem_lines = evaluate()
    stats = summary["stats"]

    print()
    print("=" * 60)
    print(f"参与评估 {summary['matched']} 张（识别结果共 {summary['result_total']} 张）")
    if summary["missing"]:
        print(f"标注了但没有识别结果：{', '.join(summary['missing'])}")
    print("-" * 60)

    total_fields = total_correct = total_silent = 0
    for key, label in FIELDS:
        item = stats[key]
        if not item["total"]:
            print(f"{label}：无可评估样本")
            continue
        accuracy = item["correct"] / item["total"]
        silent = item["silent_error"] / item["total"]
        total_fields += item["total"]
        total_correct += item["correct"]
        total_silent += item["silent_error"]
        print(
            f"{label}：准确率 {accuracy:.1%}"
            f"（{item['correct']}/{item['total']}）"
            f"  静默出错 {silent:.1%}"
            f"  已标黄 {item['flagged']} 项"
        )

    print("-" * 60)
    if total_fields:
        print(f"整体字段级准确率：{total_correct / total_fields:.1%}")
        print(f"整体静默出错率：{total_silent / total_fields:.1%}  <- 合同风险主要看这个")
    if summary["matched"]:
        rate = summary["review"] / summary["result_total"]
        print(f"需人工复核单据：{summary['review']} 张（{rate:.0%}）")
        print(f"按月 300 张推算：约 {rate * 300:.0f} 张需复核")
    if summary["illegible_total"]:
        print(
            f"人工无法辨认字段 {summary['illegible_total']} 项，"
            f"其中模型硬猜 {summary['guessed_illegible']} 项"
        )
    print("=" * 60)

    if problem_lines:
        print("\n逐张问题清单（可直接整理给客户）：\n")
        for line in problem_lines:
            print(line)
    else:
        print("\n没有发现字段错误。")

    print(
        "\n判读参考："
        "\n  金额准确率 >= 92% 且静默出错率 <= 3%  -> 可按标准版报价，验收写 92%"
        "\n  金额准确率 85%~92%                    -> 可做，但需补图片预处理或双模型交叉，工期 +2~3 人天"
        "\n  金额准确率 < 85% 或静默出错率 > 8%    -> 不要接全自动方案，改半自动录入，否则必然客诉"
    )


if __name__ == "__main__":
    main()
