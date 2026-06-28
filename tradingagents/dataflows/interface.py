import logging

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_brief_stock_data_description,
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_global_news as get_alpha_vantage_global_news,
    get_income_statement as get_alpha_vantage_income_statement,
    get_indicator as get_alpha_vantage_indicator,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_stock as get_alpha_vantage_stock,
)
from .config import get_config
from .errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from .equity_vendors import (
    analyst_estimates_fetch_fmp,
    analyst_estimates_fetch_info_sources,
    analyst_estimates_fetch_yfinance,
    company_profile_fmp,
    company_profile_yfinance,
    earnings_calendar_fmp,
    earnings_calendar_yfinance,
    filing_reader_edgar,
    filings_search_edgar,
    financial_statement_fetch_alpha_vantage,
    financial_statement_fetch_yfinance,
    news_search_jina,
    news_search_tavily,
    peer_comps_fetch_fmp,
    peer_comps_fetch_yfinance,
    stock_quote_alpha_vantage,
    stock_quote_yfinance,
    transcript_search_fmp,
    transcript_search_perplexity,
    valuation_multiples_fetch_fmp,
    valuation_multiples_fetch_yfinance,
    web_fetch_jina,
    web_fetch_tavily,
    web_search_jina,
    web_search_tavily,
)
from .fred import get_macro_data as get_fred_macro_data
from .polymarket import get_prediction_markets as get_polymarket_prediction_markets
from .vendor_routing import build_vendor_chain, execute_vendor_chain
# from .y_finance import (
#     get_balance_sheet as get_yfinance_balance_sheet,
#     get_cashflow as get_yfinance_cashflow,
#     get_fundamentals as get_yfinance_fundamentals,
#     get_income_statement as get_yfinance_income_statement,
#     get_insider_transactions as get_yfinance_insider_transactions,
#     get_stock_stats_indicators_window,
#     get_YFin_data_online,
# )
from .yfinance_news import get_global_news_yfinance, get_news_yfinance

logger = logging.getLogger(__name__)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data",
            "get_briefing_stock_info",
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macroeconomic indicators (rates, inflation, labor, growth)",
        "tools": [
            "get_macro_indicators",
        ]
    },
    "prediction_markets": {
        "description": "Market-implied probabilities for forward-looking events",
        "tools": [
            "get_prediction_markets",
        ]
    },
    "web_search_data": {
        "description": "Web search and news retrieval",
        "tools": [
            "web_search",
            "news_search",
        ],
    },
    "web_fetch_data": {
        "description": "Fetch web page content",
        "tools": [
            "web_fetch",
        ],
    },
    "equity_finance": {
        "description": "Equity finance data for research",
        "tools": [
            "stock_quote",
            "company_profile",
            "financial_statement_fetch",
            "earnings_calendar",
            "analyst_estimates_fetch",
            "peer_comps_fetch",
            "valuation_multiples_fetch",
        ],
    },
    "filings_data": {
        "description": "SEC and regulatory filings",
        "tools": [
            "filings_search",
            "filing_reader",
        ],
    },
    "transcripts_data": {
        "description": "Earnings call transcripts",
        "tools": [
            "transcript_search",
        ],
    },
}

VENDOR_LIST = [
    "yfinance",
    "fred",
    "polymarket",
    "alpha_vantage",
    "tavily",
    "jina",
    "fmp",
    "edgar",
    "perplexity",
    "info_sources",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    "get_briefing_stock_info": {
        # "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_brief_stock_data_description,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # macro_data
    "get_macro_indicators": {
        "fred": get_fred_macro_data,
    },
    # prediction_markets
    "get_prediction_markets": {
        "polymarket": get_polymarket_prediction_markets,
    },
    # web_search_data
    "web_search": {
        "tavily": web_search_tavily,
        "jina": web_search_jina,
    },
    "news_search": {
        "tavily": news_search_tavily,
        "jina": news_search_jina,
    },
    # web_fetch_data
    "web_fetch": {
        "jina": web_fetch_jina,
        "tavily": web_fetch_tavily,
    },
    # equity_finance
    "stock_quote": {
        "yfinance": stock_quote_yfinance,
        "alpha_vantage": stock_quote_alpha_vantage,
    },
    "company_profile": {
        "yfinance": company_profile_yfinance,
        "fmp": company_profile_fmp,
    },
    "financial_statement_fetch": {
        "yfinance": financial_statement_fetch_yfinance,
        "alpha_vantage": financial_statement_fetch_alpha_vantage,
    },
    "earnings_calendar": {
        "fmp": earnings_calendar_fmp,
        "yfinance": earnings_calendar_yfinance,
    },
    "analyst_estimates_fetch": {
        "fmp": analyst_estimates_fetch_fmp,
        "info_sources": analyst_estimates_fetch_info_sources,
        "yfinance": analyst_estimates_fetch_yfinance,
    },
    "peer_comps_fetch": {
        "yfinance": peer_comps_fetch_yfinance,
        "fmp": peer_comps_fetch_fmp,
    },
    "valuation_multiples_fetch": {
        "yfinance": valuation_multiples_fetch_yfinance,
        "fmp": valuation_multiples_fetch_fmp,
    },
    # filings_data
    "filings_search": {
        "edgar": filings_search_edgar,
    },
    "filing_reader": {
        "edgar": filing_reader_edgar,
    },
    # transcripts_data
    "transcript_search": {
        "fmp": transcript_search_fmp,
        "perplexity": transcript_search_perplexity,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    vendor_chain = build_vendor_chain(method, VENDOR_METHODS[method], category=category)
    return execute_vendor_chain(method, vendor_chain, VENDOR_METHODS[method], *args, **kwargs)
