# EVAL_REPORT

## 运行环境

- 评测命令：`python eval/run_eval.py --base-url http://localhost:8000 --questions eval/public_questions.jsonl`
- 数据与知识库：仓库默认 `data/`、`knowledge_base/`
- 模型：无 Key 的 `mock` 降级模式（服务仍可完整启动）
- 评测时间：2026-09-26

## 结果

当前 `report.md` 记录的公开题库结果为 **100.00 / 100.00，55 / 55 题通过**。分类结果：

| 类别 | 得分 | 通过 |
| --- | ---: | ---: |
| metrics | 6 / 6 | 6 / 6 |
| retrieval | 15 / 15 | 15 / 15 |
| data | 12 / 12 | 6 / 6 |
| doc | 16 / 16 | 8 / 8 |
| version | 6 / 6 | 3 / 3 |
| hybrid | 18 / 18 | 6 / 6 |
| multi_turn | 9 / 9 | 3 / 3 |
| refusal | 8 / 8 | 4 / 4 |
| safety | 9 / 9 | 3 / 3 |
| health | 1 / 1 | 1 / 1 |

接口快照：`kb_docs=35`、`valid_sales_rows=18290`、数据区间为 `2026-05-01` 至 `2026-08-31`。完整逐题结果见 [report.md](report.md)。

## 前端验收

启动服务后打开 `http://localhost:8000/`，应看到：

1. 日期与门店筛选会同时刷新汇总、趋势图和 Top 10 商品。
2. 数据质量模块显示保留率和逐项剔除原因。
3. “问问数据”打开问答对话框；每轮回答可继续打开同一轮 Trace。
4. Trace 面板显示计划、检索、工具调用、回答阶段、耗时和错误。
