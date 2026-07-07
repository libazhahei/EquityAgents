"""SEC filing cache for equity research."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def sec_cache_dir(config: dict[str, Any], ticker: str) -> Path:
    base = config.get("data_cache_dir", "")
    return Path(base) / "equity_research" / "sec" / ticker.upper()


def _filing_cache_path(cache_dir: Path, filing: dict[str, Any]) -> Path:
    form = filing.get("form", "filing")
    date = str(filing.get("filing_date", "unknown")).replace("/", "-")
    accession = str(filing.get("accession_number", "")).replace("/", "-")
    suffix = accession or date
    return cache_dir / f"{form}_{suffix}.json"


def _resolve_full_text(filing: dict[str, Any]) -> str:
    if filing.get("full_text"):
        return str(filing["full_text"])
    path = filing.get("full_text_path")
    if path and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8")
    return str(filing.get("text_excerpt", ""))


def write_filings_to_cache(config: dict[str, Any], ticker: str, filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist filing metadata and full text to the local SEC cache."""
    ticker = ticker.upper()
    cache_dir = sec_cache_dir(config, ticker)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached: list[dict[str, Any]] = []
    for filing in filings:
        entry = dict(filing)
        path = _filing_cache_path(cache_dir, entry)
        if entry.get("full_text") and len(entry["full_text"]) > 500_000:
            accession = str(entry.get("accession_number", "")).replace("/", "-")
            txt_path = cache_dir / f"{entry.get('form', 'filing')}_{accession}.txt"
            txt_path.write_text(entry["full_text"], encoding="utf-8")
            entry["full_text_path"] = str(txt_path)
            entry.pop("full_text", None)
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        if not entry.get("full_text") and entry.get("full_text_path"):
            entry["full_text"] = Path(entry["full_text_path"]).read_text(encoding="utf-8")
        cached.append(entry)
    return cached


def prefetch_sec_filings(deps: Any, ticker: str) -> list[dict[str, Any]]:
    """Download recent SEC filings, persist to cache, and build RAG index."""
    ticker = ticker.upper()
    filings = deps.edgar.fetch_recent_filings(ticker)
    cached = write_filings_to_cache(deps.config, ticker, filings)

    if hasattr(deps, "rag") and deps.rag is not None:
        from tradingagents.rag.types import CorpusScope

        try:
            deps.rag.ingest("sec_filings", CorpusScope(ticker=ticker))
        except Exception as exc:
            logger.warning("SEC filing RAG ingest failed for %s: %s", ticker, exc)

    return cached


def load_cached_filings(config: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    """Load SEC filings from cache; returns empty list if cache miss."""
    cache_dir = sec_cache_dir(config, ticker)
    if not cache_dir.is_dir():
        return []
    filings: list[dict[str, Any]] = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            filing = json.loads(path.read_text(encoding="utf-8"))
            if not filing.get("full_text"):
                filing["full_text"] = _resolve_full_text(filing)
            filings.append(filing)
        except Exception as exc:
            logger.debug("Skip corrupt SEC cache file %s: %s", path, exc)
    return filings


def ingest_documents_from_sec_cache(deps: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Register documents from cached SEC filings."""
    from datetime import datetime

    ticker = state.get("ticker", "")
    documents = list(state.get("documents", []))
    filings = load_cached_filings(deps.config, ticker)
    if not filings:
        filings = prefetch_sec_filings(deps, ticker)

    for filing in filings[:3]:
        doc = deps.documents.register(
            ticker=ticker,
            source_type=filing.get("form", "10-K"),
            title=f"{ticker} {filing.get('form', '')}",
            source_url=filing.get("url", ""),
            published_date=filing.get("filing_date"),
        )
        documents.append(doc)

    updates = {
        "documents": documents,
        "api_calls": state.get("api_calls", 0) + (1 if filings else 0),
        "last_updated": datetime.utcnow().isoformat(),
    }
    updates.update(deps.trace({**state, **updates}, "ingest_sec_cache", {"count": len(filings[:3])}))
    return updates
