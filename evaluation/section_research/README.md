# Section Research Evaluation

Evaluation scaffold for [`demo_section_research.py`](../../demo_section_research.py), aligned with `feedback3.md` but scoped to a single section research run.

## Modes

| Mode | Command |
|------|---------|
| Live invoke | `uv run python evaluation/section_research/run_eval.py --dataset nvda_3_business_model` |
| LangSmith replay | `uv run python evaluation/section_research/run_eval.py --run-id <id> --project finance` |
| Freeze golden scores | add `--write-expected` after a trusted judge pass |
| Upload experiment | add `--upload --experiment section-research-v1` |

## Scoring

**Deterministic:** `completion_score`, `schema_score`, `trajectory_score`

**LLM judge rubric:** `content_quality`, `coverage_vs_plan`, `faithfulness`, `gaps_honesty`, `overall`

Default judge is a single structured LLM call with a markdown breakdown table in the prompt. Use `--judge-agent` for a light read-only evidence agent. Use `--skip-judge` for deterministic-only runs.

## CI

- **PR:** `uv run pytest tests/equity_research/test_section_research_eval.py -q` (mocked, no network/LLM)
- **Nightly / manual:** full `run_eval.py` with tracing + optional `--upload`

## LangSmith

- Dataset name: `section-research-eval`
- Experiment prefix: `section-research-v*`
- Requires `LANGSMITH_API_KEY` (and usually `LANGSMITH_TRACING=true` for live runs)

## Dataset fixture

See [`datasets/nvda_3_business_model.json`](datasets/nvda_3_business_model.json). Point `background_json` / `planner_json` at richer `out/*.json` files when available.
