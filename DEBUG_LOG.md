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

---

## #22 编号紧跟中文时识别不到（`\b` 对中文不成立）

- **现象**：`S04为什么不卖吞拿鱼三明治了`、`S01的7月净营业额` 里门店编号识别不出来；`P06六月` 同理。Python 里中文字符也算单词字符，`\b` 后面没有边界。
- **假设**：把 `\b` 换成精确的 lookaround：前面不能是字母数字、后面不能是数字。
- **验证**：改成 `(?<![a-z0-9])s\d{2}(?![0-9])` 后，`S04为什么`/`S01的`/`P06六月` 都能识别，`S012`/`P061` 不再误匹配。
- **根因**：`loader.py` `_STORE_CODE`、`retriever.py` `_store_concepts`、`entities.py` `find_store`/`find_product`、`aliases.py` `expansions`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_store_code_followed_by_chinese`。

## #23 带 UTF-8 BOM 的文件元数据失效

- **现象**：带 BOM 且标了 `status: 已废止` 的文件，标题变成 `\ufeff---`、状态退回默认「现行」。
- **假设**：`decode_bytes` 用了 `utf-8`，BOM 保留在开头，front matter 解析失效。
- **验证**：改用 `utf-8-sig` 后，BOM 被剥掉，`title`/`status` 正确解析。
- **根因**：`loader.py` 的 `decode_bytes`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_decode_bom`。

## #24 显式点名旧版时旧版取不回来

- **现象**：`储值政策 v1`、`KB-010 写了什么`、`指标口径手册 v2`、`之前的储值政策` 这些问法里旧版文档被过滤掉。
- **假设**：`wants_historical` 只认「以前/旧版」等词，不认 `v1/v2`、`KB-0xx`、`之前`。
- **验证**：加入 `v\d+`、`kb-\d{3}` 正则与「之前/当时」后，四类问法都取回旧版（KB-010/KB-002）。
- **根因**：`entities.py` 的 `HISTORICAL_WORDS` 与 `wants_historical`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_wants_historical_version_refs`。

## #25 /api/retrieve 与问答链路参数不一致

- **现象**：`2025年618` 走 `/api/retrieve` 时 2026 版 KB-023 排第一；问答链路按年份解析给出 KB-024。契约 §4 要求同一套实现。
- **假设**：`/api/retrieve` 没解析年份/时间点/门店，`search` 少了参数。
- **验证**：在 `service.retrieve` 里用 `parse_time` + `find_store` + `wants_historical` 解析并传入后，两边结果一致。
- **根因**：`service.py` 的 `retrieve`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_retriever_year_and_as_of`。

## #26 文件名小写 / 文件头 doc_id 覆盖文件名

- **现象**：文件名是 `kb-xxx` 会被直接跳过；front matter 里的 `doc_id` 会覆盖文件名编号，而契约规定 doc_id 以文件名为准。
- **假设**：`_DOC_ID` 要忽略大小写，doc_id 只取文件名（转大写），不读 front matter。
- **验证**：`kb-013_...` 得到 `KB-013`；`KB-010_...` 配 `doc_id: KB-999` 仍得到 `KB-010`。
- **根因**：`loader.py` 的 `_DOC_ID` 与 `load_document`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_doc_id_from_filename_not_frontmatter`。

## #27 KB-062 标题、KB-061 导航栏文字

- **现象**：KB-062 标题认成 OA 页眉「合味餐饮管理…导出文件」；KB-061 正文里留着「首页/门店/菜单」导航。
- **假设**：标题应优先认「标题：」标记；HTML 应剥掉 nav/header/footer。
- **验证**：改后 KB-062 标题为「关于 Super Souper 门店营业时间调整的通知」，KB-061 不再含「首页/菜单」。
- **根因**：`loader.py` 的 `_title_from_body` 与 `html_to_text`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_kb062_title_and_kb061_nav`。

---

## #28 多轮追问不传 history（L3）

