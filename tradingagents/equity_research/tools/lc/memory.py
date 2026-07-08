"""LangChain memory and evidence tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from tradingagents.equity_research.tools import evidence_memory, memory_search_tools, memory_tools

_STATE = Annotated[dict[str, Any], InjectedState]


@tool
def memory_retrieve(
    state: _STATE,
    query: Annotated[str, "Memory retrieval query"] = "",
    filters: Annotated[dict[str, Any] | None, "Optional filters, e.g. parent_nodes"] = None,
) -> dict[str, Any]:
    """Retrieve relevant memory snippets from research ledgers.

    WHEN: When you need to recall what has already been stored — before writing a section,
    synthesizing a conclusion, or deciding what to research next.

    HOW IT WORKS:
    - The query is treated as a priority question and used to semantically rank evidence,
      claims, assumptions, and consensus entries in the ledger.
    - filters["parent_nodes"] narrows retrieval to items linked to specific thesis-graph
      nodes (useful when working on a particular report section).
    - filters["priority_questions"] can be passed directly as a list of questions instead
      of a single query string.
    - Returns a bundled context dict with keys: evidence, claims, assumptions, consensus.

    USE CASES:
    - Before drafting a section: call with the section question as query to gather
      everything already known.
    - Before store_claim: retrieve supporting evidence_ids to cite.
    - Mid-research: check what gaps remain by comparing retrieved evidence against the
      research plan.

    Returns a dict with keys:
        evidence (list): matching evidence fragments
        claims (list): matching claims
        assumptions (list): matching assumptions
        consensus (list): matching consensus entries
    """
    return memory_tools.memory_retrieve(state, query, filters)


@tool
def memory_write(
    state: _STATE,
    record: Annotated[dict[str, Any], "Memory record with type and payload"],
) -> dict[str, Any]:
    """Write evidence, claim, reflection, or action to memory.

    WHEN: To persist structured records beyond raw evidence fragments. This is the
    unified write entry point — it dispatches to the correct ledger based on record type.

    RECORD TYPES AND WHEN TO USE EACH:
    - type="evidence": Equivalent to store_evidence; use for raw data points.
        Payload fields: quote, metric, value, unit, period, source_type, doc_id.
    - type="claim": When you derive a conclusion or thesis from one or more evidence items.
        Include: text (the claim), supporting_evidence_ids (list of evidence_id), confidence (0-1).
        Use AFTER store_evidence for the supporting data.
    - type="assumption": When you make or surface a modeling assumption (e.g. growth rate used).
        Include: text, metric, sensitivity (high/medium/low).
    - type="reflection": When you record an insight, lesson, or observation about the research
        process itself (e.g. "10-K filings for this ticker consistently lag by 2 quarters").
        Include: content (free-text observation).
    - type="action": When you log a significant action taken (e.g. "skipped metric X — data
        unavailable after checking SEC EDGAR and company IR page").
        Include: content (free-text description of the action and reason).

    NOTE: For raw evidence, prefer store_evidence directly. Use memory_write(type="claim") only
    when you have synthesized multiple evidence items into a conclusion.

    Returns a dict with keys:
        evidence_id, claim_id, assumption_id, reflection_id, or action_id
        (the unique id of the stored record, depending on type)
    """
    return memory_tools.memory_write(state, record)


@tool
def store_evidence(
    state: _STATE,
    fragment: Annotated[dict[str, Any], "Evidence fragment to store"],
) -> dict[str, Any]:
    """Store an evidence fragment in the research ledger.

    WHEN: After EVERY data retrieval or search result — call this BEFORE drawing conclusions.
    Unstored evidence is lost; the synthesizer node can only use evidence in the ledger.

    USE CASES:
    - Fetched a filing excerpt → store the quote, metric, value, unit, period, source.
    - Searched and found a data point → store it with full metadata.
    - Extracted a number from an earnings call → store with fiscal_quarter_or_date.

    REQUIRED FIELDS in fragment:
    - quote (the text of the evidence, e.g. "Revenue grew 22% YoY to $13.5B")
    - As many as possible of: metric, value, unit, period, source_type
      (e.g. "10-K", "earnings_call", "analyst_note"), doc_id,
      fiscal_quarter_or_date, traceable_ref.

    SIDE EFFECTS:
    - Automatically runs conflict detection against existing evidence in the ledger.
      If a contradictory fact is found (e.g. different values for the same metric/period),
      a contradiction_fragments entry is created and the conflict is tracked.
    - If the fragment includes a doc_id, the source document's reliability score is
      incremented (cited sources become more trusted over time).
    - If an embeddings backend is configured, the quote is embedded for future
      semantic retrieval via search_evidence.

    Returns a dict with keys:
        evidence_id: the unique id of the stored evidence fragment
    """
    return evidence_memory.store_evidence(state, fragment)


@tool
def store_claim(
    state: _STATE,
    claim: Annotated[dict[str, Any], "Claim object to store"],
) -> dict[str, Any]:
    """Store a research claim in the ledger.

    WHEN: After you have gathered supporting evidence and synthesized a conclusion.
    Always store the underlying evidence first via store_evidence, then store the claim.

    CLAIM FIELDS:
    - text (required): The claim statement, e.g. "Gross margin contraction is driven by
      data-center GPU mix shift, not pricing pressure."
    - supporting_evidence_ids (optional): List of evidence_id strings that back this claim.
      If omitted, the tool auto-links evidence with high text similarity (>= 0.7).
    - confidence (optional): Float 0-1 representing your confidence in the claim.
    - section_id (optional): Report section this claim belongs to (e.g. "profitability").
    - metric (optional): Primary metric the claim concerns (e.g. "gross_margin").

    SIDE EFFECTS:
    - Auto-links similar evidence if supporting_evidence_ids is not provided.
    - Cited evidence sources receive a reliability boost (+0.05).

    Returns a dict with keys:
        claim_id: the unique id of the stored claim
    """
    return evidence_memory.store_claim(state, claim)


@tool
def store_assumption(
    state: _STATE,
    assumption: Annotated[dict[str, Any], "Model assumption to store"],
) -> dict[str, Any]:
    """Store a model assumption in the ledger.

    WHEN: When you make or surface a modeling assumption during research or valuation —
    for example, a growth rate you are projecting, a discount rate you chose, or a
    terminal multiple you applied.

    ASSUMPTION FIELDS:
    - text (required): The assumption statement, e.g. "Revenue CAGR of 18% over FY2026-2028
      based on data-center cycle normalization."
    - metric (required): The metric this assumption applies to (e.g. "revenue_growth").
    - sensitivity (required): How sensitive the model is to this assumption —
      "high", "medium", or "low". High-sensitivity assumptions drive the most variance
      in valuation and should be explicitly defended.
    - value (optional): The numeric value used (e.g. 0.18).
    - rationale (optional): Brief justification for why this value was chosen.

    WHY: Assumptions are surfaced during consensus and conflict resolution. The synthesizer
    uses them to flag where the model diverges from market consensus.

    Returns a dict with keys:
        assumption_id: the unique id of the stored assumption
    """
    return evidence_memory.store_assumption(state, assumption)


@tool
def link_evidence_to_claim(
    state: _STATE,
    claim_id: Annotated[str, "Claim identifier"],
    evidence_id: Annotated[str, "Evidence identifier"],
) -> dict[str, Any]:
    """Link supporting evidence to a claim.

    WHEN: When you need to manually connect an evidence fragment to a claim that was not
    auto-linked (e.g. the evidence quote uses different wording than the claim text, so
    the similarity threshold was not met).

    BEHAVIOR:
    - Adds evidence_id to the claim's supporting_evidence_ids list (both in state claims
      and in the claim_ledger).
    - If the evidence is already linked, this is a no-op (idempotent).
    - The cited evidence source receives a reliability boost (+0.05).

    USE CASE:
    - After store_claim with no supporting_evidence_ids, manually link the evidence you
      know is relevant.
    - When adding a new piece of evidence that reinforces an existing claim.

    Returns a dict with updated claims and claim_ledger lists.
    """
    return evidence_memory.link_evidence_to_claim(state, claim_id, evidence_id)


@tool
def retrieve_claims_by_section(
    state: _STATE,
    section_id: Annotated[str, "Report section identifier"],
) -> list[dict]:
    """Retrieve claims associated with a report section.

    WHEN: When you are writing or reviewing a specific report section and need to see
    which claims have already been made for that section.

    BEHAVIOR:
    - Filters the claim_ledger by exact match on section_id.
    - Returns a list of claim dicts (may be empty if no claims exist for the section).

    USE CASE:
    - Before drafting a section, call this to check what conclusions have already been
      drawn and avoid duplicating or contradicting them.
    - After research iterations, call this to assess whether a section has sufficient
      claim coverage.
    """
    return evidence_memory.retrieve_claims_by_section(state, section_id)


@tool
def retrieve_contradictory_evidence(
    state: _STATE,
) -> list[dict]:
    """Retrieve contradictory evidence fragments from state.

    WHEN: Before finalizing a section or consensus — call this to surface evidence pairs
    that conflict with each other (e.g. two filings reporting different values for the
    same metric in the same period).

    BEHAVIOR:
    - Returns all fragments stored in state["contradiction_fragments"].
    - These are populated automatically by store_evidence when conflict detection fires.

    USE CASE:
    - Review contradictions before writing consensus to decide which evidence to trust.
    - Flag unresolved contradictions in the report as risk factors or open questions.
    - Cross-reference with search_conflicts for the full conflict picture.
    """
    return evidence_memory.retrieve_contradictory_evidence(state)


@tool
def search_evidence(
    state: _STATE,
    query: Annotated[str, "Semantic search query over evidence quotes"] = "",
    metric: Annotated[str, "Optional metric filter, e.g. revenue_growth"] = "",
    max_items: Annotated[int, "Maximum evidence items to return"] = 10,
) -> dict[str, Any]:
    """Search evidence ledger by semantic query and optional metric filter.

    WHEN: When you need to find previously stored evidence without re-fetching from
    external sources. This is the primary read-path for evidence retrieval.

    SEARCH BEHAVIOR:
    - query: Used as a semantic ranking signal — evidence quotes most similar to the
      query are returned first. Use natural language describing what you are looking for,
      e.g. "gross margin drivers in FY2025".
    - metric: Exact-match filter on the metric field of stored evidence. Use when you
      need evidence for a specific metric, e.g. "revenue_growth" or "operating_margin".
    - max_items: Caps the number of results. Default 10 is usually sufficient.

    USE CASES:
    - Before drafting a section: "What evidence do I have about revenue trends?"
    - To check gaps: "Do I have any evidence about capex guidance?"
    - To cite evidence in a claim: search by metric to find the evidence_id.

    Returns a dict with keys:
        tool: "search_evidence"
        count: number of items returned
        items: list of evidence fragment dicts
        query: the query used
        metric: the metric filter used (or None)
    """
    return memory_search_tools.search_evidence(
        state, query, metric=metric, max_items=max_items,
    )


@tool
def search_claims(
    state: _STATE,
    query: Annotated[str, "Optional semantic ranking query"] = "",
    section_id: Annotated[str, "Filter by report section id"] = "",
    metric: Annotated[str, "Filter by metric keyword"] = "",
    confidence_min: Annotated[float | None, "Minimum claim confidence"] = None,
    max_items: Annotated[int, "Maximum claims to return"] = 10,
) -> dict[str, Any]:
    """Search claims by section, confidence, and metric.

    WHEN: When you need to review what conclusions have already been drawn — for example,
    before writing a section, checking for claim coverage, or finding low-confidence
    claims that need more evidence.

    FILTER BEHAVIOR:
    - query: Semantic ranking — claims most similar to the query are returned first.
    - section_id: Exact match on the section the claim belongs to (e.g. "profitability").
    - metric: Keyword match on the metric field (e.g. "gross_margin").
    - confidence_min: Only return claims with confidence >= this threshold. Use 0.7 to
      find high-confidence claims, or leave None to see all.
    - max_items: Caps the number of results.

    USE CASES:
    - "What claims exist for the profitability section?" → section_id="profitability"
    - "Which claims are low-confidence and need more evidence?" → confidence_min=None,
      then inspect the confidence field in results.
    - "What claims are about revenue?" → metric="revenue"

    Returns a dict with keys:
        tool: "search_claims"
        count: number of claims returned
        items: list of claim dicts
    """
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
    state: _STATE,
    query: Annotated[str, "Optional semantic ranking query"] = "",
    metric: Annotated[str, "Filter by assumption metric"] = "",
    sensitivity: Annotated[str, "Filter by sensitivity: high, medium, or low"] = "",
    max_items: Annotated[int, "Maximum assumptions to return"] = 10,
) -> dict[str, Any]:
    """Search model assumptions by metric and sensitivity.

    WHEN: When you need to review or audit the assumptions that have been recorded —
    especially before consensus, valuation, or risk-factor writing.

    FILTER BEHAVIOR:
    - query: Semantic ranking — assumptions most similar to the query are returned first.
    - metric: Keyword match on the metric field (e.g. "revenue_growth").
    - sensitivity: Filter to a specific sensitivity level — "high", "medium", or "low".
      High-sensitivity assumptions are the most impactful to valuation and should be
      reviewed first.
    - max_items: Caps the number of results.

    USE CASES:
    - "What high-sensitivity assumptions have I made?" → sensitivity="high"
    - "What assumption did I use for revenue growth?" → metric="revenue_growth"
    - Before consensus: compare your assumptions against market consensus to identify
      where your model diverges.

    Returns a dict with keys:
        tool: "search_assumptions"
        count: number of assumptions returned
        items: list of assumption dicts
    """
    return memory_search_tools.search_assumptions(
        state,
        query,
        metric=metric,
        sensitivity=sensitivity,
        max_items=max_items,
    )


@tool
def search_consensus(
    state: _STATE,
    query: Annotated[str, "Semantic search query over consensus entries"] = "",
    metric: Annotated[str, "Filter by consensus metric"] = "",
    max_items: Annotated[int, "Maximum consensus items to return"] = 5,
) -> dict[str, Any]:
    """Search market consensus ledger entries.

    WHEN: When you need to compare your research findings against the current market
    consensus — for example, before finalizing a valuation or identifying where your
    thesis diverges from the Street.

    BEHAVIOR:
    - query: Semantic ranking over consensus text (e.g. analyst commentary or consensus
      summaries stored in the ledger).
    - metric: Keyword filter on the metric field (e.g. "eps", "revenue").
    - max_items: Caps results (default 5, since consensus entries tend to be fewer).

    USE CASES:
    - "What is the consensus EPS estimate?" → metric="eps"
    - Before writing the investment thesis: check consensus to frame your variant view.
    - During conflict resolution: see whether consensus aligns with one side of the
      evidence conflict.

    Returns a dict with keys:
        tool: "search_consensus"
        count: number of consensus entries returned
        items: list of consensus entry dicts
    """
    return memory_search_tools.search_consensus(
        state, query, metric=metric, max_items=max_items,
    )


@tool
def search_conflicts(
    state: _STATE,
    metric: Annotated[str, "Optional metric filter for conflicts"] = "",
) -> dict[str, Any]:
    """List open evidence conflicts and contradiction fragments.

    WHEN: Before finalizing a section, consensus, or report — call this to surface
    unresolved contradictions in the evidence base.

    BEHAVIOR:
    - Returns all open memory_conflicts and contradiction_fragments from state.
    - metric (optional): If provided, filters conflicts and fragments to those whose
      metric field contains the keyword (case-insensitive substring match).

    WHY: Unresolved conflicts weaken the report. The synthesizer and consensus nodes
    use this to decide whether to flag a metric as uncertain, seek more evidence, or
    present both sides.

    USE CASES:
    - "Are there any unresolved conflicts?" → no metric filter.
    - "Are there conflicts about gross margin?" → metric="gross margin"
    - Cross-reference with retrieve_contradictory_evidence for the raw fragment details.

    Returns a dict with keys:
        tool: "search_conflicts"
        open_conflicts: count of open conflicts
        conflicts: list of conflict dicts
        contradiction_fragments: list of contradiction fragment dicts
    """
    return memory_search_tools.search_conflicts(state, metric=metric)


@tool
def search_memory_timeline(
    state: _STATE,
    last_n: Annotated[int, "Number of recent iteration snapshots"] = 5,
) -> dict[str, Any]:
    """Return recent iteration snapshots for trend analysis.

    WHEN: When you want to understand how the research state has evolved across iterations —
    for example, to see whether evidence coverage is improving, whether conflicts are
    being resolved, or whether the research is converging.

    BEHAVIOR:
    - Returns the last `last_n` snapshots from state["iteration_snapshots"].
    - Each snapshot typically contains a summary of ledger sizes, new evidence/claims
      added, and conflicts open at that iteration.

    USE CASES:
    - "How many evidence items were added in the last 3 iterations?"
    - "Are conflicts trending down or accumulating?"
    - Before deciding to stop researching: check whether recent iterations are still
      producing new evidence or have plateaued.

    Returns a dict with keys:
        tool: "search_memory_timeline"
        research_iterations: current iteration count
        count: number of snapshots returned
        snapshots: list of snapshot dicts
    """
    return memory_search_tools.search_memory_timeline(state, last_n=last_n)


@tool
def search_research_context(
    state: _STATE,
    query: Annotated[str, "Research question or objective for context ranking"] = "",
    parent_nodes: Annotated[list[str] | None, "Thesis graph parent node ids"] = None,
    max_items: Annotated[int, "Maximum total context items"] = 20,
) -> dict[str, Any]:
    """Build holistic research context across evidence, claims, assumptions, and consensus.

    WHEN: When you need a comprehensive view of everything stored in the ledgers —
    typically at the start of a research iteration, before drafting a section, or when
    handing context to the synthesizer or consensus nodes.

    BEHAVIOR:
    - Bundles evidence, claims, assumptions, and consensus entries into a single context
      dict, semantically ranked by the query.
    - parent_nodes (optional): If provided, narrows retrieval to items associated with
      specific thesis-graph node ids — useful for section-scoped context.
    - max_items: Total cap across all ledger types (default 20).

    USE CASES:
    - Before drafting a report section: pass the section question as query.
    - At the start of a research iteration: pass the research objective to load all
      relevant context into the agent's working memory.
    - When delegating to the consensus node: call with the consensus question to provide
      a full picture of evidence, claims, and assumptions.

    Returns a dict with keys:
        tool: "search_research_context"
        evidence: list of evidence entries
        claims: list of claim entries
        assumptions: list of assumption entries
        consensus: list of consensus entries
    """
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
        state: _STATE,
        query: Annotated[str, "Semantic search query over evidence quotes"] = "",
        metric: Annotated[str, "Optional metric filter"] = "",
        max_items: Annotated[int, "Maximum evidence items"] = 10,
    ) -> dict[str, Any]:
        """Search evidence ledger by semantic query and optional metric filter.

        Same behavior as the standalone search_evidence, but uses the injected deps
        for embedding-based retrieval when a vector backend is configured. Prefer this
        version when deps are available — it produces better semantic ranking.

        See search_evidence for full parameter documentation.
        """
        return memory_search_tools.search_evidence(
            state, query, metric=metric, max_items=max_items, deps=deps,
        )

    @tool
    def search_claims_deps(
        state: _STATE,
        query: Annotated[str, "Optional semantic ranking query"] = "",
        section_id: Annotated[str, "Filter by report section id"] = "",
        metric: Annotated[str, "Filter by metric keyword"] = "",
        confidence_min: Annotated[float | None, "Minimum claim confidence"] = None,
        max_items: Annotated[int, "Maximum claims to return"] = 10,
    ) -> dict[str, Any]:
        """Search claims by section, confidence, and metric.

        Same behavior as the standalone search_claims, but uses the injected deps
        for embedding-based retrieval when a vector backend is configured.

        See search_claims for full parameter documentation.
        """
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
        state: _STATE,
        query: Annotated[str, "Optional semantic ranking query"] = "",
        metric: Annotated[str, "Filter by assumption metric"] = "",
        sensitivity: Annotated[str, "Filter by sensitivity"] = "",
        max_items: Annotated[int, "Maximum assumptions to return"] = 10,
    ) -> dict[str, Any]:
        """Search model assumptions by metric and sensitivity.

        Same behavior as the standalone search_assumptions, but uses the injected deps
        for embedding-based retrieval when a vector backend is configured.

        See search_assumptions for full parameter documentation.
        """
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
        state: _STATE,
        query: Annotated[str, "Semantic search query"] = "",
        metric: Annotated[str, "Filter by consensus metric"] = "",
        max_items: Annotated[int, "Maximum consensus items"] = 5,
    ) -> dict[str, Any]:
        """Search market consensus ledger entries.

        Same behavior as the standalone search_consensus, but uses the injected deps
        for embedding-based retrieval when a vector backend is configured.

        See search_consensus for full parameter documentation.
        """
        return memory_search_tools.search_consensus(
            state, query, metric=metric, max_items=max_items, deps=deps,
        )

    search_evidence_deps.name = "search_evidence"
    search_claims_deps.name = "search_claims"
    search_assumptions_deps.name = "search_assumptions"
    search_consensus_deps.name = "search_consensus"

    @tool
    def search_research_context_deps(
        state: _STATE,
        query: Annotated[str, "Research question or objective"] = "",
        parent_nodes: Annotated[list[str] | None, "Thesis graph parent node ids"] = None,
        max_items: Annotated[int, "Maximum total context items"] = 20,
    ) -> dict[str, Any]:
        """Build holistic research context across all ledgers.

        Same behavior as the standalone search_research_context, but uses the injected
        deps for embedding-based retrieval when a vector backend is configured.

        See search_research_context for full parameter documentation.
        """
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
