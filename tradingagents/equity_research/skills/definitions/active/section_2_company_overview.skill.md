---
name: section_2_company_overview
description: Build the company overview section covering business identity, history, management, ownership, segments, geography, and transformation milestones.
when_to_use: |
  Use when an equity research report needs a structured company background section. This skill should be loaded when the analyst must explain what the company does, where it operates, who runs it, who owns it, how revenue is segmented, and what major historical transformations shaped the company..
tags: [section_research, company_overview]
status: active
tools: [web_search, filings_search, memory_retrieve, store_evidence]
compatible_with: [variant_view_discovery]
composable: false
version: 1
---

## Constraints
- Focus on business identity, corporate history, ownership, management, segment mix, geographic mix, and transformation milestones.
- Whenever introducing complex industry-specific terms, technologies, or business models, provide a plain-English explanation.
- Do not assume ownership structure, management background, or segment exposure without evidence.
- Distinguish between current business mix and historical business mix.
- Use the latest annual report, 10-K, 20-F, prospectus, investor presentation, or official company website as primary evidence where available.
- If segment or geographic revenue data is unavailable, state that clearly and use the best available proxy only with caveats.
- Avoid promotional language copied from company materials; translate corporate claims into neutral research language.
- Identify major transformation nodes such as IPO, mergers, divestitures, leadership changes, strategic pivots, major product launches, restructuring, or geographic expansion.
- Include a jargon translation glossary for non-technical readers.
- Highlight any complexity in corporate structure, variable interest entities, dual-class shares, controlling shareholders, or government ownership if relevant.
- Flag data quality issues, stale disclosures, or inconsistent segment definitions.
## Prompt Template
You are an equity research analyst preparing the Company Overview section for {ticker} ({sector}).
Context:
- report_type={report_type}
- instrument_context={instrument_context}
- industry={industry}
- objective={objective}
Your task is to explain what the company is, how it evolved, who controls and manages it, and how its business is organized.
Required outputs:
1. business_description
2. jargon_translation_glossary
3. ownership_structure
4. management_background
5. historical_transformation_nodes
6. business_segment_breakdown
7. geographic_breakdown
The section should answer:
- What does the company do in plain English?
- What are its main products, services, or platforms?
- What are its major business segments?
- Where does it generate revenue geographically?
- Who owns or controls the company?
- Who are the key executives and what are their relevant backgrounds?
- What historical events explain the company’s current shape?
- What technical or industry terms must readers understand?
Use neutral, professional language suitable for a sell-side or independent equity research report.
## Query Guidance
Use primary company sources first, then reputable secondary sources.
Preferred sources:
- Latest annual report / 10-K / 20-F / annual filing
- Latest investor presentation
- Company investor relations website
- Proxy statement or ownership filing
- Exchange filings
- Reputable business databases or financial media
Suggested queries:
- {ticker} company overview business segments geographic mix
- {ticker} annual report business segments revenue by geography
- {ticker} management team ownership structure
- {ticker} investor presentation business overview
- {ticker} history acquisitions divestitures IPO transformation
Evidence requirements:
- At least one primary source for business description or segment mix
- At least one source for management or ownership
- At least one source for historical transformation milestones, if available