"""Tests for the CI hardening tooling (change package: harden-ci-gates).

Covers the four implemented behaviors:
- branch-coverage floor (AC-CH-3) via tools/check_branch_coverage.py
- coverage line floor fails below threshold (AC-CH-1, AC-CH-2)
- graph-diff fails on regressions and passes on improvements (AC-CH-5, AC-CH-6)
- rule set matches the committed baseline (AC-CH-8 / C-CH-1: no new rules)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from openspec_graph import detect
from openspec_graph import graph as graph_module
from openspec_graph.rules import RULES, rule_table
from tests.support import write_spec as _write_spec

TOOLS = Path(__file__).resolve().parent.parent / "tools"
REPO_ROOT = Path(__file__).resolve().parent.parent


# --- AC-CH-3: branch-coverage floor ------------------------------------------


def _write_coverage_json(path: Path, branches: int, covered: int) -> Path:
    path.write_text(
        json.dumps({"totals": {"num_branches": branches, "covered_branches": covered}})
    )
    return path


def _write_pyproject(path: Path, floor: int | None) -> Path:
    if floor is None:
        path.write_text("[tool.coverage.report]\nfail_under = 90\n")
    else:
        path.write_text(
            "[tool.coverage.report]\nfail_under = 90\n"
            f"[tool.specgraph]\nbranch_fail_under = {floor}\n"
        )
    return path


def test_branch_check_fails_below_floor(tmp_path: Path, capsys) -> None:
    _write_coverage_json(tmp_path / "coverage.json", branches=10, covered=5)  # 50%
    _write_pyproject(tmp_path / "pyproject.toml", floor=80)
    rc = _run_branch_check(tmp_path)
    out = capsys.readouterr().out
    assert rc == 1
    assert "50.0%" in out
    assert "below floor 80" in out


def test_branch_check_passes_at_or_above_floor(tmp_path: Path, capsys) -> None:
    _write_coverage_json(tmp_path / "coverage.json", branches=10, covered=8)  # 80%
    _write_pyproject(tmp_path / "pyproject.toml", floor=80)
    assert _run_branch_check(tmp_path) == 0
    assert "80.0%" in capsys.readouterr().out


def test_branch_check_fails_when_no_branches_measured(tmp_path: Path) -> None:
    # branch=true is configured but zero branches were measured -> misconfiguration,
    # not a silent pass. The gate fails loud (AC-CH-3: a missing gate is a bug).
    _write_coverage_json(tmp_path / "coverage.json", branches=0, covered=0)
    _write_pyproject(tmp_path / "pyproject.toml", floor=80)
    assert _run_branch_check(tmp_path) == 2


def test_branch_check_fails_when_floor_not_configured(tmp_path: Path) -> None:
    # A repo that turns this gate on MUST set branch_fail_under. Missing it is a
    # misconfiguration, not a skip — CI must not pass silently.
    _write_coverage_json(tmp_path / "coverage.json", branches=10, covered=1)
    _write_pyproject(tmp_path / "pyproject.toml", floor=None)
    assert _run_branch_check(tmp_path) == 2


def _run_branch_check(cwd: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_branch_coverage.py"), "coverage.json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


# --- AC-CH-1 / AC-CH-2: the line-coverage floor (read from pyproject) ---------


def _run_cov_floor_check(cwd: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_coverage_floor.py"), "coverage.json"],
        cwd=cwd, capture_output=True, text=True, check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def _write_cov_lines(path: Path, statements: int, covered: int) -> Path:
    path.write_text(
        json.dumps({"totals": {"num_statements": statements, "covered_lines": covered}})
    )
    return path


def test_cov_floor_fails_below_threshold(tmp_path: Path) -> None:
    # 50% line coverage against a floor of 90 read from pyproject.
    _write_cov_lines(tmp_path / "coverage.json", statements=100, covered=50)
    _write_pyproject(tmp_path / "pyproject.toml", floor=80)  # sets fail_under=90
    assert _run_cov_floor_check(tmp_path) == 1


def test_cov_floor_passes_at_or_above(tmp_path: Path) -> None:
    _write_cov_lines(tmp_path / "coverage.json", statements=100, covered=92)
    _write_pyproject(tmp_path / "pyproject.toml", floor=80)
    assert _run_cov_floor_check(tmp_path) == 0


def test_cov_floor_fails_loud_when_floor_not_configured(tmp_path: Path) -> None:
    # fail_under missing from pyproject -> misconfiguration, not a skip.
    _write_cov_lines(tmp_path / "coverage.json", statements=100, covered=50)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert _run_cov_floor_check(tmp_path) == 2


def test_cov_floor_threshold_is_read_from_pyproject_not_hardcoded(tmp_path: Path) -> None:
    # The floor is whatever pyproject declares — 95 here, not the repo's 90.
    _write_cov_lines(tmp_path / "coverage.json", statements=100, covered=92)  # 92% < 95
    (tmp_path / "pyproject.toml").write_text(
        "[tool.coverage.report]\nfail_under = 95\n[tool.specgraph]\nbranch_fail_under = 80\n"
    )
    assert _run_cov_floor_check(tmp_path) == 1


def test_coverage_floor_fails_below_threshold_pytest(tmp_path: Path) -> None:
    """A package with uncovered lines fails the --cov-fail-under gate."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def half(a):\n    if a:\n        return 1\n    return 2\n")
    (pkg / "test_mod.py").write_text("from mod import half\ndef test_half():\n    assert half(True) == 1\n")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts='-q'\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(pkg / "test_mod.py"),
         "--cov=mod", "--cov-fail-under=100", "-q"],
        cwd=pkg.parent, capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(pkg)},
    )
    assert result.returncode != 0, "below-floor coverage must fail the gate"


