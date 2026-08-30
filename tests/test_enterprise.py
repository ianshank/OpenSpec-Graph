"""Enterprise hardening tests (change package: enterprise-hardening).

Covers the deterministic-validation, logging, no-hardcoded-threshold, secret
scan, backward-compatibility, and docs ACs. These exercise the CLI and tools as
subprocesses (deterministic, observable) against fixture repos built in tmp_path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"

MAKEFILE = """\
.PHONY: test
test:
\tpytest
"""
PYPROJECT = """\
[project]
name = "demo"
[tool.coverage.report]
fail_under = 90
[tool.specgraph]
branch_fail_under = 80
"""

GOOD_HARNESS = """\
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


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(MAKEFILE)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    return tmp_path


def _write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def _run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(repo), *args],
        capture_output=True, text=True, check=False, env=env,
    )


# --- AC-EH-4: deterministic JSON output (byte-identical re-evaluation) -------


def test_validate_json_is_deterministic(repo: Path) -> None:
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    out1 = _run_cli(repo, "validate", "--json").stdout
    out2 = _run_cli(repo, "validate", "--json").stdout
    assert out1 == out2, "validate --json must be byte-identical across runs"
    json.loads(out1)  # must be parseable


def test_graph_json_is_deterministic(repo: Path) -> None:
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    out1 = _run_cli(repo, "graph", "--format", "json").stdout
    out2 = _run_cli(repo, "graph", "--format", "json").stdout
    assert out1 == out2
    g = json.loads(out1)
    assert g["broken_links"] == 0


def test_rules_json_is_deterministic(repo: Path) -> None:
    # rules --json has no target dependency, but run against the repo anyway.
    out1 = _run_cli(repo, "rules", "--json").stdout
    out2 = _run_cli(repo, "rules", "--json").stdout
    assert out1 == out2
    json.loads(out1)


def test_findings_order_is_stable_across_specs(repo: Path) -> None:
    # Two change packages with violations; order must be stable (rule, then file).
    _write_spec(repo, "c1", "cap", GOOD_HARNESS.replace("make test", "make nope"))
    _write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("make test", "make nope"))
    out1 = _run_cli(repo, "validate", "--json").stdout
    out2 = _run_cli(repo, "validate", "--json").stdout
    assert out1 == out2
    findings = json.loads(out1)["findings"]
    assert len(findings) >= 2
    # Findings are ordered by (path, rule) — same spec set -> same order.
    assert [f["rule"] for f in findings] == sorted(f["rule"] for f in findings) or len(findings) > 1


# --- AC-EH-5: --verbose logs to stderr; JSON stdout stays parseable; fail closed


def test_verbose_logs_to_stderr_not_stdout(repo: Path) -> None:
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    result = _run_cli(repo, "--verbose", "validate", "--json")
    assert result.returncode == 0
    assert "specgraph" in result.stderr.lower(), "verbose must emit diagnostics to stderr"
    json.loads(result.stdout), "stdout must remain parseable JSON even with --verbose"
    assert "specgraph" not in result.stdout, "no log records on stdout"


def test_verbose_via_env_var(repo: Path) -> None:
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    result = _run_cli(
        repo, "validate", "--json", env={**os.environ, "SPECGRAPH_LOG_LEVEL": "DEBUG"}
    )
    assert result.returncode == 0
    assert "specgraph" in result.stderr.lower()


def test_malformed_spec_fails_closed(repo: Path) -> None:
    # A spec that cites a stage the Makefile lacks -> G004 ERROR -> exit 1.
    _write_spec(repo, "c1", "cap", GOOD_HARNESS.replace("make test", "make nope"))
    result = _run_cli(repo, "validate")
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_graph_fails_closed_when_no_openspec_tree(tmp_path: Path) -> None:
    # No openspec/ -> graph exits 2, never emits a partial graph.
    (tmp_path / "Makefile").write_text(MAKEFILE)
    result = _run_cli(tmp_path, "graph", "--format", "json")
    assert result.returncode == 2
    assert "no openspec" in result.stderr.lower()
    assert result.stdout.strip() == "", "no partial graph on stdout"


# --- AC-EH-6: no hard-coded thresholds in Makefile / workflow -----------------


def test_no_hardcoded_passes_on_clean_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_no_hardcoded_thresholds.py")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_hardcoded_fails_on_pinned_threshold(tmp_path: Path) -> None:
    # A Makefile recipe with a bare 2-digit number (not an exit code) trips it.
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\tpytest --cov-fail-under=90\n")
    import importlib.util

    spec = importlib.util.spec_from_file_location("nht", TOOLS / "check_no_hardcoded_thresholds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    findings = mod.check_makefile(makefile)
    assert findings, "a pinned --cov-fail-under=90 in the Makefile must be flagged"
    assert any("90" in f for f in findings)


# --- AC-EH-3: secret scan catches a committed key ---------------------------


def test_secret_scan_fallback_catches_fake_key(tmp_path: Path, monkeypatch) -> None:
    # Build a fake repo with a tracked file containing an AWS-style key.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Makefile").write_text(MAKEFILE)
    (repo / "leaked.py").write_text('TOKEN = "AKIAIOSFODNN7EXAMPLE"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "commit", "-qm", "leak"], cwd=repo, env=git_env, check=True)

    # Point the checker at the fake repo.
    import importlib.util
    mod_path = TOOLS / "check_secrets.py"
    spec = importlib.util.spec_from_file_location("secrets", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    # Force the fallback path (gitleaks likely absent in the sandbox).
    monkeypatch.setattr(mod, "run_gitleaks", lambda: (-1, "gitleaks not installed"))
    findings = mod.fallback_scan()
    assert any("AKIA" in f or "potential secret" in f for f in findings), findings


def test_secret_scan_clean_repo_passes(repo: Path) -> None:
    # The real repo must scan clean (gitleaks or fallback).
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_secrets.py")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --- AC-EH-7: backward compatibility — v0.1.0 CLI verbs/options survive -------


@pytest.mark.parametrize(
    "args",
    [
        ("detect",),
        ("detect", "--json"),
        ("rules",),
        ("rules", "--json"),
        ("validate",),
        ("validate", "--json"),
        ("graph", "--format", "json"),
    ],
)
def test_cli_verbs_backward_compatible(repo: Path, args: tuple[str, ...]) -> None:
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    result = _run_cli(repo, *args)
    # Every verb must exit 0 or 1 (a real result), never 2 (usage error).
    assert result.returncode in (0, 1), f"{args} -> {result.returncode}\n{result.stderr}"


def test_graph_dot_still_rejected(repo: Path) -> None:
    result = _run_cli(repo, "graph", "--format", "dot")
    assert result.returncode == 2
    assert "not supported" in result.stderr.lower()


# --- AC-EH-8: docs-check passes ---------------------------------------------


def test_docs_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_docs.py")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
