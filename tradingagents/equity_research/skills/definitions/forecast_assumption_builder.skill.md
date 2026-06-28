---
name: forecast_assumption_builder
description: Build forecast assumptions from business drivers and claims.
when_to_use: |
  Use when model assumptions must link to business drivers and verified claims.
tags: [forecast, assumptions, modeling]
tools: [store_assumption, store_claim, retrieve_claims_by_section]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:ForecastAssumptionBuilderHandler
version: 1
---

## Constraints

- Each assumption must map to a driver or claim
- State units and time horizon explicitly
- Flag assumptions needing more evidence

## Prompt Template

Build forecast assumptions for {ticker} from business drivers and verified claims.
