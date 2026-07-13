"""Tests for session blackboard mechanism."""

from __future__ import annotations

import pytest

from tradingagents.equity_research.state.blackboard import (
    BLACKBOARD_CORE_TAGS,
    BLACKBOARD_ENTRY_TYPES,
    BlackboardEntry,
    blackboard_reducer,
    extract_blackboard_entries_from_coverage,
    extract_tags_from_text,
    format_blackboard_for_prompt,
    synthesizer_blackboard_auto_write_enabled,
)


class TestBlackboardEntry:
    """Test BlackboardEntry schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        entry = BlackboardEntry(
            section_id="1_investment_summary",
            source_node="synthesizer",
            entry_type="finding",
            content="NVDA data center revenue grew 40% YoY",
        )
        assert entry.section_id == "1_investment_summary"
        assert entry.source_node == "synthesizer"
        assert entry.entry_type == "finding"
        assert entry.content == "NVDA data center revenue grew 40% YoY"
        assert entry.entry_id.startswith("bb_")
        assert entry.confidence == 0.5
        assert entry.tags == []

    def test_optional_fields(self):
        """Test optional fields with defaults."""
        entry = BlackboardEntry(
            section_id="test",
            source_node="reflector",
            entry_type="hypothesis",
            content="Test content",
            question_id="q1",
            tags=["revenue", "growth"],
            confidence=0.8,
            created_at_iteration=2,
        )
        assert entry.question_id == "q1"
        assert entry.tags == ["revenue", "growth"]
        assert entry.confidence == 0.8
        assert entry.created_at_iteration == 2

    def test_tags_normalization(self):
        """Test that tags are normalized to lowercase."""
        entry = BlackboardEntry(
            section_id="test",
            source_node="synthesizer",
            entry_type="finding",
            content="Test",
            tags=["Revenue", "  GROWTH  ", "Margin"],
        )
        assert entry.tags == ["revenue", "growth", "margin"]

    def test_entry_types(self):
        """Test all valid entry types."""
        for entry_type in BLACKBOARD_ENTRY_TYPES:
            entry = BlackboardEntry(
                section_id="test",
                source_node="synthesizer",
                entry_type=entry_type,
                content="Test",
            )
            assert entry.entry_type == entry_type


class TestBlackboardReducer:
    """Test blackboard_reducer function."""

    def test_append_new_entries(self):
        """Test appending new entries."""
        existing = [
            {"entry_id": "bb_1", "content": "First"},
        ]
        new = [
            {"entry_id": "bb_2", "content": "Second"},
            {"entry_id": "bb_3", "content": "Third"},
        ]
        result = blackboard_reducer(existing, new)
        assert len(result) == 3
        assert result[0]["entry_id"] == "bb_1"
        assert result[1]["entry_id"] == "bb_2"
        assert result[2]["entry_id"] == "bb_3"

    def test_dedup_by_entry_id(self):
        """Test deduplication by entry_id."""
        existing = [
            {"entry_id": "bb_1", "content": "First", "confidence": 0.5},
        ]
        new = [
            {"entry_id": "bb_1", "content": "First updated", "confidence": 0.8},
        ]
        result = blackboard_reducer(existing, new)
        assert len(result) == 1
        assert result[0]["content"] == "First updated"
        assert result[0]["confidence"] == 0.8

    def test_empty_inputs(self):
        """Test with empty inputs."""
        assert blackboard_reducer([], []) == []
        assert blackboard_reducer(None, []) == []
        assert blackboard_reducer([], [{"entry_id": "bb_1"}]) == [{"entry_id": "bb_1"}]


class TestFormatBlackboardForPrompt:
    """Test format_blackboard_for_prompt function."""

    def test_empty_blackboard(self):
        """Test with empty blackboard."""
        assert format_blackboard_for_prompt([]) == ""
        assert format_blackboard_for_prompt(None) == ""

    def test_basic_formatting(self):
        """Test basic formatting."""
        entries = [
            {
                "entry_id": "bb_1",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Revenue grew 40%",
                "tags": ["revenue"],
                "created_at_iteration": 1,
            },
        ]
        result = format_blackboard_for_prompt(entries)
        assert "## Session Blackboard" in result
        assert "[finding, iter=1]" in result
        assert "Revenue grew 40%" in result
        assert "(tags: revenue)" in result

    def test_max_items_limit(self):
        """Test max_items limit."""
        entries = [
            {
                "entry_id": f"bb_{i}",
                "section_id": "test",
                "entry_type": "finding",
                "content": f"Content {i}",
                "tags": [],
                "created_at_iteration": i,
            }
            for i in range(20)
        ]
        result = format_blackboard_for_prompt(entries, max_items=5)
        # Should only include 5 entries
        assert result.count("[finding, iter=") == 5

    def test_max_chars_ignored_keeps_full_content(self):
        """max_chars is ignored; content is not hard-truncated."""
        entries = [
            {
                "entry_id": "bb_1",
                "section_id": "test",
                "entry_type": "finding",
                "content": "A" * 500,
                "tags": [],
                "created_at_iteration": 1,
            },
        ]
        result = format_blackboard_for_prompt(entries, max_chars=100)
        assert "A" * 500 in result
        assert "..." not in result or result.count("A") >= 500

    def test_filter_by_tags(self):
        """Test filtering by tags."""
        entries = [
            {
                "entry_id": "bb_1",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Revenue finding",
                "tags": ["revenue"],
                "created_at_iteration": 1,
            },
            {
                "entry_id": "bb_2",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Margin finding",
                "tags": ["margin"],
                "created_at_iteration": 1,
            },
        ]
        result = format_blackboard_for_prompt(entries, filter_tags=["revenue"])
        assert "Revenue finding" in result
        assert "Margin finding" not in result

    def test_filter_by_section(self):
        """Test filtering by section_id."""
        entries = [
            {
                "entry_id": "bb_1",
                "section_id": "section_a",
                "entry_type": "finding",
                "content": "Section A finding",
                "tags": [],
                "created_at_iteration": 1,
            },
            {
                "entry_id": "bb_2",
                "section_id": "section_b",
                "entry_type": "finding",
                "content": "Section B finding",
                "tags": [],
                "created_at_iteration": 1,
            },
        ]
        result = format_blackboard_for_prompt(entries, section_id="section_a")
        assert "Section A finding" in result
        assert "Section B finding" not in result

    def test_sort_by_iteration(self):
        """Test sorting by iteration (descending)."""
        entries = [
            {
                "entry_id": "bb_1",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Iteration 1",
                "tags": [],
                "created_at_iteration": 1,
            },
            {
                "entry_id": "bb_2",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Iteration 3",
                "tags": [],
                "created_at_iteration": 3,
            },
            {
                "entry_id": "bb_3",
                "section_id": "test",
                "entry_type": "finding",
                "content": "Iteration 2",
                "tags": [],
                "created_at_iteration": 2,
            },
        ]
        result = format_blackboard_for_prompt(entries, max_items=3)
        # Should be sorted by iteration descending
        lines = result.split("\n")
        assert "Iteration 3" in lines[1]
        assert "Iteration 2" in lines[2]
        assert "Iteration 1" in lines[3]


class TestExtractTagsFromText:
    """Test extract_tags_from_text function."""

    def test_revenue_tags(self):
        """Test revenue-related tags."""
        tags = extract_tags_from_text("Revenue grew 20% YoY to $10B")
        assert "revenue" in tags
        assert "growth" in tags

    def test_margin_tags(self):
        """Test margin-related tags."""
        tags = extract_tags_from_text("Gross margin expanded 200bps")
        assert "margin" in tags

    def test_valuation_tags(self):
        """Test valuation-related tags."""
        tags = extract_tags_from_text("PE ratio of 25x and EV/EBITDA of 15x")
        assert "valuation" in tags

    def test_multiple_tags(self):
        """Test extracting multiple tags."""
        tags = extract_tags_from_text("Revenue growth driven by competitive advantages")
        assert "revenue" in tags
        assert "growth" in tags
        assert "competitive" in tags

    def test_no_tags(self):
        """Test with text that has no matching tags."""
        tags = extract_tags_from_text("Random text without financial terms")
        assert len(tags) == 0


class TestBlackboardCoreTags:
    """Test BLACKBOARD_CORE_TAGS constant."""

    def test_core_tags_exist(self):
        """Test that core tags are defined."""
        assert len(BLACKBOARD_CORE_TAGS) > 0
        assert "revenue" in BLACKBOARD_CORE_TAGS
        assert "margin" in BLACKBOARD_CORE_TAGS
        assert "valuation" in BLACKBOARD_CORE_TAGS

    def test_core_tags_are_strings(self):
        """Test that all core tags are strings."""
        for tag in BLACKBOARD_CORE_TAGS:
            assert isinstance(tag, str)


class TestBlackboardEntryTypes:
    """Test BLACKBOARD_ENTRY_TYPES constant."""

    def test_entry_types_exist(self):
        """Test that entry types are defined."""
        assert len(BLACKBOARD_ENTRY_TYPES) > 0
        assert "finding" in BLACKBOARD_ENTRY_TYPES
        assert "hypothesis" in BLACKBOARD_ENTRY_TYPES
        assert "contradiction" in BLACKBOARD_ENTRY_TYPES

    def test_entry_types_are_strings(self):
        """Test that all entry types are strings."""
        for entry_type in BLACKBOARD_ENTRY_TYPES:
            assert isinstance(entry_type, str)


class TestSynthesizerBlackboardAutoWriteFlag:
    def test_default_off(self):
        assert synthesizer_blackboard_auto_write_enabled(None) is False
        assert synthesizer_blackboard_auto_write_enabled({}) is False
        assert synthesizer_blackboard_auto_write_enabled({"equity_research": {}}) is False

    def test_explicit_on(self):
        assert synthesizer_blackboard_auto_write_enabled(
            {"equity_research": {"blackboard_synthesizer_auto_write": True}}
        ) is True

    def test_explicit_off(self):
        assert synthesizer_blackboard_auto_write_enabled(
            {"equity_research": {"blackboard_synthesizer_auto_write": False}}
        ) is False


class TestExtractBlackboardFromCoverage:
    def test_maps_section_coverage_fields(self):
        report = {
            "contradictions": [
                {"gap": "10-K segment mix disagrees with earnings call commentary on networking."}
            ],
            "critical_gaps": [
                {
                    "coverage_output": "margin_driver_analysis",
                    "gap": "No dedicated margin driver analysis output is present.",
                }
            ],
            "data_quality_issues": [
                {
                    "type": "missing_source",
                    "severity": "high",
                    "message": "Primary filing tables were not attached to the evidence bundle.",
                },
                {
                    "type": "pending_todo_items",
                    "severity": "low",
                    "message": "3 todo items still pending.",
                },
            ],
        }
        entries = extract_blackboard_entries_from_coverage(
            {"section_id": "3_business_model"},
            report,
            iteration=2,
        )
        assert len(entries) == 3
        assert [e["entry_type"] for e in entries] == [
            "contradiction",
            "methodology",
            "finding",
        ]
        assert all(e["source_node"] == "reflector" for e in entries)
        assert all(e["section_id"] == "3_business_model" for e in entries)
        assert all(e["created_at_iteration"] == 2 for e in entries)
        assert "Contradiction:" in entries[0]["content"]
        assert "Critical gap:" in entries[1]["content"]
        assert "Data quality:" in entries[2]["content"]

    def test_priority_and_cap(self):
        report = {
            "contradictions": [
                {"gap": f"Contradiction number {i} with enough detail here."}
                for i in range(3)
            ],
            "critical_gaps": [
                {"gap": f"Critical gap number {i} needs more research detail."}
                for i in range(4)
            ],
            "data_quality_issues": [
                {
                    "severity": "critical",
                    "message": "Severe missing primary source for revenue bridge.",
                }
            ],
        }
        entries = extract_blackboard_entries_from_coverage(
            {"section_id": "s1"},
            report,
            iteration=1,
            max_entries=5,
        )
        assert len(entries) == 5
        assert [e["entry_type"] for e in entries] == [
            "contradiction",
            "contradiction",
            "contradiction",
            "methodology",
            "methodology",
        ]

    def test_suggested_focus_and_dimension_scores(self):
        report = {
            "suggested_focus": "Probe whether margin compression is mix-shift driven versus ASP.",
            "dimension_scores": {
                "revenue": {"score": 0.15, "notes": "Segment tables incomplete for auto."},
                "margin": {"score": 0.9, "notes": "Fine"},
            },
        }
        entries = extract_blackboard_entries_from_coverage(
            {"section_id": "s1"},
            report,
            iteration=4,
        )
        types = [e["entry_type"] for e in entries]
        assert "hypothesis" in types
        assert "contradiction" in types  # score < 0.2

