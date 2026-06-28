"""LangChain memory and evidence tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import evidence_memory, memory_tools


@tool
def memory_retrieve(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Memory retrieval query"] = "",
    filters: Annotated[dict[str, Any] | None, "Optional filters, e.g. parent_nodes"] = None,
) -> dict[str, Any]:
    """Retrieve relevant memory snippets from research ledgers."""
    return memory_tools.memory_retrieve(state, query, filters)


@tool
def memory_write(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    record: Annotated[dict[str, Any], "Memory record with type and payload"],
) -> dict[str, Any]:
    """Write evidence, claim, reflection, or action to memory."""
    return memory_tools.memory_write(state, record)


@tool
def store_evidence(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    fragment: Annotated[dict[str, Any], "Evidence fragment to store"],
) -> dict[str, Any]:
    """Store an evidence fragment in the research ledger."""
    return evidence_memory.store_evidence(state, fragment)


@tool
def store_claim(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    claim: Annotated[dict[str, Any], "Claim object to store"],
) -> dict[str, Any]:
    """Store a research claim in the ledger."""
    return evidence_memory.store_claim(state, claim)


@tool
def store_assumption(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    assumption: Annotated[dict[str, Any], "Model assumption to store"],
) -> dict[str, Any]:
    """Store a model assumption in the ledger."""
    return evidence_memory.store_assumption(state, assumption)


@tool
def link_evidence_to_claim(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    claim_id: Annotated[str, "Claim identifier"],
    evidence_id: Annotated[str, "Evidence identifier"],
) -> dict[str, Any]:
    """Link supporting evidence to a claim."""
    return evidence_memory.link_evidence_to_claim(state, claim_id, evidence_id)


@tool
def retrieve_claims_by_section(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    section_id: Annotated[str, "Report section identifier"],
) -> list[dict]:
    """Retrieve claims associated with a report section."""
    return evidence_memory.retrieve_claims_by_section(state, section_id)


@tool
def retrieve_contradictory_evidence(
    state: Annotated[dict[str, Any], "Research state snapshot"],
) -> list[dict]:
    """Retrieve contradictory evidence fragments from state."""
    return evidence_memory.retrieve_contradictory_evidence(state)
