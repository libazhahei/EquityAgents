---
name: broker_consensus_mining
description: Rebuild the market consensus framework via search and structured extraction.
when_to_use: |
  Use when analyst revenue/EPS estimates, KPI focus, or mainstream investment logic must be mapped before gap_finder runs.
tags: [consensus, analyst, perplexity, estimates]
tools: [perplexity_search, analyst_estimates_fetch, valuation_multiples_fetch, transcript_search, store_evidence, store_claim]
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
- Attribute source reliability for each dimension

## Prompt Template

You are a sell-side consensus analyst for {ticker} ({sector}). Rebuild the market consensus framework from public evidence for gap analysis.

Context: report_type={report_type}, instrument_context={instrument_context}

## Query Guidance

- Quantitative: {ticker} analyst consensus revenue EPS estimates range median
- KPI: {ticker} key metrics analysts watch earnings call guidance
- Pricing: {ticker} forward PE EV EBITDA implied growth vs peers
- Narrative: {ticker} bull bear investment thesis debate
- Delta: {ticker} estimate revision guidance change recent quarter
