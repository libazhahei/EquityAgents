"""Tests for equity research tool registry and catalog tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.tools.errors import ToolNotImplementedError
from tradingagents.equity_research.tools.lc.stubs import STUB_LANGCHAIN_TOOLS
from tradingagents.equity_research.tools.registry import ToolRegistry
from tradingagents.equity_research.tools import search_tools, data_tools, artifact_tools
from tradingagents.equity_research.tools.workspace_utils import get_document_root


EXPECTED_NEW_TOOLS = [
    "ls_tools",
    "tool_registry_lookup",
    "ls_skills",
    "skill_registry_lookup",
    "state_snapshot",
    "web_search",
    "web_fetch",
    "news_search",
    "source_quality_check",
    "citation_extractor",
    "search_deduper",
    "list_files",
    "file_reader",
    "pdf_reader",
    "docx_reader",
    "table_extractor",
    "document_chunker",
    "document_outline_extractor",
    "reference_parser",
    "stock_quote",
    "company_profile",
    "financial_statement_fetch",
    "earnings_calendar",
    "analyst_estimates_fetch",
    "transcript_search",
    "filings_search",
    "filing_reader",
    "peer_comps_fetch",
    "valuation_multiples_fetch",
    "python_exec_sandbox",
    "shell_exec_sandbox",
    "code_reader",
    "code_search",
    "code_writer",
    "csv_reader",
    "dataframe_profiler",
    "calculator",
    "chart_generator",
    "statistical_test",
    "regression_runner",
    "time_series_analyzer",
    "markdown_writer",
    "json_writer",
    "citation_checker",
    "claim_evidence_checker",
    "coverage_evaluator",
    "conflict_detector",
    "ask_human",
    "human_approval",
    "human_review_payload",
    "human_select_branch",
    "memory_retrieve",
    "memory_write",
]


def test_tool_registry_lists_new_tools():
    registry = ToolRegistry()
    names = set(registry.list_tools())
    for tool in EXPECTED_NEW_TOOLS:
        assert tool in names, f"missing tool: {tool}"


def test_ls_tools_categories():
    registry = ToolRegistry()
    result = registry.call("ls_tools")
    assert result["level"] == "categories"
    ids = {c["id"] for c in result["categories"]}
    assert "search" in ids
    assert "finance" in ids


def test_ls_tools_search_category():
    registry = ToolRegistry()
    result = registry.call("ls_tools", category="search")
    assert result["level"] == "tools"
    assert result["category"] == "search"
    names = {t["name"] for t in result["tools"]}
    assert "web_search" in names
    assert "web_fetch" in names


def test_tool_registry_lookup_by_tags():
    registry = ToolRegistry()
    result = registry.call("tool_registry_lookup", task="fetch web page", tags=["search"])
    tools = result["tools"]
    assert any(t["name"] == "web_fetch" for t in tools)


def test_ls_skills_with_registry():
    tool_reg = ToolRegistry()
    skill_reg = SkillRegistry(known_tools=set(tool_reg.list_tools()))
    tool_reg.set_skill_registry(skill_reg)
    domains = tool_reg.call("ls_skills")
    assert domains["level"] == "domains"
    consensus = tool_reg.call("ls_skills", domain="consensus")
    assert consensus["level"] == "skills"
    names = {s["name"] for s in consensus["skills"]}
    assert "broker_consensus_mining" in names


def test_search_deduper():
    results = [
        {"title": "Apple earnings beat", "url": "http://a.com"},
        {"title": "Apple earnings beat expectations", "url": "http://b.com"},
        {"title": "Different story", "url": "http://c.com"},
    ]
    out = search_tools.search_deduper(results)
    assert len(out["results"]) == 2


def test_calculator():
    out = data_tools.calculator("2 + 3 * 4")
    assert out["result"] == 14.0


def test_markdown_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_EQUITY_RESEARCH_DIR", str(tmp_path))
    from tradingagents.dataflows.config import set_config
    import tradingagents.default_config as dc

    set_config(dc.DEFAULT_CONFIG)
    out = artifact_tools.markdown_writer("# Hello", "notes/test.md")
    assert Path(out["path"]).exists()


def test_human_tools_stub():
    from tradingagents.equity_research.tools.lc.human import ask_human

    result = ask_human.invoke({"question": "question?"})
    assert result["status"] == "stub"


def test_langchain_tool_annotations():
    registry = ToolRegistry()
    lc_tool = registry.get_langchain_tool("web_search")
    assert lc_tool.name == "web_search"
    schema = lc_tool.args_schema.model_json_schema()
    assert "query" in schema.get("properties", {})


@pytest.mark.parametrize("tool_name", sorted(STUB_LANGCHAIN_TOOLS.keys()))
def test_stub_tools_registered(tool_name: str):
    registry = ToolRegistry()
    assert tool_name in registry.list_tools()


@pytest.mark.parametrize(
    "tool_name,invoke_kwargs",
    [
        ("browser_search", {"query": "test"}),
        ("paper_pdf_reader", {"source": "paper.pdf"}),
        ("docx_writer", {"sections": [], "path": "out.docx"}),
        ("human_set_constraints", {"constraints": {}}),
    ],
)
def test_stub_tools_raise_not_implemented(tool_name: str, invoke_kwargs: dict):
    registry = ToolRegistry()
    with pytest.raises(ToolNotImplementedError) as exc:
        registry.call(tool_name, **invoke_kwargs)
    assert exc.value.tool_name == tool_name


def test_ls_tools_includes_stub_categories():
    registry = ToolRegistry()
    result = registry.call("ls_tools")
    ids = {c["id"] for c in result["categories"]}
    assert "academic" in ids
    assert "browser" in ids


def test_ls_tools_marks_unimplemented_tools():
    registry = ToolRegistry()
    result = registry.call("ls_tools", category="academic")
    assert result["level"] == "tools"
    for tool in result["tools"]:
        assert tool["implemented"] is False
