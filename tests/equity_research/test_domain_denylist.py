"""Tests for Perplexity search domain denylist."""

from unittest.mock import MagicMock

from tradingagents.equity_research.runtime.utils.domain_denylist import (
    denylists_to_api_filter,
    filter_citation_urls,
    is_denied_url,
    resolve_search_domain_denylist,
)
from tradingagents.equity_research.tools.perplexity_tool import execute_perplexity_search


def test_is_denied_url_matches_subdomains():
    denylist = ["reddit.com"]
    assert is_denied_url("https://www.reddit.com/r/stocks", denylist)
    assert is_denied_url("https://old.reddit.com/r/stocks", denylist)
    assert not is_denied_url("https://reuters.com/article", denylist)


def test_denylists_to_api_filter_prefixes_entries():
    assert denylists_to_api_filter(["reddit.com", "-quora.com"]) == [
        "-reddit.com",
        "-quora.com",
    ]


def test_filter_citation_urls_removes_denied_domains():
    urls = [
        "https://www.reuters.com/article",
        "https://reddit.com/r/stocks",
        "https://sec.gov/filing",
    ]
    filtered = filter_citation_urls(urls, ["reddit.com"])
    assert filtered == [
        "https://www.reuters.com/article",
        "https://sec.gov/filing",
    ]


def test_resolve_search_domain_denylist_uses_config_override():
    config = {"equity_research": {"search_domain_denylist": ["example.com"]}}
    assert resolve_search_domain_denylist(config) == ["example.com"]


def test_execute_perplexity_search_applies_denylist():
    deps = MagicMock()
    deps.config = {"equity_research": {"search_domain_denylist": ["reddit.com"]}}
    deps.perplexity.api_key = "test-key"
    deps.perplexity.search.return_value = {
        "answer": "data",
        "citations": [
            "https://reuters.com/a",
            "https://www.reddit.com/r/stocks",
        ],
    }
    deps.documents.register.side_effect = lambda **_: {"doc_id": "doc_x"}

    evidence = execute_perplexity_search(
        deps,
        query="NVDA consensus",
        mode="exploratory",
        target_dimension="kpi_focus",
        ticker="NVDA",
    )

    deps.perplexity.search.assert_called_once()
    call_kwargs = deps.perplexity.search.call_args.kwargs
    assert call_kwargs["search_domain_filter"] == ["-reddit.com"]
    assert evidence.citations == ["https://reuters.com/a"]
    assert deps.documents.register.call_count == 1
