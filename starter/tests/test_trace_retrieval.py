"""真实检索索引的过滤记录。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kbqa.index import load_index
from kbqa.retriever import Retriever


def test_filtered_chunks_include_reason(tmp_path):
    kb_dir = Path(__file__).resolve().parents[2] / "knowledge_base"
    index = load_index(kb_dir, tmp_path / "index.json")
    result = Retriever(index, date(2026, 9, 1)).search("会员现在单笔充值满 500 送多少？")
    filtered = result.as_trace()["filtered"]
    assert filtered
    assert all({"doc_id", "chunk_id", "score", "reason"} <= hit.keys()
               for hit in filtered)
    assert all(hit["score"] is None for hit in filtered)
