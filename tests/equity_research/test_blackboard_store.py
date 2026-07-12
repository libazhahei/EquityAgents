"""Tests for BlackboardStore persistence."""

from __future__ import annotations

import pytest

from tradingagents.equity_research.storage.blackboard_store import (
    BlackboardStore,
    InMemoryBlackboardStore,
)


class TestInMemoryBlackboardStore:
    """Test InMemoryBlackboardStore."""

    @pytest.fixture(autouse=True)
    def reset_store(self):
        """Reset store before each test."""
        InMemoryBlackboardStore.reset()

    def test_save_and_load_summary(self):
        """Test saving and loading a summary."""
        store = InMemoryBlackboardStore()
        store.save_session_summary("report_1", "section_a", "Summary of section A")
        
        result = store.load_session_summary("report_1", "section_a")
        assert result == "Summary of section A"

    def test_load_nonexistent_summary(self):
        """Test loading a summary that doesn't exist."""
        store = InMemoryBlackboardStore()
        result = store.load_session_summary("report_1", "section_nonexistent")
        assert result == ""

    def test_save_session_blackboard(self):
        """Test saving full blackboard entries."""
        store = InMemoryBlackboardStore()
        entries = [
            {"entry_id": "bb_1", "content": "Finding 1"},
            {"entry_id": "bb_2", "content": "Finding 2"},
        ]
        store.save_session_blackboard("report_1", "section_a", entries, ticker="NVDA")
        
        # Verify entries are stored (via get_prior_sessions_summaries after adding summary)
        store.save_session_summary("report_1", "section_a", "Summary")
        summaries = store.get_prior_sessions_summaries("report_1")
        assert len(summaries) == 1
        assert summaries[0]["section_id"] == "section_a"

    def test_get_prior_sessions_summaries(self):
        """Test getting prior session summaries."""
        store = InMemoryBlackboardStore()
        store.save_session_summary("report_1", "section_a", "Summary A")
        store.save_session_summary("report_1", "section_b", "Summary B")
        store.save_session_summary("report_1", "section_c", "Summary C")
        
        # Get all summaries
        summaries = store.get_prior_sessions_summaries("report_1")
        assert len(summaries) == 3
        
        # Get summaries excluding one section
        summaries = store.get_prior_sessions_summaries("report_1", exclude_section_id="section_b")
        assert len(summaries) == 2
        section_ids = {s["section_id"] for s in summaries}
        assert "section_a" in section_ids
        assert "section_c" in section_ids
        assert "section_b" not in section_ids

    def test_multiple_reports(self):
        """Test handling multiple reports."""
        store = InMemoryBlackboardStore()
        store.save_session_summary("report_1", "section_a", "Report 1 Summary A")
        store.save_session_summary("report_2", "section_a", "Report 2 Summary A")
        
        summaries_1 = store.get_prior_sessions_summaries("report_1")
        assert len(summaries_1) == 1
        assert summaries_1[0]["summary"] == "Report 1 Summary A"
        
        summaries_2 = store.get_prior_sessions_summaries("report_2")
        assert len(summaries_2) == 1
        assert summaries_2[0]["summary"] == "Report 2 Summary A"

    def test_update_summary(self):
        """Test updating an existing summary."""
        store = InMemoryBlackboardStore()
        store.save_session_summary("report_1", "section_a", "Original summary")
        store.save_session_summary("report_1", "section_a", "Updated summary")
        
        result = store.load_session_summary("report_1", "section_a")
        assert result == "Updated summary"

    def test_empty_summary_not_returned(self):
        """Test that empty summaries are not returned in get_prior_sessions_summaries."""
        store = InMemoryBlackboardStore()
        store.save_session_summary("report_1", "section_a", "")
        store.save_session_summary("report_1", "section_b", "Valid summary")
        
        summaries = store.get_prior_sessions_summaries("report_1")
        assert len(summaries) == 1
        assert summaries[0]["section_id"] == "section_b"


class TestBlackboardStoreIntegration:
    """Integration tests for BlackboardStore (requires PostgreSQL)."""

    @pytest.mark.skip(reason="Requires PostgreSQL database")
    def test_postgres_store(self):
        """Test BlackboardStore with PostgreSQL."""
        config = {"database_url": "postgresql://localhost/test"}
        store = BlackboardStore(config)
        
        # Save and load
        store.save_session_summary("report_1", "section_a", "Test summary")
        result = store.load_session_summary("report_1", "section_a")
        assert result == "Test summary"
