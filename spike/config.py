"""spike 运行参数。所有可调项集中在此，不散落到业务代码里。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

SAMPLES_DIR = Path(os.getenv("SAMPLES_DIR", BASE_DIR / "samples"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / ".cache"))

GROUND_TRUTH_CSV = BASE_DIR / "ground_truth.csv"
RESULTS_JSON = OUTPUT_DIR / "results.json"
RESULTS_XLSX = OUTPUT_DIR / "results.xlsx"

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.getenv("MODEL", "qwen-vl-max")

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# 低于此置信度的字段标黄，要求人工复核。
# 0.75 是起点，实测后应按「静默出错率」回调：静默出错多就调高。
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# 供应商名靠手写辨认，容易差一两个字，按相似度判定而非严格相等。
SUPPLIER_MATCH_RATIO = float(os.getenv("SUPPLIER_MATCH_RATIO", "0.85"))

# 明细合计与单据总额的容差（元）。超出即视为结构校验失败。
AMOUNT_TOLERANCE = os.getenv("AMOUNT_TOLERANCE", "0.02")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# 单据无年份时用于补全，一般填样本所属月份。
FALLBACK_YEAR = int(os.getenv("FALLBACK_YEAR", "2026"))


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
