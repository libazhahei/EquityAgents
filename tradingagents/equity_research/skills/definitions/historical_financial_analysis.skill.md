---
name: historical_financial_analysis
description: Analyze historical financial performance and trends.
when_to_use: |
  Use when the historical financials section or CAGR analysis is required.
tags: [financials, historical, fundamentals]
tools: [financial_statement_fetch, calculate_cagr, time_series_analyzer, store_claim]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:HistoricalFinancialAnalysisHandler
version: 1
---

## Constraints

- Use reported financials as primary evidence
- Highlight multi-year trends and inflection points
- Avoid forward projections in this skill

## Prompt Template

Review historical financial trends for {ticker}. Summarize revenue, margin, and cash flow patterns over recent years.
