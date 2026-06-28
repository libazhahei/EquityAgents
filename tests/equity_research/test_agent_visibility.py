"""Tests for agent skill visibility configuration."""

from tradingagents.equity_research.skills.agent_visibility import (
    AGENT_SKILL_VISIBILITY,
    filter_eligible_catalog,
    resolve_agent_visibility,
)
from tradingagents.equity_research.skills.base import SkillCatalogEntry
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.tools.registry import ToolRegistry


def _entry(name: str, tags: list[str]) -> SkillCatalogEntry:
    return SkillCatalogEntry(name=name, description="d", when_to_use="w", tags=tags)


def test_consensus_subgraph_visibility():
    vis = AGENT_SKILL_VISIBILITY["consensus_subgraph"]
    catalog = [
        _entry("broker_consensus_mining", ["consensus", "analyst"]),
        _entry("variant_view_discovery", ["variant_view"]),
        _entry("section_writing", ["writing"]),
        _entry("valuation", ["valuation"]),
    ]
    eligible = filter_eligible_catalog(catalog, vis)
    names = {e.name for e in eligible}
    assert "broker_consensus_mining" in names
    assert "variant_view_discovery" in names
    assert "section_writing" not in names


def test_research_loop_excludes_writing_and_qa():
    vis = AGENT_SKILL_VISIBILITY["research_loop"]
    catalog = [
        _entry("section_writing", ["writing"]),
        _entry("standardized_qa", ["qa"]),
        _entry("business_model_analysis", ["business_model"]),
    ]
    eligible = filter_eligible_catalog(catalog, vis)
    names = {e.name for e in eligible}
    assert "business_model_analysis" in names
    assert "section_writing" not in names
    assert "standardized_qa" not in names


def test_risk_mapping_whitelist():
    vis = AGENT_SKILL_VISIBILITY["risk_mapping"]
    catalog = [
        _entry("risk_counterthesis", ["risk"]),
        _entry("valuation", ["valuation"]),
    ]
    eligible = filter_eligible_catalog(catalog, vis)
    assert [e.name for e in eligible] == ["risk_counterthesis"]


def test_config_override_agent_visibility():
    config = {
        "equity_research": {
            "agent_skills": {
                "risk_mapping": {"include_names": ["valuation"]},
            }
        }
    }
    vis = resolve_agent_visibility("risk_mapping", config)
    catalog = [
        _entry("risk_counterthesis", ["risk"]),
        _entry("valuation", ["valuation"]),
    ]
    eligible = filter_eligible_catalog(catalog, vis)
    assert [e.name for e in eligible] == ["valuation"]


def test_registry_eligible_catalog_sizes():
    registry = SkillRegistry(known_tools=set(ToolRegistry().list_tools()))
    consensus = registry.get_eligible_catalog("consensus_subgraph")
    planning = registry.get_eligible_catalog("dynamic_planning")
    assert len(consensus) < len(registry.get_catalog())
    assert len(planning) < len(registry.get_catalog())
