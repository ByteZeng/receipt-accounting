"""调用多模态模型抽取单据字段。

提示词的设计目标不是「尽可能填满字段」，而是「不确定时必须承认」。
CIKM 2026 的 OmniHandwritingOCR 基准发现主流生成式模型会把模糊数字
补成看起来合理的值而不报告不确定——在对账场景里这是最危险的失败模式，
因为错误不会暴露。因此提示词里反复强制忠实转录、允许留空。
"""

import base64
import json
import mimetypes
import random
import re
import time
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

import config

SYSTEM_PROMPT = """\
你是单据信息抽取器，服务于财务对账。你的唯一职责是转录图片中肉眼可见的内容。

铁律（违反任何一条都会造成对账错误）：
1. 只转录你实际看到的字符。禁止推理、禁止补全、禁止纠正。
2. 若某字段看不清、被涂改覆盖、被遮挡或超出画面，该字段 value 必须为 null，
   confidence 必须低于 0.4，并在 notes 中说明原因。留空是正确行为，猜测是错误行为。
3. 即使发现数字前后矛盾（例如单价乘数量不等于小计），也要照抄单据原值，
   不要修正成「合理」的数字。矛盾请写进 notes，由人工判断。
4. 手写数字易混对（1/7、3/8、0/6、4/9）若无法确定是哪一个，视为看不清，按第 2 条处理。
5. confidence 表达你对该字段转录准确性的真实判断，不是礼貌性的高分。
   字迹清晰工整才给 0.9 以上；能认但需要辨认给 0.5~0.8；勉强猜测一律低于 0.4。

金额格式：只输出数字和小数点，不要货币符号、不要千分位逗号。
日期格式：按单据原样输出，不要自行补全年份。

严格输出以下 JSON，不要任何解释文字、不要 markdown 代码块：
{
  "doc_type": "进货单 | 运费物流 | 固定开支 | 其他 | 无法判断",
  "date":     {"value": "单据日期或null", "confidence": 0.0},
  "supplier": {"value": "供应商或收款方名称或null", "confidence": 0.0},
  "doc_no":   {"value": "单据号或null", "confidence": 0.0},
  "total_amount": {"value": "合计金额或null", "confidence": 0.0},
  "line_items": [
    {"name": "品名", "qty": "数量或null", "unit_price": "单价或null",
     "amount": "小计或null", "confidence": 0.0}
  ],
  "illegible": true 或 false,
  "notes": "异常、矛盾、看不清的具体说明；无异常填空字符串"
}

illegible 在整张单据严重模糊或大部分字段无法辨认时填 true。"""

USER_PROMPT = "请抽取这张单据的信息，严格按系统提示的 JSON 格式返回。"

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.API_KEY:
            raise RuntimeError(
                "未配置 DASHSCOPE_API_KEY。复制 .env.example 为 .env 并填入 Key。"
            )
        _client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.BASE_URL,
            timeout=config.REQUEST_TIMEOUT,
        )
    return _client


def encode_image(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _parse_json(text: str) -> Dict[str, Any]:
    """模型偶尔会裹 markdown 代码块或加前后缀，这里做容错剥离。"""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def extract(path: Path) -> Dict[str, Any]:
    """识别单张单据。失败时按指数退避重试，最终失败抛出异常由上层记录。"""
    client = get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": encode_image(path)}},
                {"type": "text", "text": USER_PROMPT},
            ],
        },
    ]

    last_error = None
    for attempt in range(config.MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=0.0,  # 抽取任务不需要多样性
            )
            content = response.choices[0].message.content or ""
            parsed = _parse_json(content)
            usage = response.usage
            parsed["_usage"] = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
            }
            return parsed
        except Exception as exc:  # 网络抖动、限流、JSON 不合法都走重试
            last_error = exc
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(2**attempt + random.random())

    raise RuntimeError(f"{path.name} 识别失败（重试 {config.MAX_RETRIES} 次）：{last_error}")