def test_coverage_floor_passes_at_threshold(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def add(a, b):\n    return a + b\n")
    (pkg / "test_mod.py").write_text("from mod import add\ndef test_add():\n    assert add(1, 2) == 3\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(pkg / "test_mod.py"),
         "--cov=mod", "--cov-fail-under=90", "-q"],
        cwd=pkg.parent, capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(pkg)},
    )
    assert result.returncode == 0


# --- AC-CH-5 / AC-CH-6: graph-diff fails on regressions, passes on fixes ----


MAKEFILE = textwrap.dedent(
    """\
    .PHONY: test
    test:
    \tpytest
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
GOOD_HARNESS = textwrap.dedent(
    """\
    # Spec: Demo

    > **Status:** DRAFT

    ## Problem Statement

    **Evidence:** `mod.py::run` does X.

    ## Requirements

    - R-DMO-1: The system MUST do a thing.

    ## Acceptance Criteria

    - [ ] **AC-DMO-1:** The thing is done. (R-DMO-1)
      _Verified by:_ `pytest -k test_thing` · stage: `make test`

    - [ ] **AC-DMO-2 (non-success):** The thing is refused when invalid. (R-DMO-1)
      _Verified by:_ `pytest -k test_refused` · stage: `make test`

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
    return tmp_path


def _graph_json(repo: Path) -> dict:
    return graph_module.build_graph(detect.profile(repo))


def _diff(base: dict, head: dict) -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        bp = Path(d) / "base.json"
        hp = Path(d) / "head.json"
        bp.write_text(json.dumps(base))
        hp.write_text(json.dumps(head))
        result = subprocess.run(
            [sys.executable, str(TOOLS / "diff_spec_graph.py"), str(bp), str(hp)],
            capture_output=True, text=True, check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode


def test_graph_diff_passes_when_clean(repo: Path) -> None:
    _write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    base = _graph_json(repo)
    head = json.loads(json.dumps(base))
    assert _diff(base, head) == 0


def test_graph_diff_fails_on_new_broken_edges(repo: Path) -> None:
    # base: clean spec
    _write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    base = _graph_json(repo)
    # head: same spec but the AC cites a stage the repo lacks -> broken edge
    bad = GOOD_HARNESS.replace("make test", "make nope")
    _write_spec(repo, "c1", "cap1", bad)
    head = _graph_json(repo)
    assert head["broken_links"] > base["broken_links"]
    assert _diff(base, head) == 1


def test_graph_diff_fails_on_new_orphan(repo: Path) -> None:
    _write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    base = _graph_json(repo)
    # head: add an orphan requirement nothing verifies
    orphan_body = GOOD_HARNESS.replace(
        "- R-DMO-1: The system MUST do a thing.",
        "- R-DMO-1: The system MUST do a thing.\n- R-DMO-9: MUST do an untested thing.",
    )
    _write_spec(repo, "c1", "cap1", orphan_body)
    head = _graph_json(repo)
    assert "R-DMO-9" in {n["id"] for n in head["nodes"] if n.get("orphan")}
    assert _diff(base, head) == 1


def test_graph_diff_passes_when_orphan_fixed(repo: Path) -> None:
    # base has an orphan; head fixes it by adding a criterion that traces to it
    orphan_body = GOOD_HARNESS.replace(
        "- R-DMO-1: The system MUST do a thing.",
        "- R-DMO-1: The system MUST do a thing.\n- R-DMO-9: MUST do an untested thing.",
    )
    _write_spec(repo, "c1", "cap1", orphan_body)
    base = _graph_json(repo)
    assert "R-DMO-9" in {n["id"] for n in base["nodes"] if n.get("orphan")}

    fixed = orphan_body.replace(
        "- [ ] **AC-DMO-2 (non-success):** The thing is refused when invalid. (R-DMO-1)",
        "- [ ] **AC-DMO-2 (non-success):** The thing is refused when invalid. (R-DMO-1)\n- [ ] **AC-DMO-3:** The untested thing is now tested. (R-DMO-9)\n  _Verified by:_ `pytest -k test_now` · stage: `make test`",
    )
    _write_spec(repo, "c1", "cap1", fixed)
    head = _graph_json(repo)
    assert "R-DMO-9" not in {n["id"] for n in head["nodes"] if n.get("orphan")}
    assert _diff(base, head) == 0  # fixing an orphan is an improvement, not a regression


def test_graph_diff_rejects_bad_args() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "diff_spec_graph.py"), "only-one-arg"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2


# --- render_mermaid.py: thin consumer of a saved graph.json (CP-GV) ---------


def test_render_mermaid_matches_to_mermaid_byte_for_byte(repo: Path, tmp_path: Path) -> None:
    from openspec_graph.mermaid import to_mermaid

    _write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    graph = _graph_json(repo)
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph))

    result = subprocess.run(
        [sys.executable, str(TOOLS / "render_mermaid.py"), str(graph_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert result.stdout == to_mermaid(graph)


def test_render_mermaid_rejects_bad_args() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "render_mermaid.py")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2


# --- AC-CH-8 / C-CH-1: the rule set matches the committed baseline -----------
# A future change that adds or removes a rule without updating the baseline
# fails this test — forcing the change to be a conscious decision (C-CH-1).


def test_rule_set_matches_baseline() -> None:
    baseline_path = REPO_ROOT / "tests" / "baseline_rules.json"
    assert baseline_path.exists(), "baseline_rules.json must be committed"
    baseline = json.loads(baseline_path.read_text())
    live = rule_table()
    assert live == baseline, (
        "the rule set changed; if this is intentional, regenerate "
        "tests/baseline_rules.json with `planlint rules --json > tests/baseline_rules.json`"
    )
    # sanity: the baseline is non-empty and covers the rules we rely on
    assert len(baseline) == len(RULES)


# --- AC-CH-4 / AC-CH-7: claims about the CI configuration itself -------------
# Both acceptance criteria describe properties of the committed workflow and
# Makefile rather than of any Python function, and both cited tests that were
# never written -- found by tests/test_spec_test_citations.py, the guard that
# now holds every `_Verified by:` citation to a test that exists. Asserted
# against the real files so the criteria stop being prose.


def test_lint_is_a_hard_gate() -> None:
    """AC-CH-4 (non-success): `make lint` fails on a violation and offers no
    "skipping" escape hatch.

    The failure mode this forbids is a gate that degrades to a pass when its
    tool is missing -- the "configured but not enforced" class this project
    exists to catch in other repositories.
    """
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    lint_recipe = [
        line for line in makefile.splitlines() if line.startswith("\t") and "ruff" in line
    ]

    assert lint_recipe, "no ruff invocation found in the Makefile's lint target"
    for line in lint_recipe:
        assert not line.lstrip("\t").startswith("-"), (
            f"lint recipe {line!r} is prefixed with '-', which makes make ignore "
            "its exit code -- the gate would pass on a violation"
        )
        assert "|| true" not in line and "|| echo" not in line, (
            f"lint recipe {line!r} swallows its own failure"
        )
        assert "skipping" not in line.lower()

    # And CI runs that same target rather than a laxer inline command.
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "make lint" in workflow, "CI does not run the `make lint` gate"


def test_graph_diff_artifact_uploaded() -> None:
    """AC-CH-7: the graph-diff job publishes the graph and its comparison, so a
    reviewer can see what changed rather than taking the job's word for it."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "upload-artifact" in workflow, "no artifact upload configured in CI"


# --- harden-two-track-e2e-aqa: the two-track e2e gates exist and stay synced ---


def _ci_workflow_text() -> str:
    return (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _ci_job_blocks(text: str) -> dict[str, str]:
    """Job name -> body, line-scanned out of the workflow's `jobs:` mapping.

    Structural, not substring matching (DEC-AQA-005): PyYAML is deliberately
    not a dependency (zero-runtime-deps contract), and `jobs:` keys sit at a
    fixed two-space indent, so a line scan is exact -- a cosmetic reformat
    can't false-fail and a renamed job can't false-pass.
    """
    lines = text.splitlines()
    try:
        start = lines.index("jobs:") + 1
    except ValueError:
        return {}
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break  # left the top-level mapping
        match = re.match(r"^  ([A-Za-z][\w-]*):\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


def test_ci_job_blocks_returns_empty_when_jobs_key_is_absent() -> None:
    # The guard tests above must fail on a real missing job, not on a parser
    # that silently found nothing.
    assert _ci_job_blocks("name: CI\non: push\n") == {}


def test_ci_job_blocks_ignores_comments_mentioning_jobs() -> None:
    text = "jobs:\n  test:\n    # see the other jobs: for context\n    runs-on: ubuntu-latest\n"
    assert set(_ci_job_blocks(text)) == {"test"}


def test_makefile_has_e2e_live_target() -> None:
    """AC-AQA-1: the no-mocks live track is one local command, not a recipe
    contributors must copy out of the CI YAML."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^e2e-live:.*?##", makefile, re.MULTILINE), (
        "Makefile has no documented `e2e-live` target"
    )
    phony = next(line for line in makefile.splitlines() if line.startswith(".PHONY"))
    assert "e2e-live" in phony.split(), "e2e-live missing from .PHONY"
    assert "PYTHONIOENCODING=ascii" in makefile, (
        "e2e-live must include one pass under the ASCII-only console that "
        "reproduces the fix-stdout-encoding-crash environment"
    )

    # AC-AQA-7: the pre-PR gate's composition is unchanged -- the live track
    # is additive (its own target and CI jobs), never folded into pre-pr.
    pre_pr = next(
        line for line in makefile.splitlines() if re.match(r"^pre-pr:", line)
    )
    assert "e2e-live" not in pre_pr, "e2e-live must not become part of `make pre-pr`"


def test_ci_workflow_has_a_windows_job() -> None:
    """AC-AQA-2: the platform guard tests (path separators, console encoding,
    symlink privilege) must actually execute on the OS they guard."""
    blocks = _ci_job_blocks(_ci_workflow_text())
    windows = {name: body for name, body in blocks.items() if "windows-latest" in body}
    assert windows, (
        "ci.yml has no windows-latest job -- ubuntu-only CI is how three "
        "Windows-blind defects shipped green"
    )
    body = next(iter(windows.values()))
    for gate in ("make lint", "make typecheck", "make test"):
        assert gate in body, f"the Windows job must run `{gate}`, the same gates as `test`"


def test_ci_workflow_has_an_encoding_stress_job() -> None:
    """AC-AQA-3: the encoding crash's original failure environment is itself
    a gate, so a regression can't ship silently the way the original did."""
    blocks = _ci_job_blocks(_ci_workflow_text())
    stressed = {name: body for name, body in blocks.items() if "PYTHONIOENCODING" in body}
    assert stressed, "ci.yml has no job running under an ASCII-only console"
    assert "make e2e-live" in next(iter(stressed.values())), (
        "the encoding-stress job must run the live track (`make e2e-live`)"
    )


def test_hooks_ci_table_lists_every_ci_job() -> None:
    """AC-AQA-4 (non-success): a ci.yml job absent from docs/hooks.md's CI
    hooks table fails the suite -- the `packaging` drift this package
    backfills is a hard error on recurrence, never a silent doc gap."""
    jobs = set(_ci_job_blocks(_ci_workflow_text()))
    assert jobs, "parsed no jobs from ci.yml -- the parser, not the table, is broken"
    hooks = (REPO_ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    missing = sorted(job for job in jobs if job not in hooks)
    assert not missing, f"docs/hooks.md CI hooks table is missing jobs: {missing}"
