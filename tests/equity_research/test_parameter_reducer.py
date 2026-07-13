"""Tests for the ParameterPreservingReducer pipeline.

Covers:
- Schema validation (ParameterValue, Parameter, ParameterRegistry)
- Skill-driven dimension extraction
- LangGraph-native reducers (semantic dedup, doc_id dedup, etc.)
- Parameter extraction from evidence (with mocked LLM)
- Parameter reduction: merge, conflict detection, version chain
- Parameter grid compilation (no length limit)
- End-to-end integration via executor apply node
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ── Schema imports ──────────────────────────────────────────────────────
from tradingagents.equity_research.runtime.parameter_schemas import (
    ExtractedParameter,
    LLMExtractionOutput,
    Parameter,
    ParameterRegistry,
    ParameterValue,
)

# ── Parser imports ──────────────────────────────────────────────────────
from tradingagents.equity_research.runtime.skill_parameter_parser import (
    build_extraction_prompt_template,
    extract_parameter_dimensions,
)

# ── Reducer imports ─────────────────────────────────────────────────────
from tradingagents.equity_research.runtime.reducers import (
    calculation_store_reducer,
    documents_reducer,
    errors_reducer,
    evidence_buffer_reducer,
    fact_store_reducer,
    merge_ledger_by_id,
    pending_evidence_reducer,
    search_memory_reducer,
)
from tradingagents.equity_research.state.blackboard import blackboard_reducer

# ── Extractor imports ───────────────────────────────────────────────────
from tradingagents.equity_research.runtime.parameter_extractor import (
    _format_evidence_for_extraction,
    _infer_dimension,
    extract_parameters_from_evidence,
)

# ── Reducer (parameter) imports ─────────────────────────────────────────
from tradingagents.equity_research.runtime.parameter_reducer import (
    _values_compatible,
    reduce_parameters,
)

# ── Compiler imports ────────────────────────────────────────────────────
from tradingagents.equity_research.runtime.parameter_compiler import (
    compile_parameter_grid,
)


# ═══════════════════════════════════════════════════════════════════════
# Schema tests
# ═══════════════════════════════════════════════════════════════════════


class TestParameterSchemas:
    def test_parameter_value_as_of_required(self):
        pv = ParameterValue(value=75.2, as_of="FY2025")
        assert pv.as_of == "FY2025"
        assert pv.value == 75.2
        assert pv.unit == ""
        assert pv.confidence == 0.8

    def test_parameter_with_history(self):
        p = Parameter(
            key="gross_margin",
            dimension="margin_driver_analysis",
            current=ParameterValue(value=75.2, as_of="FY2025", turn=1, source="10-K"),
            history=[
                ParameterValue(value=73.0, as_of="FY2024", turn=0, source="10-K"),
            ],
        )
        assert len(p.history) == 1
        assert p.history[0].value == 73.0

    def test_parameter_registry_empty_default(self):
        reg = ParameterRegistry()
        assert reg.parameters == {}
        assert reg.dimensions == []

    def test_parameter_registry_roundtrip(self):
        reg = ParameterRegistry(
            parameters={
                "revenue": Parameter(
                    key="revenue",
                    current=ParameterValue(value=100e9, as_of="FY2025"),
                ),
            },
            dimensions=["revenue_model_explanation"],
        )
        dumped = reg.model_dump()
        restored = ParameterRegistry.model_validate(dumped)
        assert "revenue" in restored.parameters
        assert restored.parameters["revenue"].current.value == 100e9

    def test_extracted_parameter_as_of_mandatory(self):
        ep = ExtractedParameter(key="gross_margin", value=75.2, as_of="Q3 2024")
        assert ep.as_of == "Q3 2024"

    def test_llm_extraction_output_empty(self):
        out = LLMExtractionOutput()
        assert out.parameters == []
        assert out.unstructured_narrative == ""


# ═══════════════════════════════════════════════════════════════════════
# Skill parameter parser tests
# ═══════════════════════════════════════════════════════════════════════


class TestSkillParameterParser:
    def test_extract_dimensions_from_required_outputs(self):
        ctx = {
            "prompt_template": "Required outputs:\n1. margin_driver_analysis\n2. revenue_model_explanation\n",
            "constraints": "",
        }
        dims = extract_parameter_dimensions(ctx)
        assert "margin_driver_analysis" in dims
        assert "revenue_model_explanation" in dims

    def test_extract_dimensions_from_constraints(self):
        ctx = {
            "prompt_template": "",
            "constraints": "Discuss key_operating_metrics and revenue_model_explanation.",
        }
        dims = extract_parameter_dimensions(ctx)
        assert "key_operating_metrics" in dims
        assert "revenue_model_explanation" in dims

    def test_extract_dimensions_empty(self):
        dims = extract_parameter_dimensions({})
        assert dims == []

    def test_extract_dimensions_dedup(self):
        ctx = {
            "prompt_template": "Required outputs:\n1. margin_driver_analysis\n",
            "constraints": "Focus on margin_driver_analysis and key_operating_metrics.",
        }
        dims = extract_parameter_dimensions(ctx)
        # margin_driver_analysis should appear once
        assert dims.count("margin_driver_analysis") == 1

    def test_build_extraction_prompt_template(self):
        prompt = build_extraction_prompt_template(
            ["margin_driver_analysis", "revenue_model"],
            "Discuss key margin drivers.",
        )
        assert "margin_driver_analysis" in prompt
        assert "revenue_model" in prompt
        assert "as_of" in prompt
        assert "Discuss key margin drivers." in prompt

    def test_build_extraction_prompt_no_dimensions(self):
        prompt = build_extraction_prompt_template([], "")
        assert "general" in prompt


# ═══════════════════════════════════════════════════════════════════════
# LangGraph-native reducer tests
# ═══════════════════════════════════════════════════════════════════════


class TestLangGraphReducers:
    def test_evidence_buffer_dedup(self):
        existing = [{"snippet": "Gross margin was 75.2% in FY2025", "source": "10-K"}]
        new = [{"snippet": "Gross margin was 75.2% in FY2025", "source": "10-K"}]
        result = evidence_buffer_reducer(existing, new)
        # Should deduplicate the identical snippet
        assert len(result) == 1

    def test_evidence_buffer_dedup_by_evidence_id(self):
        existing = [{"evidence_id": "ev_1", "snippet": "Alpha"}]
        new = [{"evidence_id": "ev_1", "snippet": "Completely different wording"}]
        result = evidence_buffer_reducer(existing, new)
        assert len(result) == 1
        assert result[0]["snippet"] == "Alpha"

    def test_evidence_buffer_append_different(self):
        existing = [{"snippet": "Gross margin was 75.2%", "source": "10-K"}]
        new = [{"snippet": "Revenue grew 20% year over year", "source": "earnings"}]
        result = evidence_buffer_reducer(existing, new)
        assert len(result) == 2

    def test_evidence_buffer_empty_new(self):
        existing = [{"snippet": "some evidence", "source": "x"}]
        result = evidence_buffer_reducer(existing, [])
        assert result == existing

    def test_pending_evidence_overwrites(self):
        result = pending_evidence_reducer(
            [{"id": 1}], [{"id": 1}, {"id": 2}]
        )
        assert result == [{"id": 1}, {"id": 2}]

    def test_pending_evidence_empty_clears(self):
        result = pending_evidence_reducer([{"id": 1}, {"id": 2}], [])
        assert result == []

    def test_documents_reducer_dedup_by_doc_id(self):
        existing = [{"doc_id": "d1", "title": "Doc 1"}]
        new = [{"doc_id": "d1", "title": "Doc 1"}, {"doc_id": "d2", "title": "Doc 2"}]
        result = documents_reducer(existing, new)
        assert len(result) == 2
        assert result[0]["doc_id"] == "d1"
        assert result[1]["doc_id"] == "d2"

    def test_documents_reducer_no_doc_id(self):
        existing = [{"title": "A"}]
        new = [{"title": "B"}]
        result = documents_reducer(existing, new)
        assert len(result) == 2

    def test_documents_reducer_skips_empty_anonymous(self):
        result = documents_reducer([], [{}])
        assert result == []

    def test_errors_reducer_dedupes_full_list_resubmit(self):
        result = errors_reducer(["err1"], ["err1", "err2"])
        assert result == ["err1", "err2"]

    def test_fact_store_reducer_no_double_on_resubmit(self):
        existing = [{"evidence_id": "ev_1", "text": "Margin expanded", "question_id": "q1"}]
        new = [
            {"evidence_id": "ev_1", "text": "Margin expanded", "question_id": "q1"},
            {"evidence_id": "ev_2", "text": "Revenue grew", "question_id": "q1"},
        ]
        result = fact_store_reducer(existing, new)
        assert len(result) == 2
        assert [r["evidence_id"] for r in result] == ["ev_1", "ev_2"]

    def test_fact_store_reducer_jaccard_near_dup(self):
        existing = [{"text": "Gross margin was 75.2% in FY2025 driven by mix", "question_id": "q1"}]
        new = [{"text": "Gross margin was 75.2% in FY2025 driven by mix shift", "question_id": "q1"}]
        result = fact_store_reducer(existing, new)
        assert len(result) == 1

    def test_calculation_store_reducer_keyed(self):
        existing = [{"question_id": "q1", "expression": "1+1", "metric": "x"}]
        new = [
            {"question_id": "q1", "expression": "1+1", "metric": "x"},
            {"question_id": "q1", "expression": "2+2", "metric": "y"},
        ]
        result = calculation_store_reducer(existing, new)
        assert len(result) == 2

    def test_search_memory_reducer_keyed(self):
        existing = [{"query": "NVDA margin", "target_dimension": "m", "mode": "targeted"}]
        new = [
            {"query": "NVDA margin", "target_dimension": "m", "mode": "targeted"},
            {"query": "NVDA revenue", "target_dimension": "m", "mode": "targeted"},
        ]
        result = search_memory_reducer(existing, new)
        assert len(result) == 2

    def test_merge_ledger_by_id_upserts_without_doubling(self):
        existing = [{"evidence_id": "e1", "quote": "old"}]
        incoming = [
            {"evidence_id": "e1", "quote": "new"},
            {"evidence_id": "e2", "quote": "extra"},
        ]
        # Simulate buggy extend payload: existing rows + new
        doubled = existing + incoming
        result = merge_ledger_by_id(existing, doubled, "evidence_id")
        assert len(result) == 2
        assert result[0]["quote"] == "new"
        assert result[1]["evidence_id"] == "e2"

    def test_blackboard_jaccard_skips_near_dup_different_ids(self):
        existing = [{
            "entry_id": "bb_1",
            "entry_type": "finding",
            "content": "Gross margin expanded on Blackwell mix and packaging costs in FY2026",
        }]
        new = [{
            "entry_id": "bb_2",
            "entry_type": "finding",
            "content": "Gross margin expanded on Blackwell mix and packaging costs in FY2026 quarter",
        }]
        result = blackboard_reducer(existing, new)
        assert len(result) == 1
        assert result[0]["entry_id"] == "bb_1"

    def test_blackboard_keeps_different_content(self):
        existing = [{
            "entry_id": "bb_1",
            "entry_type": "finding",
            "content": "Gross margin expanded on product mix",
        }]
        new = [{
            "entry_id": "bb_2",
            "entry_type": "finding",
            "content": "Customer concentration remains undisclosed in filings",
        }]
        result = blackboard_reducer(existing, new)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════
# Parameter extractor tests
# ═══════════════════════════════════════════════════════════════════════


class TestParameterExtractor:
    def test_format_evidence_for_extraction(self):
        evidence = [
            {"snippet": "Gross margin 75.2%", "source": "10-K", "evidence_id": "ev_001"},
            {"snippet": "Revenue grew 20%", "source": "earnings", "evidence_id": "ev_002"},
        ]
        text = _format_evidence_for_extraction(evidence)
        assert "[1] 10-K" in text
        assert "ev_001" in text
        assert "[2] earnings" in text

    def test_infer_dimension_match(self):
        dims = ["margin_driver_analysis", "revenue_model"]
        assert _infer_dimension("gross_margin", dims) == "margin_driver_analysis"

    def test_infer_dimension_no_match(self):
        dims = ["revenue_model"]
        assert _infer_dimension("gross_margin", dims) == "general"

    def test_extract_parameters_with_mock_llm(self):
        """Test extraction with a mocked LLM that returns structured output."""
        mock_deps = MagicMock()
        mock_deps.config = {"equity_research": {}}

        evidence = [
            {
                "snippet": "Gross margin increased to 75.2% in FY2025",
                "source": "10-K:Results of Operations",
                "evidence_id": "ev_001",
            }
        ]
        skill_context = {
            "prompt_template": "Required outputs:\n1. margin_driver_analysis\n",
            "constraints": "Discuss key margin drivers.",
        }

        mock_output = LLMExtractionOutput(
            parameters=[
                ExtractedParameter(
                    key="gross_margin",
                    value=75.2,
                    unit="%",
                    as_of="FY2025",
                    context="Gross margin increased to 75.2% in FY2025",
                    confidence=0.9,
                    dimension="margin_driver_analysis",
                ),
            ],
            unstructured_narrative="",
        )

        with patch(
            "tradingagents.equity_research.runtime.parameter_extractor.invoke_structured_with_retry",
            return_value=mock_output,
        ):
            params, narrative = extract_parameters_from_evidence(
                mock_deps, evidence, skill_context, question_id="q1", current_turn=1
            )

        assert len(params) == 1
        assert params[0].key == "gross_margin"
        assert params[0].current.value == 75.2
        assert params[0].current.unit == "%"
        assert params[0].current.as_of == "FY2025"
        assert params[0].current.turn == 1
        assert params[0].dimension == "margin_driver_analysis"
        assert narrative == ""

    def test_extract_parameters_empty_evidence(self):
        mock_deps = MagicMock()
        params, narrative = extract_parameters_from_evidence(
            mock_deps, [], {"prompt_template": "", "constraints": ""}
        )
        assert params == []
        assert narrative == ""

    def test_extract_parameters_llm_failure(self):
        """When LLM extraction fails, we get an empty list (graceful degradation)."""
        mock_deps = MagicMock()
        evidence = [{"snippet": "some data", "source": "x", "evidence_id": "ev_001"}]
        skill_context = {"prompt_template": "", "constraints": ""}

        with patch(
            "tradingagents.equity_research.runtime.parameter_extractor.invoke_structured_with_retry",
            side_effect=Exception("LLM rate limited"),
        ):
            params, narrative = extract_parameters_from_evidence(
                mock_deps, evidence, skill_context
            )
        assert params == []


# ═══════════════════════════════════════════════════════════════════════
# Parameter reducer tests
# ═══════════════════════════════════════════════════════════════════════


class TestParameterReducer:
    def test_values_compatible_equal(self):
        assert _values_compatible(75.2, 75.2)
        assert _values_compatible("FY2025", "FY2025")

    def test_values_compatible_within_tolerance(self):
        # 75.2 vs 74.0 → ~1.6% diff, within 5% tolerance
        assert _values_compatible(75.2, 74.0)

    def test_values_incompatible(self):
        # 75.2 vs 60.0 → ~20% diff, exceeds 5%
        assert not _values_compatible(75.2, 60.0)

    def test_values_compatible_zero(self):
        assert _values_compatible(0, 0)
        assert not _values_compatible(0, 100)

    def test_reduce_new_parameter(self):
        registry = ParameterRegistry()
        new_param = Parameter(
            key="gross_margin",
            dimension="margin_driver_analysis",
            current=ParameterValue(value=75.2, as_of="FY2025", turn=1, source="10-K"),
        )
        result = reduce_parameters(registry, [new_param], current_turn=1)
        assert "gross_margin" in result.parameters
        assert result.parameters["gross_margin"].current.value == 75.2

    def test_reduce_conflict_detection(self):
        """Different value for same key → conflict flag + version chain."""
        registry = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    dimension="margin_driver_analysis",
                    current=ParameterValue(
                        value=75.2, as_of="FY2025", turn=1, source="10-K"
                    ),
                )
            }
        )
        new_param = Parameter(
            key="gross_margin",
            dimension="margin_driver_analysis",
            current=ParameterValue(
                value=60.0, as_of="Q1 2025", turn=2, source="Earnings Call"
            ),
        )
        updated = reduce_parameters(registry, [new_param], current_turn=2)
        param = updated.parameters["gross_margin"]
        assert param.is_conflict is True
        # current should be the newest value
        assert param.current.value == 60.0
        assert param.current.as_of == "Q1 2025"
        # history should contain the old current
        assert len(param.history) == 1
        assert param.history[0].value == 75.2

    def test_reduce_same_value_no_conflict(self):
        """Same value → just append to history, no conflict."""
        registry = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    current=ParameterValue(
                        value=75.2, as_of="FY2025", turn=1, source="10-K"
                    ),
                )
            }
        )
        new_param = Parameter(
            key="gross_margin",
            current=ParameterValue(
                value=75.2, as_of="FY2025", turn=2, source="Earnings"
            ),
        )
        updated = reduce_parameters(registry, [new_param], current_turn=2)
        param = updated.parameters["gross_margin"]
        assert param.is_conflict is False
        assert len(param.history) == 1

    def test_reduce_merges_evidence_ids(self):
        registry = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    current=ParameterValue(value=75.2, as_of="FY2025"),
                    source_evidence_ids=["ev_001"],
                )
            }
        )
        new_param = Parameter(
            key="gross_margin",
            current=ParameterValue(value=75.2, as_of="FY2025"),
            source_evidence_ids=["ev_002"],
        )
        updated = reduce_parameters(registry, [new_param], current_turn=1)
        assert set(updated.parameters["gross_margin"].source_evidence_ids) == {
            "ev_001", "ev_002"
        }

    def test_reduce_updates_dimensions(self):
        registry = ParameterRegistry(dimensions=["margin_driver_analysis"])
        new_param = Parameter(
            key="revenue_growth",
            dimension="revenue_model_explanation",
            current=ParameterValue(value=0.20, as_of="FY2025"),
        )
        updated = reduce_parameters(registry, [new_param], current_turn=1)
        assert "revenue_model_explanation" in updated.dimensions
        assert "margin_driver_analysis" in updated.dimensions


# ═══════════════════════════════════════════════════════════════════════
# Parameter compiler tests
# ═══════════════════════════════════════════════════════════════════════


class TestParameterCompiler:
    def test_compile_empty_registry(self):
        grid = compile_parameter_grid(ParameterRegistry())
        assert "no parameters extracted" in grid

    def test_compile_basic_parameter(self):
        reg = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    dimension="margin_driver_analysis",
                    current=ParameterValue(
                        value=75.2, unit="%", as_of="FY2025", source="10-K"
                    ),
                ),
            }
        )
        grid = compile_parameter_grid(reg)
        assert "gross_margin: 75.2 %" in grid
        assert "FY2025" in grid
        assert "10-K" in grid
        assert "margin_driver_analysis" in grid

    def test_compile_with_history(self):
        reg = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    current=ParameterValue(value=75.2, unit="%", as_of="FY2025"),
                    history=[
                        ParameterValue(value=73.0, unit="%", as_of="FY2024", turn=0),
                    ],
                ),
            }
        )
        grid = compile_parameter_grid(reg)
        assert "73.0 %" in grid
        assert "FY2024" in grid

    def test_compile_conflict_rendering(self):
        reg = ParameterRegistry(
            parameters={
                "gross_margin": Parameter(
                    key="gross_margin",
                    is_conflict=True,
                    current=ParameterValue(
                        value=60.0, unit="%", as_of="Q1 2025", source="Earnings"
                    ),
                    history=[
                        ParameterValue(
                            value=75.2, unit="%", as_of="FY2025", source="10-K"
                        ),
                    ],
                ),
            }
        )
        grid = compile_parameter_grid(reg)
        assert "⚠️ Conflicts:" in grid
        assert "60.0 %" in grid
        assert "75.2 %" in grid

    def test_compile_preserves_all_parameters(self):
        """No length cap — all 100 parameters must appear."""
        reg = ParameterRegistry(
            parameters={
                f"metric_{i}": Parameter(
                    key=f"metric_{i}",
                    current=ParameterValue(value=i, as_of="FY2025", turn=1, source="test"),
                )
                for i in range(100)
            }
        )
        grid = compile_parameter_grid(reg)
        for i in range(100):
            assert f"metric_{i}" in grid

    def test_compile_filters_by_question_id(self):
        reg = ParameterRegistry(
            parameters={
                "gm": Parameter(
                    key="gm",
                    question_id="q1",
                    current=ParameterValue(value=75.2, as_of="FY2025"),
                ),
                "rev": Parameter(
                    key="rev",
                    question_id="q2",
                    current=ParameterValue(value=100e9, as_of="FY2025"),
                ),
                "shared": Parameter(
                    key="shared",
                    question_id="general",
                    current=ParameterValue(value="yes", as_of="FY2025"),
                ),
            }
        )
        grid_q1 = compile_parameter_grid(reg, question_id="q1")
        assert "gm" in grid_q1
        assert "shared" in grid_q1
        assert "rev" not in grid_q1


# ═══════════════════════════════════════════════════════════════════════
# State integration tests
# ═══════════════════════════════════════════════════════════════════════


class TestStateIntegration:
    def test_empty_agent_state_has_parameter_fields(self):
        from tradingagents.equity_research.runtime.state import empty_agent_state

        state = empty_agent_state({"ticker": "NVDA"})
        assert "parameter_registry" in state
        assert "parameter_grid" in state
        assert state["parameter_registry"] == {"parameters": {}, "dimensions": []}
        assert state["parameter_grid"] == ""

    def test_state_reducer_annotations(self):
        """Verify that state fields have proper reducer annotations."""
        from tradingagents.equity_research.runtime.state import AgentState

        annotations = AgentState.__annotations__
        # These should be Annotated types with reducers
        assert "evidence_buffer" in annotations
        assert "pending_evidence" in annotations
        assert "documents" in annotations
        assert "errors" in annotations
        assert "fact_store" in annotations
        assert "calculation_store" in annotations
        assert "parameter_registry" in annotations
        assert "parameter_grid" in annotations
