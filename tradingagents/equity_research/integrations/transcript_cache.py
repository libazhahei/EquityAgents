"""Disk cache for earnings transcript search requests and results."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _normalize_quarter(quarter: str | None) -> str | None:
    if quarter is None:
        return None
    label = quarter.strip()
    if not label:
        return None
    match = re.match(r"Q\s*([1-4])\s*(\d{4})", label, flags=re.IGNORECASE)
    if match:
        return f"Q{match.group(1)} {match.group(2)}"
    match = re.match(r"(\d{4})Q([1-4])", label, flags=re.IGNORECASE)
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return label


def _normalize_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized = " ".join(query.strip().lower().split())
    return normalized or None


def normalize_transcript_input(
    ticker: str,
    *,
    quarter: str | None = None,
    query: str | None = None,
    include_query: bool = False,
) -> dict[str, Any]:
    return {
        "ticker": _normalize_ticker(ticker),
        "quarter": _normalize_quarter(quarter),
        "query": _normalize_query(query) if include_query else None,
    }


def cache_input_for_lookup(
    ticker: str,
    *,
    quarter: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Build cache lookup key. Only Perplexity-style requests include query."""
    if _normalize_query(query):
        return normalize_transcript_input(
            ticker, quarter=quarter, query=query, include_query=True,
        )
    return normalize_transcript_input(ticker, quarter=quarter, include_query=False)


def cache_input_for_store(
    ticker: str,
    *,
    quarter: str | None = None,
    query: str | None = None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build cache storage key. Query is stored only for Perplexity results."""
    include_query = result.get("vendor_used") == "perplexity"
    return normalize_transcript_input(
        ticker,
        quarter=quarter,
        query=query,
        include_query=include_query,
    )


def _cache_dir(config: dict[str, Any], ticker: str) -> Path:
    base = config.get("data_cache_dir", "")
    return Path(base) / "equity_research" / "transcripts" / _normalize_ticker(ticker)


def _cache_path(config: dict[str, Any], cache_input: dict[str, Any]) -> Path:
    digest = hashlib.sha256(
        json.dumps(cache_input, sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()[:16]
    return _cache_dir(config, cache_input["ticker"]) / f"{digest}.json"


def _is_cacheable_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    data = result.get("data")
    if isinstance(data, list) and data:
        return True
    return False


def get_cached_transcript_search(
    config: dict[str, Any],
    ticker: str,
    *,
    quarter: str | None = None,
    query: str | None = None,
) -> dict[str, Any] | None:
    """Return a cached transcript search result when the same input was seen before."""
    cache_input = cache_input_for_lookup(ticker, quarter=quarter, query=query)
    path = _cache_path(config, cache_input)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("Skip corrupt transcript cache file %s: %s", path, exc)
        return None
    if payload.get("input") != cache_input:
        return None
    result = payload.get("result")
    if not _is_cacheable_result(result):
        return None
    return {**result, "cached": True, "cache_path": str(path)}


def set_cached_transcript_search(
    config: dict[str, Any],
    ticker: str,
    *,
    quarter: str | None = None,
    query: str | None = None,
    result: Any,
) -> str | None:
    """Persist a successful transcript search result keyed by normalized input."""
    if not _is_cacheable_result(result):
        return None
    cache_input = cache_input_for_store(
        ticker, quarter=quarter, query=query, result=result,
    )
    path = _cache_path(config, cache_input)
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = {k: v for k, v in result.items() if k not in {"cached", "cache_path"}}
    payload = {
        "input": cache_input,
        "result": stored,
        "cached_at": datetime.utcnow().isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
