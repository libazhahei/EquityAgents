"""Tests for visualize_equity_research_trace name-based bundle loading."""

from pathlib import Path

from scripts.visualize_equity_research_trace import (
    _strip_name,
    discover_bundle_files,
    load_run_bundle,
    render_html,
)


def test_strip_name_variants():
    assert _strip_name("nvda_equity_e2e") == "nvda_equity_e2e"
    assert _strip_name("nvda_equity_e2e.json") == "nvda_equity_e2e"
    assert _strip_name("nvda_equity_e2e.progress_events.json") == "nvda_equity_e2e"
    assert _strip_name("out/NVDA_equity_x/full_state.json") == "NVDA_equity_x"


def test_discover_stem_bundle(tmp_path: Path):
    stem = "nvda_equity_e2e"
    (tmp_path / f"{stem}.json").write_text('{"ticker":"NVDA","research_traces":[]}', encoding="utf-8")
    (tmp_path / f"{stem}.progress_events.json").write_text("[]", encoding="utf-8")
    (tmp_path / f"{stem}.research_traces.json").write_text("[]", encoding="utf-8")
    (tmp_path / f"{stem}.run_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / f"{stem}.run_tree.json").write_text("[]", encoding="utf-8")

    files = discover_bundle_files(stem, root=tmp_path)
    assert set(files) == {
        "full_state",
        "progress_events",
        "research_traces",
        "run_summary",
        "run_tree",
    }


def test_discover_dir_bundle(tmp_path: Path):
    bundle = tmp_path / "NVDA_equity_run"
    bundle.mkdir()
    (bundle / "full_state.json").write_text('{"ticker":"NVDA"}', encoding="utf-8")
    (bundle / "progress_events.json").write_text('[{"stage":"consensus"}]', encoding="utf-8")
    (bundle / "run_tree.json").write_text("[]", encoding="utf-8")

    files = discover_bundle_files("NVDA_equity_run", root=tmp_path)
    assert files["full_state"] == bundle / "full_state.json"
    assert "progress_events" in files


def test_load_run_bundle_and_render(tmp_path: Path):
    stem = "nvda_equity_e2e"
    (tmp_path / f"{stem}.json").write_text(
        '{"ticker":"NVDA","selected_section_ids":["3_business_model"],'
        '"section_research_outputs":{"3_business_model":{"executive_summary":"biz"}},'
        '"research_traces":[]}',
        encoding="utf-8",
    )
    (tmp_path / f"{stem}.progress_events.json").write_text(
        '[{"stage":"consensus","status":"succeeded","ts":"t"}]',
        encoding="utf-8",
    )
    (tmp_path / f"{stem}.research_traces.json").write_text(
        '[{"node_name":"consensus_planner","payload":{"new_queries":1}}]',
        encoding="utf-8",
    )
    (tmp_path / f"{stem}.run_summary.json").write_text(
        '{"stages_seen":["consensus"]}',
        encoding="utf-8",
    )
    (tmp_path / f"{stem}.run_tree.json").write_text(
        '[{"node_path":"consensus","status":"succeeded"}]',
        encoding="utf-8",
    )

    bundle = load_run_bundle(stem, root=tmp_path)
    assert len(bundle.files) == 5
    assert bundle.progress_events[0]["stage"] == "consensus"
    assert bundle.research_traces[0]["node_name"] == "consensus_planner"

    page = render_html(
        bundle.state,
        progress_events=bundle.progress_events,
        run_tree=bundle.run_tree,
        research_traces=bundle.research_traces,
        run_summary=bundle.run_summary,
        files=bundle.files,
        bundle_name=bundle.name,
    )
    assert "Bundle JSON files" in page
    assert "progress_events" in page
    assert "consensus_planner" in page
    assert "biz" in page
