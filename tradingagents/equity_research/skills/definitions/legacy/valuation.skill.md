---
status: legacy
name: valuation
description: Compute valuation using trading multiples and structured facts.
when_to_use: |
  Use when target price and rating must be derived from fundamentals and forecast inputs.
tags: [valuation, multiples, modeling]
tools: [calculate_trading_multiple_valuation, stock_quote, valuation_multiples_fetch, calculate_sensitivity_table, store_claim]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:ValuationHandler
version: 1
---

## Constraints

- Target price must come from the valuation calculator output
- State key multiples and assumptions explicitly
- Flag mock or low-confidence inputs

## Prompt Template

Produce a valuation view for {ticker} using trading multiples and available forecast data.
