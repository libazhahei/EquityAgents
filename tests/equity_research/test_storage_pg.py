"""Integration tests for storage layer (requires PostgreSQL or skips)."""

import os
import uuid

import pytest

from tradingagents.equity_research.storage.document_registry import DocumentRegistry
from tradingagents.equity_research.storage.db import init_db


@pytest.fixture
def storage_config():
    url = os.environ.get("TRADINGAGENTS_POSTGRES_URL")
    if not url:
        pytest.skip("TRADINGAGENTS_POSTGRES_URL not set")
    return {"postgres_url": url}


@pytest.mark.integration
def test_document_fingerprint_dedup(storage_config):
    init_db(storage_config)
    reg = DocumentRegistry(storage_config)
    ticker = f"T{uuid.uuid4().hex[:6].upper()}"
    d1 = reg.register(ticker=ticker, source_type="news", title="Test Doc", source_url="http://example.com")
    d2 = reg.register(ticker=ticker, source_type="news", title="Test Doc", source_url="http://example.com")
    assert d1["doc_id"] == d2["doc_id"]
