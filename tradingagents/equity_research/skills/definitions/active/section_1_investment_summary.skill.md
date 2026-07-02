---
name: section_1_investment_summary
description: Build the executive summary, investment rating, target price, thesis, catalysts, and risk/reward snapshot for an equity research report..
when_to_use: |
  Use when the report needs a concise front-page investment summary, including rating, target price, upside/downside, core thesis, variant view, and catalyst timeline. This skill is especially useful after company, industry, financial, forecast, valuation, scenario, and risk work has been completed and needs to be synthesized for a retail-investor-readable summary.
tags: [section_research, investment_summary]
status: active
tools: [web_search, filings_search, memory_retrieve, store_evidence]
compatible_with: [variant_view_discovery]
composable: false
version: 1
---

## Constraints
- Write for a retail investor who should understand the section in under 60 seconds.
- State the investment rating, target price, current price, expected 12-month total return, and market cap clearly near the top.
- The rating must be consistent with the expected 12-month total return.
- Use the following rating basis unless instructed otherwise:
  - Buy: upside of at least 15%
  - Overweight: upside of at least 10%
  - Hold: between -10% and +15%
  - Underperform: downside worse than -5%
  - Sell: downside worse than -10%
- Include a clear “Bottom Line” statement summarizing the asymmetric risk/reward.
- Do not provide a rating if current price or target price is missing.
- Do not invent market data, consensus data, financial metrics, or catalysts.
- If current price, market cap, or consensus target price is used, include the date and source context.
- Include a variant view explaining what the market is missing or mispricing.
- Include a strict catalyst timeline with expected timing, event type, and likely stock impact.
- Explain why the stock should move and when it may move.
- Avoid excessive jargon; if technical terms are unavoidable, explain them briefly.
- Distinguish clearly between company facts, market consensus, and the analyst’s own view.
- Flag any unresolved data gaps that could affect the rating or target price.
## Prompt Template
You are an equity research analyst preparing the Executive Summary & Investment Thesis for {ticker} ({sector}).
Context:
- report_type={report_type}
- instrument_context={instrument_context}
- industry={industry}
- objective={objective}
Your task is to produce a concise but professional investment summary that a retail investor can understand in under 60 seconds.
Required outputs:
1. retail_tldr_bottom_line
2. investment_rating
3. target_price
4. current_price
5. expected_total_return_pct
6. market_cap
7. key_financial_summary_table
8. core_thesis_bullet_points
9. variant_view
10. catalyst_timeline
The summary must answer:
- What is the rating?
- What is the target price?
- What return does that imply?
- Why should the stock move?
- When could the stock move?
- What is the key risk/reward asymmetry?
- What is the market missing?
If price, target price, or rating support is insufficient, explicitly say the section cannot be finalized and list the missing items.
## Query Guidance
Use public web sources only unless internal approved data is provided.
Prioritize:
- Company investor relations pages
- Latest earnings releases and earnings call transcripts
- SEC filings or local exchange filings
- Reputable financial news
- Public analyst consensus aggregators
- Market data providers with timestamped prices
Suggested queries:
- {ticker} analyst rating target price consensus latest
- {ticker} stock price market cap latest
- {ticker} investment thesis catalysts latest
- {ticker} earnings call guidance catalyst timeline
- {ticker} bull bear case valuation upside downside
Evidence requirements:
- At least one source for current price and market cap
- At least one source for consensus or external target price context, if used
- At least one source for recent company performance, guidance, or catalyst timing