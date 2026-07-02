---
name: section_4_industry_and_competition
description: Analyze industry structure, TAM, growth, value chain position, market share shifts, competitors, competitive moat, substitution risk, and regulation.
when_to_use: |
  Use when an equity research report needs an industry and competitive landscape section. This skill is useful when the analyst must assess market size, industry growth, competitive positioning, market share movement, value chain role, regulatory factors, and risks from substitutes or supply constraints.
tags: [section_research, industry]
status: active
tools: [web_search, filings_search, memory_retrieve, store_evidence]
compatible_with: [variant_view_discovery]
composable: false
version: 1
---

## Constraints
- Focus on TAM, industry growth, value chain position, market share, competitor comparison, moat, substitution risk, and regulatory factors.
- TAM analysis must include both opportunity size and constraints on growth.
- Identify physical, operational, regulatory, or supply-chain constraints that could limit TAM realization, such as power availability, manufacturing capacity, raw materials, labor, logistics, spectrum, grid capacity, data center capacity, or permitting.
- Do not present TAM as guaranteed revenue.
- Distinguish between total addressable market, serviceable available market, and realistically obtainable market where possible.
- Competitor analysis must be dynamic: highlight market share gains, losses, new entrants, pricing pressure, product transitions, or regional shifts.
- Avoid static “Company A vs Company B” tables without explaining how the competitive position is changing.
- Include direct competitors, indirect competitors, substitutes, and potential disruptors where relevant.
- Explain the company’s value chain position and whether it has bargaining power with suppliers, customers, distributors, platforms, or regulators.
- Assess competitive moat using evidence such as scale, cost advantage, brand, network effects, switching costs, intellectual property, data advantage, distribution, ecosystem control, regulatory licenses, or customer lock-in.
- Include regulatory and policy factors that could expand or restrict the market.
- Use plain-English explanations for technical industry terms.
- Flag uncertainty in industry estimates and cite the source type for TAM or market share data.
## Prompt Template
You are an equity research analyst preparing the Industry Analysis & Competitive Landscape section for {ticker} ({sector}).
Context:
- report_type={report_type}
- instrument_context={instrument_context}
- industry={industry}
- objective={objective}
Your task is to assess the company’s industry opportunity, competitive position, market share trajectory, moat, substitutes, and regulatory environment.
Required outputs:
1. tam_estimate_and_physical_constraints
2. industry_growth_rate
3. value_chain_analysis
4. dynamic_market_share_analysis
5. competitor_comparison_table
6. competitive_position_assessment
7. regulatory_or_policy_factors
The section should answer:
- How large is the market opportunity?
- How fast is the industry growing?
- What constraints could prevent the market from reaching optimistic forecasts?
- Where does the company sit in the value chain?
- Who are the key competitors and substitutes?
- Is the company gaining or losing share?
- What is the company’s moat, and is it strengthening or weakening?
- What regulatory or policy factors matter?
- What industry changes could alter the investment case?
The output should combine quantitative industry data with qualitative competitive judgment.
## Query Guidance
Use a mix of company filings, industry reports, regulator publications, trade associations, reputable financial media, and competitor disclosures.
Preferred sources:
- Company annual reports and investor presentations
- Competitor annual reports and investor presentations
- Industry association reports
- Government or regulator publications
- Reputable market research summaries
- Trade publications
- Earnings call transcripts discussing demand, supply, market share, or pricing
Suggested queries:
- {ticker} market share competitors latest
- {ticker} industry growth TAM competition latest
- {ticker} value chain suppliers customers competitive moat
- {ticker} competitors market share gains losses latest
- {ticker} regulation policy risk industry latest
TAM and constraints query examples:
- {industry} TAM growth forecast constraints
- {industry} supply chain bottleneck capacity constraint
- {industry} regulation policy market growth
- {industry} power availability data center capacity constraint
- {industry} raw material supply constraint
Evidence requirements:
- At least one source for TAM or industry growth
- At least one source for competitor set or market share
- At least one source for regulatory or policy factors, if relevant
- At least one source showing dynamic change such as share shifts, pricing changes, capacity expansion, product transition, or new entrants