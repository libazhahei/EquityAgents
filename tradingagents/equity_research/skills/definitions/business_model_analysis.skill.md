---
name: business_model_analysis
description: Analyze business model structure and revenue drivers.
when_to_use: |
  Use when building the business model section or revenue driver claims.
tags: [business_model, drivers, fundamentals]
tools: [financial_statement_fetch, company_profile, store_claim, store_evidence]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:BusinessModelAnalysisHandler
version: 1
---

## Constraints

- Identify at least two distinct revenue drivers
- Tie drivers to financial statement line items
- Cite supporting evidence

## Prompt Template

Analyze the business model and revenue drivers for {ticker} in {sector}. Sector: {sector}. Report type: {report_type}.
