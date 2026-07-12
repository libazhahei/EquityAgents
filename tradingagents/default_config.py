import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER":         "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM":       "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM":      "quick_think_llm",
    "TRADINGAGENTS_NANO_THINK_LLM":       "nano_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL":      "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE":      "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "TRADINGAGENTS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER":     "benchmark_ticker",
    "TRADINGAGENTS_TEMPERATURE":          "temperature",
    "TRADINGAGENTS_POSTGRES_URL":         "postgres_url",
    "TRADINGAGENTS_REDIS_URL":            "redis_url",
    "PERPLEXITY_API_KEY":                 "perplexity_api_key",
}


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.5",
    "quick_think_llm": "gpt-5.4-mini",
    "nano_think_llm": "gpt-5.4-nano",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Sampling temperature, forwarded to every provider when set. None leaves
    # each provider at its own default. Lower values reduce run-to-run
    # variation on models that honor it; reasoning models largely ignore it
    # and no setting makes LLM output bit-identical across runs (see README).
    "temperature": None,
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "analyst_concurrency_limit": 1,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Search queries used by get_global_news for macro headlines. Extend or
    # replace to broaden geographic / sector coverage.
    "global_news_queries": [
        "Federal Reserve interest rates inflation",
        "S&P 500 earnings GDP economic outlook",
        "geopolitical risk trade war sanctions",
        "ECB Bank of England BOJ central bank policy",
        "oil commodities supply chain energy",
    ],
    # Data vendor configuration
    # Category-level configuration (default for all tools in category).
    # The configured value is the exact vendor chain — requests are NOT silently
    # routed to vendors you didn't choose. For ordered fallback, list several,
    # e.g. "yfinance,alpha_vantage". "default" uses all available vendors.
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
        "macro_data": "fred",                # Options: fred (needs FRED_API_KEY)
        "prediction_markets": "polymarket",  # Options: polymarket (keyless)
        "web_search_data": "tavily,jina",
        "web_fetch_data": "jina,tavily",
        "equity_finance": "yfinance,fmp",
        "filings_data": "edgar",
        "transcripts_data": "alpha_vantage,fmp,perplexity",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer.
    # ``benchmark_ticker`` (when set) overrides the suffix map for all
    # tickers; leave it None to use ``benchmark_map`` for auto-detection
    # based on the ticker's exchange suffix. SPY remains the US default
    # so the reflection label keeps reading "Alpha vs SPY" for US tickers
    # while non-US tickers get their regional index automatically.
    "benchmark_ticker": None,
    "benchmark_map": {
        ".NS":  "^NSEI",       # NSE India (Nifty 50)
        ".BO":  "^BSESN",      # BSE India (Sensex)
        ".T":   "^N225",       # Tokyo (Nikkei 225)
        ".HK":  "^HSI",        # Hong Kong (Hang Seng)
        ".L":   "^FTSE",       # London (FTSE 100)
        ".TO":  "^GSPTSE",     # Toronto (TSX Composite)
        ".AX":  "^AXJO",       # Australia (ASX 200)
        ".SS":  "000001.SS",   # Shanghai (SSE Composite)
        ".SZ":  "399001.SZ",   # Shenzhen (SZSE Component)
        "":     "SPY",         # default for US-listed tickers (no suffix)
    },
    # Deep Equity Research (optional feature)
    "postgres_url": os.getenv(
        "TRADINGAGENTS_POSTGRES_URL",
        "postgresql+psycopg://localhost/tradingagents_equity",
    ),
    "redis_url": os.getenv("TRADINGAGENTS_REDIS_URL", "redis://localhost:6379/0"),
    "perplexity_api_key": os.getenv("PERPLEXITY_API_KEY"),
    "equity_research_results_dir": os.getenv(
        "TRADINGAGENTS_EQUITY_RESEARCH_DIR",
        os.path.join(_TRADINGAGENTS_HOME, "equity_research"),
    ),
    "equity_research": {
        "report_type": "initiation",
        "time_horizon": "12m",
        "quick_research": os.getenv("TRADINGAGENTS_QUICK_RESEARCH", "true").strip().lower()
        in ("true", "1", "yes", "on"),
        "compact_cache_size": 256,
        "executor_context_max_chars": 6000,
        "section_research_recursion_limit": 250,
        "consensus_context_max_chars": 6000,
        "max_hypotheses_per_section": 5,
        "max_hypothesis_iterations": 3,
        "max_recur_limit": 200,
        "perplexity_rate_limit": 20,
        "llm_rate_limit_max_retries": 5,
        "llm_rate_limit_base_delay": 2.0,
        "llm_rate_limit_max_delay": 60.0,
        "document_root": os.getenv(
            "TRADINGAGENTS_EQUITY_RESEARCH_DOCS_DIR",
            os.path.join(_TRADINGAGENTS_HOME, "equity_research", "docs"),
        ),
        # Perplexity search_domain_filter denylist (prefix "-" added at call time).
        # Set to [] to disable; omit key to use built-in defaults.
        "search_domain_denylist": [
            "reddit.com",
            "pinterest.com",
            "quora.com",
            "medium.com",
            "twitter.com",
            "x.com",
            "facebook.com",
            "tiktok.com",
        ],
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dim": 1536,
        "memory_use_embedding": True,
        "memory_semantic_top_k": 30,
        "memory_prune_max_age_days": 30,
        "memory_merge_threshold": 0.85,
        "memory_claim_decay_rate": 0.95,
        "rag_default_chunker": "paragraph",
        "sec_filing_chunker": "sec_item",
        "filing_chunk_size": 300,
        "filing_chunk_overlap": 100,
        "table_rows_per_chunk": 12,
        "table_row_overlap": 2,
        "table_context_paragraphs": 2,
        "rag_search_top_k": 8,
        "rag_search_max_chars": 16000,
        "rag_rrf_k": 60,
        "rag_search_pool_k": 30,
        "budget": {
            "max_search_queries": 5,
            "max_extraction_docs": 8,
        },
        "web_search_max_url_fetches": 3,
        "human_tools_mode": "stub",
        "checkpoint_enabled": True,
        "checkpoint_dir": None,  # default: {data_cache}/checkpoints/equity_research
        "human_review_interrupt": True,
        "default_selected_section_ids": ["3_business_model"],
        "document_root": None,
        "code_root": None,
        "tools": {
            "python_exec_sandbox": False,
            "shell_exec_sandbox": False,
            "code_writer": False,
        },
        "data_vendors": {
            "transcripts_data": "alpha_vantage,fmp,perplexity",
        },
        "tool_vendors": {},
        # ParameterPreservingReducer configuration
        "reducer_dedup_threshold": 0.85,
        "reducer_conflict_tolerance": 0.05,
        "reducer_max_history": 10,
    },
})
