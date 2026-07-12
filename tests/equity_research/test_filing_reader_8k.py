"""Tests for filing_reader dynamic form handling."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestFilingReaderDynamicFormHandling:
    """Verify filing_reader dynamically handles different form types based on available_items."""

    def test_toc_instruction_lists_available_items(self):
        """TOC instruction should dynamically list available items from the filing."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        # Mock an 8-K filing with 8-K specific items
        mock_filing = MagicMock()
        mock_filing.form = "8-K"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000228"
        mock_filing.filing_url = "https://example.com/filing.htm"

        mock_obj = MagicMock()
        mock_obj.items = ["Item 2.02", "Item 9.01"]  # 8-K specific items
        mock_obj.financials = None
        mock_obj.structure = None
        mock_obj.__getitem__ = MagicMock(side_effect=KeyError)
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        with patch.object(client, "_document_tables", return_value=[]):
                            result = client.read_filing_section(
                                filing_url="https://example.com/filing.htm",
                                section="toc",
                            )

        assert result["form"] == "8-K"
        assert "Item 2.02" in result["instruction"]
        assert "Item 9.01" in result["instruction"]
        assert "available_items" in result

    def test_toc_instruction_for_10k_lists_standard_items(self):
        """10-K TOC should list standard 10-K items."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-K"
        mock_filing.filing_date = "2025-01-31"
        mock_filing.accession_number = "0000320193-25-000001"
        mock_filing.filing_url = "https://example.com/filing.htm"

        mock_obj = MagicMock()
        mock_obj.items = ["Item 1", "Item 1A", "Item 7", "Item 8"]
        mock_obj.financials = None
        mock_obj.structure = None
        mock_obj.__getitem__ = MagicMock(side_effect=KeyError)
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        with patch.object(client, "_document_tables", return_value=[]):
                            result = client.read_filing_section(
                                filing_url="https://example.com/filing.htm",
                                section="toc",
                            )

        assert result["form"] == "10-K"
        assert "Item 1" in result["instruction"]
        assert "Item 7" in result["instruction"]

    def test_section_access_validates_against_available_items(self):
        """Accessing a section not in available_items should return clear error."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        # Mock 8-K filing without mda/risk_factors/business items
        mock_filing = MagicMock()
        mock_filing.form = "8-K"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000228"
        mock_filing.filing_url = "https://example.com/filing.htm"

        mock_obj = MagicMock()
        mock_obj.items = ["Item 2.02", "Item 9.01"]  # No mda/risk_factors
        mock_obj.financials = None
        mock_obj.structure = None
        mock_obj.sections = {}
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        result = client.read_filing_section(
                            filing_url="https://example.com/filing.htm",
                            section="mda",
                        )

        assert "error" in result
        assert "mda" in result["error"]
        assert "not available" in result["error"]
        assert "Item 2.02" in result["error"] or "Item 9.01" in result["error"]

    def test_section_access_allowed_when_in_available_items(self):
        """Accessing a section that IS in available_items should proceed normally."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        # Mock 10-K filing WITH mda item
        mock_filing = MagicMock()
        mock_filing.form = "10-K"
        mock_filing.filing_date = "2025-01-31"
        mock_filing.accession_number = "0000320193-25-000001"
        mock_filing.filing_url = "https://example.com/filing.htm"

        mock_obj = MagicMock()
        mock_obj.items = ["Item 1", "Item 1A", "Item 7"]
        mock_obj.financials = None
        mock_obj.structure = None
        
        # Mock section found
        mock_section = MagicMock()
        mock_section.markdown.return_value = "Management discussion content..."
        mock_section.tables.return_value = []
        mock_obj.sections = {"Item 7": mock_section}
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        with patch.object(client, "_find_section_by_item", return_value=mock_section):
                            result = client.read_filing_section(
                                filing_url="https://example.com/filing.htm",
                                section="mda",
                            )

        # Should not have error, should have content
        assert "error" not in result or result.get("content")


class TestFilingsSearchFallback:
    """Verify filings_search progressively relaxes filters when no results."""

    def _make_deps(self, search_side_effect=None, search_return=None):
        deps = MagicMock()
        mock_rag = MagicMock()
        deps.rag = mock_rag

        if search_side_effect:
            mock_rag.search.side_effect = search_side_effect
        elif search_return:
            mock_rag.search.return_value = search_return
        return deps

    def test_fallback_relaxes_quarter_filter(self):
        """When quarter filter yields no results, should retry without quarter."""
        from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

        empty_result = MagicMock()
        empty_result.hits = []
        empty_result.keywords = "revenue"
        empty_result.indexed = True
        empty_result.extra = {}

        hit = MagicMock()
        hit.text = "Revenue grew 50% YoY"
        hit.score = 0.8
        hit.metadata = {
            "form": "10-Q",
            "filing_date": "2026-02-15",
            "section": "mda",
            "accession_number": "0001-23-456",
            "chunk_index": 0,
            "chunk_type": "text",
            "subsection_title": "Results",
            "subsection_key": "results",
            "content_hash": "abc123",
            "info_score_seed": 0.7,
        }
        good_result = MagicMock()
        good_result.hits = [hit]
        good_result.keywords = "revenue"
        good_result.indexed = True
        good_result.extra = {}

        # First call returns empty, second returns hits
        deps = self._make_deps(search_side_effect=[empty_result, good_result])

        result = filings_search_rag(
            deps,
            ticker="NVDA",
            keywords="revenue",
            form_type="10-Q",
            quarter="Q1",
            year="2026",
        )

        assert len(result["hits"]) > 0
        assert deps.rag.search.call_count == 2

    def test_fallback_relaxes_year_then_form(self):
        """When year filter also fails, should try without year, then without form."""
        from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

        empty_result = MagicMock()
        empty_result.hits = []
        empty_result.keywords = "revenue"
        empty_result.indexed = True
        empty_result.extra = {}

        hit = MagicMock()
        hit.text = "Revenue grew 50% YoY"
        hit.score = 0.8
        hit.metadata = {
            "form": "10-K",
            "filing_date": "2025-01-31",
            "section": "mda",
            "accession_number": "0001-23-456",
            "chunk_index": 0,
            "chunk_type": "text",
            "subsection_title": "Results",
            "subsection_key": "results",
            "content_hash": "abc123",
            "info_score_seed": 0.7,
        }
        good_result = MagicMock()
        good_result.hits = [hit]
        good_result.keywords = "revenue"
        good_result.indexed = True
        good_result.extra = {}

        # First 3 calls empty (with quarter, without quarter, without year), 4th has hits
        deps = self._make_deps(search_side_effect=[empty_result, empty_result, empty_result, good_result])

        result = filings_search_rag(
            deps,
            ticker="NVDA",
            keywords="revenue",
            form_type="10-Q",
            quarter="Q1",
            year="2026",
        )

        assert len(result["hits"]) > 0
        assert deps.rag.search.call_count == 4

    def test_no_fallback_when_results_found(self):
        """When initial search returns results, no fallback should be triggered."""
        from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

        hit = MagicMock()
        hit.text = "Revenue grew 50% YoY"
        hit.score = 0.8
        hit.metadata = {
            "form": "10-Q",
            "filing_date": "2026-02-15",
            "section": "mda",
            "accession_number": "0001-23-456",
            "chunk_index": 0,
            "chunk_type": "text",
            "subsection_title": "Results",
            "subsection_key": "results",
            "content_hash": "abc123",
            "info_score_seed": 0.7,
        }
        good_result = MagicMock()
        good_result.hits = [hit]
        good_result.keywords = "revenue"
        good_result.indexed = True
        good_result.extra = {}

        deps = self._make_deps(search_return=good_result)

        result = filings_search_rag(
            deps,
            ticker="NVDA",
            keywords="revenue",
            form_type="10-Q",
            quarter="Q1",
            year="2026",
        )

        assert len(result["hits"]) > 0
        assert deps.rag.search.call_count == 1


class TestPartQualifiedItemFormat:
    """Verify filing_reader handles 'Part I, Item 2' format correctly."""

    def test_resolve_section_extracts_item_from_part_qualified(self):
        """_resolve_section_param should convert 'Part X, Item Y' to section key format."""
        from tradingagents.dataflows.equity_vendors import _resolve_section_param

        assert _resolve_section_param("Part I, Item 2", "full") == "part_i_item_2"
        assert _resolve_section_param("Part II, Item 1A", "full") == "part_ii_item_1a"
        assert _resolve_section_param("Part I, Item 1", "full") == "part_i_item_1"
        assert _resolve_section_param("Part II, Item 6", "full") == "part_ii_item_6"

    def test_resolve_section_passes_through_item_format(self):
        """Direct 'Item X' format should pass through or be aliased correctly."""
        from tradingagents.dataflows.equity_vendors import _resolve_section_param

        # "Item 2" is not aliased, should pass through
        assert _resolve_section_param("Item 2", "full") == "Item 2"
        # "Item 1A" is aliased to "risk_factors" (correct behavior)
        assert _resolve_section_param("Item 1A", "full") == "risk_factors"
        # "Item 7" is aliased to "mda" (correct behavior)
        assert _resolve_section_param("Item 7", "full") == "mda"
        # "Item 1" is aliased to "business" (correct behavior)
        assert _resolve_section_param("Item 1", "full") == "business"

    def test_resolve_section_still_handles_aliases(self):
        """Standard aliases (mda, risk_factors, etc.) should still work."""
        from tradingagents.dataflows.equity_vendors import _resolve_section_param

        assert _resolve_section_param("mda", "full") == "mda"
        assert _resolve_section_param("risk_factors", "full") == "risk_factors"
        assert _resolve_section_param("business", "full") == "business"
        assert _resolve_section_param("toc", "full") == "toc"
        assert _resolve_section_param("tables", "full") == "tables"

    def test_edgar_client_handles_item_format_directly(self):
        """EdgarClient should handle 'Item X' format without _resolve_section_param."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-Q"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000230"
        mock_filing.filing_url = "https://example.com/filing.htm"

        mock_section = MagicMock()
        mock_section.markdown.return_value = "MD&A content here..."
        mock_section.tables.return_value = []
        mock_section.text.return_value = "MD&A content here..."
        mock_section.item = "2"

        mock_obj = MagicMock()
        mock_obj.items = ["Part I, Item 1", "Part I, Item 2"]
        mock_obj.financials = None
        mock_obj.structure = None
        mock_obj.sections = {"mock": mock_section}
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        with patch.object(client, "_find_section_by_item", return_value=mock_section):
                            result = client.read_filing_section(
                                filing_url="https://example.com/filing.htm",
                                section="Item 2",
                            )

        # Should have content, not just metadata
        assert "content" in result or "text_excerpt" in result


