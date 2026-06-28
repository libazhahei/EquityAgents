---
name: standardized_qa
description: Run standardized quality assessment on report state.
when_to_use: |
  Use at IC or final QA gates for standardized scoring.
tags: [qa, quality, review]
tools: [claim_evidence_checker, coverage_evaluator, conflict_detector, citation_checker]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:StandardizedQAHandler
version: 1
---

## Constraints

- Score across standard QA dimensions
- List blocking issues separately from warnings
- Do not modify underlying claims

## Prompt Template

Run standardized QA assessment on the current {ticker} report state.
