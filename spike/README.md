# 识别效果验证 spike

报价前用来实测客户真实单据的识别准确率。**这不是交付给客户的产品**，是你自己判断「这活能不能接、验收标准写多少、报价报多少」的依据。

跑完能拿到三个直接决定商务条款的数字：字段级准确率、静默出错率、需人工复核比例。

## 为什么必须先跑这一步

手写单据的识别准确率完全取决于客户的字迹和拍摄习惯，不同店能差十几个百分点。不实测就报价，等于把全部准确率风险自己扛下来。

更重要的是测「静默出错率」。CIKM 2026 的 OmniHandwritingOCR 基准发现，主流多模态模型遇到看不清的数字时会**补一个看起来合理的值**而不报告不确定。对账场景里这是最危险的失败模式：错误不会暴露，等客户发现账对不上时，责任在你。本脚本的提示词专门压制这种行为，并把「模型硬猜」单独统计出来。

## 环境准备

Python 3.9 或更高。建议用虚拟环境，避免污染系统 Python：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

之后所有命令用 `.\.venv\Scripts\python.exe` 替代 `python`。

配置 API Key：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，填入阿里云百炼的 API Key（控制台 https://bailian.console.aliyun.com 获取）。新账号有 100 万 token 免费额度，做一轮几十张的测试基本用不到钱。

先跑自检确认环境正常（不联网、不花钱）：

```powershell
.\.venv\Scripts\python.exe selftest.py
```

## 实测流程

**第一步：放样本**

把客户发来的单据图片放进 `samples/`（支持 jpg、png、webp、bmp，可以有子目录）。

样本必须包含潦草的、涂改的、拍模糊的。挑好的测出来数字虚高，实际交付时会翻车。覆盖度要求见 `../docs/sample-request.md`。

**第二步：先跑 5 张试水**

```powershell
.\.venv\Scripts\python.exe run_ocr.py --limit 5
```

确认 Key 有效、输出格式正常，再跑全量。识别结果按图片内容哈希缓存在 `.cache/`，重复运行不会重复计费。

**第三步：跑全量**

```powershell
.\.venv\Scripts\python.exe run_ocr.py
```

产出 `output/results.json` 和 `output/results.xlsx`。表格里置信度低的单元格自动标黄，识别失败的单独一个 sheet。

控制台会打印本次 token 消耗和费用估算，可直接用于报价里的成本测算。

**第四步：人工标注**

```powershell
Copy-Item ground_truth.csv.example ground_truth.csv
```

照抄单据上**肉眼看到的原值**填写。两条铁律：

- **照抄，不修正。** 单据写 `1580` 就填 `1580`，哪怕你知道他算错了。这样才能测出模型是否在擅自纠错。
- **看不清就留空。** 留空表示「人也认不出」，该字段不计入准确率，但脚本会单独统计模型有没有硬猜。

这一步约 1~2 小时，不能省——没有标注就算不出准确率。

**第五步：出评估报告**

```powershell
.\.venv\Scripts\python.exe eval_accuracy.py
```

## 怎么读结果

脚本末尾会给出判读参考，核心是这三条：

- **金额准确率 >= 92% 且静默出错率 <= 3%** — 可按标准版报价，验收标准写 92%
- **金额准确率 85%~92%** — 能做，但需补图片预处理或双模型交叉校验，工期加 2~3 人天，报价相应上调
- **金额准确率 < 85% 或静默出错率 > 8%** — 不要接全自动方案。改成半自动录入（AI 出草稿、人工逐张确认），否则必然客诉

盯静默出错率比盯总体准确率更重要。识别错了但标黄提示是可接受的，错了还很自信才是灾难。

如果准确率不达标，按顺序试：调高 `CONFIDENCE_THRESHOLD` 让更多字段标黄 → 换 `MODEL` 对比 qwen-vl-max 与 plus → 加图片预处理（去背景、增强对比、纠偏）→ 考虑接 TextIn 这类手写专项引擎。

## 文件说明

- `config.py` — 所有可调参数，改这里不用碰业务代码
- `normalize.py` — 金额与日期归一化，金额一律用 Decimal（float 的舍入误差在账表里会变成投诉）
- `ocr_client.py` — 模型调用与提示词，**提示词是整个 spike 的核心**，重点在强制模型承认不确定
- `run_ocr.py` — 主流程：扫描、缓存、并发、结构校验、Excel 输出
- `eval_accuracy.py` — 准确率评估，产出可直接进合同的数字
- `selftest.py` — 不联网自检

## 隐私

`samples/`、`output/`、`.cache/`、`.env`、`ground_truth.csv` 已全部在 `.gitignore` 中排除。客户的真实单据含进货价等经营数据，不要提交到任何版本库，测试结束后按约定删除或归还。
