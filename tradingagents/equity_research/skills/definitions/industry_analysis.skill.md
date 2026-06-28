---
name: industry_analysis
description: Analyze industry structure and competitive landscape.
when_to_use: |
  Use when the industry and competition section needs evidence-backed claims.
tags: [industry, competition, fundamentals]
tools: [news_search, peer_comps_fetch, filings_search, store_claim, store_evidence]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:IndustryAnalysisHandler
version: 1
---

## Constraints

- Compare competitive dynamics and market structure
- Cite recent industry news or filings
- Link industry trends to company drivers

## Prompt Template

Analyze industry and competitive dynamics for {ticker} in {industry}.
