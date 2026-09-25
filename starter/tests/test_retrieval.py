"""L2 检索链路的回归测试：加载、解码、分词、切块、检索金标。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kbqa.chunker import chunk_document
from kbqa.index import build_index
from kbqa.loader import Document, decode_bytes, load_knowledge_base
from kbqa.retriever import Retriever
from kbqa.tokenizer import tokenize

KB_DIR = Path(__file__).resolve().parents[2] / "knowledge_base"

RETRIEVAL_CASES = {
    "R01": ("外卖订单多久内可以申请退款", ["KB-013"]),
    "R02": ("牛肉poke 含哪些过敏原", ["KB-040"]),
    "R03": ("Super Souper 周五晚上营业到几点", ["KB-062"]),
    "R04": ("三文鱼那次断供供应商赔了多少钱", ["KB-022"]),
    "R05": ("发票怎么开", ["KB-061"]),
    "R06": ("净营业额怎么算，退款算不算进去", ["KB-001"]),
    "R07": ("今年 618 牛肉poke 的活动价和目标销量", ["KB-023"]),
    "R08": ("现在单笔充值 500 送多少", ["KB-011"]),
    "R09": ("味噌拉面在数据库里叫什么", ["KB-003"]),
    "R10": ("S04 为什么不卖吞拿鱼三明治了", ["KB-029"]),
    "R11": ("冷萃乌龙茶首月的目标销量是多少", ["KB-028"]),
    "R12": ("S03 六月停业几天，什么原因", ["KB-020", "KB-051"]),
    "R13": ("台风那天几点提前闭店", ["KB-026", "KB-053"]),
    "R14": ("S05 那天为什么只能收现金", ["KB-027", "KB-052"]),
    "R15": ("员工折扣几折，能不能和活动叠加", ["KB-014"]),
}


@pytest.fixture(scope="module")
def retriever():
    return Retriever(build_index(KB_DIR), date(2026, 9, 1))


def test_loader_loads_all_docs():
    docs, _ = load_knowledge_base(KB_DIR)
    assert len(docs) == 35
    ids = {d.doc_id for d in docs}
    missing = ("KB-011", "KB-013", "KB-022", "KB-025", "KB-026", "KB-027",
               "KB-028", "KB-029", "KB-061", "KB-062")
    assert ids.issuperset(missing)


def test_gbk_decode():
    path = KB_DIR / "legacy" / "KB-062_旧OA导出_营业时间调整通知.txt"
    text = decode_bytes(path.read_bytes(), path, [])
    assert "营业时间" in text
    assert "23:00" in text


def test_html_stripped():
    docs, _ = load_knowledge_base(KB_DIR)
    doc = next(d for d in docs if d.doc_id == "KB-061")
    assert "<script" not in doc.text
    assert "<style" not in doc.text
    assert "<table" not in doc.text
    assert "小程序" in doc.text


def test_tokenizer_bigram():
    assert tokenize("外卖") == ["外卖"]
    assert tokenize("外卖订单") == ["外卖", "卖订", "订单"]
    assert tokenize("Salmon Poke") == ["salmon", "poke"]
    assert tokenize("三文鱼poke") == ["三文", "文鱼", "poke"]


def test_chunker_tail_and_table():
    text = ("A" * 700) + "\n| 名称 | 值 |\n|---|---|\n| x | 1 |\n"
    doc = Document(doc_id="KB-999", title="t", text=text, path=Path("x.md"), fmt="md")
    chunks = chunk_document(doc)
    assert "table" in {c.kind for c in chunks}
    assert [len(c.text) for c in chunks if c.kind == "text"] == [300, 300, 100]


@pytest.mark.parametrize("query,gold", list(RETRIEVAL_CASES.values()), ids=list(RETRIEVAL_CASES))
def test_retrieval_gold(retriever, query, gold):
    result = retriever.search(query, top_k=5)
    got = [hit.doc_id for hit in result.hits]
    assert len(got) == 5
    assert any(g in got for g in gold), "%s 应命中 %s，实际 %s" % (query, gold, got)
