"""Tool catalog metadata for equity research (ls_tools / tool_registry_lookup)."""

from __future__ import annotations

from typing import Any

ToolSpec = dict[str, Any]
CategorySpec = dict[str, Any]

EQUITY_TOOLS_CATEGORIES: dict[str, CategorySpec] = {
    "system": {
        "label": "System & runtime",
        "description": "Registry lookup, snapshots, and runtime utilities",
        "tools": {
            "ls_tools": {"description": "Browse tool categories and tools", "inputs": ["category"], "risk": "low"},
            "tool_registry_lookup": {"description": "Search tools by task and tags", "inputs": ["task", "tags"], "risk": "low"},
            "ls_skills": {"description": "Browse skill domains and skills", "inputs": ["domain"], "risk": "low"},
            "skill_registry_lookup": {"description": "Search skills by task and domain", "inputs": ["task", "domain"], "risk": "low"},
            "state_snapshot": {"description": "Save current task state snapshot", "inputs": ["state"], "risk": "low"},
            "cost_tracker": {"description": "Track tool invocation cost and usage", "inputs": ["tool_calls"], "risk": "low", "implemented": False},
            "permission_check": {"description": "Check whether a high-risk action is permitted", "inputs": ["action"], "risk": "medium", "implemented": False},
            "task_progress_report": {"description": "Summarize current task progress", "inputs": ["state"], "risk": "low", "implemented": False},
        },
    },
    "search": {
        "label": "Search & web",
        "description": "Web search, fetch, and news retrieval",
        "tools": {
            "web_search": {"description": "General web search", "inputs": ["query", "recency"], "risk": "low"},
            "web_fetch": {"description": "Fetch URL content as markdown/text", "inputs": ["url"], "risk": "low"},
            "news_search": {"description": "Search news and recent events", "inputs": ["query", "date_range"], "risk": "low"},
            "source_quality_check": {"description": "Score source URL quality", "inputs": ["url"], "risk": "low"},
            "citation_extractor": {"description": "Extract citation URLs from text", "inputs": ["text"], "risk": "low"},
            "search_deduper": {"description": "Deduplicate similar search results", "inputs": ["results"], "risk": "low"},
            "perplexity_search": {"description": "Perplexity web search for evidence", "inputs": ["ticker", "query"], "risk": "low"},
            "batch_light_grounding_search": {"description": "Batch lightweight web grounding search", "inputs": ["query_items"], "risk": "low"},
            "browser_search": {"description": "Search the web using a headless browser", "inputs": ["query"], "risk": "medium", "implemented": False},
            "browser_fetch_rendered": {"description": "Fetch dynamically rendered page content", "inputs": ["url"], "risk": "medium", "implemented": False},
        },
    },
    "document": {
        "label": "Document I/O",
        "description": "Read and parse local documents",
        "tools": {
            "list_files": {"description": "List files in workspace directory", "inputs": ["file_path"], "risk": "low"},
            "file_reader": {"description": "Read text/markdown/json/csv files", "inputs": ["file_path"], "risk": "low"},
            "pdf_reader": {"description": "Read PDF content", "inputs": ["file_path"], "risk": "low"},
            "docx_reader": {"description": "Read Word documents", "inputs": ["file_path"], "risk": "low"},
            "table_extractor": {"description": "Extract tables from documents", "inputs": ["file_path"], "risk": "low"},
            "document_chunker": {"description": "Chunk document text", "inputs": ["text", "strategy"], "risk": "low"},
            "document_outline_extractor": {"description": "Extract document outline", "inputs": ["text"], "risk": "low"},
            "reference_parser": {"description": "Parse bibliographic references", "inputs": ["text"], "risk": "low"},
            "ocr_reader": {"description": "OCR text from image or scanned PDF", "inputs": ["file_path"], "risk": "medium", "implemented": False},
            "cross_document_compare": {"description": "Compare multiple documents", "inputs": ["docs"], "risk": "low", "implemented": False},
        },
    },
    "finance": {
        "label": "Financial research",
        "description": "Market data, filings, transcripts, and estimates",
        "tools": {
            "stock_quote": {"description": "Get stock quote and market data", "inputs": ["ticker"], "risk": "low"},
            "company_profile": {"description": "Company profile and business description", "inputs": ["ticker"], "risk": "low"},
            "financial_statement_fetch": {"description": "Fetch financial statements", "inputs": ["ticker", "period"], "risk": "low"},
            "earnings_calendar": {"description": "Earnings report dates", "inputs": ["ticker"], "risk": "low"},
            "analyst_estimates_fetch": {"description": "Analyst consensus estimates", "inputs": ["ticker"], "risk": "low"},
            "transcript_search": {"description": "Search earnings call transcripts", "inputs": ["ticker", "quarter"], "risk": "low"},
            "filings_search": {"description": "Hybrid search SEC filings by keywords", "inputs": ["ticker", "keywords", "form_type", "section", "top_k", "max_chars"], "risk": "low"},
            "filing_reader": {"description": "Read filing content", "inputs": ["filing_url"], "risk": "low"},
            "peer_comps_fetch": {"description": "Fetch comparable companies", "inputs": ["ticker"], "risk": "low"},
            "valuation_multiples_fetch": {"description": "Fetch valuation multiples", "inputs": ["tickers"], "risk": "low"},
            "estimate_revision_tracker": {"description": "Track analyst estimate revisions", "inputs": ["ticker", "date_range"], "risk": "medium", "implemented": False},
            "segment_revenue_parser": {"description": "Parse segment revenue from filings", "inputs": ["source"], "risk": "medium", "implemented": False},
            "guidance_extractor": {"description": "Extract management guidance", "inputs": ["source"], "risk": "medium", "implemented": False},
            "sentiment_signal_fetch": {"description": "Fetch news/social sentiment signals", "inputs": ["ticker"], "risk": "medium", "implemented": False},
        },
    },
    "code": {
        "label": "Code & sandbox",
        "description": "Read, search, write code and sandbox execution",
        "tools": {
            "python_exec_sandbox": {"description": "Execute Python in E2B sandbox", "inputs": ["code"], "risk": "medium"},
            "shell_exec_sandbox": {"description": "Execute shell in E2B sandbox", "inputs": ["command"], "risk": "high"},
            "code_reader": {"description": "Read code file", "inputs": ["path"], "risk": "low"},
            "code_search": {"description": "Search project code", "inputs": ["query", "path"], "risk": "low"},
            "code_writer": {"description": "Write or update code file", "inputs": ["path", "content"], "risk": "high"},
            "unit_test_runner": {"description": "Run unit tests in sandbox", "inputs": ["test_command"], "risk": "medium", "implemented": False},
            "lint_runner": {"description": "Run static linter on code", "inputs": ["path"], "risk": "low", "implemented": False},
            "log_analyzer": {"description": "Analyze runtime logs", "inputs": ["logs"], "risk": "low", "implemented": False},
            "dependency_inspector": {"description": "Inspect project dependencies", "inputs": ["target"], "risk": "low", "implemented": False},
            "repo_clone": {"description": "Clone a git repository", "inputs": ["repo_url"], "risk": "medium", "implemented": False},
            "notebook_runner": {"description": "Execute a Jupyter notebook", "inputs": ["notebook_path"], "risk": "medium", "implemented": False},
            "experiment_runner": {"description": "Run experiment from configuration", "inputs": ["config"], "risk": "high", "implemented": False},
            "metric_evaluator": {"description": "Compute evaluation metrics", "inputs": ["predictions", "labels"], "risk": "low", "implemented": False},
            "diff_generator": {"description": "Generate diff between contents", "inputs": ["old", "new"], "risk": "low", "implemented": False},
            "patch_apply": {"description": "Apply a code patch", "inputs": ["diff"], "risk": "high", "implemented": False},
        },
    },
    "data": {
        "label": "Data analysis",
        "description": "CSV, profiling, statistics, and charts",
        "tools": {
            "csv_reader": {"description": "Read CSV with summary", "inputs": ["path"], "risk": "low"},
            "dataframe_profiler": {"description": "Profile dataframe schema and stats", "inputs": ["path"], "risk": "low"},
            "calculator": {"description": "Safe numeric expression calculator", "inputs": ["expression"], "risk": "low"},
            "chart_generator": {"description": "Generate chart image", "inputs": ["data", "chart_spec"], "risk": "low"},
            "statistical_test": {"description": "Run statistical test", "inputs": ["data", "test_type"], "risk": "low"},
            "regression_runner": {"description": "Run regression analysis", "inputs": ["data", "formula"], "risk": "low"},
            "time_series_analyzer": {"description": "Analyze time series trends", "inputs": ["data"], "risk": "low"},
            "data_cleaner": {"description": "Clean missing or anomalous data", "inputs": ["data", "strategy"], "risk": "medium", "implemented": False},
            "feature_engineering_assistant": {"description": "Suggest or generate features", "inputs": ["data", "goal"], "risk": "medium", "implemented": False},
        },
    },
    "artifact": {
        "label": "Artifact output",
        "description": "Write structured outputs and reports",
        "tools": {
            "markdown_writer": {"description": "Write markdown file", "inputs": ["content", "path"], "risk": "low"},
            "json_writer": {"description": "Write JSON file", "inputs": ["json", "path"], "risk": "low"},
            "docx_writer": {"description": "Write a Word document", "inputs": ["sections", "path"], "risk": "low", "implemented": False},
            "pptx_writer": {"description": "Write a PowerPoint presentation", "inputs": ["slides", "path"], "risk": "low", "implemented": False},
            "chart_embedder": {"description": "Embed charts into a report", "inputs": ["chart_paths", "document_path"], "risk": "low", "implemented": False},
            "pdf_exporter": {"description": "Export document to PDF", "inputs": ["source_path", "output_path"], "risk": "low", "implemented": False},
            "report_formatter": {"description": "Apply formatting template to report", "inputs": ["report", "template"], "risk": "low", "implemented": False},
            "citation_formatter": {"description": "Format bibliography citations", "inputs": ["references", "style"], "risk": "low", "implemented": False},
        },
    },
    "quality": {
        "label": "Verification",
        "description": "Citation, claim, and coverage checks",
        "tools": {
            "citation_checker": {"description": "Check citation URLs are accessible", "inputs": ["urls"], "risk": "low"},
            "claim_evidence_checker": {"description": "Check claims have supporting evidence", "inputs": ["claims", "evidence"], "risk": "low"},
            "coverage_evaluator": {"description": "Evaluate dimension coverage", "inputs": ["artifact", "criteria"], "risk": "low"},
            "conflict_detector": {"description": "Detect conflicting evidence", "inputs": ["evidence"], "risk": "low"},
            "compliance_filter": {"description": "Filter non-compliant sources", "inputs": ["evidence"], "risk": "low", "implemented": False},
            "hallucination_checker": {"description": "Flag unsupported statements", "inputs": ["artifact", "evidence"], "risk": "medium", "implemented": False},
            "recency_checker": {"description": "Check recency of cited sources", "inputs": ["citations"], "risk": "low", "implemented": False},
            "source_reliability_scorer": {"description": "Score source reliability", "inputs": ["source"], "risk": "low", "implemented": False},
            "assumption_stress_tester": {"description": "Stress-test model assumptions", "inputs": ["assumptions", "evidence"], "risk": "medium", "implemented": False},
            "reproducibility_checker": {"description": "Check experiment reproducibility", "inputs": ["code_path", "logs", "metrics"], "risk": "medium", "implemented": False},
            "result_consistency_checker": {"description": "Detect internal report inconsistencies", "inputs": ["artifact"], "risk": "low", "implemented": False},
        },
    },
    "human": {
        "label": "Human-in-the-loop",
        "description": "Request user input and approval",
        "tools": {
            "ask_human": {"description": "Ask user a question", "inputs": ["question"], "risk": "low"},
            "human_approval": {"description": "Request approval for high-risk action", "inputs": ["action_summary"], "risk": "low"},
            "human_review_payload": {"description": "Present state for human review", "inputs": ["state_summary"], "risk": "low"},
            "human_select_branch": {"description": "Let user select exploration branch", "inputs": ["branch_options"], "risk": "low"},
            "human_edit_artifact": {"description": "Allow user to edit intermediate artifact", "inputs": ["artifact"], "risk": "medium", "implemented": False},
            "human_set_constraints": {"description": "Let user update research constraints", "inputs": ["constraints"], "risk": "low", "implemented": False},
        },
    },
    "academic": {
        "label": "Academic & paper replication",
        "description": "Read papers, extract claims, and find related code",
        "tools": {
            "paper_pdf_reader": {"description": "Read academic paper PDF", "inputs": ["source"], "risk": "low", "implemented": False},
            "paper_section_extractor": {"description": "Extract paper sections", "inputs": ["paper_text"], "risk": "low", "implemented": False},
            "paper_claim_extractor": {"description": "Extract core claims from paper", "inputs": ["paper_text"], "risk": "low", "implemented": False},
            "github_search": {"description": "Search GitHub for related repositories", "inputs": ["query"], "risk": "low", "implemented": False},
            "citation_graph_search": {"description": "Search citation graph for a paper", "inputs": ["paper"], "risk": "low", "implemented": False},
            "dataset_finder": {"description": "Find datasets related to a paper", "inputs": ["query"], "risk": "medium", "implemented": False},
            "benchmark_info_fetch": {"description": "Fetch benchmark setup and metrics", "inputs": ["benchmark_name"], "risk": "medium", "implemented": False},
            "prompt_extractor": {"description": "Extract prompts from paper appendix", "inputs": ["paper_text"], "risk": "low", "implemented": False},
            "equation_extractor": {"description": "Extract equations from paper", "inputs": ["paper_text"], "risk": "medium", "implemented": False},
            "method_to_pseudocode": {"description": "Convert methods section to pseudocode", "inputs": ["method_section"], "risk": "medium", "implemented": False},
            "experiment_table_extractor": {"description": "Extract experiment tables from paper", "inputs": ["paper_pages"], "risk": "medium", "implemented": False},
        },
    },
    "browser": {
        "label": "Browser automation",
        "description": "Computer-use browser tools (high risk; gated by default)",
        "tools": {
            "browser_open": {"description": "Open URL in browser session", "inputs": ["url"], "risk": "medium", "implemented": False},
            "browser_click": {"description": "Click element on page", "inputs": ["selector"], "risk": "high", "implemented": False},
            "browser_type": {"description": "Type into browser input", "inputs": ["selector", "text"], "risk": "high", "implemented": False},
            "browser_screenshot": {"description": "Capture page screenshot", "inputs": [], "risk": "low", "implemented": False},
            "browser_extract_text": {"description": "Extract visible page text", "inputs": [], "risk": "low", "implemented": False},
            "browser_download": {"description": "Download file from page", "inputs": ["target"], "risk": "medium", "implemented": False},
            "browser_form_fill": {"description": "Fill web form automatically", "inputs": ["form_spec"], "risk": "high", "implemented": False},
            "browser_login_flow": {"description": "Run browser login flow", "inputs": ["credentials_ref"], "risk": "very_high", "implemented": False},
        },
    },
    "memory": {
        "label": "Memory & evidence",
        "description": "Store and retrieve research memory",
        "tools": {
            "memory_retrieve": {"description": "Retrieve relevant memory snippets", "inputs": ["query", "filters"], "risk": "low"},
            "search_evidence": {"description": "Semantic search over evidence ledger", "inputs": ["query", "metric"], "risk": "low"},
            "search_claims": {"description": "Search claims by section/confidence/metric", "inputs": ["query", "section_id", "confidence_min"], "risk": "low"},
            "search_assumptions": {"description": "Search assumptions by metric/sensitivity", "inputs": ["query", "metric", "sensitivity"], "risk": "low"},
            "search_consensus": {"description": "Search consensus ledger", "inputs": ["query", "metric"], "risk": "low"},
            "search_conflicts": {"description": "List open evidence conflicts", "inputs": ["metric"], "risk": "low"},
            "search_memory_timeline": {"description": "Recent iteration snapshots", "inputs": ["last_n"], "risk": "low"},
            "search_research_context": {"description": "Holistic context bundle for prompt injection", "inputs": ["query", "parent_nodes"], "risk": "low"},
            "memory_write": {"description": "Write evidence/action/reflection to memory", "inputs": ["record"], "risk": "low"},
            "store_evidence": {"description": "Store evidence fragment", "inputs": ["fragment"], "risk": "low"},
            "store_claim": {"description": "Store research claim", "inputs": ["claim"], "risk": "low"},
            "store_assumption": {"description": "Store model assumption", "inputs": ["assumption"], "risk": "low"},
            "link_evidence_to_claim": {"description": "Link evidence to claim", "inputs": ["claim_id", "evidence_id"], "risk": "low"},
            "retrieve_claims_by_section": {"description": "Retrieve claims by section", "inputs": ["section_id"], "risk": "low"},
            "retrieve_contradictory_evidence": {"description": "Retrieve contradictory evidence", "inputs": [], "risk": "low"},
        },
    },
    "planning": {
        "label": "Planning & tasking",
        "description": "Research planning helpers and todo queue operations",
        "tools": {
            "list_research_todos": {"description": "List all research todos", "inputs": [], "risk": "low"},
            "add_research_todo": {"description": "Add a research todo item", "inputs": ["title", "description", "priority"], "risk": "low"},
            "remove_research_todo": {"description": "Remove a research todo by id", "inputs": ["todo_id"], "risk": "low"},
            "update_research_todo_status": {"description": "Update a research todo status", "inputs": ["todo_id", "status"], "risk": "low"},
            "get_next_research_todo": {"description": "Get next pending research todo", "inputs": [], "risk": "low"},
        },
    },
}

