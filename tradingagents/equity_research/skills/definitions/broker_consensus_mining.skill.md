---
name: broker_consensus_mining
description: Rebuild the market consensus framework via search and structured extraction.
when_to_use: |
  Use when analyst revenue/EPS estimates, KPI focus, or mainstream investment logic must be mapped before gap_finder runs.
tags: [consensus, analyst, perplexity, estimates]
tools: []
compatible_with: [variant_view_discovery]
composable: true
handler: tradingagents.equity_research.skills.handlers.impl:BrokerConsensusHandler
output_schema:
  type: StructuredConsensusView
version: 1
---

## Constraints

- Collect public market information only; do not invent forecasts
- Cover all five consensus dimensions
- Attribute source reliability for each dimension (primary / institutional / aggregator / media / social)
- Normalize fiscal/calendar period, quarter, GAAP/non-GAAP, actual vs guidance vs consensus for every numeric estimate
- Do not use Reddit, YouTube, or social sources as core estimate evidence

## Prompt Template

You are a sell-side consensus analyst for {ticker} ({sector}). Rebuild the market consensus framework from public evidence for gap analysis.

Context: report_type={report_type}, instrument_context={instrument_context}

## Query Guidance

Public web sources only — no FactSet, Bloomberg Terminal, Refinitiv, or other paid databases.

- Quantitative: {ticker} public analyst consensus revenue EPS estimates range from earnings calls news aggregator
- KPI: {ticker} key metrics analysts watch earnings call guidance public filings
- Pricing: {ticker} forward PE EV EBITDA implied growth vs peers public market data
- Narrative: {ticker} bull bear investment thesis debate financial news
- Delta: {ticker} estimate revision guidance change recent quarter public sources
