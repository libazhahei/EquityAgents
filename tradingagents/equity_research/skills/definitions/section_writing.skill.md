---
name: section_writing
description: Prepare report section context from verified claims.
when_to_use: |
  Use when drafting a report section from verified claims.
tags: [writing, report]
tools: [retrieve_claims_by_section, link_evidence_to_claim, memory_retrieve]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:SectionWritingHandler
version: 1
---

## Constraints

- Use verified claims only
- Preserve claim-to-evidence linkage
- Do not introduce new facts

## Prompt Template

Prepare writing context for the active report section on {ticker} using verified claims.
