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

from openspec_graph import detect, rules
from openspec_graph import graph as graph_module
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


def test_graph_matches_validate_findings_with_an_orphan_invariant(repo: Path) -> None:
    # A second declared invariant no spec cites -- forces a real G006
    # (tree-level) finding, proving AC-GR-4 still holds once evaluate_tree()
    # findings, not just evaluate()'s, are counted into broken_links.
    (repo / "CONTRACT.md").write_text("# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n")
    write_spec(repo, "demo-change", "demo-cap", GOOD_HARNESS)
    prof = detect.profile(repo)

    specs = [parse_spec(p, "auto") for p in detect.find_spec_files(prof.openspec_root)]
    tree_findings = rules.evaluate_tree(specs, prof)
    assert any(f.rule == "G006" for f in tree_findings), "fixture must produce a real orphan"
    validate_findings = sum(len(rules.evaluate(s, prof)) for s in specs) + len(tree_findings)

    graph = graph_module.build_graph(prof)
    assert graph["broken_links"] == validate_findings


def test_graph_marks_an_orphan_invariant_node(repo: Path) -> None:
    (repo / "CONTRACT.md").write_text("# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n")
    graph = graph_for(repo, GOOD_HARNESS)
    inv2_nodes = [n for n in graph["nodes"] if n["id"] == "invariant:INV-2"]
    assert inv2_nodes, "an orphan invariant must still get a graph node"
    assert inv2_nodes[0]["type"] == "invariant"
    assert inv2_nodes[0]["orphan"] is True
    assert any(
        e["source"] == "invariant:INV-2" and e["type"] == "finding" and e["target"] == "G006"
        for e in graph["edges"]
    )


def test_graph_matches_validate_findings_with_an_orphan_adr(repo: Path) -> None:
    # A second declared ADR no spec cites -- forces a real G009 (tree-level)
    # finding, proving AC-GR-4 still holds once evaluate_tree() findings
    # include G009 alongside G006.
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-use-postgres.md").write_text("# ADR-1: Use Postgres\n")
    (repo / "docs" / "adr" / "0002-use-rest.md").write_text("# ADR-2: Use REST\n")
    body = GOOD_HARNESS.replace(
        "**Evidence:** `demo/mod.py::run` writes without attestation.",
        "**Evidence:** `demo/mod.py::run` writes without attestation. See ADR-1.",
    )
    write_spec(repo, "demo-change", "demo-cap", body)
    prof = detect.profile(repo)

    specs = [parse_spec(p, "auto") for p in detect.find_spec_files(prof.openspec_root)]
    tree_findings = rules.evaluate_tree(specs, prof)
    assert any(f.rule == "G009" for f in tree_findings), "fixture must produce a real orphan"
    validate_findings = sum(len(rules.evaluate(s, prof)) for s in specs) + len(tree_findings)

    graph = graph_module.build_graph(prof)
    assert graph["broken_links"] == validate_findings


def test_graph_marks_an_orphan_adr_node(repo: Path) -> None:
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-use-postgres.md").write_text("# ADR-1: Use Postgres\n")
    (repo / "docs" / "adr" / "0002-use-rest.md").write_text("# ADR-2: Use REST\n")
    body = GOOD_HARNESS.replace(
        "**Evidence:** `demo/mod.py::run` writes without attestation.",
        "**Evidence:** `demo/mod.py::run` writes without attestation. See ADR-1.",
    )
    graph = graph_for(repo, body)
    adr2_nodes = [n for n in graph["nodes"] if n["id"] == "adr:ADR-2"]
    assert adr2_nodes, "an orphan ADR must still get a graph node"
    assert adr2_nodes[0]["type"] == "adr"
    assert adr2_nodes[0]["orphan"] is True
    assert any(
        e["source"] == "adr:ADR-2" and e["type"] == "finding" and e["target"] == "G009"
        for e in graph["edges"]
    )


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


# --- AC-GV: --format mermaid + --change scoping (change package: add-mermaid-graph-export) --


def test_graph_format_mermaid_emits_a_flowchart(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--format", "mermaid"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart LR")
    assert "-->|" in out


def test_graph_dot_is_still_rejected_after_mermaid_ships(repo: Path, capsys) -> None:
    # AC-GV-4: adding --format mermaid does not revise AC-GR-6 -- dot stays
    # rejected with the exact same message and exit code.
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--format", "dot"])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "error: --format dot is not supported; graph rendering is a " "downstream, out-of-scope concern. Use --format json." in err


