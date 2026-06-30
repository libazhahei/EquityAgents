"""Tests for batch_perplexity_search."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from tradingagents.equity_research.state.consensus_schemas import EvidenceItem
from tradingagents.equity_research.tools import search_tools


def _mock_deps():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.quick_llm.invoke.return_value = MagicMock(content="summary")
    return deps


def _search_fn_factory(counter: dict[str, int] | None = None):
    def _search(deps, *, query, mode, target_dimension, ticker):
        if counter is not None:
            counter["calls"] = counter.get("calls", 0) + 1
        return EvidenceItem(
            answer=f"answer for {query}",
            citations=[f"https://example.com/{target_dimension}"],
            target_dimension=target_dimension,
            query_used=query,
            doc_ids=[f"doc_{target_dimension}"],
        )

    return _search


def test_batch_perplexity_search_single_string():
    deps = _mock_deps()
    result = search_tools.batch_perplexity_search(
        deps,
        ticker="NVDA",
        queries="NVDA revenue estimates",
        search_fn=_search_fn_factory(),
    )
    assert len(result["items"]) == 1
    assert result["items"][0]["evidence"]["answer"] == "answer for NVDA revenue estimates"
    assert result["api_calls"] == 1


def test_batch_perplexity_search_list():
    deps = _mock_deps()
    counter: dict[str, int] = {}
    queries = [
        {"query": "NVDA query 0", "target_dimension": "quantitative_estimates", "mode": "targeted", "priority": 0},
        {"query": "NVDA query 1", "target_dimension": "kpi_focus", "mode": "exploratory", "priority": 1},
    ]
    result = search_tools.batch_perplexity_search(
        deps,
        ticker="NVDA",
        queries=queries,
        search_fn=_search_fn_factory(counter),
    )
    assert len(result["items"]) == 2
    assert counter["calls"] == 2
    assert result["api_calls"] == 2


def test_batch_perplexity_search_dedupes_identical_queries_in_batch():
    deps = _mock_deps()
    counter: dict[str, int] = {}
    same = "NVDA analyst consensus revenue"
    queries = [
        {"query": same, "target_dimension": "quantitative_estimates", "priority": 2},
        {"query": f"  {same}  ", "target_dimension": "kpi_focus", "priority": 1},
    ]
    result = search_tools.batch_perplexity_search(
        deps,
        ticker="NVDA",
        queries=queries,
        search_fn=_search_fn_factory(counter),
    )
    assert counter["calls"] == 1
    assert result["api_calls"] == 1
    assert len(result["items"]) == 2
    assert result["items"][0]["target_dimension"] == "quantitative_estimates"
    assert result["items"][1]["target_dimension"] == "kpi_focus"


def test_batch_perplexity_search_reuses_search_memory_cache():
    deps = _mock_deps()
    counter: dict[str, int] = {}
    memory = [{
        "query": "NVDA KPI focus",
        "answer": "cached answer",
        "citations": ["https://example.com/cached"],
        "doc_ids": ["doc_cached"],
        "target_dimension": "kpi_focus",
        "retrieved_at": "2024-01-01T00:00:00",
    }]
    result = search_tools.batch_perplexity_search(
        deps,
        ticker="NVDA",
        queries="NVDA KPI focus",
        search_memory=memory,
        search_fn=_search_fn_factory(counter),
    )
    assert counter.get("calls", 0) == 0
    assert result["api_calls"] == 0
    assert result["items"][0]["cached"] is True
    assert result["items"][0]["evidence"]["answer"] == "cached answer"


def test_batch_perplexity_search_runs_in_parallel():
    deps = _mock_deps()
    deps.config["equity_research"]["batch_search_concurrency"] = 3
    active = {"count": 0}
    peak = {"value": 0}
    lock = threading.Lock()

    def slow_search(deps, *, query, mode, target_dimension, ticker):
        with lock:
            active["count"] += 1
            peak["value"] = max(peak["value"], active["count"])
        time.sleep(0.05)
        with lock:
            active["count"] -= 1
        return EvidenceItem(answer="ok", citations=[], doc_ids=[], target_dimension=target_dimension)

    queries = [{"query": f"q{i}", "target_dimension": "debates", "priority": i} for i in range(3)]
    result = search_tools.batch_perplexity_search(
        deps,
        ticker="NVDA",
        queries=queries,
        search_fn=slow_search,
    )
    assert len(result["items"]) == 3
    assert peak["value"] >= 2
