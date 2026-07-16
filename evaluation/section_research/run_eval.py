#!/usr/bin/env python3
"""CLI runner for section research evaluation."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `uv run python evaluation/section_research/run_eval.py` from repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.section_research.adapters.langsmith_pull import bundle_from_langsmith
from evaluation.section_research.adapters.live import bundle_from_live
from evaluation.section_research.evaluators.end_to_end import evaluate_end_to_end
from evaluation.section_research.evaluators.merge import deltas_exceed_threshold, merge_scores
from evaluation.section_research.evaluators.trajectory import evaluate_trajectory
from evaluation.section_research.judge.agent import run_judge_agent
from evaluation.section_research.judge.rubric import load_rubric, merge_rubric
from evaluation.section_research.judge.structured import (
    judge_breakdown_to_expected,
    run_structured_judge,
)
from evaluation.section_research.types import EvalBundle, FixtureMeta, ScoreReport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("section_research_eval")

_PKG = Path(__file__).resolve().parent
_DATASETS = _PKG / "datasets"
_REPORTS = _PKG / "reports"
_LS_DATASET_NAME = "section-research-eval"


def _load_fixture(case_id: str) -> tuple[FixtureMeta, Path]:
    path = _DATASETS / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Dataset case not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = FixtureMeta.model_validate({**raw, "case_id": raw.get("case_id") or case_id})
    return meta, path


def _write_expected(fixture_path: Path, report: ScoreReport) -> None:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected = dict(raw.get("expected_scores") or {})
    expected.update({
        "completion_score": report.completion_score,
        "schema_score": report.schema_score,
        "trajectory_score": report.trajectory_score,
        "overall_score": report.overall_score,
    })
    if report.judge is not None:
        expected.update(judge_breakdown_to_expected(report.judge))
    raw["expected_scores"] = expected
    fixture_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote expected_scores to %s", fixture_path)


def _evaluate_bundle(
    bundle: EvalBundle,
    *,
    skip_judge: bool,
    judge_agent: bool,
) -> ScoreReport:
    default_rubric = load_rubric()
    rubric = merge_rubric(default_rubric, bundle.fixture_meta.rubric_breakdown)

    e2e = evaluate_end_to_end(bundle)
    traj = evaluate_trajectory(bundle)

    judge = None
    if not skip_judge:
        if judge_agent:
            logger.info("Running judge agent…")
            judge = run_judge_agent(bundle, rubric)
        else:
            logger.info("Running structured judge…")
            judge = run_structured_judge(bundle, rubric)

    report = merge_scores(
        bundle,
        completion_score=e2e["completion_score"],
        schema_score=e2e["schema_score"],
        trajectory_score=traj["trajectory_score"],
        judge=judge,
        rubric=rubric,
        details={
            "end_to_end": e2e["details"],
            "trajectory": traj["details"],
            "evidence_counts": {
                "tool_outputs": len(bundle.evidence.tool_outputs),
                "citations": len(bundle.evidence.citations),
                "evidence_ledger": len(bundle.evidence.evidence_ledger),
                "pending_evidence": len(bundle.evidence.pending_evidence),
            },
        },
    )
    failed = deltas_exceed_threshold(report, rubric)
    if failed:
        report.details["delta_failures"] = failed
        logger.warning("Expected-score deltas exceeded threshold for: %s", failed)
    return report


def _save_report(report: ScoreReport, path: Path | None = None) -> Path:
    _REPORTS.mkdir(parents=True, exist_ok=True)
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        case = report.case_id or f"{report.ticker}_{report.section_id}"
        path = _REPORTS / f"{case}_{stamp}.json"
    payload = report.model_dump()
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    logger.info("Wrote report %s", path)
    return path


def _upload_experiment(
    report: ScoreReport,
    bundle: EvalBundle,
    *,
    experiment: str,
    dataset_name: str = _LS_DATASET_NAME,
) -> None:
    try:
        from langsmith import Client
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("langsmith is required for --upload") from exc

    client = Client()
    # Ensure dataset exists and has this example
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except Exception:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Section research evaluation golden cases",
        )
        logger.info("Created LangSmith dataset %s", dataset_name)

    inputs = {
        "ticker": bundle.ticker,
        "section_id": bundle.section_id,
        "case_id": bundle.fixture_meta.case_id,
        "source": bundle.source,
        "run_id": bundle.run_id,
    }
    outputs = report.metrics_dict()
    outputs["details"] = report.details

    # Prefer evaluate API when available; fall back to create_run feedback style
    try:
        from langsmith.evaluation import evaluate as ls_evaluate

        def _target(example_inputs: dict[str, Any]) -> dict[str, Any]:
            return {"report": outputs, **example_inputs}

        def _metric_completion(run, example) -> dict:  # noqa: ANN001
            return {"key": "completion_score", "score": outputs.get("completion_score", 0.0)}

        def _metric_schema(run, example) -> dict:  # noqa: ANN001
            return {"key": "schema_score", "score": outputs.get("schema_score", 0.0)}

        def _metric_trajectory(run, example) -> dict:  # noqa: ANN001
            return {"key": "trajectory_score", "score": outputs.get("trajectory_score", 0.0)}

        def _metric_faithfulness(run, example) -> dict:  # noqa: ANN001
            return {
                "key": "faithfulness_score",
                "score": outputs.get("faithfulness_score", outputs.get("faithfulness", 0.0)),
            }

        def _metric_overall(run, example) -> dict:  # noqa: ANN001
            return {"key": "overall_score", "score": outputs.get("overall_score", 0.0)}

        # Upsert a single example then evaluate against it
        examples = list(client.list_examples(dataset_name=dataset_name, limit=100))
        matched = None
        for ex in examples:
            if (ex.inputs or {}).get("case_id") == inputs["case_id"]:
                matched = ex
                break
        if matched is None:
            client.create_examples(
                dataset_id=dataset.id,
                examples=[{"inputs": inputs, "outputs": {"expected_scores": bundle.fixture_meta.expected_scores}}],
            )

        ls_evaluate(
            _target,
            data=dataset_name,
            evaluators=[
                _metric_completion,
                _metric_schema,
                _metric_trajectory,
                _metric_faithfulness,
                _metric_overall,
            ],
            experiment_prefix=experiment,
            metadata={"section_research_eval": True, "case_id": inputs["case_id"]},
            max_concurrency=1,
            num_repetitions=1,
            upload_results=True,
        )
        logger.info("Uploaded LangSmith experiment prefix=%s dataset=%s", experiment, dataset_name)
    except Exception as exc:
        logger.warning("langsmith.evaluate failed (%s); creating feedback run instead", exc)
        run = client.create_run(
            name=f"section-research-eval:{bundle.fixture_meta.case_id or bundle.ticker}",
            inputs=inputs,
            run_type="chain",
            project_name=os.environ.get("LANGSMITH_PROJECT", "finance"),
            outputs=outputs,
        )
        for key, value in report.metrics_dict().items():
            try:
                client.create_feedback(run.id, key=key, score=float(value))
            except Exception as fb_exc:  # noqa: BLE001
                logger.debug("feedback %s failed: %s", key, fb_exc)
        logger.info("Created fallback LangSmith run id=%s", getattr(run, "id", run))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate section research runs")
    parser.add_argument("--dataset", help="Local dataset case id (e.g. nvda_3_business_model)")
    parser.add_argument("--run-id", help="LangSmith run id to replay")
    parser.add_argument(
        "--project",
        default=os.environ.get("LANGSMITH_PROJECT", "finance"),
        help="LangSmith project name for pull/upload context",
    )
    parser.add_argument(
        "--mode",
        choices=["live", "langsmith"],
        default=None,
        help="Override source mode (default: live if --dataset, langsmith if --run-id)",
    )
    parser.add_argument("--skip-judge", action="store_true", help="Skip LLM judge")
    parser.add_argument("--judge-agent", action="store_true", help="Use light tool-using judge agent")
    parser.add_argument(
        "--write-expected",
        action="store_true",
        help="Write scores into the dataset JSON expected_scores",
    )
    parser.add_argument("--upload", action="store_true", help="Upload metrics to LangSmith Experiment")
    parser.add_argument(
        "--experiment",
        default="section-research-v1",
        help="LangSmith experiment prefix/name",
    )
    parser.add_argument(
        "--quick-research",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Pass-through to live section research",
    )
    parser.add_argument(
        "--skip-verify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Pass-through to live section research",
    )
    parser.add_argument("-o", "--output", help="Write report JSON to this path")
    args = parser.parse_args(argv)

    if not args.dataset and not args.run_id:
        parser.error("Provide --dataset and/or --run-id")

    fixture: FixtureMeta | None = None
    fixture_path: Path | None = None
    if args.dataset:
        fixture, fixture_path = _load_fixture(args.dataset)

    mode = args.mode
    if mode is None:
        mode = "langsmith" if args.run_id and not args.dataset else "live"
        if args.run_id and args.dataset and args.mode is None:
            # Explicit: run-id wins when both given without --mode
            mode = "langsmith"

    if mode == "langsmith":
        if not args.run_id:
            parser.error("--mode langsmith requires --run-id")
        bundle = bundle_from_langsmith(
            args.run_id,
            fixture=fixture,
            project_name=args.project,
        )
    else:
        if fixture is None:
            parser.error("--mode live requires --dataset")
        bundle = bundle_from_live(
            fixture,
            dataset_dir=_DATASETS,
            quick_research=args.quick_research,
            skip_verify=args.skip_verify,
        )

    report = _evaluate_bundle(
        bundle,
        skip_judge=args.skip_judge,
        judge_agent=args.judge_agent,
    )
    out_path = Path(args.output) if args.output else None
    _save_report(report, out_path)

    print(json.dumps(report.metrics_dict(), indent=2))

    if args.write_expected:
        if fixture_path is None:
            parser.error("--write-expected requires --dataset")
        _write_expected(fixture_path, report)

    if args.upload:
        _upload_experiment(report, bundle, experiment=args.experiment)

    # Non-zero if golden regression failed
    if report.details.get("delta_failures"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
