---
name: example_skill
description: One-line English description for LLM catalog discovery
when_to_use: |
  Natural-language trigger conditions describing when this skill should be loaded.
tags: [tag1, tag2]
tools: [tool_name_a, tool_name_b]
compatible_with: []
composable: false
handler: tradingagents.equity_research.skills.handlers.impl:ExampleHandler
output_schema:
  type: SkillOutput
version: 1
---

## Constraints

- Behavioral constraints injected into the system prompt after the skill is loaded
- One constraint per bullet

## Prompt Template

Core prompt fragment for the skill. Variables: {ticker} {sector} {report_type} {instrument_context} {industry} {objective}

## Query Guidance

(Optional) Query construction principles for search-heavy skills.

---

### Catalog vs full load

At startup the registry scans **frontmatter only** and builds a lightweight catalog with:

- `name`, `description`, `when_to_use`, `tags`

Agent visibility config ([`agent_visibility.py`](agent_visibility.py)) narrows which catalog entries each agent sees.
The LLM receives only that catalog in the prompt and decides which skills to load.
Full markdown body (Constraints, Prompt Template, Query Guidance) is parsed on demand via `registry.read_skill(name)`.

Do not reference other skills inside prompt text; use `compatible_with` in frontmatter for pairing hints only.
