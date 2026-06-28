---
name: scientific_investment_reasoning
description: Formulate testable investment hypotheses with structured scoring.
when_to_use: |
  Use when generating testable hypotheses from research problems.
tags: [reasoning, hypothesis, research]
tools: [store_claim, store_assumption, memory_retrieve]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:ScientificInvestmentReasoningHandler
version: 1
---

## Constraints

- Hypotheses must be testable with specified evidence
- Include mechanism and forecast linkage
- Score across materiality, verifiability, and risk-reward

## Prompt Template

Formulate testable investment hypotheses for {ticker}. Objective: {objective}.
