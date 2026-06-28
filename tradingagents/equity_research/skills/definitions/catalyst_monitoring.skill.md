---
name: catalyst_monitoring
description: Build a catalyst calendar from gaps and earnings events.
when_to_use: |
  Use when tracking near-term and medium-term catalysts for the thesis.
tags: [catalyst, calendar, monitoring]
tools: [earnings_calendar, news_search, store_claim]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:CatalystMonitoringHandler
version: 1
---

## Constraints

- Include earnings and gap-linked catalysts
- Assign timeframe buckets: near_term, medium_term
- Keep catalyst descriptions actionable

## Prompt Template

Build a catalyst calendar for {ticker} from expectation gaps and upcoming events.
