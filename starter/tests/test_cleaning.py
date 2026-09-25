"""清洗与指标口径的单元测试，外加只读连接与 SQL 白名单的安全回归。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kbqa.cleaning import (
    build_clean_db,
    parse_amount,
    parse_date,
    parse_qty,
)
from kbqa.tools import DataTools

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_parse_amount():
    assert parse_amount("38.00") == (3800, "ok")
    assert parse_amount("¥38.00") == (3800, "ok")
    assert parse_amount("-5.00") == (-500, "ok")
    assert parse_amount("") == (None, "empty")
    assert parse_amount("abc") == (None, "bad")
    assert parse_amount("Infinity") == (None, "bad")
    assert parse_amount("NaN") == (None, "bad")


def test_parse_qty():
    assert parse_qty("5") == 5
    assert parse_qty("-3") == -3
    assert parse_qty("2.5") is None
    assert parse_qty("1e2") is None
    assert parse_qty("Infinity") is None
    assert parse_qty("") is None
    assert parse_qty("abc") is None


def test_parse_date():
    assert parse_date("2026-08-10") == "2026-08-10"
    assert parse_date("2026/8/5") == "2026-08-05"
    assert parse_date("25-07-2026") == "2026-07-25"  # 日在前
    assert parse_date("07-06-2026") == "2026-06-07"  # 日在前
    assert parse_date("N/A") is None
    assert parse_date("") is None
    assert parse_date("2026-13-45") is None


@pytest.fixture(scope="module")
def tools(tmp_path_factory):
    target = tmp_path_factory.mktemp("var") / "clean.db"
    build_clean_db(DATA_DIR / "pos.db", target)
    return DataTools(target)


def test_cleaning_report(tools):
    report = tools.cleaning_report()
    assert report["raw_rows"] == 18628
    assert report["kept_rows"] == 18290
    assert report["kept_sales_rows"] == 18196
    assert report["kept_refund_rows"] == 94
    assert report["removed"] == {
        "1_unparseable_date": 8,
        "2_empty_amount": 150,
        "3_qty_le_zero": 30,
        "4_store_not_in_stores": 10,
        "5_product_not_in_products": 40,
        "6_duplicate_row": 100,
        "note_unparseable_amount": 0,
    }


def test_valid_sales_rows(tools):
    assert tools.valid_sales_rows() == 18290


@pytest.mark.parametrize(
    "args, expected",
    [
        (
            ("2026-06-01", "2026-06-30", None, None),
            {"net_revenue": 156757.0, "refund_amount": 953.0, "orders": 4311,
             "aov": 36.36, "qty": 6496},
        ),
        (
            ("2026-07-01", "2026-07-31", "S02", None),
            {"net_revenue": 41740.0, "refund_amount": 107.0, "orders": 875,
             "aov": 47.7, "qty": 1395},
        ),
        (
            ("2026-08-01", "2026-08-31", None, "P21"),
            {"net_revenue": 11024.0, "refund_amount": 16.0, "orders": 461,
             "aov": 23.91, "qty": 689},
        ),
        (
            ("2026-06-18", "2026-06-18", "S02", "P06"),
            {"net_revenue": 3625.0, "refund_amount": 0.0, "orders": 53,
             "aov": 68.4, "qty": 125},
        ),
    ],
)
def test_query_metrics_values(tools, args, expected):
    actual = tools.query_metrics(*args)
    assert actual["net_revenue"] == pytest.approx(expected["net_revenue"])
    assert actual["refund_amount"] == pytest.approx(expected["refund_amount"])
    assert actual["orders"] == expected["orders"]
    assert actual["aov"] == pytest.approx(expected["aov"])
    assert actual["qty"] == expected["qty"]


def test_query_metrics_empty_range(tools):
    actual = tools.query_metrics("2026-09-01", "2026-09-30")
    assert actual["net_revenue"] == 0.0
    assert actual["refund_amount"] == 0.0
    assert actual["orders"] == 0
    assert actual["aov"] is None
    assert actual["qty"] == 0


def test_daily_metrics(tools):
    actual = tools.daily_metrics("2026-06-08", "2026-06-12", "S03")["days"]
    assert [d["date"] for d in actual] == [
        "2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12",
    ]
    assert actual[4]["net_revenue"] == pytest.approx(998.0)
    assert actual[4]["orders"] == 27
    assert actual[4]["aov"] == pytest.approx(36.96)
    assert all(d["net_revenue"] == 0.0 for d in actual[:4])


def test_open_readonly_blocks_write(tools):
    with pytest.raises(sqlite3.OperationalError):
        tools.conn.execute("DELETE FROM sales_clean")


def test_run_sql_rejects_write(tools):
    result = tools.run_sql("DELETE FROM sales_clean")
    assert "error" in result
    assert tools.valid_sales_rows() == 18290
