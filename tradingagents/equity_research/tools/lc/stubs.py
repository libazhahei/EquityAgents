"""LangChain @tool stubs for not-yet-implemented feedback.md tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import stub_impl as impl

# --- §1 system (commented) ---


@tool
def cost_tracker(
    tool_calls: Annotated[list[dict[str, Any]], "Tool call records to aggregate"],
) -> dict[str, Any]:
    """Track tool invocation cost and usage counts."""
    return impl.cost_tracker(tool_calls=tool_calls)


@tool
def permission_check(
    action: Annotated[dict[str, Any], "High-risk action to validate"],
) -> dict[str, Any]:
    """Check whether a high-risk action is permitted."""
    return impl.permission_check(action=action)


@tool
def task_progress_report(
    state: Annotated[dict[str, Any], "Current research task state"],
) -> dict[str, Any]:
    """Summarize current task progress."""
    return impl.task_progress_report(state=state)


# --- §2 search (commented) ---


@tool
def browser_search(query: Annotated[str, "Browser search query"]) -> dict[str, Any]:
    """Search the web using a headless browser."""
    return impl.browser_search(query=query)


@tool
def browser_fetch_rendered(url: Annotated[str, "URL to render and extract"]) -> dict[str, Any]:
    """Fetch dynamically rendered page content via browser."""
    return impl.browser_fetch_rendered(url=url)


# --- §3 document (commented) ---


@tool
def ocr_reader(
    file_path: Annotated[str, "Image or scanned PDF path"],
) -> dict[str, Any]:
    """OCR text from image or scanned PDF."""
    return impl.ocr_reader(file_path=file_path)


@tool
def cross_document_compare(
    docs: Annotated[list[dict[str, Any]], "Documents to compare"],
) -> dict[str, Any]:
    """Compare multiple documents and summarize differences."""
    return impl.cross_document_compare(docs=docs)


# --- §4 finance (P2 / commented) ---


@tool
def estimate_revision_tracker(
    ticker: Annotated[str, "Ticker symbol"],
    date_range: Annotated[str | None, "Date range for revision history"] = None,
) -> dict[str, Any]:
    """Track analyst estimate revisions over time."""
    return impl.estimate_revision_tracker(ticker=ticker, date_range=date_range)


@tool
def segment_revenue_parser(
    source: Annotated[str, "Filing or transcript text/path"],
) -> dict[str, Any]:
    """Parse segment revenue breakdown from filings or transcripts."""
    return impl.segment_revenue_parser(source=source)


@tool
def guidance_extractor(
    source: Annotated[str, "Transcript or filing text/path"],
) -> dict[str, Any]:
    """Extract management guidance from transcript or filing."""
    return impl.guidance_extractor(source=source)


@tool
def sentiment_signal_fetch(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch news/social/research sentiment signals for a ticker."""
    return impl.sentiment_signal_fetch(ticker=ticker)


# --- §5 academic (commented section) ---


@tool
def paper_pdf_reader(
    source: Annotated[str, "Paper PDF file path or URL"],
) -> dict[str, Any]:
    """Read and structure academic paper PDF content."""
    return impl.paper_pdf_reader(source=source)


@tool
def paper_section_extractor(
    paper_text: Annotated[str, "Full paper text"],
) -> dict[str, Any]:
    """Extract abstract, methods, experiments, and other sections."""
    return impl.paper_section_extractor(paper_text=paper_text)


@tool
def paper_claim_extractor(
    paper_text: Annotated[str, "Full paper text"],
) -> dict[str, Any]:
    """Extract core claims and experimental claims from a paper."""
    return impl.paper_claim_extractor(paper_text=paper_text)


@tool
def github_search(
    query: Annotated[str, "Paper title or repository search query"],
) -> dict[str, Any]:
    """Search GitHub for related code repositories."""
    return impl.github_search(query=query)


@tool
def citation_graph_search(
    paper: Annotated[str, "Paper title or DOI"],
) -> dict[str, Any]:
    """Search citation and cited-by graph for a paper."""
    return impl.citation_graph_search(paper=paper)


@tool
def dataset_finder(
    query: Annotated[str, "Paper text or dataset search query"],
) -> dict[str, Any]:
    """Find datasets referenced in or related to a paper."""
    return impl.dataset_finder(query=query)


