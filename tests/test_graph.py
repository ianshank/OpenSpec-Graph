"""Tests for the graph export (change package: add-graph-export).

Each test maps to an acceptance criterion in
openspec/changes/add-graph-export/specs/graph-export/spec.md. The graph is a
pure projection of `validate`, so several tests assert agreement between the two.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from openspec_graph import detect, graph as graph_module, rules, scaffold
from openspec_graph.cli import main
from openspec_graph.parse import parse_spec

MAKEFILE = textwrap.dedent(
    """\
    .PHONY: help test ci
    help:
    \t@echo hi
    test:
    \tpytest
    ci: test
    \t@echo ok
    """
)
PYPROJECT = textwrap.dedent(
    """\
    [project]
    name = "demo"

    [tool.coverage.report]
    fail_under = 90
    """
)
CONTRACT = "# Contract\n\n- INV-1 no unattested writes\n"

GOOD_HARNESS = textwrap.dedent(
    """\
    # Spec: Demo Capability

    > **Status:** DRAFT

    ## Problem Statement

    **Evidence:** `demo/mod.py::run` writes without attestation.

    ## Requirements

    - R-DMO-1: The system MUST attest every write.
    - C-DMO-1: The change MUST NOT weaken INV-1.

    ## Acceptance Criteria

    - [ ] **AC-DMO-1:** An attested write records an evidence id. (R-DMO-1)
      _Verified by:_ `pytest -k test_attested_write` · stage: `make test`

    - [ ] **AC-DMO-2 (non-success):** An unattested write is denied and the
      error names INV-1. (C-DMO-1)
      _Verified by:_ `pytest -k test_unattested_denied` · stage: `make test`

    ## Invariants Touched

    - INV-1: preserved, proven by AC-DMO-2.

    ## Validation Matrix

    | Stage | Make Target | Pass Criteria |
    |---|---|---|
    | Focused | `make test` | AC-DMO-1..2 |
    """
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(MAKEFILE)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "CONTRACT.md").write_text(CONTRACT)
    return tmp_path


def write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def graph_for(repo: Path, body: str) -> dict:
    write_spec(repo, "demo-change", "demo-capability", body)
    return graph_module.build_graph(detect.profile(repo))


# --- AC-GR-1: emits nodes and edges covering every parsed spec --------------


def test_graph_emits_nodes_and_edges(repo: Path) -> None:
    graph = graph_for(repo, GOOD_HARNESS)
    assert "nodes" in graph and "edges" in graph
    types = {n["type"] for n in graph["nodes"]}
    assert {"spec", "requirement", "criterion", "stage"} <= types
    # the stage cited by the AC (make test) appears as a node
    assert any(n["id"] == "stage:test" and n["exists"] for n in graph["nodes"])
    # a traces-to edge links the criterion to its requirement
    assert any(
        e["type"] == "traces-to" and e["source"] == "AC-DMO-1" and e["target"] == "R-DMO-1"
        for e in graph["edges"]
    )
    assert graph["specs"] == 1


def test_graph_covers_every_parsed_spec_when_multiple(repo: Path) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2"))
    graph = graph_module.build_graph(detect.profile(repo))
    assert graph["specs"] == 2
    assert sum(1 for n in graph["nodes"] if n["type"] == "spec") == 2


# --- AC-GR-2: no openspec/ tree -> non-zero exit, names missing directory ----


def test_graph_rejects_missing_tree(repo: Path, capsys) -> None:
    # repo has Makefile + pyproject but no openspec/
    exit_code = main(["--target", str(repo), "graph"])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "openspec/" in err
    assert "missing" not in err.lower() or "no openspec/" in err.lower()


def test_build_graph_raises_for_missing_tree(repo: Path) -> None:
    prof = detect.profile(repo)
    with pytest.raises(graph_module.NoOpenSpecTreeError) as exc:
        graph_module.build_graph(prof)
    assert "openspec/" in str(exc.value)


# --- AC-GR-3: orphan requirement -> node with no incoming traces-to edge -----


def test_graph_surfaces_orphan_requirement(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "- C-DMO-1: The change MUST NOT weaken INV-1.",
        "- C-DMO-1: The change MUST NOT weaken INV-1.\n- R-DMO-9: MUST do an untested thing.",
    )
    graph = graph_for(repo, body)
    orphan_nodes = [n for n in graph["nodes"] if n.get("orphan")]
    assert any(n["id"] == "R-DMO-9" for n in orphan_nodes)
    # no incoming traces-to edge targets the orphan
    incoming = {e["target"] for e in graph["edges"] if e["type"] == "traces-to"}
    assert "R-DMO-9" not in incoming


def test_non_orphan_requirement_is_not_marked(repo: Path) -> None:
    graph = graph_for(repo, GOOD_HARNESS)
    assert not any(n.get("orphan") and n["id"] == "R-DMO-1" for n in graph["nodes"])


# --- AC-GR-4: graph broken_links == validate finding count ------------------


def test_graph_matches_validate_findings(repo: Path) -> None:
    # a spec with real violations: unknown make target + no non-success path
    body = GOOD_HARNESS.replace("make test", "make nope").replace(
        "**AC-DMO-2 (non-success):** An unattested write is denied and the\n      error names INV-1.",
        "**AC-DMO-2:** A second attested write also records an id.",
    )
    write_spec(repo, "bad", "bad-cap", body)
    prof = detect.profile(repo)

    validate_findings = 0
    for path in detect.find_spec_files(prof.openspec_root):
        validate_findings += len(rules.evaluate(parse_spec(path, "auto"), prof))

    graph = graph_module.build_graph(prof)
    assert graph["broken_links"] == validate_findings
    # and the broken-link count is non-zero (the violations are real)
    assert graph["broken_links"] > 0


def test_graph_matches_validate_findings_on_clean_spec(repo: Path) -> None:
    graph = graph_for(repo, GOOD_HARNESS)
    assert graph["broken_links"] == 0


# --- AC-GR-5: unknown make stage -> edge to a stage node not in make_targets -


def test_graph_surfaces_unknown_stage(repo: Path) -> None:
    body = GOOD_HARNESS.replace("make test", "make nope")
    graph = graph_for(repo, body)
    nope_edges = [
        e for e in graph["edges"]
        if e["type"] == "verified-by" and e["target"] == "stage:nope"
    ]
    assert nope_edges, "an unknown stage must appear as a verified-by edge"
    assert all(e["exists"] is False for e in nope_edges)
    assert any(n["id"] == "stage:nope" and n["exists"] is False for n in graph["nodes"])


# --- AC-GR-6: --format dot rejected, non-zero exit, names rendering ----------


def test_graph_rejects_dot_format(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--format", "dot"])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "dot" in err
    assert "downstream" in err or "out-of-scope" in err


def test_graph_accepts_json_format_explicitly(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "nodes" in payload and "edges" in payload


# --- CLI branch coverage (closes the gap that kept total below 90%) -----------


def test_cli_detect_human_readable(repo: Path, capsys) -> None:
    assert main(["--target", str(repo), "detect"]) == 0
    out = capsys.readouterr().out
    assert "languages" in out and "make targets" in out


def test_cli_init_writes_config_and_project(repo: Path) -> None:
    assert main(["--target", str(repo), "init"]) == 0
    assert (repo / "openspec" / "specgraph.json").exists()
    assert (repo / "openspec" / "project.md").exists()


def test_cli_init_force_overwrites(repo: Path) -> None:
    main(["--target", str(repo), "init"])
    cfg = repo / "openspec" / "specgraph.json"
    cfg.write_text("{\"stale\": true}")
    assert main(["--target", str(repo), "init", "--force"]) == 0
    import json as _json
    data = _json.loads(cfg.read_text())
    assert "dialect" in data and "stale" not in data


def test_cli_new_creates_files(repo: Path) -> None:
    assert main(["--target", str(repo), "new", "add-x", "--capability", "x-cap"]) == 0
    assert (repo / "openspec" / "changes" / "add-x" / "proposal.md").exists()
    assert (repo / "openspec" / "changes" / "add-x" / "specs" / "x-cap" / "spec.md").exists()


def test_cli_validate_json_output(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    assert main(["--target", str(repo), "validate", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["specs_checked"] == 1
    assert payload["blocking"] == 0


def test_cli_validate_single_change(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2"))
    assert main(["--target", str(repo), "validate", "--change", "c1"]) == 0
    out = capsys.readouterr().out
    assert "1 spec(s)" in out


def test_cli_validate_change_not_found(repo: Path) -> None:
    assert main(["--target", str(repo), "validate", "--change", "nope"]) == 2


def test_cli_validate_no_openspec_dir(repo: Path, capsys) -> None:
    # repo has no openspec/ yet
    assert main(["--target", str(repo), "validate"]) == 2


def test_cli_rules_human_readable(repo: Path, capsys) -> None:
    assert main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "G001" in out and "SEV" in out


def test_cli_rules_json(repo: Path, capsys) -> None:
    assert main(["rules", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(row["id"] == "G002" for row in payload)


def test_cli_target_not_a_directory(tmp_path, capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--target", str(tmp_path / "does-not-exist"), "detect"])


# --- AC-GR-7: coverage floor met under `make ci` -----------------------------
# AC-GR-7 is the coverage gate, verified by `make ci` running the test_graph
# selector under fail_under=90. It is not a unit test: asserting it here would
# require invoking pytest on this file, which re-runs this test and recurses.
# The gate is exercised directly in the implementation step (`make ci`).
