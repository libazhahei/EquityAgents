"""Domain denylist helpers for Perplexity search filtering."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

# Low-signal / UGC domains commonly excluded from equity research evidence.
DEFAULT_SEARCH_DOMAIN_DENYLIST: tuple[str, ...] = (
    "reddit.com",
    "pinterest.com",
    "quora.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "tiktok.com",
)

_MAX_API_DOMAINS = 20


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().removeprefix("www.")


def normalize_deny_entry(domain: str) -> str:
    return domain.strip().lower().removeprefix("-").removeprefix("www.")


def is_denied_url(url: str, denylist: list[str]) -> bool:
    domain = extract_domain(url)
    if not domain:
        return False
    for entry in denylist:
        denied = normalize_deny_entry(entry)
        if not denied:
            continue
        if domain == denied or domain.endswith(f".{denied}"):
            return True
    return False


def filter_citation_urls(urls: list[str], denylist: list[str]) -> list[str]:
    if not denylist:
        return list(urls)
    return [url for url in urls if not is_denied_url(url, denylist)]


def denylists_to_api_filter(
    denylist: list[str],
    *,
    max_domains: int = _MAX_API_DOMAINS,
) -> list[str]:
    """Convert a denylist to Perplexity ``search_domain_filter`` entries."""
    out: list[str] = []
    for entry in denylist:
        if len(out) >= max_domains:
            break
        denied = normalize_deny_entry(entry)
        if denied:
            out.append(f"-{denied}")
    return out


def resolve_search_domain_denylist(config: dict[str, Any] | None) -> list[str]:
    er = (config or {}).get("equity_research", {}) or {}
    custom = er.get("search_domain_denylist")
    if custom is None:
        return list(DEFAULT_SEARCH_DOMAIN_DENYLIST)
    return [str(d) for d in custom]