@tool
def benchmark_info_fetch(
    benchmark_name: Annotated[str, "Benchmark name"],
) -> dict[str, Any]:
    """Fetch benchmark metrics and setup information."""
    return impl.benchmark_info_fetch(benchmark_name=benchmark_name)


@tool
def prompt_extractor(
    paper_text: Annotated[str, "Paper text including appendix"],
) -> dict[str, Any]:
    """Extract prompts from paper appendix."""
    return impl.prompt_extractor(paper_text=paper_text)


@tool
def equation_extractor(
    paper_text: Annotated[str, "Paper text containing equations"],
) -> dict[str, Any]:
    """Extract equations and variable explanations."""
    return impl.equation_extractor(paper_text=paper_text)


@tool
def method_to_pseudocode(
    method_section: Annotated[str, "Methods section text"],
) -> dict[str, Any]:
    """Convert method description to pseudocode."""
    return impl.method_to_pseudocode(method_section=method_section)


@tool
def experiment_table_extractor(
    paper_pages: Annotated[str | list[str], "Paper pages or text with experiment tables"],
) -> dict[str, Any]:
    """Extract experiment result tables from paper."""
    return impl.experiment_table_extractor(paper_pages=paper_pages)


# --- §6 code (commented) ---


@tool
def unit_test_runner(
    test_command: Annotated[str, "Unit test command to run"],
) -> dict[str, Any]:
    """Run unit tests in sandbox."""
    return impl.unit_test_runner(test_command=test_command)


@tool
def lint_runner(path: Annotated[str, "Path to lint"]) -> dict[str, Any]:
    """Run static linter on code path."""
    return impl.lint_runner(path=path)


@tool
def log_analyzer(logs: Annotated[str, "Log text to analyze"]) -> dict[str, Any]:
    """Analyze runtime logs for issues."""
    return impl.log_analyzer(logs=logs)


@tool
def dependency_inspector(
    target: Annotated[str, "Environment or dependency file path"],
) -> dict[str, Any]:
    """Inspect project dependencies."""
    return impl.dependency_inspector(target=target)


@tool
def repo_clone(repo_url: Annotated[str, "Git repository URL"]) -> dict[str, Any]:
    """Clone a git repository to workspace."""
    return impl.repo_clone(repo_url=repo_url)


@tool
def notebook_runner(
    notebook_path: Annotated[str, "Path to .ipynb notebook"],
) -> dict[str, Any]:
    """Execute a Jupyter notebook."""
    return impl.notebook_runner(notebook_path=notebook_path)


@tool
def experiment_runner(
    config: Annotated[dict[str, Any], "Experiment configuration"],
) -> dict[str, Any]:
    """Run experiment from configuration."""
    return impl.experiment_runner(config=config)


@tool
def metric_evaluator(
    predictions: Annotated[list[Any], "Model predictions"],
    labels: Annotated[list[Any], "Ground-truth labels"],
) -> dict[str, Any]:
    """Compute evaluation metrics."""
    return impl.metric_evaluator(predictions=predictions, labels=labels)


@tool
def diff_generator(
    old: Annotated[str, "Original content"],
    new: Annotated[str, "Updated content"],
) -> dict[str, Any]:
    """Generate diff between old and new content."""
    return impl.diff_generator(old=old, new=new)


@tool
def patch_apply(diff: Annotated[str, "Patch diff to apply"]) -> dict[str, Any]:
    """Apply a code patch."""
    return impl.patch_apply(diff=diff)


# --- §7 data (P2) ---


@tool
def data_cleaner(
    data: Annotated[list[dict] | dict, "Input data"],
    strategy: Annotated[str, "Cleaning strategy"],
) -> dict[str, Any]:
    """Clean missing or anomalous data."""
    return impl.data_cleaner(data=data, strategy=strategy)


@tool
def feature_engineering_assistant(
    data: Annotated[list[dict] | dict, "Input data"],
    goal: Annotated[str, "Feature engineering goal"],
) -> dict[str, Any]:
    """Suggest or generate features from data."""
    return impl.feature_engineering_assistant(data=data, goal=goal)


# --- §8 browser / computer use (commented) ---


@tool
def browser_open(url: Annotated[str, "URL to open"]) -> dict[str, Any]:
    """Open a URL in browser automation session."""
    return impl.browser_open(url=url)


