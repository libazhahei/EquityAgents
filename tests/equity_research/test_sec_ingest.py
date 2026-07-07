"""Tests for SEC filing year ingest."""

from tradingagents.equity_research.integrations.sec_ingest import filings_to_documents


def test_filings_to_documents_skips_empty():
    docs = filings_to_documents(
        "AAPL",
        [
            {"accession_number": "a1", "form": "10-K", "full_text": ""},
            {"accession_number": "a2", "form": "10-Q", "full_text": "has content"},
        ],
    )
    assert len(docs) == 1
    assert docs[0].doc_key == "a2"
    assert docs[0].metadata["ticker"] == "AAPL"
