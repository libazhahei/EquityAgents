---
name: variant_view_discovery
description: Identify variant views that differ from market consensus.
when_to_use: |
  Use after consensus is available to articulate where our view differs from the market.
tags: [variant_view, consensus, thesis]
tools: [memory_retrieve, retrieve_claims_by_section, store_claim]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:VariantViewDiscoveryHandler
version: 1
---

## Constraints

- Each variant view must reference a specific consensus assumption
- Limit to the highest-materiality gaps
- Store claims with clear variant statements

## Prompt Template

Identify 2-3 variant views for {ticker} that differ from the current consensus snapshot. Link each view to expectation gaps and required evidence.