@tool
def browser_click(
    selector: Annotated[str, "CSS selector or coordinates"],
) -> dict[str, Any]:
    """Click an element in the browser page."""
    return impl.browser_click(selector=selector)


@tool
def browser_type(
    selector: Annotated[str, "CSS selector for input element"],
    text: Annotated[str, "Text to type"],
) -> dict[str, Any]:
    """Type text into a browser input element."""
    return impl.browser_type(selector=selector, text=text)


@tool
def browser_screenshot() -> dict[str, Any]:
    """Capture browser page screenshot."""
    return impl.browser_screenshot()


@tool
def browser_extract_text() -> dict[str, Any]:
    """Extract visible text from current browser page."""
    return impl.browser_extract_text()


@tool
def browser_download(
    target: Annotated[str, "Selector or URL to download"],
) -> dict[str, Any]:
    """Download file from browser page."""
    return impl.browser_download(target=target)


@tool
def browser_form_fill(
    form_spec: Annotated[dict[str, Any], "Form field specification"],
) -> dict[str, Any]:
    """Fill a web form automatically."""
    return impl.browser_form_fill(form_spec=form_spec)


@tool
def browser_login_flow(
    credentials_ref: Annotated[str, "Reference to stored credentials"],
) -> dict[str, Any]:
    """Run browser login flow (high risk)."""
    return impl.browser_login_flow(credentials_ref=credentials_ref)


# --- §9 artifact (commented) ---


@tool
def docx_writer(
    sections: Annotated[list[dict[str, Any]], "Document sections"],
    path: Annotated[str, "Output .docx path"],
) -> dict[str, Any]:
    """Write a Word document."""
    return impl.docx_writer(sections=sections, path=path)


@tool
def pptx_writer(
    slides: Annotated[list[dict[str, Any]], "Slide definitions"],
    path: Annotated[str, "Output .pptx path"],
) -> dict[str, Any]:
    """Write a PowerPoint presentation."""
    return impl.pptx_writer(slides=slides, path=path)


@tool
def chart_embedder(
    chart_paths: Annotated[list[str], "Paths to chart images"],
    document_path: Annotated[str, "Target document path"],
) -> dict[str, Any]:
    """Embed charts into a report document."""
    return impl.chart_embedder(chart_paths=chart_paths, document_path=document_path)


@tool
def pdf_exporter(
    source_path: Annotated[str, "Source file to export"],
    output_path: Annotated[str, "Output PDF path"],
) -> dict[str, Any]:
    """Export document to PDF."""
    return impl.pdf_exporter(source_path=source_path, output_path=output_path)


@tool
def report_formatter(
    report: Annotated[dict[str, Any], "Report content"],
    template: Annotated[str, "Template name or path"],
) -> dict[str, Any]:
    """Apply formatting template to report."""
    return impl.report_formatter(report=report, template=template)


@tool
def citation_formatter(
    references: Annotated[list[dict[str, Any]], "Bibliographic references"],
    style: Annotated[str, "Citation style, e.g. APA"] = "APA",
) -> dict[str, Any]:
    """Format bibliography citations."""
    return impl.citation_formatter(references=references, style=style)


# --- §10 quality (commented) ---


@tool
def compliance_filter(
    evidence: Annotated[list[dict[str, Any]], "Evidence items to filter"],
) -> dict[str, Any]:
    """Filter non-compliant sources or content."""
    return impl.compliance_filter(evidence=evidence)


@tool
def hallucination_checker(
    artifact: Annotated[dict[str, Any], "Report artifact"],
    evidence: Annotated[list[dict[str, Any]], "Supporting evidence"],
) -> dict[str, Any]:
    """Flag unsupported statements in artifact."""
    return impl.hallucination_checker(artifact=artifact, evidence=evidence)


@tool
def recency_checker(
    citations: Annotated[list[dict[str, Any]], "Citations with dates"],
) -> dict[str, Any]:
    """Check recency of cited sources."""
    return impl.recency_checker(citations=citations)


@tool
def source_reliability_scorer(
    source: Annotated[str, "Source URL or identifier"],
) -> dict[str, Any]:
    """Score source reliability."""
    return impl.source_reliability_scorer(source=source)