class TestPartQualifiedSectionKeyFormat:
    """Verify Part-qualified format is converted to section key format."""

    def test_resolve_section_converts_to_section_key(self):
        """_resolve_section_param should convert 'Part X, Item Y' to 'part_x_item_y'."""
        from tradingagents.dataflows.equity_vendors import _resolve_section_param

        assert _resolve_section_param("Part I, Item 1", "full") == "part_i_item_1"
        assert _resolve_section_param("Part I, Item 2", "full") == "part_i_item_2"
        assert _resolve_section_param("Part II, Item 1", "full") == "part_ii_item_1"
        assert _resolve_section_param("Part II, Item 1A", "full") == "part_ii_item_1a"

    def test_section_key_lookup_in_edgar_client(self):
        """EdgarClient should handle section key format directly."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-Q"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000230"
        mock_filing.filing_url = "https://example.com/filing.htm"

        # Mock sections with part_i_item_1 and part_ii_item_1
        mock_section_i = MagicMock()
        mock_section_i.markdown.return_value = "Part I Item 1 content"
        mock_section_i.tables.return_value = []
        mock_section_i.text.return_value = "Part I Item 1 content"

        mock_section_ii = MagicMock()
        mock_section_ii.markdown.return_value = "Part II Item 1 content"
        mock_section_ii.tables.return_value = []
        mock_section_ii.text.return_value = "Part II Item 1 content"

        mock_obj = MagicMock()
        mock_obj.sections = {
            "part_i_item_1": mock_section_i,
            "part_ii_item_1": mock_section_ii,
        }
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                with patch.object(client, "_get_section_cached", return_value=None):
                    with patch.object(client, "_put_section_cached"):
                        # Test Part I, Item 1
                        result = client.read_filing_section(
                            filing_url="https://example.com/filing.htm",
                            section="part_i_item_1",
                        )
                        assert result.get("content") == "Part I Item 1 content"
                        assert result.get("item") == "part_i_item_1"

                        # Test Part II, Item 1
                        result = client.read_filing_section(
                            filing_url="https://example.com/filing.htm",
                            section="part_ii_item_1",
                        )
                        assert result.get("content") == "Part II Item 1 content"
                        assert result.get("item") == "part_ii_item_1"


class TestPartQualifiedFormatWithComma:
    """Verify EdgarClient handles 'Part X, Item Y' format directly (with comma and space)."""

    def test_edgar_client_handles_part_comma_item_format(self):
        """EdgarClient.read_filing_section should handle 'Part X, Item Y' format directly."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-Q"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000230"
        mock_filing.filing_url = "https://example.com/filing.htm"

        # Mock sections with part_i_item_2
        mock_section = MagicMock()
        mock_section.markdown.return_value = "Part I Item 2 content (MD&A)"
        mock_section.tables.return_value = []
        mock_section.text.return_value = "Part I Item 2 content (MD&A)"

        mock_obj = MagicMock()
        mock_obj.sections = {"part_i_item_2": mock_section}
        mock_obj.items = ["Part I, Item 2"]
        mock_filing.obj.return_value = mock_obj

        # Mock _load_filing_by_url to return our mock filing
        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                # Test with "Part I, Item 2" format (with comma and space)
                result = client.read_filing_section(
                    filing_url="https://example.com/filing.htm",
                    section="Part I, Item 2"
                )

                assert "error" not in result
                assert result.get("content") == "Part I Item 2 content (MD&A)"
                assert result.get("item") == "part_i_item_2"
                assert result.get("form") == "10-Q"

    def test_edgar_client_handles_various_part_formats(self):
        """EdgarClient should handle various Part-qualified formats."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-Q"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000230"
        mock_filing.filing_url = "https://example.com/filing.htm"

        # Mock multiple sections
        mock_section_1 = MagicMock()
        mock_section_1.markdown.return_value = "Item 1 content"
        mock_section_1.tables.return_value = []
        
        mock_section_1a = MagicMock()
        mock_section_1a.markdown.return_value = "Item 1A content"
        mock_section_1a.tables.return_value = []

        mock_obj = MagicMock()
        mock_obj.sections = {
            "part_i_item_1": mock_section_1,
            "part_ii_item_1a": mock_section_1a,
        }
        mock_obj.items = ["Part I, Item 1", "Part II, Item 1A"]
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                # Test "Part I, Item 1"
                result = client.read_filing_section(
                    filing_url="https://example.com/filing.htm",
                    section="Part I, Item 1"
                )
                assert "error" not in result
                assert result.get("content") == "Item 1 content"

                # Test "Part II, Item 1A"
                result = client.read_filing_section(
                    filing_url="https://example.com/filing.htm",
                    section="Part II, Item 1A"
                )
                assert "error" not in result
                assert result.get("content") == "Item 1A content"


class TestMdaAliasMapping:
    """Verify mda alias maps to correct Item based on form type."""

    def test_mda_maps_to_item_2_in_10q(self):
        """In 10-Q filings, mda should map to Item 2 (not Item 7)."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-Q"
        mock_filing.filing_date = "2025-11-19"
        mock_filing.accession_number = "0001045810-25-000230"
        mock_filing.filing_url = "https://example.com/filing.htm"

        # Mock sections with part_i_item_2 (10-Q MDA)
        mock_section = MagicMock()
        mock_section.markdown.return_value = "10-Q MDA content (Item 2)"
        mock_section.tables.return_value = []
        mock_section.text.return_value = "10-Q MDA content (Item 2)"
        mock_section.item = "2"  # This is what _find_section_by_item looks for

        mock_obj = MagicMock()
        mock_obj.sections = {"part_i_item_2": mock_section}
        mock_obj.items = ["Part I, Item 1", "Part I, Item 2"]
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                result = client.read_filing_section(
                    filing_url="https://example.com/filing.htm",
                    section="mda"
                )

                assert "error" not in result
                assert result.get("content") == "10-Q MDA content (Item 2)"
                assert result.get("item") == "Item 2"
                assert result.get("form") == "10-Q"

    def test_mda_maps_to_item_7_in_10k(self):
        """In 10-K filings, mda should map to Item 7."""
        from tradingagents.equity_research.integrations.edgar import EdgarClient

        client = EdgarClient()

        mock_filing = MagicMock()
        mock_filing.form = "10-K"
        mock_filing.filing_date = "2025-01-26"
        mock_filing.accession_number = "0001045810-25-000023"
        mock_filing.filing_url = "https://example.com/filing.htm"

        # Mock sections with Item 7 (10-K MDA)
        mock_section = MagicMock()
        mock_section.markdown.return_value = "10-K MDA content (Item 7)"
        mock_section.tables.return_value = []
        mock_section.text.return_value = "10-K MDA content (Item 7)"
        mock_section.item = "7"  # This is what _find_section_by_item looks for

        mock_obj = MagicMock()
        mock_obj.sections = {"item_7": mock_section}
        mock_obj.items = ["Item 1", "Item 1A", "Item 7"]
        mock_filing.obj.return_value = mock_obj

        with patch.object(client, "_load_filing_by_url", return_value=mock_filing):
            with patch.object(client, "_set_identity"):
                result = client.read_filing_section(
                    filing_url="https://example.com/filing.htm",
                    section="mda"
                )

                assert "error" not in result
                assert result.get("content") == "10-K MDA content (Item 7)"
                assert result.get("item") == "Item 7"
                assert result.get("form") == "10-K"
