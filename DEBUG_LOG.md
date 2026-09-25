# DEBUG_LOG

记录 starter 代码里和「数据清洗 + 指标」相关的缺陷，以及本次 review 补充修掉的健壮性与安全缺陷。
每条按「现象 → 假设 → 验证 → 根因 → 修复 → 回归测试」展开。

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
