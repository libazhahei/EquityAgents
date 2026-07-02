"""Tests for demo_section_research JSON loaders."""

import json
from pathlib import Path

from demo_section_research import _load_background_json, _load_planner_json


def test_load_background_json_structured_view(tmp_path: Path):
    path = tmp_path / "nvda5.json"
    path.write_text(json.dumps({
        "structured_view": {"ticker": "NVDA", "coverage_score": 0.8},
        "assumption_view": {"ticker": "NVDA", "assumption_map": []},
        "final_report": "consensus report text",
        "assumption_report": "assumption report text",
    }), encoding="utf-8")
    bg = _load_background_json(path)
    assert bg["consensus_view"]["ticker"] == "NVDA"
    assert bg["assumption_view"]["ticker"] == "NVDA"
    assert "consensus_report" not in bg
    assert bg["assumption_report"] == "assumption report text"
    assert bg["ticker"] == "NVDA"


def test_load_planner_json(tmp_path: Path):
    path = tmp_path / "planner.json"
    path.write_text(json.dumps({
        "ticker": "NVDA",
        "section_plans": {"3_business_model": {"root_question": "how?"}},
    }), encoding="utf-8")
    data = _load_planner_json(path)
    assert "3_business_model" in data["section_plans"]
    assert data["ticker"] == "NVDA"