- **现象**：`那 7 月呢？` 被当成没上文的追问反问；T01–T03 多轮题全挂。
- **假设**：`planner.plan(question)` 没把会话历史传进去；`SessionStore` 又忽略 `session_id` 全局串线。
- **验证**：改成 `plan(question, history)` 并把会话按 `session_id` 隔离后，T01/T02/T03 三轮全对。
- **根因**：`service.py` 的 `_answer`、`sessions.py` 的 `SessionStore`。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_multi_turn_session_isolation`。

## #29 异常被吞、trace 看不到原因（L3）

- **现象**：`_answer` 的 `except Exception` 直接返回「抱歉」，trace 里没有真实原因。
- **假设**：异常分支没调 `trace.error`。
- **验证**：补上 `trace.error("answer", exc)` 后，出错时 trace 能定位。
- **根因**：`service.py` 的 `_answer` 异常分支。
- **修复**：本次提交。
- **回归测试**：无独立用例（由 trace 面板覆盖）。

## #30 路由强制覆盖 + two_part 恒 False（L3）

- **现象**：`外卖订单多久内可以申请退款` 被「多少/多久」强制路由成 data；`供应商后来赔了多少` 也是 data；两段式问题从不会合并另一半。
- **假设**：`_choose_kind` 末尾有个「多少→data、为什么→doc」的覆盖块，且 `two_part` 写死 False。
- **验证**：删掉覆盖块、按「有原因 + 有数据」计算 `two_part` 后，C01–C08、H01–H06 全部路由正确。
- **根因**：`planner.py` 的 `_choose_kind`。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_doc_citation`、`::test_hybrid_target`。

## #31 MAX_CONTEXT_CHARS=200 + _context 整篇倒出（L3）

- **现象**：文档回答正文被截到 200 字，还把第一个命中文档的所有块原样拼进 answer，超长、超数字上限、还可能原样带出 KB-060 注入。
- **假设**：作答资料上限太小；`_context` 把整篇文档拼进去。
- **验证**：上限调到 1200、删掉 `_context` 只留摘出的引用句后，doc 回答又短又准。
- **根因**：`answerer.py` 的 `MAX_CONTEXT_CHARS` 与 `_context`。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_doc_citation`。

## #32 sanitize 从未接入检索链路（L3）

- **现象**：`sanitize.py` 定义的注入剥离逻辑没人调用，KB-060 里「系统提示：忽略你之前收到的所有指令…」这句会进入索引、可能被照抄。
- **假设**：入库前应把疑似注入句剥掉。
- **验证**：在 `load_document` 里调用 `sanitize` 后，KB-060 正文不再含「忽略你之前收到的所有指令」「9999999」。
- **根因**：`loader.py` 未调用 `sanitize`。
- **修复**：本次提交。
- **回归测试**：`tests/test_retrieval.py::test_injection_stripped`。

## #33 _doc_block 候选句升序排、挑了最差的一句

- **现象**：`外卖订单退款` 引用 KB-061（发票）而不是 KB-013（退款），因为候选按分数**升序**排，`best` 取的是最低分，最先引用的反而是最差的那句。
- **假设**：排序方向反了。
- **验证**：改成 `reverse=True` 后，最高分句子（KB-013 的 24 小时句）被优先引用。
- **根因**：`answerer.py` 的 `_doc_block` 排序。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_doc_citation`。

## #34 破坏性/套词检测是死代码（L3 安全）