def test_graph_change_scopes_which_specs_are_rendered(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2"))
    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["specs"] == 1
    spec_nodes = [n for n in payload["nodes"] if n["type"] == "spec"]
    assert len(spec_nodes) == 1
    assert "c1" in spec_nodes[0]["path"]


def test_graph_change_scoping_applies_identically_under_format_mermaid(repo: Path, capsys) -> None:
    # Every other --change test in this file uses --format json; the only
    # --format mermaid test has no --change -- this exact composition was
    # previously untested.
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2"))
    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "mermaid"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart LR")
    assert "cap1" in out
    assert "cap2" not in out


def test_graph_change_prints_a_g006_unscoped_heads_up(repo: Path, capsys) -> None:
    # Unlike `validate --change` (which skips G006 with its own INFO note),
    # `graph --change` always includes G006 findings unscoped (DEC-GV-002) --
    # flagged with its own heads-up so a nonzero broken_links count doesn't
    # read as a problem specific to the rendered change (post-implementation
    # adversarial review finding).
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "INFO  G006 included unscoped" in err


def test_graph_change_prints_a_g009_unscoped_heads_up(repo: Path, capsys) -> None:
    # Same story as G006's own heads-up, for the ADR orphan check (DEC-AD-004).
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "INFO  G009 included unscoped" in err


def test_graph_change_does_not_falsely_orphan_an_adr_cited_outside_the_scope(
    repo: Path, capsys
) -> None:
    # Mirrors the identical guard for invariants: naively scoping
    # evaluate_tree()'s input to the rendered --change would make an ADR
    # cited only by an unrendered change look orphaned. It must not.
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-use-postgres.md").write_text("# ADR-1: Use Postgres\n")
    (repo / "docs" / "adr" / "0002-use-rest.md").write_text("# ADR-2: Use REST\n")
    body_c1 = GOOD_HARNESS.replace(
        "**Evidence:** `demo/mod.py::run` writes without attestation.",
        "**Evidence:** `demo/mod.py::run` writes without attestation. See ADR-1.",
    )  # cites ADR-1 only
    body_c2 = (
        GOOD_HARNESS.replace("AC-DMO", "AC-DM2")
        .replace("R-DMO", "R-DM2")
        .replace(
            "**Evidence:** `demo/mod.py::run` writes without attestation.",
            "**Evidence:** `demo/mod.py::run` writes without attestation. See ADR-2.",
        )
    )  # cites ADR-2 only
    write_spec(repo, "c1", "cap1", body_c1)
    write_spec(repo, "c2", "cap2", body_c2)

    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    orphan_nodes = [n for n in payload["nodes"] if n.get("type") == "adr" and n.get("orphan")]
    assert not any(n["name"] == "ADR-2" for n in orphan_nodes), (
        "ADR-2 is genuinely cited by c2 -- rendering only c1 must not make it look orphaned"
    )


def test_graph_change_still_surfaces_a_genuinely_orphaned_adr(repo: Path, capsys) -> None:
    # The other half of the same fix: evaluate_tree() must still RUN (and
    # its results still surface) under --change, just always unscoped --
    # scoping must not silently suppress a real orphan either.
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-use-postgres.md").write_text("# ADR-1: Use Postgres\n")
    (repo / "docs" / "adr" / "0002-use-rest.md").write_text("# ADR-2: Use REST\n")
    body_c1 = GOOD_HARNESS.replace(
        "**Evidence:** `demo/mod.py::run` writes without attestation.",
        "**Evidence:** `demo/mod.py::run` writes without attestation. See ADR-1.",
    )  # cites ADR-1 only; ADR-2 is cited by nothing anywhere
    write_spec(repo, "c1", "cap1", body_c1)

    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    orphan_nodes = [n for n in payload["nodes"] if n.get("type") == "adr" and n.get("orphan")]
    assert any(n["name"] == "ADR-2" for n in orphan_nodes)
    assert payload["broken_links"] > 0


def test_graph_change_does_not_falsely_orphan_an_invariant_cited_outside_the_scope(
    repo: Path, capsys
) -> None:
    # The bug an adversarial review caught: naively scoping evaluate_tree()'s
    # input to the rendered --change would make an invariant cited only by
    # an unrendered change look orphaned. It must not.
    (repo / "CONTRACT.md").write_text("# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n")
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)  # cites INV-1 only
    other = GOOD_HARNESS.replace("INV-1", "INV-2").replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2")
    write_spec(repo, "c2", "cap2", other)  # cites INV-2 only

    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    orphan_nodes = [n for n in payload["nodes"] if n.get("type") == "invariant" and n.get("orphan")]
    assert not any(n["name"] == "INV-2" for n in orphan_nodes), (
        "INV-2 is genuinely cited by c2 -- rendering only c1 must not make it look orphaned"
    )


