---
id: receipt-accounting-project
type: domain
tags: [单据核算, 商务项目, OCR, 跨境电商]
updated: 2026-09-04
---

# 单据自动汇总核算服务

给跨境内衣卖家做的本地财务核算工具。需求方主业为 **Temu / 速卖通全托管**（兼 TK 自营与代发）。一期从单据识别切入；完整目标对齐其现有账本：提货、出库、退供、提现、支出、工资与代发。

**GitHub（私有）**：https://github.com/ByteZeng/receipt-accounting

**当前状态**：已根据 `src/` 案例图将大表改为全托管口径（v2）。待需求方按表映射并确认「东棠/风棠」身份、平台扣费是否拆分等问题；并行可测手写送货单 OCR。

## 结论摘要

全托管下「出库 ≠ 收入，提现 ≈ 回款，退供必须独立成表」。计量上必须保留包数 × 件装数 = 件数，并支持分码单价与袋子费。详见案例研判与映射指引。

技术上单据识别无攻关点；准确率仍是 OCR 主风险。商业上建议先体验版验证再产品化。

## 文件导航

- [docs/ledger-templates/mapping-guide.md](docs/ledger-templates/mapping-guide.md) — **给需求方**：全托管口径映射指引。
- [docs/ledger-templates/ledger-workbook.xlsx](docs/ledger-templates/ledger-workbook.xlsx) — **给需求方**：提货/出库/退供/提现/支出/工资与代发模板。
- [docs/ledger-templates/ingest-merge-pipeline.md](docs/ledger-templates/ingest-merge-pipeline.md) — **内部**：手写单/台账如何识别并合并进提货明细。
- [docs/ledger-templates/case-review-quan-tuoguan.md](docs/ledger-templates/case-review-quan-tuoguan.md) — **内部**：`src/` 五份案例研判与改表依据。
- [src/](src/) — 需求方提供的案例图（手写单、台账、出库退供、汇总表）。
- [docs/feasibility-assessment.md](docs/feasibility-assessment.md) — **内部**评估（单据识别一期）。
- [docs/proposal-v2.md](docs/proposal-v2.md) — 对客户方案书（单据识别一期）。
- [docs/quotation.md](docs/quotation.md) — 报价单。
- [docs/sample-request.md](docs/sample-request.md) — 样本索取清单。
- [spike/](spike/) — 识别效果验证脚本。

## 相比客户初稿改了什么

初稿有三处会在验收或第二个月使用时爆发的问题，方案 v2 已全部修正：

1. **「数据不外传」与「用 AI 识别」自相矛盾** — 改为诚实口径。
2. **要客户手工合并多份明细表** — 改为断点续跑自动汇总。
3. **人工复核结果无处存放** — 补充修正持久化。

大表侧（2026-09-04）：按全托管案例从「进货/出货/分包/收支」改为「提货/出库/退供/提现/支出/工资与代发」。

## 下一步

1. 把 `docs/ledger-templates/` 的指引与 Excel 发给需求方，请其用最近一个月数据对号入座并回答指引第七节问题
2. 用 `src/供应商手写单.jpg` 先跑一轮 spike OCR，验证分码包数抽取
3. 根据映射反馈收口字段后，再定自动写入范围（优先：提货、退供、提现）
4. 先推体验版，跑满一个月再谈标准版升级
