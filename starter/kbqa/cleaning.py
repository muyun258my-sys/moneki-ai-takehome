"""把原始 sales 导进 var/clean.db，指标都查这张表。"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

#: 金额里的 `¥` 去掉再按数字解析。
_CURRENCY = str.maketrans("", "", "¥￥ \t　")

REMOVAL_REASONS = (
    "1_unparseable_date",
    "2_empty_amount",
    "3_qty_le_zero",
    "4_store_not_in_stores",
    "5_product_not_in_products",
    "6_duplicate_row",
)


def parse_amount(value: Optional[str]) -> tuple[Optional[int], str]:
    """返回 (分, 状态)。状态取值：`ok`、`empty`、`bad`。

    KB-001 §2.3 与 §3.2：`¥38.00` 与 `38.00` 是同一个金额；空金额直接剔除，**不回填**。
    `Infinity` / `NaN` 等非有限值按 `bad` 处理，不参与统计。
    """
    text = ("" if value is None else str(value)).translate(_CURRENCY)
    if not text:
        return None, "empty"
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            return None, "bad"
        cents = int((amount * 100).to_integral_value())
    except (InvalidOperation, ValueError, OverflowError):
        return None, "bad"
    return cents, "ok"


def parse_qty(value: Optional[str]) -> Optional[int]:
    """KB-001 §2.4：按整数解析。空、非整数（小数/科学计数/Infinity）解析失败时
    返回 None，之后由 §3.3（qty ≤ 0）统一剔除，不做截断。"""
    text = ("" if value is None else str(value)).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_date(value: Optional[str]) -> Optional[str]:
    """KB-001 §2.2：接受三种日期格式，统一输出 ISO `YYYY-MM-DD`。

    `DD-MM-YYYY` 是旧 POS 的导出格式，**日在前、月在后**；解析不了返回 None。
    """
    text = ("" if value is None else str(value)).strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    else:
        m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
        if m:
            y, mo, d = int(m[1]), int(m[2]), int(m[3])
        else:
            m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", text)
            if m:
                d, mo, y = int(m[1]), int(m[2]), int(m[3])
            else:
                return None
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


@dataclass
class CleaningReport:
    raw_rows: int = 0
    kept_rows: int = 0
    kept_sales_rows: int = 0
    kept_refund_rows: int = 0
    removed: dict[str, int] = field(default_factory=lambda: {k: 0 for k in REMOVAL_REASONS})
    note_unparseable_amount: int = 0

    def as_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "removed": dict(self.removed, note_unparseable_amount=self.note_unparseable_amount),
            "kept_rows": self.kept_rows,
            "kept_sales_rows": self.kept_sales_rows,
            "kept_refund_rows": self.kept_refund_rows,
        }


def open_readonly(path: Path) -> sqlite3.Connection:
    """以只读模式打开数据库（`mode=ro`），任何写操作都会在 SQLite 层失败。"""
    conn = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def clean_rows(
    rows: Iterable[sqlite3.Row],
    store_ids: set[str],
    product_ids: set[str],
) -> tuple[list[tuple], CleaningReport]:
    """按 KB-001 v3 规范化并剔除，返回清洗后的明细行。

    剔除顺序（§3）：日期无法解析 → 空金额 → qty≤0 → 门店外键 → 商品外键 → 完全重复。
    """
    report = CleaningReport()
    kept: list[tuple] = []
    seen: set[tuple] = set()
    for row in rows:
        report.raw_rows += 1
        order_id = (row["order_id"] or "").strip()
        iso_date = parse_date(row["date"])
        if iso_date is None:
            report.removed["1_unparseable_date"] += 1
            continue
        cents, status = parse_amount(row["amount"])
        if status == "empty":
            report.removed["2_empty_amount"] += 1
            continue
        if status == "bad":
            report.note_unparseable_amount += 1
            continue
        qty = parse_qty(row["qty"])
        if qty is None or qty <= 0:
            report.removed["3_qty_le_zero"] += 1
            continue
        store_id = (row["store_id"] or "").strip().upper()
        if store_id not in store_ids:
            report.removed["4_store_not_in_stores"] += 1
            continue
        product_id = (row["product_id"] or "").strip().upper()
        if product_id not in product_ids:
            report.removed["5_product_not_in_products"] += 1
            continue
        payment = (row["payment"] or "").strip()
        key = (order_id, iso_date, store_id, product_id, qty, cents, payment)
        if key in seen:
            report.removed["6_duplicate_row"] += 1
            continue
        seen.add(key)
        kept.append(
            (
                order_id,
                iso_date,
                store_id,
                product_id,
                qty,
                cents,
                payment,
                1 if cents < 0 else 0,
            )
        )
    report.kept_rows = len(kept)
    report.kept_refund_rows = sum(1 for row in kept if row[-1])
    report.kept_sales_rows = report.kept_rows - report.kept_refund_rows
    return kept, report


_SCHEMA = """
CREATE TABLE stores (store_id TEXT PRIMARY KEY, store_name TEXT, category TEXT, district TEXT);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT,
                       product_category TEXT, unit_price REAL);
CREATE TABLE sales_clean (
    order_id TEXT, date TEXT, store_id TEXT, product_id TEXT,
    qty INTEGER, amount_cents INTEGER, payment TEXT, is_refund INTEGER
);
CREATE INDEX idx_clean_date ON sales_clean(date);
CREATE INDEX idx_clean_store ON sales_clean(store_id);
CREATE INDEX idx_clean_product ON sales_clean(product_id);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def build_clean_db(source: Path, target: Path) -> CleaningReport:
    """从只读的源库重建清洗表。返回清洗台账，供 `/api/health` 与数据质量面板使用。"""
    if not source.exists():
        raise FileNotFoundError("找不到源数据库：%s" % source)
    src = open_readonly(source)
    try:
        stores = [
            tuple(r)
            for r in src.execute("SELECT store_id, store_name, category, district FROM stores")
        ]
        products = [
            tuple(r)
            for r in src.execute(
                "SELECT product_id, product_name, product_category, unit_price FROM products"
            )
        ]
        store_ids = {(s[0] or "").strip().upper() for s in stores}
        product_ids = {(p[0] or "").strip().upper() for p in products}
        rows, report = clean_rows(
            src.execute(
                "SELECT order_id, date, store_id, product_id, qty, amount, payment FROM sales"
            ),
            store_ids,
            product_ids,
        )
    finally:
        src.close()

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    out = sqlite3.connect(target)
    try:
        out.executescript(_SCHEMA)
        out.executemany("INSERT INTO stores VALUES (?,?,?,?)", stores)
        out.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
        out.executemany("INSERT INTO sales_clean VALUES (?,?,?,?,?,?,?,?)", rows)
        out.execute(
            "INSERT INTO meta VALUES ('cleaning_report', ?)",
            (json.dumps(report.as_dict(), ensure_ascii=False),),
        )
        out.execute("INSERT INTO meta VALUES ('source_db', ?)", (source.name,))
        out.commit()
    finally:
        out.close()
    return report