def test_graph_change_still_surfaces_a_genuinely_orphaned_invariant(repo: Path, capsys) -> None:
    # The other half of the same fix: evaluate_tree() must still RUN (and
    # its results still surface) under --change, just always unscoped --
    # scoping must not silently suppress a real orphan either.
    (repo / "CONTRACT.md").write_text("# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n")
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)  # cites INV-1 only; INV-2 is cited by nothing anywhere

    exit_code = main(["--target", str(repo), "graph", "--change", "c1", "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    orphan_nodes = [n for n in payload["nodes"] if n.get("type") == "invariant" and n.get("orphan")]
    assert any(n["name"] == "INV-2" for n in orphan_nodes)
    assert payload["broken_links"] > 0


def test_graph_change_not_found(repo: Path, capsys) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    exit_code = main(["--target", str(repo), "graph", "--change", "nope"])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "no specs found for change" in err


def test_graph_change_with_no_openspec_dir(repo: Path, capsys) -> None:
    # repo has no openspec/ yet
    exit_code = main(["--target", str(repo), "graph", "--change", "c1"])
    assert exit_code == 2
    assert "no openspec/ directory" in capsys.readouterr().err


def test_graph_format_mermaid_on_a_freshly_initialized_repo_with_no_changes(tmp_path: Path, capsys) -> None:
    # Agent-review-flagged gap: no CLI-level test exercised `graph` against a
    # real, valid openspec/ tree with zero change packages -- the reachable
    # state right after `planlint init`, before the first `planlint new`.
    (tmp_path / "Makefile").write_text(MAKEFILE)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    assert main(["--target", str(tmp_path), "init"]) == 0
    capsys.readouterr()  # discard init's own stdout
    exit_code = main(["--target", str(tmp_path), "graph", "--format", "mermaid"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart LR")
    assert "n0" not in out
    assert "-->|" not in out


def test_filter_by_change_is_a_pure_path_filter() -> None:
    paths = [
        Path("openspec/changes/c1/specs/cap/spec.md"),
        Path("openspec/changes/c2/specs/cap/spec.md"),
    ]
    assert detect.filter_by_change(paths, "c1") == [paths[0]]
    assert detect.filter_by_change(paths, "nope") == []


def test_filter_by_change_is_precise_against_a_change_name_that_collides_with_another_path_segment() -> None:
    # A change literally named "specs" must not match every entry just
    # because "specs" is also a fixed path segment of the convention itself
    # (openspec/changes/<name>/specs/<cap>/spec.md) -- a substring check
    # (f"/changes/{change}/" in str(p)) would get this wrong; matching by
    # structural position (Path.parts, the segment right after "changes")
    # does not.
    paths = [
        Path("openspec/changes/specs/specs/cap/spec.md"),  # a change genuinely named "specs"
        Path("openspec/changes/c1/specs/cap/spec.md"),
    ]
    assert detect.filter_by_change(paths, "specs") == [paths[0]]


def test_filter_by_change_is_precise_against_a_change_literally_named_changes() -> None:
    # The symmetric case: a change literally named "changes" must not make
    # its own name segment read as a second, bogus "changes" marker whose
    # following (fixed) "specs" segment then spuriously satisfies a query
    # for an unrelated change also named "specs" -- the exact bug a forward
    # scan for the first/any "changes" occurrence (rather than the fixed
    # structural position) reintroduced one level down from the fix above.
    paths = [
        Path("openspec/changes/changes/specs/cap/spec.md"),  # a change genuinely named "changes"
        Path("openspec/changes/specs/specs/cap/spec.md"),  # a change genuinely named "specs"
    ]
    assert detect.filter_by_change(paths, "specs") == [paths[1]]
    assert detect.filter_by_change(paths, "changes") == [paths[0]]


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


def test_cli_validate_change_not_found(repo: Path, capsys) -> None:
    # A real openspec/ tree with an unrelated change must reach cli.py's
    # "no specs found for change" guard (:117-119), not the earlier "no
    # openspec/ directory" guard (:110-112) -- both exit 2, so without a
    # real change present this test would pass for the wrong reason.
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    assert main(["--target", str(repo), "validate", "--change", "nope"]) == 2
    err = capsys.readouterr().err
    assert "no specs found for change" in err
    assert "no openspec/ directory" not in err


def test_cli_validate_no_openspec_dir(repo: Path, capsys) -> None:
    # repo has no openspec/ yet
    assert main(["--target", str(repo), "validate"]) == 2
    assert "no openspec/ directory" in capsys.readouterr().err


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


# --- AC-WM-21: witnesses (CP-WM) get no graph representation, ever ----------


def test_graph_never_includes_w001_or_w002_findings_even_with_a_stale_witness_present(
    repo: Path,
) -> None:
    # A repo with zero recorded witnesses would fire W001 for every cited
    # stage under --require-witness -- graph must never reflect that under
    # any flag, since it has no --require-witness of its own (DEC-WM-013).
    path = write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    prof = detect.profile(repo)
    spec = parse_spec(path, "harness")

    # Prove W001 really would fire here, so this test isn't vacuous.
    assert any(f.rule == "W001" for f in rules.evaluate(spec, prof, rules.RULES))

    non_witness_only = rules.evaluate(spec, prof, rules.NON_WITNESS_RULES)
    graph = graph_module.build_graph(prof)
    assert graph["broken_links"] == len(non_witness_only)
    node_types = {n.get("type") for n in graph.get("nodes", [])}
    assert "witness" not in node_types