@tool
def assumption_stress_tester(
    assumptions: Annotated[list[dict[str, Any]], "Model assumptions"],
    evidence: Annotated[list[dict[str, Any]], "Supporting evidence"],
) -> dict[str, Any]:
    """Stress-test core assumptions against evidence."""
    return impl.assumption_stress_tester(assumptions=assumptions, evidence=evidence)


@tool
def reproducibility_checker(
    code_path: Annotated[str, "Code path"],
    logs: Annotated[str, "Execution logs"] = "",
    metrics: Annotated[dict[str, Any] | None, "Reported metrics"] = None,
) -> dict[str, Any]:
    """Check experiment reproducibility."""
    return impl.reproducibility_checker(code_path=code_path, logs=logs, metrics=metrics)


@tool
def result_consistency_checker(
    artifact: Annotated[dict[str, Any], "Report artifact to check"],
) -> dict[str, Any]:
    """Detect internal inconsistencies in report."""
    return impl.result_consistency_checker(artifact=artifact)


# --- §11 human (P2) ---


@tool
def human_edit_artifact(
    artifact: Annotated[dict[str, Any], "Intermediate artifact for user edit"],
) -> dict[str, Any]:
    """Allow user to edit an intermediate artifact."""
    return impl.human_edit_artifact(artifact=artifact)


@tool
def human_set_constraints(
    constraints: Annotated[dict[str, Any], "Updated research constraints"],
) -> dict[str, Any]:
    """Let user update research constraints."""
    return impl.human_set_constraints(constraints=constraints)


STUB_LANGCHAIN_TOOLS: dict[str, Any] = {
    "cost_tracker": cost_tracker,
    "permission_check": permission_check,
    "task_progress_report": task_progress_report,
    "browser_search": browser_search,
    "browser_fetch_rendered": browser_fetch_rendered,
    "ocr_reader": ocr_reader,
    "cross_document_compare": cross_document_compare,
    "estimate_revision_tracker": estimate_revision_tracker,
    "segment_revenue_parser": segment_revenue_parser,
    "guidance_extractor": guidance_extractor,
    "sentiment_signal_fetch": sentiment_signal_fetch,
    "paper_pdf_reader": paper_pdf_reader,
    "paper_section_extractor": paper_section_extractor,
    "paper_claim_extractor": paper_claim_extractor,
    "github_search": github_search,
    "citation_graph_search": citation_graph_search,
    "dataset_finder": dataset_finder,
    "benchmark_info_fetch": benchmark_info_fetch,
    "prompt_extractor": prompt_extractor,
    "equation_extractor": equation_extractor,
    "method_to_pseudocode": method_to_pseudocode,
    "experiment_table_extractor": experiment_table_extractor,
    "unit_test_runner": unit_test_runner,
    "lint_runner": lint_runner,
    "log_analyzer": log_analyzer,
    "dependency_inspector": dependency_inspector,
    "repo_clone": repo_clone,
    "notebook_runner": notebook_runner,
    "experiment_runner": experiment_runner,
    "metric_evaluator": metric_evaluator,
    "diff_generator": diff_generator,
    "patch_apply": patch_apply,
    "data_cleaner": data_cleaner,
    "feature_engineering_assistant": feature_engineering_assistant,
    "browser_open": browser_open,
    "browser_click": browser_click,
    "browser_type": browser_type,
    "browser_screenshot": browser_screenshot,
    "browser_extract_text": browser_extract_text,
    "browser_download": browser_download,
    "browser_form_fill": browser_form_fill,
    "browser_login_flow": browser_login_flow,
    "docx_writer": docx_writer,
    "pptx_writer": pptx_writer,
    "chart_embedder": chart_embedder,
    "pdf_exporter": pdf_exporter,
    "report_formatter": report_formatter,
    "citation_formatter": citation_formatter,
    "compliance_filter": compliance_filter,
    "hallucination_checker": hallucination_checker,
    "recency_checker": recency_checker,
    "source_reliability_scorer": source_reliability_scorer,
    "assumption_stress_tester": assumption_stress_tester,
    "reproducibility_checker": reproducibility_checker,
    "result_consistency_checker": result_consistency_checker,
    "human_edit_artifact": human_edit_artifact,
    "human_set_constraints": human_set_constraints,
}
