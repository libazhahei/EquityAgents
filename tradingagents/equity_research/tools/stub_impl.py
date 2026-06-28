"""Stub implementations for catalogued but not-yet-built tools."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.tools.errors import raise_not_implemented


def _stub(name: str, **_kwargs: Any) -> None:
    raise_not_implemented(name)


# §1 system (commented in feedback)
cost_tracker = lambda **kw: _stub("cost_tracker", **kw)
permission_check = lambda **kw: _stub("permission_check", **kw)
task_progress_report = lambda **kw: _stub("task_progress_report", **kw)

# §2 search (commented)
browser_search = lambda **kw: _stub("browser_search", **kw)
browser_fetch_rendered = lambda **kw: _stub("browser_fetch_rendered", **kw)

# §3 document (commented)
ocr_reader = lambda **kw: _stub("ocr_reader", **kw)
cross_document_compare = lambda **kw: _stub("cross_document_compare", **kw)

# §4 finance (P2 / commented)
estimate_revision_tracker = lambda **kw: _stub("estimate_revision_tracker", **kw)
segment_revenue_parser = lambda **kw: _stub("segment_revenue_parser", **kw)
guidance_extractor = lambda **kw: _stub("guidance_extractor", **kw)
sentiment_signal_fetch = lambda **kw: _stub("sentiment_signal_fetch", **kw)

# §5 academic (commented section)
paper_pdf_reader = lambda **kw: _stub("paper_pdf_reader", **kw)
paper_section_extractor = lambda **kw: _stub("paper_section_extractor", **kw)
paper_claim_extractor = lambda **kw: _stub("paper_claim_extractor", **kw)
github_search = lambda **kw: _stub("github_search", **kw)
citation_graph_search = lambda **kw: _stub("citation_graph_search", **kw)
dataset_finder = lambda **kw: _stub("dataset_finder", **kw)
benchmark_info_fetch = lambda **kw: _stub("benchmark_info_fetch", **kw)
prompt_extractor = lambda **kw: _stub("prompt_extractor", **kw)
equation_extractor = lambda **kw: _stub("equation_extractor", **kw)
method_to_pseudocode = lambda **kw: _stub("method_to_pseudocode", **kw)
experiment_table_extractor = lambda **kw: _stub("experiment_table_extractor", **kw)

# §6 code (commented)
unit_test_runner = lambda **kw: _stub("unit_test_runner", **kw)
lint_runner = lambda **kw: _stub("lint_runner", **kw)
log_analyzer = lambda **kw: _stub("log_analyzer", **kw)
dependency_inspector = lambda **kw: _stub("dependency_inspector", **kw)
repo_clone = lambda **kw: _stub("repo_clone", **kw)
notebook_runner = lambda **kw: _stub("notebook_runner", **kw)
experiment_runner = lambda **kw: _stub("experiment_runner", **kw)
metric_evaluator = lambda **kw: _stub("metric_evaluator", **kw)
diff_generator = lambda **kw: _stub("diff_generator", **kw)
patch_apply = lambda **kw: _stub("patch_apply", **kw)

# §7 data (P2)
data_cleaner = lambda **kw: _stub("data_cleaner", **kw)
feature_engineering_assistant = lambda **kw: _stub("feature_engineering_assistant", **kw)

# §8 browser / computer use (commented)
browser_open = lambda **kw: _stub("browser_open", **kw)
browser_click = lambda **kw: _stub("browser_click", **kw)
browser_type = lambda **kw: _stub("browser_type", **kw)
browser_screenshot = lambda **kw: _stub("browser_screenshot", **kw)
browser_extract_text = lambda **kw: _stub("browser_extract_text", **kw)
browser_download = lambda **kw: _stub("browser_download", **kw)
browser_form_fill = lambda **kw: _stub("browser_form_fill", **kw)
browser_login_flow = lambda **kw: _stub("browser_login_flow", **kw)

# §9 artifact (commented)
docx_writer = lambda **kw: _stub("docx_writer", **kw)
pptx_writer = lambda **kw: _stub("pptx_writer", **kw)
chart_embedder = lambda **kw: _stub("chart_embedder", **kw)
pdf_exporter = lambda **kw: _stub("pdf_exporter", **kw)
report_formatter = lambda **kw: _stub("report_formatter", **kw)
citation_formatter = lambda **kw: _stub("citation_formatter", **kw)

# §10 quality (commented)
compliance_filter = lambda **kw: _stub("compliance_filter", **kw)
hallucination_checker = lambda **kw: _stub("hallucination_checker", **kw)
recency_checker = lambda **kw: _stub("recency_checker", **kw)
source_reliability_scorer = lambda **kw: _stub("source_reliability_scorer", **kw)
assumption_stress_tester = lambda **kw: _stub("assumption_stress_tester", **kw)
reproducibility_checker = lambda **kw: _stub("reproducibility_checker", **kw)
result_consistency_checker = lambda **kw: _stub("result_consistency_checker", **kw)

# §11 human (P2)
human_edit_artifact = lambda **kw: _stub("human_edit_artifact", **kw)
human_set_constraints = lambda **kw: _stub("human_set_constraints", **kw)
