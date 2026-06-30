"""Tests for task_analysis orchestration."""

from unittest.mock import MagicMock, patch
from typing import Any, cast

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.task_analysis import create_analyze_research_task
from tradingagents.equity_research.state.equity_research_state import EquityResearchState


def _minimal_state() -> dict[str, Any]:
    return {
        "ticker": "NVDA",
        "sector": "Technology",
        "report_type": "initiation",
        "documents": [],
        "api_calls": 0,
        "errors": [],
        "evidence_fragments": [],
        "expectation_gaps": [],
    }


def test_analyze_research_task_runs_consensus_then_assumption():
    deps = EquityResearchDeps(
        config={"equity_research_use_memory": True, "data_cache_dir": "/tmp/ta-test"},
        deep_llm=MagicMock(),
        quick_llm=MagicMock(),
    )
    deps.fmp = MagicMock(available=False)
    deps.trace = MagicMock(return_value={})

    call_order: list[str] = []

    def _consensus(state):
        call_order.append("consensus")
        return {
            "consensus_view": {"ticker": "NVDA"},
            "consensus_report": "report",
            "consensus_coverage_report": {"overall_score": 0.8},
            "consensus_search_memory": [],
            "consensus_evidence_buffer": [],
            "consensus_iterations": 1,
        }

    def _assumption(state):
        call_order.append("assumption")
        assert state.get("consensus_view") == {"ticker": "NVDA"}
        return {
            "assumption_view": {"assumption_map": []},
            "consensus_assumptions": {"business_model": "chips"},
            "research_suggestions": [{"direction": "cloud KPI"}],
            "research_directions": ["cloud KPI"],
            "assumption_report": "assumption report",
            "assumption_coverage_report": {"overall_score": 0.7},
        }

    with patch("tradingagents.equity_research.agents.task_analysis.prefetch_sec_filings"):
        with patch(
            "tradingagents.equity_research.agents.task_analysis.ingest_documents_from_sec_cache",
            return_value={"documents": []},
        ):
            with patch(
                "tradingagents.equity_research.agents.task_analysis.create_run_consensus_subgraph",
                return_value=_consensus,
            ):
                with patch(
                    "tradingagents.equity_research.agents.task_analysis.create_run_assumption_subgraph",
                    return_value=_assumption,
                ):
                    run = create_analyze_research_task(deps)
                    result = run(cast(EquityResearchState, _minimal_state()))

    assert call_order == ["consensus", "assumption"]
    assert result["consensus_assumptions"]["business_model"] == "chips"
    assert result["research_directions"] == ["cloud KPI"]
    assert result["subgraph_outputs"]["consensus"]["report"] == "report"
    assert result["subgraph_outputs"]["consensus"]["coverage_report"]["overall_score"] == 0.8
    assert result["subgraph_outputs"]["assumption"]["report"] == "assumption report"
    assert result["subgraph_outputs"]["assumption"]["coverage_report"]["overall_score"] == 0.7
