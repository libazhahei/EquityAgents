"""In-memory storage fallback when PostgreSQL is unavailable."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any


class InMemoryStore:
    _documents: dict[str, dict] = {}
    _fingerprints: dict[str, str] = {}
    _fragments: dict[str, dict] = {}
    _facts: dict[str, dict] = {}
    _traces: list[dict] = []
    _ledgers: dict[str, dict[str, dict]] = {}

    @classmethod
    def reset(cls) -> None:
        cls._documents.clear()
        cls._fingerprints.clear()
        cls._fragments.clear()
        cls._facts.clear()
        cls._traces.clear()
        cls._ledgers.clear()


def _fingerprint(ticker: str, source_type: str, title: str, published_date: str | None) -> str:
    raw = f"{ticker}|{source_type}|{title}|{published_date or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


class InMemoryDocumentRegistry:
    def register(self, ticker: str, source_type: str, title: str = "", source_url: str = "",
                 published_date: str | None = None, fiscal_period: str | None = None,
                 access_path: str | None = None, file_hash: str | None = None) -> dict[str, Any]:
        fp = _fingerprint(ticker, source_type, title, published_date)
        if fp in InMemoryStore._fingerprints:
            return InMemoryStore._documents[InMemoryStore._fingerprints[fp]]
        doc_id = str(uuid.uuid4())
        doc = {
            "doc_id": doc_id, "ticker": ticker.upper(), "source_type": source_type,
            "title": title, "published_date": published_date, "fiscal_period": fiscal_period,
            "source_url": source_url, "access_path": access_path, "file_hash": file_hash,
            "doc_fingerprint": fp, "processing_status": "registered",
            "reliability_score": 0.5, "citation_count": 0, "last_used_at": None,
        }
        InMemoryStore._documents[doc_id] = doc
        InMemoryStore._fingerprints[fp] = doc_id
        return doc

    def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        return InMemoryStore._documents.get(doc_id)

    def list_by_ticker(self, ticker: str) -> list[dict[str, Any]]:
        return [d for d in InMemoryStore._documents.values() if d["ticker"] == ticker.upper()]

    def update_reliability(self, doc_id: str, delta: float, reason: str = "") -> dict[str, Any] | None:
        doc = InMemoryStore._documents.get(doc_id)
        if not doc:
            return None
        current = float(doc.get("reliability_score", 0.5))
        doc["reliability_score"] = max(0.0, min(1.0, current + delta))
        doc["citation_count"] = int(doc.get("citation_count", 0)) + (1 if delta > 0 else 0)
        doc["last_used_at"] = datetime.utcnow().isoformat()
        return dict(doc)


class InMemoryEvidenceStore:
    def insert(self, ticker: str, doc_id: str, excerpt_text: str, **kwargs) -> dict[str, Any]:
        fid = kwargs.pop("fragment_id", None) or str(uuid.uuid4())
        frag = {
            "fragment_id": fid, "doc_id": doc_id, "ticker": ticker.upper(),
            "excerpt_text": excerpt_text, **kwargs,
        }
        InMemoryStore._fragments[fid] = frag
        return frag

    def search_similar(self, ticker: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        from tradingagents.equity_research.memory.similarity import cosine_similarity

        scored = []
        for frag in InMemoryStore._fragments.values():
            if frag["ticker"] != ticker.upper():
                continue
            emb = frag.get("embedding")
            if emb:
                score = cosine_similarity(query_embedding, emb)
            else:
                score = 0.0
            scored.append((score, {**frag, "score": score}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def list_by_ticker(self, ticker: str) -> list[dict]:
        return [f for f in InMemoryStore._fragments.values() if f["ticker"] == ticker.upper()]


class InMemoryFactStore:
    def insert(self, ticker: str, metric_name: str, metric_value: float | None = None, **kwargs) -> dict:
        fid = str(uuid.uuid4())
        fact = {"fact_id": fid, "ticker": ticker.upper(), "metric_name": metric_name,
                "metric_value": metric_value, **kwargs}
        InMemoryStore._facts[fid] = fact
        return fact

    def get_latest(self, ticker: str, metric_name: str, fiscal_period: str | None = None) -> dict | None:
        for f in InMemoryStore._facts.values():
            if f["ticker"] == ticker.upper() and f["metric_name"] == metric_name:
                return f
        return None

    def list_by_ticker(self, ticker: str) -> list[dict]:
        return [f for f in InMemoryStore._facts.values() if f["ticker"] == ticker.upper()]


class InMemoryTraceStore:
    def append(self, report_id: str, ticker: str, node_name: str, payload: dict, **kwargs) -> dict:
        entry = {
            "trace_id": str(uuid.uuid4()), "report_id": report_id, "ticker": ticker.upper(),
            "node_name": node_name, "payload": payload, **kwargs,
        }
        InMemoryStore._traces.append(entry)
        return entry


class InMemoryLedgerStore:
    def upsert(
        self,
        report_id: str,
        ticker: str,
        ledger_type: str,
        entry: dict[str, Any],
        *,
        created_by: str = "",
    ) -> dict[str, Any]:
        from tradingagents.equity_research.storage.ledger_store import _ID_FIELDS

        id_field = _ID_FIELDS.get(ledger_type, "id")
        entry_id = entry.get(id_field) or entry.get("id", "")
        if not entry_id:
            return entry
        report_bucket = InMemoryStore._ledgers.setdefault(report_id, {})
        report_bucket[entry_id] = {
            "report_id": report_id,
            "ticker": ticker.upper(),
            "ledger_type": ledger_type,
            "payload": dict(entry),
            "created_by": created_by or entry.get("created_by", ""),
            "created_at": entry.get("created_at", datetime.utcnow().isoformat()),
        }
        return entry

    def load_by_report(self, report_id: str) -> dict[str, list[dict[str, Any]]]:
        from tradingagents.equity_research.storage.ledger_store import _LEDGER_TYPE_TO_STATE_KEY

        rows = InMemoryStore._ledgers.get(report_id, {}).values()
        result: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            state_key = _LEDGER_TYPE_TO_STATE_KEY.get(
                row["ledger_type"], f"{row['ledger_type']}_ledger"
            )
            result.setdefault(state_key, []).append(dict(row["payload"]))
        return result

    def list_by_ticker(self, ticker: str, ledger_type: str | None = None) -> list[dict[str, Any]]:
        ticker = ticker.upper()
        entries: list[dict[str, Any]] = []
        for report_bucket in InMemoryStore._ledgers.values():
            for row in report_bucket.values():
                if row["ticker"] != ticker:
                    continue
                if ledger_type and row["ledger_type"] != ledger_type:
                    continue
                entries.append(dict(row["payload"]))
        return entries
