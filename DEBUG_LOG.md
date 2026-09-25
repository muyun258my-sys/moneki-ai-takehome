# DEBUG_LOG

记录 starter 代码里的缺陷（L1 数据清洗、L2 检索链路，以及 review 补充的健壮性与安全缺陷）。
每条按「现象 → 假设 → 验证 → 根因 → 修复 → 回归测试」展开。

---

## #1 加载层只收 .md / .markdown

- **现象**：KB-022（英文 .txt）、KB-061（.html）、KB-062（GBK .txt）从未被加载，R03/R04/R05、C03/C04/C05 必挂。
- **假设**：`SUPPORTED_SUFFIXES` 只写了 `.md`/`.markdown`。
- **验证**：改成 `.md/.markdown/.txt/.html/.htm` 后，`load_knowledge_base` 从 25 篇变 35 篇。
- **根因**：`starter/kbqa/loader.py` 的 `SUPPORTED_SUFFIXES`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_loader_loads_all_docs`。

## #2 GBK 文件按 UTF-8 读成乱码

- **现象**：KB-062 是旧 OA 导出的 GBK 文件，按 `utf-8 errors="ignore"` 读会丢字符，quote 无法逐字匹配。
- **假设**：需要 UTF-8 失败后回退 GB18030（兼容 GBK）。
- **验证**：改后 KB-062 里能读到「营业时间」「23:00」。
- **根因**：`starter/kbqa/loader.py` 的 `decode_bytes`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_gbk_decode`。

## #3 HTML 保留了 script/style/标签

- **现象**：KB-061 整页 HTML 入库，噪声淹没正文，quote 也不是可见文本。
- **假设**：需要剥掉 script/style 和所有标签再 unescape。
- **验证**：改后 KB-061 不含 `<script>/<style>/<table`，正文能读到「小程序」。
- **根因**：`starter/kbqa/loader.py` 的 HTML 分支。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_html_stripped`。

## #4 meta 写 `state`、检索读 `status`

- **现象**：`Document.meta()` 把状态写在 `"state"` 键，`retriever._eligible` 读 `meta.get("status")`，已废止判断永不生效。
- **假设**：两处键名不一致。
- **验证**：统一成 `status` 后，`meta()["status"]` 正确返回「已废止/现行」。
- **根因**：`starter/kbqa/loader.py` 的 `Document.meta()`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_retrieval_gold[R08]`（现行 KB-011 胜出旧版 KB-010）。

## #5 content_key 不含 KB 内容

- **现象**：缓存键只哈希三个版本号，KB 内容变了缓存也不失效（旧键 `8651fac326e2` 一直被沿用）。
- **假设**：键里要纳入每个文件的名字 + 内容哈希。
- **验证**：加入文件内容哈希后，键变为 `3da60e58c32c`，评委换 KB 会触发重建。
- **根因**：`starter/kbqa/index.py` 的 `content_key`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py` 构建索引时隐式覆盖（键随内容变化）。

## #6 `.cache/index.json` 被提交且过期

- **现象**：仓库里提交了一份 25 篇/53 块的旧索引，缺 KB-011/013/022/025/026/027/028/029/061/062。
- **假设**：缓存不该入库。
- **验证**：把 `.cache/` 加入 `.gitignore` 并 `git rm --cached`，删除过期文件，索引改为运行时重建。
- **根因**：`starter/.gitignore` 漏了 `.cache/`。
- **修复**：本次提交。
- **回归测试**：无（产物文件，非逻辑）。

## #7 rebuild 没传 rebuild=True

- **现象**：`make rebuild` 调 `load_index` 时没带 `rebuild=True`，缓存命中就直接用，评委换 KB 后看不到新内容。
- **假设**：重建命令必须强制重建。
- **验证**：改传 `rebuild=True` 后，重建命令每次都重算索引。
- **根因**：`starter/kbqa/rebuild.py`。
- **修复**：本次提交。
- **回归测试**：无（命令行路径）。

## #8 中文没有 bigram

- **现象**：`tokenize` 只按空白切，整句中文变成一个 token，BM25 基本失效。
- **假设**：中文要切成重叠二元组，英文/数字按词切。
- **验证**：`tokenize("外卖订单") == ["外卖", "卖订", "订单"]`。
- **根因**：`starter/kbqa/tokenizer.py` 的 `tokenize`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_tokenizer_bigram` + R01–R15。

## #9 chunker 丢末段、不产表格块

