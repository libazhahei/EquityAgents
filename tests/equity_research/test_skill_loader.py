"""Tests for file-based skill loading and lazy catalog."""

from pathlib import Path

import pytest

from tradingagents.equity_research.skills.agent_visibility import (
    AGENT_SKILL_VISIBILITY,
    filter_eligible_catalog,
)
from tradingagents.equity_research.skills.base import SkillCatalogEntry
from tradingagents.equity_research.skills.catalog import format_catalog_for_prompt
from tradingagents.equity_research.skills.loader import SkillLoader
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.skills.runnable import RunnableSkill
from tradingagents.equity_research.tools.registry import ToolRegistry


DEFINITIONS_DIR = Path(__file__).resolve().parents[2] / "tradingagents/equity_research/skills/definitions"


def test_scan_catalog_skips_body_validation(tmp_path):
    catalog_only = tmp_path / "catalog_only.skill.md"
    catalog_only.write_text(
        "---\nname: catalog_only\ndescription: d\nwhen_to_use: w\n---\n\n## Prompt Template\n\nno constraints section\n",
        encoding="utf-8",
    )
    loader = SkillLoader(definitions_dir=tmp_path)
    entry = loader.scan_catalog_entry(catalog_only)
    assert entry.name == "catalog_only"
    with pytest.raises(ValueError, match="Constraints"):
        loader.read_skill_file(catalog_only)


def test_parse_broker_consensus_skill_full_read():
    loader = SkillLoader(definitions_dir=DEFINITIONS_DIR)
    path = DEFINITIONS_DIR / "broker_consensus_mining.skill.md"
    parsed = loader.read_skill_file(path)
    assert parsed.manifest.name == "broker_consensus_mining"
    assert parsed.constraints
    assert parsed.prompt_template
    assert parsed.handler


def test_registry_lazy_catalog_and_read():
    registry = SkillRegistry(known_tools=set(ToolRegistry().list_tools()))
    assert "broker_consensus_mining" in registry.list()
    summaries = registry.get_manifests_summary()
    assert summaries
    loaded = registry.read_skill("broker_consensus_mining")
    assert loaded.prompt_template
    assert registry.read_skill("broker_consensus_mining") is loaded


def test_get_manifests_summary_excludes_prompt_body():
    registry = SkillRegistry()
    summaries = registry.get_manifests_summary()
    loaded = registry.read_skill("broker_consensus_mining")
    catalog_json = format_catalog_for_prompt(registry.get_catalog())
    assert loaded.prompt_template not in catalog_json
    assert "perplexity_search" not in catalog_json
    assert summaries[0].description


def test_format_catalog_for_prompt_fields_only():
    entry = SkillCatalogEntry(
        name="x",
        description="desc",
        when_to_use="when",
        tags=["t1"],
        tools=["hidden_tool"],
        handler="hidden.handler:H",
    )
    text = format_catalog_for_prompt([entry])
    assert "hidden_tool" not in text
    assert "hidden.handler" not in text
    assert "desc" in text


def test_get_returns_runnable_skill():
    registry = SkillRegistry()
    skill = registry.get("valuation")
    assert isinstance(skill, RunnableSkill)
    assert skill.manifest.allowed_tools


def test_filename_must_match_name(tmp_path):
    bad = tmp_path / "wrong_name.skill.md"
    bad.write_text(
        "---\nname: expected_name\ndescription: d\nwhen_to_use: w\n---\n\n",
        encoding="utf-8",
    )
    loader = SkillLoader(definitions_dir=tmp_path)
    with pytest.raises(ValueError, match="filename must be"):
        loader.scan_catalog_entry(bad)


def test_filter_eligible_by_tags():
    catalog = [
        SkillCatalogEntry(name="a", description="d", when_to_use="w", tags=["planning"]),
        SkillCatalogEntry(name="b", description="d", when_to_use="w", tags=["writing"]),
    ]
    vis = AGENT_SKILL_VISIBILITY["dynamic_planning"]
    eligible = filter_eligible_catalog(catalog, vis)
    names = {e.name for e in eligible}
    assert "a" in names
    assert "b" not in names


def test_get_eligible_catalog_consensus_subgraph():
    registry = SkillRegistry(known_tools=set(ToolRegistry().list_tools()))
    eligible = registry.get_eligible_catalog("consensus_subgraph")
    names = {e.name for e in eligible}
    assert names == {"broker_consensus_mining", "variant_view_discovery"}
    assert "market_assumption_decomposition" not in names


def test_get_eligible_catalog_assumption_subgraph():
    registry = SkillRegistry(known_tools=set(ToolRegistry().list_tools()))
    eligible = registry.get_eligible_catalog("assumption_subgraph")
    names = {e.name for e in eligible}
    assert names == {"market_assumption_decomposition"}