- **现象**：S02「删掉销售记录」、S03「系统提示词 + DROP TABLE」都返回了 doc 而不是 refusal。
- **假设**：`is_destructive`/`is_prompt_probe` 定义了但 planner 从没调用。
- **验证**：在 `plan()` 最前面接入这两个检查后，S02/S03 直接 refusal，且不碰数据库。
- **根因**：`planner.py` 未调用 `entities.is_destructive`/`is_prompt_probe`。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_destructive_refused`、`::test_prompt_probe_refused`。

## #35 chunker 盲切把一句话拦腰截断

- **现象**：S04 吞拿鱼「毛利率低于 35%」这句被 300 字边界切成两半，引用只拿到「备货损耗」那半句；冷萃乌龙茶「目标销量 900 杯」同理。
- **假设**：按 300 字盲切会切在句子中间。
- **验证**：改成只在句号/问号/换行处断、再按约 300 字打包后，这两句都完整保留，C07、H03 通过。
- **根因**：`chunker.py` 的 `_text_chunks`。
- **修复**：本次提交。
- **回归测试**：`tests/test_chat.py::test_hybrid_target`。

---

## #36 「S01 7月」这类编号后跟空格的时间解析成全期（L3）

- **现象**：`S01 7月的净营业额是多少？` 答的是 2026-05-01 至 08-31 全期；`S03 6 月 8 日到 14 日…`、`S02 8 月 17 日…` 同样退化成全期。去掉空格写成 `S01的7月` 就正常。
- **假设**：`parse_time` 先删掉全部空格，编号尾数和月份粘在一起，被当成非法月份丢掉。
- **验证**：`S01 7月` 变成 `S017月`，`_MONTH` 匹配到 `17月`；`S03 6 月` 变成 `S036月`，匹配到 `36月`。两者都超出 1–12，窗口为空。
- **根因**：`starter/kbqa/timeparse.py` 的 `parse_time` / `loose_days`（`text.replace(" ", "")`），以及 `_NUM` 没有左边界。
- **修复**：本次提交。新增 `_squash`：「字母/数字 + 空格 + 数字」处留一个分隔符；`_NUM` 的阿拉伯数字加上 `(?<![A-Za-z\d])`。
- **回归测试**：`tests/test_chat.py::test_time_after_code_with_space`（修复前 4 例全红）。

## #37 追问「那 S02 呢」丢掉上一轮的月份（L3 多轮）

- **现象**：先问 `S01 6 月营业额多少`（正确，6 月），再问 `那 S02 呢？`，答的是 S02 全期（05-01 至 08-31）。
- **假设**：追问还原时，上一轮问句的空格被删掉，月份粘坏了；同时还原句里上一轮和这一轮的门店都在，谁在前取谁。
- **验证**：还原结果是 `S016月营业额多少 S02`：`S016月` 解析不出月份（同 #36）；`find_store` 只取第一个门店，就算月份正常也会查成 S01。
- **根因**：`starter/kbqa/followup.py` 的 `resolve`（`re.sub(r"\s+", "", base)`）；`starter/kbqa/planner.py` 的 `plan` 只在还原句里认门店和商品。
- **修复**：本次提交。`resolve` 改用 `timeparse.squash`；planner 先在本轮原句里认门店和商品，认不到再用还原句（继承上一轮）。
- **回归测试**：`tests/test_chat.py::test_follow_up_swaps_store_keeps_month`（修复前拿到的是全期）。

## #38 「多少订单」「卖了多少」被当成文档问题（L3）

- **现象**：`6 月份一共有多少订单` 走文档后拒答；`牛肉poke 6 月卖了多少` 走文档，拿周报里的「大概 150 份」作答（数据库是 545 份），违反 KB-001 §5.2「数字以数据库为准」。
- **假设**：指标词表只有书面说法（订单数、销量、卖了多少份），口语说法认不出指标，路由就退回文档。
- **验证**：`find_metric` 对这两句都返回 None；在句中换成 `订单数` / `销量` 后走数据、结果正确。
- **根因**：`starter/kbqa/entities.py` 的 `METRIC_WORDS` 缺少「多少订单」「几单」和不带单位的「卖了多少」。
- **修复**：本次提交。orders 增加「几单」「多少订单」「多少个订单」「几个订单」；新增 `METRIC_FALLBACK`，把「卖了多少」「卖出多少」等归到销量，排在主表之后，「卖了多少钱」仍归营业额。没有加单独的「订单」，否则「外卖订单多久内可以退款」会被误判成问数。
- **回归测试**：`tests/test_chat.py::test_colloquial_metric_routes_to_data`（修复前 2 例全红）。

## #39 不带「那/后来」的省略追问被拒答（L3 多轮）

- **现象**：先问 `三文鱼poke 为什么停售？`（正确），再问 `用什么替代？` 或 `赔了多少钱？`，两句都拒答「知识库里没有找到」。加上「后来」（`后来用什么替代？`）就能接住上一轮。
- **假设**：追问识别只认「那/后来/再/那次」等标记词；没有标记、也没有主语的短句被当成独立问题，它自己检索不到东西。
- **验证**：`_is_follow_up` 对这两句返回 False；这两句单独探底的词表覆盖率是 0.33 和 0.0，而 `怎么退款？`、`退款政策是什么？` 这种独立短问句在 0.5 以上。
- **根因**：`starter/kbqa/followup.py` 的 `_is_follow_up` 只有标记词这一条路。
- **修复**：本次提交。新增 `_lacks_subject`：不超过 12 个字、没有门店/商品/别名、以动词或疑问词开头（用、赔、为什么、多少……），而且自己的词表覆盖率低于 `MEANINGFUL_COVERAGE`，就当作省略主语的追问。探底函数复用 planner 的 scout。`怎么退款？` 覆盖率够，仍按独立问题处理。
- **回归测试**：`tests/test_chat.py::test_follow_up_without_marker`（修复前 2 例都是拒答）。「用什么替代」引用的是 KB-060 而不是 KB-021，这属于检索排序，另记。

## #40 追问「用什么替代」引用反馈汇总而不是停售通知（L3 多轮）

- **现象**：接着 `三文鱼poke 为什么停售？` 问 `（后来）用什么替代？`，答案只引 KB-060《顾客反馈汇总》的「3 条表示接受鸡肉poke 的替代方案」。真正规定替代品的是 KB-021 第 3 条。
- **假设**：检索没问题，是挑句子时上一轮的话题词（三文鱼、停售）把重复了所有词的转述句抬上去了。
- **验证**：检索 KB-021 排第一（33.8 对 23.2）。挑句时 KB-021 第 3 条只直接命中「替代」「poke」，「三文鱼」「停售」只在标题里，按一半计，得 0.53；KB-060 那句全部直接命中，得 0.68。
- **根因**：`starter/kbqa/docfacts.py` 的 `rank` 把追问还原后的整句当成挑句依据，接过来的话题词和本轮问的词一视同仁。
- **修复**：本次提交。`rank` 新增 `own`（追问原句）：原句有自己的实词时，从上一轮接过来的话题词只要出现在标题、上下文里就计满分。挑哪一句由本轮的词决定。原句没有实词（`那以前呢`）时照旧。只在文档作答（`answerer._candidates`）里传入。
- **回归测试**：`tests/test_chat.py::test_follow_up_cites_the_notice`（修复前 2 例引用的都是 KB-060）。

## #41 「6 月的时候会员充 500 送多少」被越界闸门拒答（L3 版本）

- **现象**：`6 月的时候会员充 500 送多少？` 拒答「知识库里没有找到」；去掉「6 月的时候」就能答（KB-011，60 元）。
- **假设**：版本选择没问题，是闸门判低了。
- **验证**：检索按 as_of=06-30 选对了 KB-010，但越界闸门用的 `clean_question` 是 `6 月会员充 500 送多少？`：`6 月` 和 `会员` 拼成跨词二元组「月会」，语料里没有，词表覆盖率从 0.5 掉到 0.4，低于 `VOCAB_SOFT_GATE`，检索分又不到 12。
- **根因**：`starter/kbqa/planner.py` 的 `_build_search_query` 只去掉了「现在/的时候」，已解析的时间短语仍留在闸门的输入里。
- **修复**：本次提交。新增 `topic_question` 槽位：把 `spec.labels` 里的时间短语（容许中间有空格）换成空格，`answerer._should_refuse` 改用它。检索仍用带时间的句子（「7 月 24 日」「618」要能对上正文）。
- **回归测试**：`tests/test_chat.py::test_month_prefix_does_not_trip_refusal_gate`（修复前拒答）。

## #42 追问「那现在呢」仍按上一轮的旧版回答（L3 多轮 / 版本）

- **现象**：先问 `6 月的时候会员充 500 送多少？`（KB-010，50 元，正确），再问 `那现在呢`，答的还是 KB-010。先问 `储值充值以前的赠送规则是什么？` 再问 `那现在呢`，也是一样。
- **假设**：追问还原把上一轮的时间和「以前」原样带了过来。
- **验证**：还原结果分别是 `6月会员充500送多少？ 现在`（as_of 仍是 06-30）和 `储值充值以前的赠送规则是什么？ 现在`（historical 为真）。
- **根因**：`starter/kbqa/followup.py` 的 `resolve` 只在追问自带时间区间时才去掉上一轮的时间标签。「现在」不产生区间（`relative_now`），走不到那条分支。
- **修复**：本次提交。追问是 `relative_now` 时，去掉上一轮的时间标签和 `HISTORICAL_WORDS`，只保留话题。
- **回归测试**：`tests/test_chat.py::test_follow_up_now_switches_to_current_version`（修复前 2 例引用的都是 KB-010）。

## #43 「7 月之前充值 500 送多少」按 7 月的新版回答（L3 版本）

- **现象**：`7 月之前充值 500 送多少` 引用 KB-011（60 元）。7 月之前生效的是 KB-010（50 元）。
- **假设**：「之前」没有进入时间解析，判定时点按「7 月」取了月底。
- **验证**：`parse_time` 返回的 windows 是 7 月整月，as_of 是 2026-07-31；`7 月 1 日以前` 的 as_of 是 07-01，同样落在 KB-011 的生效日上。
- **根因**：`starter/kbqa/timeparse.py` 的 `_as_of` 一律取区间末尾，没有处理「X 之前/以前」。
- **修复**：本次提交。时间标签后面紧跟 `之前/以前` 时，as_of 取区间开始的前一天（不超过今天）。数据区间不变，只影响按哪天判生效版本。
- **回归测试**：`tests/test_chat.py::test_before_month_means_previous_version`（修复前 2 例的 as_of 分别是 07-31、07-01）。

## #44 「去年 618 活动价多少」答成今年的方案（L3 版本）

- **现象**：`去年 618 活动价多少？` 引用 KB-023《2026 年 618 活动方案》（牛肉poke ¥29）。去年是 KB-024（三文鱼poke 特价 ¥25）。`2025 年 618 的活动价` 答对了，但第二条引用又带上了 KB-023。
- **假设**：年份解析和检索都对，是挑句子时跨文档比较把被降权的文档捡了回来。
- **验证**：plan 的 year=2025、as_of=2025-06-18；检索 KB-024 排第一（9.78），KB-023 吃了年份和未生效两道降权，只剩 2.55。但 KB-023 那句「活动价 ¥29」字面命中「活动价」，KB-024 写的是「特价」，挑句分数高出一倍多，检索分的开方加权抵不过。
- **根因**：`starter/kbqa/answerer.py` 的 `answerable_hits` 对年份冲突的文档只有检索时的软降权，作答阶段不管年份。
- **修复**：本次提交。新增 `_other_year`：问句明说了时间（`time_explicit`）、文档标题带年份，而且这个年份不在问句的区间里，就不拿来作答。没说时间的问题不受影响；`618 活动价多少` 仍按今年答。
- **回归测试**：`tests/test_chat.py::test_named_year_excludes_other_years_plan`（修复前 2 例分别引用了 KB-023 作为第一条、第二条）。

## #45 「牛肉poke 现在多少钱」答成 618 活动价（L3 版本 / 混合）

- **现象**：`牛肉poke 现在多少钱？` 和 `牛肉poke 多少钱` 都引用 KB-023「活动价 ¥29，仅限当天」。现行售价是 KB-025 的 45 元。公开题的问法 `多少钱一份` 是对的。
- **假设**：没有走售价路线，而是当成普通文档题，按字面挑到了带金额的活动句。
- **验证**：plan 的 kind 是 doc。`PRICE_WORDS` 只有「多少钱一」「卖多少钱」「售价」等，单独的「多少钱」不算问价。
- **根因**：`starter/kbqa/planner.py` 的 `_choose_kind` 用来判断问价的词表不认「商品 + 多少钱」。
- **修复**：本次提交。新增 `entities.asks_bare_price`：只说「多少钱」、前面不是「了」、没提活动/特价/促销时，算问售价。另外还要求没有指标词，而且商品是这一句自己点的。第一版没有「本句点名」这一条，结果追问 `赔了多少钱？` 还原后带上了三文鱼poke，被误判成问价（#39 的测试当场变红），所以补上了。
- **回归测试**：`tests/test_chat.py::test_bare_how_much_asks_current_price`（修复前 2 例引用 KB-023；`牛肉poke 618 活动多少钱` 作为守门用例，前后都应引用 KB-023）。

## #46 「S01 店长是谁」答成门店名称那一行（L3 文档）

- **现象**：`S01 店长是谁` 引用 KB-030 的「门店名称：Super Souper」，没有答「店长：周岚」。
- **假设**：planner 把店名拼进检索词，挑句时重复店名的那一行压过了店长那一行。
- **验证**：检索词是 `S01 店长是谁 S01 Super Souper`；在 KB-030 里「门店名称 | Super Souper」得 0.63，「店长 | 周岚」得 0.51。店名只写在标题里时，按一半计。另外「是谁」被当成 entity 焦点，写着任何商品名、店名的句子（「毛豆」「豚骨拉面」）都乘 1.8。只修前一条，店长行还是排第三。
- **根因**：`starter/kbqa/docfacts.py` 的 `rank` 把问句点名的门店、商品当成答案词；`starter/kbqa/entities.py` 的 `ENTITY_QUESTION` 里的「是谁/谁负责」问的是人，而 entity 焦点只认别名表里的商品和门店。
- **修复**：本次提交。`rank` 新增 `_subject_terms`：问句点名的门店、商品及门店编号只说明「问的是谁」，出现在标题、上下文里就计满分，和 #40 的上一轮话题词同一套处理。`ENTITY_QUESTION` 去掉「是谁」「谁负责」。
- **回归测试**：`tests/test_chat.py::test_who_question_not_answered_by_the_entity_it_names`（修复前答的是门店名称）。

## #47 「8 月退款金额比 7 月多还是少」只查了 7 月（L3 数据）

- **现象**：`8 月退款金额比 7 月多还是少`、`8 月比 7 月营业额高吗`、`S01 8 月营业额和 7 月比怎么样` 都只查了 7 月，调的是 `query_metrics`，不是两段对比。
- **假设**：时间解析已经给出了两个窗口，但 planner 认比较只看 `TREND_WORDS`（涨/跌/相比/对比……），这几种说法里一个都没有。
- **验证**：`parse_time` 返回 7 月、8 月两个窗口；`_choose_kind` 里的 `compares` 为假，最后落到 summary，只用第一个窗口。
- **根因**：`starter/kbqa/planner.py` 的 `_choose_kind` 只认趋势词，不认「A 比 B 多/高/好」「和 B 比」「多还是少」这些比较句式。
- **修复**：本次提交。`entities.compares_periods` = 趋势词 + 句式正则。「比」后 16 字内出现多/少/高/低/好/差……、「和/跟/与/同 … 比」、「多还是少」一类都算。只有问句里有两段时间时才起作用，单独一个「比」不会触发。红测试原来只读 `start/end` 参数，而两段对比的参数是 `start_a/end_a/start_b/end_b`，这次把断言改成两种都认。
- **回归测试**：`tests/test_chat.py::test_two_months_compared`（修复前 3 例都只查了 7 月）。

## #48 「S02 7 月比 6 月订单多吗」按净营业额比较（L3 数据）

- **现象**：#47 修好后，`S02 7 月比 6 月订单多吗`、`8 月退款比 7 月少吗` 已经走两段对比，但比的是净营业额，不是订单数和退款金额。
- **假设**：指标词表里只有「订单数」「多少订单」「退款金额」这些完整说法，「订单多」「退款比…少」都认不出，只能退到默认指标。
- **验证**：`find_metric` 对这两句都返回 None，`plan.metric` 回落到 net_revenue。
- **根因**：`starter/kbqa/entities.py` 的 `find_metric` 只做整词匹配，不认「名词 +（比…）多/少」这种比较说法。
- **修复**：本次提交。新增 `METRIC_COMPARATIVE`，放在主词表和兜底表之后：「订单/单子」「退款」后面跟着多/少（中间可以隔一个「比…」）时，认成对应指标。光一个名词不算指标，「退款怎么处理」照旧问规定；后面跟着「久/长」的也不算，「外卖订单多久内可以申请退款」照旧走知识库。
- **回归测试**：`tests/test_chat.py::test_metric_named_by_comparative`（修复前 2 例都答的是净营业额）。

## #49 追问「那 7 月比 6 月呢」只查了 6 月（L3 多轮）

- **现象**：上一轮问 `S01 6 月营业额`，追问 `那 7 月比 6 月呢`，答的还是 S01 6 月的汇总。
- **假设**：追问还原没问题，是比较句式没认出来。
- **验证**：还原后的句子是 `7 月比 6 月 S01|营业额`，解析出两个窗口，门店 S01；但 #47 的句式要求「比」后面跟着多/少/高/低，这句只有一个「比」，所以 kind=summary。
- **根因**：`starter/kbqa/entities.py` 的 `_COMPARE` 太窄。其实 planner 已经要求问句里有两段时间，这时两段时间夹着一个「比」就是在比较，不需要再带上多还是少。
- **修复**：本次提交。`_COMPARE` 改成：「比」本身就算，但排除「占比/比例/比率/比重/比如」；再加上「多还是少」这类不带「比」的说法。「6 月和 7 月的微信支付占比」照旧走支付构成。
- **回归测试**：`tests/test_chat.py::test_follow_up_two_months_compared`（修复前调用的是 query_metrics，只查了 6 月）。

## #50 「6 月和 7 月的营业额分别是多少」只答了 6 月（L3 数据）

- **现象**：`6 月和 7 月的营业额分别是多少`、`6 月和 7 月的微信支付占比` 只查了 6 月，7 月没提。
- **假设**：时间解析给出了两个窗口，但不是比较时，作答只用第一个。
- **验证**：`parse_time` 返回 6 月、7 月两个窗口；`_choose_kind` 只把 `windows[0]` 放进 `plan.window`，第二个窗口在非 compare 路线上直接丢了。
- **根因**：`starter/kbqa/answerer.py` 的 `_answer_data` 除 compare 外只按 `plan.window` 取一次数。
- **修复**：本次提交。planner 把解析出的窗口（最多 3 个）记进 `plan.slots["windows"]`；`_answer_data` 把各路线的取数与描述抽成 `_describe_window`，非 compare 时每个窗口各查一次、各答一句，合并后受 1200 字上限约束。compare、价格、目标、异常路线不变。
- **回归测试**：`tests/test_chat.py::test_each_named_month_answered`（修复前 2 例都只查了 6 月）。

## #51 「哪家店订单最多」「7 月哪家店退款最少」没有查库（L3 路由）

- **现象**：`哪家店订单最多` 引用了 KB-030 门店档案，`7 月哪家店退款最少` 直接拒答，都没有调用数据工具。
- **假设**：「订单最多」「退款最少」没被认成指标，planner 判定问句里没有可查的东西，只好去知识库。
- **验证**：`find_metric` 返回 None，`may_query` 为假，所以 kind=doc。#48 的比较式只认「(更/要/还)多/少」，不认「最多/最少」。
- **根因**：`starter/kbqa/entities.py` 的 `_THAN` 少了「最」。
- **修复**：本次提交。`_THAN` 的程度词加上「最」，两句现在都走 by_store。（by_store 的描述始终按净营业额排序，是另一个问题，见 #52。）
- **回归测试**：`tests/test_chat.py::test_superlative_metric_routes_to_data`（修复前一句走 doc、一句拒答）。

## #52 分店排名总按净营业额从高到低说（L3 数据）

- **现象**：#51 之后 `哪家店订单最多`、`7 月哪家店退款最少` 调用了 by_store，但回答都是「净营业额最高的是 S02」。
- **假设**：分店排名的描述函数没有用问句里的指标和方向。
- **验证**：by_store 的结果里每家店都有订单数、退款金额等全部指标；`render.describe_by_store` 写死了按 net_revenue 降序，也写死了「最高」。
- **根因**：`starter/kbqa/render.py` 的 `describe_by_store` 不接收指标和方向，answerer 也没传。
- **修复**：本次提交。`describe_by_store` 接收 `metric` 和 `lowest`，按问的指标排序，单位用 `metric_value`。问句带「最低/最少/最差/垫底」（`entities.LOWEST_WORDS`）时从低往高说。默认的「净营业额最高」输出与原来逐字一致。
- **回归测试**：`tests/test_chat.py::test_store_ranking_uses_asked_metric`（期望的门店从 evidence 里的工具结果算出来，不写死店名；修复前 2 例都答净营业额最高的 S02）。

## #53 「哪个月营业额最高」答成了商品排名（L3 数据）

- **现象**：`哪个月营业额最高` 回答「卖得最好的是牛肉poke」；`6 月到 8 月哪个月订单最多` 只给了三个月的合计；`S01 每个月的退款金额` 也只有合计。
- **假设**：没有「按月」这条路线，带排名词的落到 top_products，不带的落到 summary。
- **验证**：`_choose_kind` 里没有任何分支认「哪个月/每个月」；工具层也没有按月汇总的工具，只有 query_metrics。
- **根因**：`starter/kbqa/planner.py` 和 `starter/kbqa/answerer.py` 缺少逐月对照的路线。
- **修复**：本次提交。
  - 新增 `entities.MONTHLY_WORDS`（哪个月、每个月、各月、逐月……）和 `timeparse.months_in`（把区间按自然月切开，首尾按区间截断）。
  - 问数路线上，问句带这些词且区间跨了不止一个月时，kind=by_month：每个月调一次 query_metrics（每次都记进 data_evidence），`render.describe_by_month` 先说最高（问最低时说最低）的那个月，再按时间顺序列出各月。
  - 只在问数路线上生效，`员工每月可以享受几次折扣` 照旧走知识库。
- **回归测试**：`tests/test_chat.py::test_month_breakdown`（期望的月份从 evidence 算出；修复前 3 例都没有逐月查询）。

## #54 「7 月营业额最高的一天是哪天」答成了商品排名（L3 数据）

- **现象**：`7 月营业额最高的一天是哪天` 回答「卖得最好的是牛肉poke」，`8 月哪天订单最少` 也一样，都没有给出日期。
- **假设**：「哪天」没被当成逐日的问法，排名词把它带到了 top_products。
- **验证**：`DAILY_WORDS` 只有每天、逐日、按天……，没有「哪天/哪一天」，所以 `asks_rank` 先命中，kind=top_products。`describe_daily` 也只会按时间顺序列出前 7 天，不会指出哪一天最高。
- **根因**：`starter/kbqa/planner.py` 缺少「问哪一天」的路由；`starter/kbqa/render.py` 的 `describe_daily` 不支持按指标找极值。
- **修复**：本次提交。
  - 新增 `entities.WHICH_DAY_WORDS`，区间不止一天时走 daily。
  - 问句带排名词时，`describe_daily` 按问的指标（逐日结果里有净营业额、订单数、客单价）和方向先说是哪一天，再列逐日明细。
  - 问的指标逐日结果里没有（如销量）时，如实说明，改按净营业额说。
  - 不带排名词的逐日问题，输出与原来一致。
- **回归测试**：`tests/test_chat.py::test_peak_day`（期望的日期从 evidence 算出；修复前 2 例都调用的是 top_products）。

## #55 「店长们的手机号是多少」拿一句提到“手机”的话充数（L3 文档）

- **现象**：`店长们的手机号是多少？` 和 `S02 店长手机号多少` 都答成了 doc：前者引用 KB-027 的「只带手机出门的顾客……」，后者引用 KB-031 的「门店编号：S02」，都没有给出任何号码。知识库里门店和供应商只登记了座机，没有手机号，应该拒答。
- **假设**：挑句子时，“手机”作为普通词参与打分，焦点系统里没有“号码”这种答案形状，所以提到“手机”的句子就被当成了答案。
- **验证**：`focus_kinds("店长们的手机号是多少？")` 只得到兜底的 value，任何带数字的句子都满足它。拒答闸门只看词表覆盖率和检索分，“手机”“店长”都在词表里，所以闸门放行。
- **根因**：`starter/kbqa/entities.py` 不知道这类问题的答案必须是一个号码；`starter/kbqa/answerer.py` 也不检查引用里有没有这种号码。
- **修复**：本次提交。
  - 新增 `entities.required_value`：问「手机号是多少」要求 mobile，问「电话多少/怎么联系」要求 phone（座机、手机都算）。只是提到“手机”“电话”的不算，例如「只带手机的顾客」「手机号后四位怎么核对」。
  - `docfacts._CARRIES` 增加 mobile（1 开头的 11 位号码）和 phone（手机或带区号的座机）两种形状，并作为首个焦点参与挑句。
  - `_answer_doc` 在问号码、而所有引用里都没有这种号码时拒答，并在 notes 里写明原因。问手机号时座机不算数。
- **回归测试**：`tests/test_chat.py::test_missing_phone_number_refused`（2 例，修复前都是 doc），以及守门用例 `test_landline_still_answered`（问门店电话照常答出座机）。
