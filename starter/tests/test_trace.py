"""L4 Trace 中必须留有能定位答案来源的完整记录。"""

from __future__ import annotations

import httpx
import pytest

from kbqa.live import LiveEngine
from kbqa.llm import LLMClient, LLMReply
from kbqa.planner import Plan
from kbqa.trace import Trace


def test_mock_trace_has_search_and_evidence(client):
    response = client.post("/api/chat", json={"question": "会员现在单笔充值满 500 送多少？"})
    trace = client.get("/api/trace/%s" % response.json()["trace_id"]).json()
    search = next(step["detail"] for step in trace["steps"] if step["step"] == "search")
    assert all({"doc_id", "chunk_id", "score", "text"} <= hit.keys() for hit in search["hits"])
    assert all(isinstance(step["took_ms"], (int, float)) for step in trace["steps"])

    response = client.post("/api/chat", json={"question": "6 月营业额是多少？"})
    trace = client.get("/api/trace/%s" % response.json()["trace_id"]).json()
    evidence = next(step["detail"] for step in trace["steps"] if step["step"] == "evidence")
    assert evidence[0]["tool"] == "query_metrics"
    assert evidence[0]["result"]["net_revenue"] == 156757.0


def test_llm_trace_keeps_full_prompt_and_output(monkeypatch):
    calls = []
    content = "答" * 4500
    reasoning = "想" * 4500
    response = httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": content,
                                  "reasoning_content": reasoning}, "finish_reason": "stop"}]
    })
    monkeypatch.setattr("kbqa.llm.httpx.post", lambda *args, **kwargs: response)

    LLMClient("http://example.test", "test-key", "test-model").chat(
        [{"role": "user", "content": "问" * 4500}], on_call=calls.append
    )
    assert len(calls[0]["prompt"]) > 4500
    assert calls[0]["raw_content"] == content
    assert calls[0]["raw_reasoning"] == reasoning
    assert calls[0]["took_ms"] >= 0


def test_llm_trace_keeps_http_error_body(monkeypatch):
    from kbqa.llm import LLMError

    calls = []
    body = "failure detail " * 500
    monkeypatch.setattr("kbqa.llm.httpx.post", lambda *args, **kwargs:
                        httpx.Response(503, text=body))
    with pytest.raises(LLMError):
        LLMClient("http://example.test", "test-key", "test-model").chat(
            [{"role": "user", "content": "question"}], on_call=calls.append
        )
    assert calls[0]["raw_response"] == body


def test_live_trace_records_tool_result():
    class OneToolCall:
        calls = 0

        def chat_with_retry(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                call = {"id": "call-1", "function": {"name": "query_metrics", "arguments": "{}"}}
                return LLMReply({"role": "assistant", "tool_calls": [call]},
                                "tool_calls", "", [call], 0.0)
            raise RuntimeError("stop after tool")

    trace = Trace("test", "question")
    engine = LiveEngine(OneToolCall(), None, lambda name, params: {"net_revenue": 12},
                        "2026-09-01", {"start": "2026-05-01", "end": "2026-08-31"})
    with pytest.raises(RuntimeError, match="stop after tool"):
        engine.answer(Plan("question", "question", "question"), trace, [])
    tool = next(step for step in trace.steps if step["step"] == "tool")
    assert tool["detail"] == {"tool": "query_metrics", "params": {},
                              "result": {"net_revenue": 12}}
    assert tool["took_ms"] >= 0
