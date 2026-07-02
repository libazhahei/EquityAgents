---
status: legacy
name: risk_counterthesis
description: Map risks to the thesis and gather counter-evidence.
when_to_use: |
  Use when the risk section or counter-thesis mapping is required.
tags: [risk, counterthesis, diligence]
tools: [retrieve_contradictory_evidence, store_claim]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:RiskCounterThesisHandler
version: 1
---

## Constraints

- Each core thesis point needs a mapped risk
- Include monitoring metrics for key risks
- Surface contradictory evidence when available

## Prompt Template

Map key risks and counter-evidence for the {ticker} investment thesis.
