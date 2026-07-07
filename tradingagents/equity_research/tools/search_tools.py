"""Search tools for equity research."""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from tradingagents.equity_research.state.consensus_schemas import EvidenceItem
from tradingagents.equity_research.tools.interface import route_equity_tool

_DEFAULT_MAX_URL_FETCHES = 3

_TRUSTED_DOMAINS = {
    "sec.gov", "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "cnbc.com", "finance.yahoo.com", "marketwatch.com",
}


def web_search(query: str, recency: str | None = None) -> dict[str, Any]:
    return route_equity_tool("web_search", query, recency=recency)


def _max_url_fetches(deps: Any) -> int:
    config = getattr(deps, "config", None) or {}
    er = config.get("equity_research", {}) or {}
    configured = er.get("web_search_max_url_fetches", _DEFAULT_MAX_URL_FETCHES)
    try:
        return max(0, int(configured))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_URL_FETCHES


def _extract_result_urls(result: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url:
            urls.append(url)
    return list(dict.fromkeys(urls))


def _web_cache_path(config: dict[str, Any], ticker: str, url: str) -> Path:
    base = config.get("data_cache_dir", "")
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return Path(base) / "equity_research" / "web" / ticker.upper() / f"{digest}.md"


def _cache_fetched_content(
    config: dict[str, Any],
    ticker: str,
    url: str,
    content: str,
) -> str | None:
    if not content.strip():
        return None
    path = _web_cache_path(config, ticker, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _title_for_url(result: dict[str, Any], url: str) -> str:
    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("url") or "").strip() == url:
            title = str(item.get("title") or "").strip()
            if title:
                return title[:200]
    return url[:200]


def web_search_with_url_storage(
    query: str,
    *,
    recency: str | None = None,
    deps: Any = None,
    ticker: str = "",
) -> dict[str, Any]:
    """Run web search and fetch/store content for result URLs when deps are available."""
    from tradingagents.equity_research.runtime.utils.domain_denylist import (
        filter_citation_urls,
        resolve_search_domain_denylist,
    )

    result = web_search(query, recency=recency)
    urls = _extract_result_urls(result)
    result["urls"] = urls
    result["doc_ids"] = []
    result["api_calls"] = 1

    if not deps or not urls or not getattr(deps, "documents", None):
        return result

    denylist = resolve_search_domain_denylist(getattr(deps, "config", None))
    fetch_urls = filter_citation_urls(urls, denylist)[:_max_url_fetches(deps)]
    doc_ids: list[str] = []
    fetch_errors: list[dict[str, str]] = []
    url_to_doc: dict[str, str] = {}
    ticker_key = (ticker or "UNKNOWN").upper()
    config = getattr(deps, "config", None) or {}

    for url in fetch_urls:
        try:
            fetched = web_fetch(url)
            result["api_calls"] += 1
            content = str(fetched.get("content") or "")
            access_path = _cache_fetched_content(config, ticker_key, url, content)
            doc = deps.documents.register(
                ticker=ticker_key,
                source_type="web",
                title=_title_for_url(result, url),
                source_url=url,
                access_path=access_path,
            )
            doc_ids.append(doc["doc_id"])
            url_to_doc[url] = doc["doc_id"]
        except Exception as exc:
            fetch_errors.append({"url": url, "error": str(exc)})

    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url in url_to_doc:
            item["doc_id"] = url_to_doc[url]

    result["doc_ids"] = doc_ids
    if fetch_errors:
        result["fetch_errors"] = fetch_errors
    return result


def web_fetch(url: str) -> dict[str, Any]:
    return route_equity_tool("web_fetch", url)


def news_search(query: str, date_range: str | None = None) -> dict[str, Any]:
    return route_equity_tool("news_search", query, date_range=date_range)


def source_quality_check(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower().removeprefix("www.")
    score = 0.5
    if domain in _TRUSTED_DOMAINS:
        score = 0.9
    elif domain.endswith(".gov") or domain.endswith(".edu"):
        score = 0.85
    elif not domain:
        score = 0.1
    return {"url": url, "domain": domain, "quality_score": score}


def citation_extractor(text: str) -> dict[str, Any]:
    urls = re.findall(r"https?://[^\s\)\]\"']+", text)
    return {"citations": list(dict.fromkeys(urls))}


def _normalize_query_key(query: str) -> str:
    return " ".join(query.strip().lower().split())


def _normalize_query_item(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, str):
        return {
            "query": raw,
            "target_dimension": "narrative_framework",
            "mode": "exploratory",
            "priority": 0,
        }
    return {
        "query": str(raw.get("query", "")),
        "target_dimension": raw.get("target_dimension", "narrative_framework"),
        "mode": raw.get("mode", "exploratory"),
        "priority": int(raw.get("priority", 0)),
    }


def _normalize_query_items(
    queries: str | dict[str, Any] | list[str | dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(queries, str):
        return [_normalize_query_item(queries)]
    if isinstance(queries, dict):
        return [_normalize_query_item(queries)]
    return [_normalize_query_item(item) for item in queries]


def _batch_concurrency(deps: Any, batch_size: int) -> int:
    config = getattr(deps, "config", None) or {}
    er = config.get("equity_research", {}) or {}
    configured = er.get("batch_search_concurrency", batch_size)
    try:
        return max(1, min(int(configured), batch_size))
    except (TypeError, ValueError):
        return max(1, batch_size)


def _memory_index(search_memory: list[dict] | None) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for record in search_memory or []:
        key = _normalize_query_key(str(record.get("query", "")))
        if key and key not in index:
            index[key] = record
    return index


def _evidence_from_memory(record: dict[str, Any], item: dict[str, Any]) -> EvidenceItem:
    return EvidenceItem(
        answer=record.get("answer", ""),
        citations=list(record.get("citations") or []),
        target_dimension=item.get("target_dimension", record.get("target_dimension", "")),
        query_used=item.get("query", record.get("query", "")),
        retrieved_at=record.get("retrieved_at") or datetime.utcnow().isoformat(),
        doc_ids=list(record.get("doc_ids") or []),
    )


def _record_from_evidence(deps: Any, evidence: EvidenceItem, *, iteration: int, mode: str, query: str):
    from tradingagents.equity_research.runtime.utils.search_memory import record_from_evidence

    return record_from_evidence(deps, evidence, iteration=iteration, mode=mode, query=query)


def _run_unique_query(
    deps: Any,
    *,
    item: dict[str, Any],
    ticker: str,
    iteration: int,
    search_fn: Callable[..., Any],
) -> tuple[EvidenceItem | None, dict[str, Any] | None, list[str], int, str | None]:
    query = item.get("query", "")
    target_dimension = item.get("target_dimension", "narrative_framework")
    mode = item.get("mode", "exploratory")
    try:
        evidence = search_fn(
            deps,
            query=query,
            mode=mode,
            target_dimension=target_dimension,
            ticker=ticker,
        )
        record = _record_from_evidence(
            deps, evidence, iteration=iteration, mode=str(mode), query=query,
        )
        return evidence, record.model_dump(), list(evidence.doc_ids), 1, None
    except Exception as exc:
        return None, None, [], 0, f"query failed ({query[:60]}): {exc}"


def _fan_out_item(
    deps: Any,
    *,
    item: dict[str, Any],
    evidence: EvidenceItem,
    iteration: int,
    cached: bool,
) -> dict[str, Any]:
    mode = str(item.get("mode", "exploratory"))
    query = item.get("query", "")
    adapted = evidence.model_copy(
        update={
            "target_dimension": item.get("target_dimension", evidence.target_dimension),
            "query_used": query,
        },
    )
    record = _record_from_evidence(deps, adapted, iteration=iteration, mode=mode, query=query)
    return {
        "query": query,
        "target_dimension": item.get("target_dimension", "narrative_framework"),
        "priority": int(item.get("priority", 0)),
        "evidence": adapted.model_dump(),
        "record": record.model_dump(),
        "doc_ids": list(adapted.doc_ids),
        "cached": cached,
        "error": None,
    }


def batch_perplexity_search(
    deps: Any,
    *,
    ticker: str,
    queries: str | dict[str, Any] | list[str | dict[str, Any]],
    iteration: int = 0,
    search_memory: list[dict] | None = None,
    concurrency: int | None = None,
    search_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run one or many Perplexity searches with batch dedup and optional memory cache."""
    if search_fn is None:
        from tradingagents.equity_research.tools.perplexity_tool import execute_perplexity_search

        run_search = execute_perplexity_search
    else:
        run_search = search_fn
    items = _normalize_query_items(queries)
    if not items:
        return {"items": [], "api_calls": 0, "errors": []}

    memory = _memory_index(search_memory)
    errors: list[str] = []
    api_calls = 0

    # key -> (evidence, record, doc_ids, cached, error)
    resolved: dict[str, tuple[EvidenceItem | None, dict[str, Any] | None, list[str], bool, str | None]] = {}

    keys_needing_api: list[str] = []
    key_to_representative: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _normalize_query_key(item.get("query", ""))
        if not key:
            continue
        if key in resolved or key in keys_needing_api:
            continue
        if key in memory:
            evidence = _evidence_from_memory(memory[key], item)
            resolved[key] = (evidence, None, list(evidence.doc_ids), True, None)
        else:
            keys_needing_api.append(key)
            key_to_representative[key] = item

    workers = concurrency if concurrency is not None else _batch_concurrency(deps, len(keys_needing_api))

    def _fetch(key: str) -> tuple[str, EvidenceItem | None, dict[str, Any] | None, list[str], int, str | None]:
        item = key_to_representative[key]
        evidence, record, doc_ids, calls, err = _run_unique_query(
            deps,
            item=item,
            ticker=ticker,
            iteration=iteration,
            search_fn=run_search,
        )
        return key, evidence, record, doc_ids, calls, err

    if len(keys_needing_api) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch, key): key for key in keys_needing_api}
            for fut in as_completed(futures):
                key, evidence, record, doc_ids, calls, err = fut.result()
                api_calls += calls
                if err:
                    errors.append(err)
                    resolved[key] = (None, None, [], False, err)
                elif evidence is not None:
                    resolved[key] = (evidence, record, doc_ids, False, None)
    else:
        for key in keys_needing_api:
            _, evidence, record, doc_ids, calls, err = _fetch(key)
            api_calls += calls
            if err:
                errors.append(err)
                resolved[key] = (None, None, [], False, err)
            elif evidence is not None:
                resolved[key] = (evidence, record, doc_ids, False, None)

    output_items: list[dict[str, Any]] = []
    for item in items:
        key = _normalize_query_key(item.get("query", ""))
        if not key:
            output_items.append({
                "query": item.get("query", ""),
                "target_dimension": item.get("target_dimension", "narrative_framework"),
                "priority": int(item.get("priority", 0)),
                "evidence": None,
                "record": None,
                "doc_ids": [],
                "cached": False,
                "error": "empty query",
            })
            errors.append("empty query")
            continue
        evidence, _record, _doc_ids, cached, err = resolved.get(key, (None, None, [], False, "missing result"))
        if err or evidence is None:
            output_items.append({
                "query": item.get("query", ""),
                "target_dimension": item.get("target_dimension", "narrative_framework"),
                "priority": int(item.get("priority", 0)),
                "evidence": None,
                "record": None,
                "doc_ids": [],
                "cached": cached,
                "error": err,
            })
            continue
        output_items.append(_fan_out_item(deps, item=item, evidence=evidence, iteration=iteration, cached=cached))

    return {"items": output_items, "api_calls": api_calls, "errors": errors}


def search_deduper(results: list[dict]) -> dict[str, Any]:
    deduped: list[dict] = []
    seen_titles: list[str] = []
    for item in results:
        title = (item.get("title") or item.get("url") or "").strip().lower()
        if not title:
            deduped.append(item)
            continue
        if any(
            SequenceMatcher(None, title, s).ratio() > 0.75 or title in s or s in title
            for s in seen_titles
        ):
            continue
        seen_titles.append(title)
        deduped.append(item)
    return {"results": deduped, "removed": len(results) - len(deduped)}
