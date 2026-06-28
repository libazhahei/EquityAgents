"""Tests for task_analysis orchestration."""

from unittest.mock import MagicMock, patch

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.task_analysis import create_analyze_research_task


def _minimal_state():
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
            "consensus_search_memory": [],
            "consensus_evidence_buffer": [],
            "consensus_iterations": 1,
        }

    def _assumption(state):
        call_order.append("assumption")
        assert state.get("consensus_view") == {"ticker": "NVDA"}
        return {
            "consensus_assumptions": {"business_model": "chips"},
            "research_suggestions": [{"direction": "cloud KPI"}],
            "research_directions": ["cloud KPI"],
            "assumption_report": "assumption report",
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
                    with patch(
                        "tradingagents.equity_research.agents.task_analysis.create_load_report_template",
                        return_value=lambda s: {"report_template": []},
                    ):
                        with patch(
                            "tradingagents.equity_research.agents.task_analysis.create_define_research_mandate",
                            return_value=lambda s: {"mandate": {}},
                        ):
                            with patch(
                                "tradingagents.equity_research.agents.task_analysis.create_build_source_index",
                                return_value=lambda s: {"source_index": []},
                            ):
                                with patch(
                                    "tradingagents.equity_research.agents.task_analysis.create_extract_broker_views",
                                    return_value=lambda s: {"broker_views": []},
                                ):
                                    with patch(
                                        "tradingagents.equity_research.agents.task_analysis.create_gap_finder",
                                        return_value=lambda s: {"expectation_gaps": []},
                                    ):
                                        with patch(
                                            "tradingagents.equity_research.agents.task_analysis.create_generate_research_plan",
                                            return_value=lambda s: {"research_plan": {}},
                                        ):
                                            run = create_analyze_research_task(deps)
                                            result = run(_minimal_state())

    assert call_order == ["consensus", "assumption"]
    assert result["consensus_assumptions"]["business_model"] == "chips"
    assert result["research_directions"] == ["cloud KPI"]
    assert "research_graph" in result
