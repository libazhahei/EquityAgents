---
name: thesis_exploration_dag
description: Initialize and extend thesis exploration branches in the research graph.
when_to_use: |
  Use when initializing or extending the in-state research graph from expectation gaps.
tags: [thesis, dag, research]
tools: []
compatible_with: [variant_view_discovery]
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:ThesisExplorationDAGHandler
version: 1
---

## Constraints

- Branch from expectation gaps with distinct hypotheses
- Keep branch count manageable
- Link branches to parent thesis nodes

## Prompt Template

Initialize thesis exploration branches for {ticker} from current expectation gaps.
