---
name: collaborative_memory
description: Retrieve cross-branch collaborative memory for research iterations.
when_to_use: |
  Use when prior branch evidence and claims should inform the current iteration.
tags: [memory, collaboration, research]
tools: [memory_retrieve, retrieve_claims_by_section, retrieve_contradictory_evidence]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:CollaborativeMemoryHandler
version: 1
---

## Constraints

- Prefer high-reliability evidence from parent branches
- Summarize reusable claims only
- Avoid duplicating already verified facts

## Prompt Template

Retrieve collaborative memory context for {ticker} research branches.
