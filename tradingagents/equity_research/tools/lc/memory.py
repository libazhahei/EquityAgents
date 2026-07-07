"""LangChain memory and evidence tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool

from tradingagents.equity_research.tools import evidence_memory, memory_search_tools, memory_tools


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


@tool
def search_evidence(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Semantic search query over evidence quotes"] = "",
    metric: Annotated[str, "Optional metric filter, e.g. revenue_growth"] = "",
    max_items: Annotated[int, "Maximum evidence items to return"] = 10,
) -> dict[str, Any]:
    """Search evidence ledger by semantic query and optional metric filter."""
    return memory_search_tools.search_evidence(
        state, query, metric=metric, max_items=max_items,
    )


@tool
def search_claims(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Optional semantic ranking query"] = "",
    section_id: Annotated[str, "Filter by report section id"] = "",
    metric: Annotated[str, "Filter by metric keyword"] = "",
    confidence_min: Annotated[float | None, "Minimum claim confidence"] = None,
    max_items: Annotated[int, "Maximum claims to return"] = 10,
) -> dict[str, Any]:
    """Search claims by section, confidence, and metric."""
    return memory_search_tools.search_claims(
        state,
        query,
        section_id=section_id,
        metric=metric,
        confidence_min=confidence_min,
        max_items=max_items,
    )


@tool
def search_assumptions(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Optional semantic ranking query"] = "",
    metric: Annotated[str, "Filter by assumption metric"] = "",
    sensitivity: Annotated[str, "Filter by sensitivity: high, medium, or low"] = "",
    max_items: Annotated[int, "Maximum assumptions to return"] = 10,
) -> dict[str, Any]:
    """Search model assumptions by metric and sensitivity."""
    return memory_search_tools.search_assumptions(
        state,
        query,
        metric=metric,
        sensitivity=sensitivity,
        max_items=max_items,
    )


@tool
def search_consensus(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Semantic search query over consensus entries"] = "",
    metric: Annotated[str, "Filter by consensus metric"] = "",
    max_items: Annotated[int, "Maximum consensus items to return"] = 5,
) -> dict[str, Any]:
    """Search market consensus ledger entries."""
    return memory_search_tools.search_consensus(
        state, query, metric=metric, max_items=max_items,
    )


@tool
def search_conflicts(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    metric: Annotated[str, "Optional metric filter for conflicts"] = "",
) -> dict[str, Any]:
    """List open evidence conflicts and contradiction fragments."""
    return memory_search_tools.search_conflicts(state, metric=metric)


@tool
def search_memory_timeline(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    last_n: Annotated[int, "Number of recent iteration snapshots"] = 5,
) -> dict[str, Any]:
    """Return recent iteration snapshots for trend analysis."""
    return memory_search_tools.search_memory_timeline(state, last_n=last_n)


@tool
def search_research_context(
    state: Annotated[dict[str, Any], "Research state snapshot"],
    query: Annotated[str, "Research question or objective for context ranking"] = "",
    parent_nodes: Annotated[list[str] | None, "Thesis graph parent node ids"] = None,
    max_items: Annotated[int, "Maximum total context items"] = 20,
) -> dict[str, Any]:
    """Build holistic research context across evidence, claims, assumptions, and consensus."""
    return memory_search_tools.search_research_context(
        state, query, parent_nodes=parent_nodes, max_items=max_items,
    )


MEMORY_SEARCH_TOOL_NAMES: tuple[str, ...] = (
    "search_evidence",
    "search_claims",
    "search_assumptions",
    "search_consensus",
    "search_conflicts",
    "search_memory_timeline",
    "search_research_context",
)


def make_memory_search_tools(deps: Any) -> list[BaseTool]:
    """Deps-aware memory search tools (embedding retrieval when configured)."""

    @tool
    def search_evidence_deps(
        state: Annotated[dict[str, Any], "Research state snapshot"],
        query: Annotated[str, "Semantic search query over evidence quotes"] = "",
        metric: Annotated[str, "Optional metric filter"] = "",
        max_items: Annotated[int, "Maximum evidence items"] = 10,
    ) -> dict[str, Any]:
        """Search evidence ledger by semantic query and optional metric filter."""
        return memory_search_tools.search_evidence(
            state, query, metric=metric, max_items=max_items, deps=deps,
        )

    @tool
    def search_claims_deps(
        state: Annotated[dict[str, Any], "Research state snapshot"],
        query: Annotated[str, "Optional semantic ranking query"] = "",
        section_id: Annotated[str, "Filter by report section id"] = "",
        metric: Annotated[str, "Filter by metric keyword"] = "",
        confidence_min: Annotated[float | None, "Minimum claim confidence"] = None,
        max_items: Annotated[int, "Maximum claims to return"] = 10,
    ) -> dict[str, Any]:
        """Search claims by section, confidence, and metric."""
        return memory_search_tools.search_claims(
            state,
            query,
            section_id=section_id,
            metric=metric,
            confidence_min=confidence_min,
            max_items=max_items,
            deps=deps,
        )

    @tool
    def search_assumptions_deps(
        state: Annotated[dict[str, Any], "Research state snapshot"],
        query: Annotated[str, "Optional semantic ranking query"] = "",
        metric: Annotated[str, "Filter by assumption metric"] = "",
        sensitivity: Annotated[str, "Filter by sensitivity"] = "",
        max_items: Annotated[int, "Maximum assumptions to return"] = 10,
    ) -> dict[str, Any]:
        """Search model assumptions by metric and sensitivity."""
        return memory_search_tools.search_assumptions(
            state,
            query,
            metric=metric,
            sensitivity=sensitivity,
            max_items=max_items,
            deps=deps,
        )

    @tool
    def search_consensus_deps(
        state: Annotated[dict[str, Any], "Research state snapshot"],
        query: Annotated[str, "Semantic search query"] = "",
        metric: Annotated[str, "Filter by consensus metric"] = "",
        max_items: Annotated[int, "Maximum consensus items"] = 5,
    ) -> dict[str, Any]:
        """Search market consensus ledger entries."""
        return memory_search_tools.search_consensus(
            state, query, metric=metric, max_items=max_items, deps=deps,
        )

    search_evidence_deps.name = "search_evidence"
    search_claims_deps.name = "search_claims"
    search_assumptions_deps.name = "search_assumptions"
    search_consensus_deps.name = "search_consensus"

    @tool
    def search_research_context_deps(
        state: Annotated[dict[str, Any], "Research state snapshot"],
        query: Annotated[str, "Research question or objective"] = "",
        parent_nodes: Annotated[list[str] | None, "Thesis graph parent node ids"] = None,
        max_items: Annotated[int, "Maximum total context items"] = 20,
    ) -> dict[str, Any]:
        """Build holistic research context across all ledgers."""
        return memory_search_tools.search_research_context(
            state, query, parent_nodes=parent_nodes, max_items=max_items, deps=deps,
        )

    search_research_context_deps.name = "search_research_context"

    return [
        search_evidence_deps,
        search_claims_deps,
        search_assumptions_deps,
        search_consensus_deps,
        search_conflicts,
        search_memory_timeline,
        search_research_context_deps,
    ]