SKILL_DOMAINS: dict[str, dict[str, Any]] = {
    "consensus": {"label": "Consensus & estimates", "tags": ["consensus", "analyst", "estimates"]},
    "valuation": {"label": "Valuation", "tags": ["valuation"]},
    "planning": {"label": "Research planning", "tags": ["planning", "thesis", "reasoning"]},
    "writing": {"label": "Report writing", "tags": ["writing"]},
    "risk": {"label": "Risk analysis", "tags": ["risk"]},
    "industry": {"label": "Industry analysis", "tags": ["industry"]},
    "memory": {"label": "Collaborative memory", "tags": ["memory"]},
    "forecast": {"label": "Forecasting", "tags": ["forecast"]},
    "catalyst": {"label": "Catalyst monitoring", "tags": ["catalyst"]},
    "qa": {"label": "Quality assurance", "tags": ["qa"]},
}


def get_category_for_tool(tool_name: str) -> str | None:
    for cat_id, cat in EQUITY_TOOLS_CATEGORIES.items():
        if tool_name in cat.get("tools", {}):
            return cat_id
    return None


def list_tool_categories(registered: set[str] | None = None) -> list[dict[str, Any]]:
    categories = []
    for cat_id, cat in EQUITY_TOOLS_CATEGORIES.items():
        tools = cat.get("tools", {})
        tool_names = list(tools.keys())
        if registered is not None:
            tool_names = [t for t in tool_names if t in registered]
        categories.append({
            "id": cat_id,
            "label": cat.get("label", cat_id),
            "description": cat.get("description", ""),
            "tool_count": len(tool_names),
        })
    return categories


def list_tools_in_category(category: str, registered: set[str] | None = None) -> list[dict[str, Any]]:
    cat = EQUITY_TOOLS_CATEGORIES.get(category)
    if not cat:
        return []
    items = []
    for name, spec in cat.get("tools", {}).items():
        if registered is not None and name not in registered:
            continue
        items.append({
            "name": name,
            "description": spec.get("description", ""),
            "inputs": spec.get("inputs", []),
            "risk": spec.get("risk", "low"),
            "implemented": spec.get("implemented", True),
            "registered": registered is None or name in registered,
        })
    return items


def all_tool_specs(registered: set[str] | None = None) -> list[dict[str, Any]]:
    specs = []
    for cat_id in EQUITY_TOOLS_CATEGORIES:
        for tool in list_tools_in_category(cat_id, registered):
            specs.append({**tool, "category": cat_id})
    return specs