- **现象**：`range(0, len-300, 300)` 丢掉末尾不足 300 字的一段；从不产出 `kind="table"` 的块，而 `units.py` 依赖它做表格引用。
- **假设**：末段要保留；Markdown 表格要单独成块并带 `table_header`。
- **验证**：700 字正文切成 300/300/100；表格文档（KB-003/040/042 等）产出 table 块。
- **根因**：`starter/kbqa/chunker.py` 的 `chunk_document`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_chunker_tail_and_table`。

## #10 allowed 没排除 excluded

- **现象**：`allowed = set(range(len(chunks)))` 无视被元数据过滤掉的文档，废版本文档照样参与打分。
- **假设**：先按 `excluded` 算出 allowed 块集合，再打分、取 top_k。
- **验证**：改后 R08（问现行储值）只返回现行版，旧版不再抢位。
- **根因**：`starter/kbqa/retriever.py` 的 `search`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_retrieval_gold[R08]`。

## #11 doc_id 张冠李戴

- **现象**：`hit.doc_id = ordered[len(hits)].doc_id` 把引用挂到错误的文档上（按排序位置而不是命中块）。
- **假设**：`_hit()` 已经从 `chunk.doc_id` 正确取了 doc_id，这一行是多余的覆盖。
- **验证**：删掉后 top-5 的 doc_id 与命中的块一致。
- **根因**：`starter/kbqa/retriever.py` 的 `search` 内多余赋值。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_retrieval_gold`。

## #12 先取 top_k 再过滤 excluded

- **现象**：最后才 `hits = [h for h in hits if h.doc_id not in excluded]`，导致返回条数少于 top_k，违反 `results_count`。
- **假设**：把排除前置到 `allowed`（同 #10），末段过滤可以删掉。
- **验证**：`len(results) == 5` 恒成立，且不含被过滤文档。
- **根因**：`starter/kbqa/retriever.py` 的 `search`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_retrieval_gold`（断言恰好 5 条）。

---

## #13 数据清洗根本没做

- **现象**：`/api/health` 里 `valid_sales_rows = 18628`、`cleaning_report.removed` 六项全为 0；`data_period` 显示 `start="" / end="N/A"`。M01–M06、N01 全部对不上。
- **假设**：原始 `clean_rows` 只是把 sales 原样搬进 clean 表，金额解析不了就按 0、日期照抄字符串，没有任何规范化和剔除。
- **验证**：用 `data/pos.db` 独立复算，得到 日期 8 行无法解析、空金额 150、qty≤0 30、门店外键 10、商品外键 40、完全重复 100，合计 338，保留 18290；与 KB-001 口径和题库期望一致。
- **根因**：`starter/kbqa/cleaning.py` 的 `clean_rows`（旧实现），以及 `build_clean_db` 没有把 stores/products 的合法编号传给清洗函数。
- **修复**：commit `0c0e881`（新增 `parse_date`，重写 `clean_rows` 按 6 步剔除，`build_clean_db` 传入外键集合）。
- **回归测试**：`tests/test_cleaning.py::test_cleaning_report`、`::test_valid_sales_rows`，以及 `tests/test_api.py::test_health_cleaning_report`。修复前 `valid_sales_rows` 为 18628（红），修复后为 18290（绿）。

---

## #14 结束日期用了 `date < ?`（漏掉月末最后一天）

- **现象**：HANDOVER 里写「月末数对不上」；直接查 6 月全店 net_revenue 少了 3874（报告里 M01 实际 152883 vs 期望 156757）。
- **假设**：区间过滤把结束日当成开区间，`end` 当天被漏掉。
- **验证**：把 `_where` 的 `date < ?` 改成 `date <= ?` 后，M01 的 net_revenue/orders/qty 全部对上。
- **根因**：`starter/kbqa/tools.py` 的 `DataTools._where`（`date < ?`）。
- **修复**：commit `0c0e881`。
- **回归测试**：`tests/test_cleaning.py::test_query_metrics_values`（M01 闭区间断言）。

---

## #15 指标口径全错（退款恒 0、订单按行数、销量不扣退款）

- **现象**：`/api/metrics/summary` 的 `refund_amount` 恒为 0；M01 期望 refund 953 实际 0、orders 期望 4311 实际 4272、qty 期望 6496 实际 6360。
- **假设**：`query_metrics` 写死了 `is_refund = 0`，且订单用 `COUNT(*)`、qty 直接 `SUM(qty)`，没按 KB-001 §4（退款计入净营业额、订单去重 order_id、销量扣退款）算。
- **验证**：改成按金额符号聚合后，M01–M05 全部与题库期望一致。
- **根因**：`starter/kbqa/tools.py` 的 `DataTools.query_metrics`（旧 SQL 带 `AND is_refund = 0`、`0`、`COUNT(*)`、`SUM(qty)`）。
- **修复**：commit `0c0e881`。
- **回归测试**：`tests/test_cleaning.py::test_query_metrics_values`、`::test_query_metrics_empty_range`。

---

## #16 run_sql 能执行任意 SQL 并 commit（可删库）

