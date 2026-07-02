---
status: legacy
name: dynamic_research_planning
description: Stage-aware dynamic research planning.
when_to_use: |
  Use when the research loop needs stage prioritization and skill selection guidance.
tags: [planning, strategy, research]
tools: [ls_skills, skill_registry_lookup]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:DynamicResearchPlanningHandler
version: 1
---

## Constraints

- Balance exploration vs convergence based on iteration budget
- Recommend concrete next skills from the catalog
- Avoid redundant work on closed questions

## Prompt Template

Plan the next research stage for {ticker} given current iteration progress and open gaps.
