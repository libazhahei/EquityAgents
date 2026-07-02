---
name: section_3_business_model
description: Analyze how the company makes money, including revenue mechanics, pricing, customers, channels, unit economics, operating metrics, margins, and alternative data signals.
when_to_use: |
  Use when an equity research report needs to explain the company’s business model and revenue drivers. This skill is appropriate when the analyst must connect products, customers, pricing, operating metrics, unit economics, and margin drivers to future financial performance.
tags: [section_research, business_model]
status: active
tools: [web_search, filings_search, memory_retrieve, store_evidence]
compatible_with: [variant_view_discovery]
composable: false
version: 1
---

## Constraints
- Explain clearly how the company makes money.
- Link revenue drivers to business mechanics such as volume, price, mix, take rate, subscription count, ARPU, utilization, bookings, backlog, retention, or transaction frequency, as applicable.
- Identify the pricing model and whether revenue is recurring, transactional, usage-based, advertising-based, license-based, hardware-based, service-based, or hybrid.
- Analyze customers and distribution channels, including direct sales, resellers, marketplaces, enterprise contracts, retail channels, app stores, distributors, or OEM relationships where relevant.
- Discuss unit economics where available, including customer acquisition cost, lifetime value, gross margin per unit, contribution margin, churn, payback period, or utilization economics.
- Explain key margin drivers such as scale, product mix, input costs, cloud costs, labor costs, manufacturing yield, logistics, R&D leverage, sales efficiency, or pricing power.
- Use alternative data only as supporting evidence, not as a replacement for company-reported financials.
- Clearly state limitations of alternative data sources such as web traffic, app downloads, job postings, credit card panels, or search trends.
- Do not infer precise financial outcomes from alternative data without caveats.
- Distinguish between reported operating metrics, management commentary, consensus focus metrics, and external alternative data signals.
- Avoid generic business model language; tailor the analysis to the company’s specific revenue engine.
- If key operating metrics are no longer disclosed or definitions changed, flag the issue.
## Prompt Template
You are an equity research analyst preparing the Business Model & Revenue Drivers section for {ticker} ({sector}).
Context:
- report_type={report_type}
- instrument_context={instrument_context}
- industry={industry}
- objective={objective}
Your task is to explain how the company generates revenue, what drives growth, what affects margins, and what operating signals validate or challenge current momentum.
Required outputs:
1. revenue_model_explanation
2. key_operating_metrics
3. pricing_model
4. customer_and_channel_analysis
5. unit_economics
6. margin_driver_analysis
7. alternative_data_momentum_signals
The section should answer:
- What exactly does the company sell?
- Who pays the company?
- How is the company paid?
- What are the key drivers of revenue growth?
- What operating metrics matter most?
- What determines gross margin and operating margin?
- Are current operating trends improving, stable, or deteriorating?
- Do alternative data signals confirm or contradict management’s narrative?
Where possible, connect business model mechanics directly to future revenue, margin, and cash flow implications.
## Query Guidance
Prioritize public company disclosures and management commentary, then supplement with reputable third-party data.
Preferred sources:
- Annual reports and quarterly filings
- Earnings releases
- Earnings call transcripts
- Investor presentations
- Company KPI disclosures
- Reputable industry datasets
- Publicly available alternative data sources
Suggested queries:
- {ticker} revenue model pricing unit economics
- {ticker} key operating metrics margin drivers
- {ticker} customers channels revenue breakdown
- {ticker} earnings call operating metrics guidance
- {ticker} alternative data web traffic app downloads hiring trends
Alternative data query examples:
- {ticker} web traffic trend latest
- {ticker} app downloads trend latest
- {ticker} job postings hiring trend
- {ticker} customer reviews usage trend
- {ticker} search interest trend
Evidence requirements:
- At least one company-reported source for revenue model or revenue breakdown
- At least one source for operating metrics or margin drivers
- At least one source for alternative data or a clear statement that relevant alternative data is unavailable