- **现象**：`run_sql` 直接 `execute(sql)` 然后 `commit()`，S02/S03 安全题可以借此真的删除数据。
- **假设**：清洗表连接没有只读保护，工具也没有 SQL 白名单。
- **验证**：改只读连接后 `DELETE FROM sales_clean` 抛 `OperationalError: attempt to write a readonly database`；`run_sql("DELETE ...")` 返回 `error`。
- **根因**：`starter/kbqa/tools.py` 的 `DataTools.run_sql`（任意 SQL + `commit()`）。
- **修复**：本次提交（`run_sql` 加只读校验、去掉 `commit()`）。
- **回归测试**：`tests/test_cleaning.py::test_run_sql_rejects_write`、`::test_open_readonly_blocks_write`。

---

## #17 open_readonly 名不副实（没有 mode=ro）

- **现象**：源库 `pos.db` 和查询用的 `clean.db` 都经 `open_readonly` 打开，但底层是读写连接。
- **假设**：函数名是「只读」，但 `sqlite3.connect(path)` 默认可写。
- **验证**：改成 `file:...?mode=ro` URI 后，写操作在 SQLite 层直接失败。
- **根因**：`starter/kbqa/cleaning.py` 的 `open_readonly`（未用 `mode=ro`）。
- **修复**：本次提交。
- **回归测试**：`tests/test_cleaning.py::test_open_readonly_blocks_write`。

---

## #18 金额为 0 的行被当成销售行（review 第 3 条）

- **现象**：指标 SQL 用 `is_refund = 0` 判断「销售行」，但 `is_refund` 是 `amount < 0` 的补集，会把 `amount = 0` 的行也算进订单数和销量。KB-001 §4 定义销售行是 `amount > 0`。
- **假设**：当前数据没有 `amount = 0` 的行，所以本地看不出错；评委换数据后可能出错。
- **验证**：把销售行判定改成 `amount_cents > 0`、退款改成 `amount_cents < 0`，qty 用三分支 CASE 排除 0 金额行；M01–M06 仍全部一致。
- **根因**：`starter/kbqa/tools.py` 的 `query_metrics` / `daily_metrics` / `payment_mix` / `top_products` / `first_sale_date` / `unit_price_check` 里的 `is_refund = 0`。
- **修复**：本次提交。
- **回归测试**：`tests/test_cleaning.py::test_query_metrics_values` 等（金额符号聚合的既有断言）。

---

## #19 金额/数量为 Infinity、NaN 会崩（review 第 4、6 条）

- **现象**：`parse_amount` 对 `Infinity`/`NaN` 抛 `OverflowError`（未捕获），`parse_qty` 对小数额（`2.5`→2）和科学计数（`1e2`→100）静默截断。
- **假设**：`Decimal` 能表示 Infinity/NaN，`int()` 转换时抛 `OverflowError`；`int(Decimal("2.5"))` 直接截断。
- **验证**：`parse_amount("Infinity")` 修复前崩溃，修复后返回 `(None, "bad")`；`parse_qty("2.5")`/`("1e2")`/`("Infinity")` 修复后返回 `None`。
- **根因**：`starter/kbqa/cleaning.py` 的 `parse_amount`（缺 `is_finite` 检查）、`parse_qty`（`int(Decimal(...))` 截断）。
- **修复**：本次提交（`parse_amount` 加 `is_finite` + 捕获 `OverflowError`；`parse_qty` 改为严格 `int(text)`）。
- **回归测试**：`tests/test_cleaning.py::test_parse_amount`、`::test_parse_qty`。

---

## #20 启动时 clean.db 存在就不重建（review 第 9 条）

- **现象**：`Service.__init__` 用 `rebuild(only_if_missing=True)`，clean.db 已存在时不会重建；评委换 `data/` 后直接启动会读到旧清洗表。
- **假设**：清洗表重建很便宜，没必要跳过。
- **验证**：改成启动时无条件重建后，`/api/health` 与指标始终反映当前 `data/pos.db`。
- **根因**：`starter/kbqa/service.py` 的 `Service.rebuild`（clean.db 重建被 `only_if_missing` 挡住）。
- **修复**：本次提交。
- **回归测试**：`tests/test_api.py::test_health_cleaning_report`（HTTP 路径读取的清洗表与源库一致）。

---

## #21 `/api/health` 的 kb_docs 统计了全部文件

- **现象**：`kb_docs` 用 `rglob` 数文件得到 36，把 `knowledge_base/README.md` 也算进去；契约要求只统计已建索引的 KB-xxx 文档（35）。
- **假设**：应该直接取 `len(self.index.docs_meta)`。
- **验证**：改后 `/api/health` 返回 `kb_docs=35`。
- **根因**：`starter/kbqa/service.py` 的 `Service.health`。
- **修复**：本次提交。
- **回归测试**：`tests/test_api.py::test_health_ok`（断言 `kb_docs == 35`）。
