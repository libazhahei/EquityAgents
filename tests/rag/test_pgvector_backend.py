"""PgVector backend upsert tests."""

from tradingagents.rag.backends.in_memory import InMemoryBackend
from tradingagents.rag.types import Chunk


def test_upsert_with_json_embedding_false_does_not_raise():
    """Regression: json_embedding=False must not use `'embedding' in False`."""
    backend = InMemoryBackend()
    chunks = [
        Chunk(
            "c1",
            "revenue growth",
            "acc1",
            0,
            {"ticker": "NVDA", "accession_number": "acc1", "form": "10-K"},
        )
    ]
    schema = {
        "json_embedding": False,
        "id_column": "chunk_id",
        "text_column": "chunk_text",
        "doc_key_column": "accession_number",
    }
    count = backend.upsert_chunks("filing_chunk", chunks, [[0.1, 0.2, 0.3]], schema=schema)
    assert count == 1
