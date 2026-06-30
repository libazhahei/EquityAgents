"""LangChain @tool exports for equity research."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool

from tradingagents.equity_research.tools import system_tools
from tradingagents.equity_research.tools.lc import (
    artifact,
    code,
    data,
    document,
    finance,
    human,
    legacy,
    memory,
    planner,
    quality,
    search,
    stubs,
)

STATIC_LANGCHAIN_TOOLS: dict[str, BaseTool] = {
    # Legacy data + calculators
    "get_financial_statements": legacy.get_financial_statements,
    "get_consensus_estimates": legacy.get_consensus_estimates,
    "yfinance_consensus": legacy.yfinance_consensus,
    "get_current_price": legacy.get_current_price,
    "search_web": legacy.search_web,
    "search_company_filings": legacy.search_company_filings,
    "get_news": legacy.get_news,
    "calculate_cagr": legacy.calculate_cagr,
    "calculate_total_return": legacy.calculate_total_return,
    "calculate_trading_multiple_valuation": legacy.calculate_trading_multiple_valuation,
    "calculate_sensitivity_table": legacy.calculate_sensitivity_table,
    # Search
    "web_search": search.web_search,
    "web_fetch": search.web_fetch,
    "news_search": search.news_search,
    "source_quality_check": search.source_quality_check,
    "citation_extractor": search.citation_extractor,
    "search_deduper": search.search_deduper,
    "batch_light_grounding_search": planner.batch_light_grounding_search,
    # Finance
    "stock_quote": finance.stock_quote,
    "company_profile": finance.company_profile,
    "financial_statement_fetch": finance.financial_statement_fetch,
    "earnings_calendar": finance.earnings_calendar,
    "analyst_estimates_fetch": finance.analyst_estimates_fetch,
    "transcript_search": finance.transcript_search,
    "filings_search": finance.filings_search,
    "filing_reader": finance.filing_reader,
    "peer_comps_fetch": finance.peer_comps_fetch,
    "valuation_multiples_fetch": finance.valuation_multiples_fetch,
    # Document
    "list_files": document.list_files,
    "file_reader": document.file_reader,
    "pdf_reader": document.pdf_reader,
    "docx_reader": document.docx_reader,
    "table_extractor": document.table_extractor,
    "document_chunker": document.document_chunker,
    "document_outline_extractor": document.document_outline_extractor,
    "reference_parser": document.reference_parser,
    # Data
    "csv_reader": data.csv_reader,
    "dataframe_profiler": data.dataframe_profiler,
    "calculator": data.calculator,
    "chart_generator": data.chart_generator,
    "statistical_test": data.statistical_test,
    "regression_runner": data.regression_runner,
    "time_series_analyzer": data.time_series_analyzer,
    # Artifact
    "markdown_writer": artifact.markdown_writer,
    "json_writer": artifact.json_writer,
    # Quality
    "citation_checker": quality.citation_checker,
    "claim_evidence_checker": quality.claim_evidence_checker,
    "coverage_evaluator": quality.coverage_evaluator,
    "conflict_detector": quality.conflict_detector,
    # Human
    "ask_human": human.ask_human,
    "human_approval": human.human_approval,
    "human_review_payload": human.human_review_payload,
    "human_select_branch": human.human_select_branch,
    # Memory / evidence
    "memory_retrieve": memory.memory_retrieve,
    "memory_write": memory.memory_write,
    "store_evidence": memory.store_evidence,
    "store_claim": memory.store_claim,
    "store_assumption": memory.store_assumption,
    "link_evidence_to_claim": memory.link_evidence_to_claim,
    "retrieve_claims_by_section": memory.retrieve_claims_by_section,
    "retrieve_contradictory_evidence": memory.retrieve_contradictory_evidence,
    # Code
    "code_reader": code.code_reader,
    "code_search": code.code_search,
    "code_writer": code.code_writer,
    "python_exec_sandbox": code.python_exec_sandbox,
    "shell_exec_sandbox": code.shell_exec_sandbox,
}
STATIC_LANGCHAIN_TOOLS.update(stubs.STUB_LANGCHAIN_TOOLS)


def build_system_langchain_tools(
    *,
    registered: Callable[[], set[str]],
    skill_registry: Any | None = None,
    deps: Any | None = None,
) -> dict[str, BaseTool]:
    """Build dynamic system tools that depend on registry context."""

    @tool
    def ls_tools(
        category: Annotated[str | None, "Tool category id, e.g. search or finance"] = None,
    ) -> dict[str, Any]:
        """Browse tool categories or list tools in a category."""
        return system_tools.ls_tools(category, registered=registered())

    @tool
    def tool_registry_lookup(
        task: Annotated[str, "Task description for semantic tool search"] = "",
        tags: Annotated[list[str] | None, "Optional tags to filter tools"] = None,
    ) -> dict[str, Any]:
        """Search registered tools by task description and tags."""
        return system_tools.tool_registry_lookup(task, tags, registered=registered())

    @tool
    def ls_skills(
        domain: Annotated[str | None, "Skill domain id, e.g. consensus or valuation"] = None,
    ) -> dict[str, Any]:
        """Browse skill domains or list skills in a domain."""
        if skill_registry is None:
            return {"level": "domains", "domains": [], "error": "skill registry not available"}
        return system_tools.ls_skills(skill_registry, domain)

    @tool
    def skill_registry_lookup(
        task: Annotated[str, "Task description for semantic skill search"] = "",
        domain: Annotated[str | None, "Optional skill domain filter"] = None,
    ) -> dict[str, Any]:
        """Search skills by task description and optional domain."""
        if skill_registry is None:
            return {"task": task, "skills": [], "error": "skill registry not available"}
        return system_tools.skill_registry_lookup(skill_registry, task, domain)

    @tool
    def state_snapshot(
        state: Annotated[dict[str, Any], "Research state snapshot to persist"],
    ) -> dict[str, Any]:
        """Save a compact snapshot of the current research state."""
        return system_tools.state_snapshot(state, deps)

    return {
        "ls_tools": ls_tools,
        "tool_registry_lookup": tool_registry_lookup,
        "ls_skills": ls_skills,
        "skill_registry_lookup": skill_registry_lookup,
        "state_snapshot": state_snapshot,
    }


__all__ = ["STATIC_LANGCHAIN_TOOLS", "build_system_langchain_tools"]
