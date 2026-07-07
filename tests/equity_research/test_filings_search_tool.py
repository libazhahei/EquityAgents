"""Filings search tool tests."""

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag
from tradingagents.rag.types import CorpusScope, Document


def test_filings_search_requires_keywords():
    config = {"equity_research_use_memory": True, "equity_research": {}}
    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)
    result = filings_search_rag(deps, "AAPL", "")
    assert "error" in result


def test_filings_search_returns_hits_from_index():
    config = {"equity_research_use_memory": True, "equity_research": {}}
    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)
    deps.rag.ingest(
        "sec_filings",
        CorpusScope(
            ticker="AAPL",
            documents=[
                Document(
                    doc_key="0001",
                    text="ITEM 7. MD&A\n\nServices revenue rose 12% driven by installed base growth.",
                    metadata={
                        "ticker": "AAPL",
                        "form": "10-K",
                        "accession_number": "0001",
                        "filing_date": "2024-11-01",
                        "source_url": "https://sec.gov/0001",
                    },
                )
            ],
        ),
    )
    result = filings_search_rag(deps, "AAPL", "services revenue installed base")
    assert not result.get("error")
    assert result["hits"]
    assert "revenue" in result["hits"][0]["chunk_text"].lower()


def test_filings_search_rerank_demotes_low_info_chunk():
    config = {"equity_research_use_memory": True, "equity_research": {}}
    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)
    deps.rag.ingest(
        "sec_filings",
        CorpusScope(
            ticker="NVDA",
            documents=[
                Document(
                    doc_key="000a",
                    text=(
                        "ITEM 7. MANAGEMENT'S DISCUSSION\n\n"
                        "Gross Profit and Gross Margin\n"
                        "Refer to the Gross Profit and Gross Margin discussion below."
                    ),
                    metadata={
                        "ticker": "NVDA",
                        "form": "10-K",
                        "accession_number": "000a",
                        "filing_date": "2025-02-26",
                        "source_url": "https://sec.gov/000a",
                    },
                ),
                Document(
                    doc_key="000b",
                    text=(
                        "ITEM 7. MANAGEMENT'S DISCUSSION\n\n"
                        "Gross Profit and Gross Margin\n"
                        "Gross margin increased to 75.0% primarily driven by Data Center mix."
                    ),
                    metadata={
                        "ticker": "NVDA",
                        "form": "10-K",
                        "accession_number": "000b",
                        "filing_date": "2025-02-26",
                        "source_url": "https://sec.gov/000b",
                    },
                ),
            ],
        ),
    )
    result = filings_search_rag(deps, "NVDA", "gross margin", section="mda", top_k=1, rerank=True)
    assert "error" not in result
    assert result["hits"]
    assert "increased to 75.0%" in result["hits"][0]["chunk_text"]
    assert "final_score" in result["hits"][0]


def test_filings_search_prefers_recent_10q_for_recent_query():
    config = {"equity_research_use_memory": True, "equity_research": {}}
    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)
    deps.rag.ingest(
        "sec_filings",
        CorpusScope(
            ticker="NVDA",
            documents=[
                Document(
                    doc_key="k1",
                    text="ITEM 7. MANAGEMENT'S DISCUSSION\n\nGross Profit and Gross Margin\nGross margin was 75.0%.",
                    metadata={
                        "ticker": "NVDA",
                        "form": "10-K",
                        "accession_number": "k1",
                        "filing_date": "2025-02-26",
                        "source_url": "https://sec.gov/k1",
                    },
                ),
                Document(
                    doc_key="q1",
                    text=(
                        "ITEM 2. MANAGEMENT'S DISCUSSION\n\n"
                        "Gross Profit and Gross Margin\n"
                        "Gross margin decreased to 73.4% due to product transition."
                    ),
                    metadata={
                        "ticker": "NVDA",
                        "form": "10-Q",
                        "accession_number": "q1",
                        "filing_date": "2025-11-19",
                        "source_url": "https://sec.gov/q1",
                    },
                ),
            ],
        ),
    )
    result = filings_search_rag(deps, "NVDA", "gross margin recent quarters", top_k=1)
    assert result["hits"]
    assert result["prefer_recent"] is True
    assert result["hits"][0]["form"] == "10-Q"
