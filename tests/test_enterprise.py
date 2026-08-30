"""Enterprise hardening tests (change package: enterprise-hardening).

Covers the deterministic-validation, logging, no-hardcoded-threshold, secret
scan, backward-compatibility, and docs ACs. These exercise the CLI and tools as
subprocesses (deterministic, observable) against fixture repos built in tmp_path.
"""

from __future__ import annotations

import json
import logging
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
    # Two change packages with violations; ordering must be stable (rule, then file).
    _write_spec(repo, "c1", "cap", GOOD_HARNESS.replace("make test", "make nope"))
    _write_spec(repo, "c2", "cap2", GOOD_HARNESS.replace("make test", "make nope"))
    out1 = _run_cli(repo, "validate", "--json").stdout
    out2 = _run_cli(repo, "validate", "--json").stdout
    assert out1 == out2
    findings = json.loads(out1)["findings"]
    assert len(findings) >= 2
    # Findings are ordered by (path, rule); assert that invariant directly.
    keys = [(f["path"], f["rule"]) for f in findings]
    assert keys == sorted(keys), "findings must be stably ordered by (path, rule)"


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


def test_verbose_or_closed(repo: Path) -> None:
    # AC-EH-5, verified by `pytest -k verbose_or_closed`: an invalid convention
    # (a stage the repo lacks) fails closed, AND --verbose puts diagnostics on
    # stderr while stdout carries the FAIL line — the two guarantees together.
    _write_spec(repo, "c1", "cap", GOOD_HARNESS.replace("make test", "make nope"))
    result = _run_cli(repo, "--verbose", "validate")
    assert result.returncode == 1, "invalid convention must fail closed"
    assert "FAIL" in result.stdout, "stdout must carry the failure"
    assert "specgraph" in result.stderr.lower(), "--verbose must log to stderr"
    assert "specgraph" not in result.stdout, "no log records on stdout"


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


# --- AC-EH-2 (non-success): a type error fails make typecheck ----------


def test_mypy_fails_on_a_type_error(tmp_path: Path) -> None:
    # A deliberately-broken module must fail mypy non-zero and name the file.
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "broken.py").write_text("def f() -> int:\n    return 'x'\n")
    result = subprocess.run(
        [sys.executable, "-m", "mypy", str(pkg / "broken.py")],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(pkg)},
    )
    assert result.returncode != 0, "a type error must fail mypy"
    assert "broken.py" in result.stdout, "mypy must name the offending file"


def test_typecheck_passes_on_clean_repo() -> None:
    result = subprocess.run(
        ["make", "typecheck"], capture_output=True, text=True, check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --- AC-EH-3: secret scan catches a committed key ---------------------------


def test_secret_scan_fallback_catches_fake_key(tmp_path: Path, monkeypatch) -> None:
    # Build a fake repo with a tracked file containing an AWS-style key. The
    # token is assembled at runtime so the *test source* itself contains no
    # literal high-entropy string (which would trip the scanner on this file).
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Makefile").write_text(MAKEFILE)
    token = "AKIA" + "IOSFODNN7EXAMPLE"  # canonical AWS example key
    (repo / "leaked.py").write_text(f'TOKEN = "{token}"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "commit", "-qm", "leak"], cwd=repo, env=git_env, check=True)

    import importlib.util
    mod_path = TOOLS / "check_secrets.py"
    spec = importlib.util.spec_from_file_location("secrets", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    monkeypatch.setattr(mod, "run_gitleaks", lambda: (-1, "gitleaks not installed"))
    findings = mod.fallback_scan()
    assert any(token in f or "potential secret" in f for f in findings), findings


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


# --- Peer-review edge cases (post-merge-quality-review) ---------------------
# Targeted coverage of high-risk branches surfaced by the coverage report,
# not a chase for 100%. Each test names the uncovered line it closes.

from openspec_graph import graph as graph_mod
from openspec_graph import log as log_mod
from openspec_graph.rules import Finding


def test_log_level_from_unknown_env_returns_default() -> None:
    # Closes log.py:28 — an unrecognized SPECGRAPH_LOG_LEVEL must fall back to
    # the default (WARNING), not raise and not crash the CLI. Asserts against
    # the logging constants, not magic integers.
    assert log_mod.level_from(verbose=False, env="BOGUS") == logging.WARNING
    assert log_mod.level_from(verbose=False, env="DEBUG") == logging.DEBUG
    assert log_mod.level_from(verbose=False, env="INFO") == logging.INFO
    # --verbose overrides any env var, including an unknown one.
    assert log_mod.level_from(verbose=True, env="BOGUS") == logging.DEBUG


def test_graph_relative_to_outside_root_falls_back() -> None:
    # Closes graph.py:160-161 — a spec path not under the repo root must fall
    # back to its absolute string rather than raising ValueError.
    outside = Path("/elsewhere/not/under/root/spec.md")
    assert graph_mod._relative_to(outside, Path("/repo")) == str(outside)
    # And a path under root still resolves relatively.
    assert graph_mod._relative_to(Path("/repo/openspec/x.md"), Path("/repo")) == "openspec/x.md"


def test_finding_render_when_path_outside_root() -> None:
    # Closes rules.py:47-48 (the contextlib.suppress path) — a Finding whose
    # path is not under root still renders, showing the absolute path.
    f = Finding(
        rule="G004",
        severity="ERROR",
        message="criterion cites a stage the repo lacks",
        path=Path("/elsewhere/spec.md"),
        line=12,
    )
    rendered = f.render(root=Path("/repo"))
    assert "/elsewhere/spec.md:12" in rendered
    assert "G004" in rendered


def test_init_dry_run_writes_nothing(repo: Path) -> None:
    # Closes cli.py:72-73 — `init --dry-run` lists the planned files but writes
    # nothing (no openspec/ tree created).
    result = _run_cli(repo, "init", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dry run" in result.stdout.lower()
    assert not (repo / "openspec").exists(), "--dry-run must not create openspec/"


_UPSTREAM_SPEC = """\
# Spec delta — Demo capability

## ADDED Requirements

### Requirement: the writer SHALL attest every write

Prose obligation.

#### Scenario: attested writes record an evidence id

- **GIVEN** an attested writer
- **WHEN** `make test` runs the suite
- **THEN** an evidence id is recorded
"""


def test_detect_warns_on_mixed_dialects(repo: Path) -> None:
    # Closes cli.py:62 + parse.py:284 — a repo containing both an upstream-form
    # spec and a harness-form spec is classified "mixed" and `detect` emits the
    # warning rather than silently resolving per file.
    _write_spec(repo, "c1", "cap", GOOD_HARNESS)
    _write_spec(repo, "c2", "cap2", _UPSTREAM_SPEC)
    result = _run_cli(repo, "detect")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "mixed" in result.stdout.lower()
    assert "WARN" in result.stdout


# --- Structural guards: wire AC-PR-3/4/6/8 into make test ---------------------
# These read the repo's own source so a regression that reintroduces a banned
# pattern fails `make test`, not a one-off manual grep.


def test_graph_has_no_bare_truncation_magic_number() -> None:
    # AC-PR-3: the public graph JSON contract must not carry a bare [:200]
    # literal; the truncation limit is the named NODE_TEXT_LIMIT constant.
    source = (REPO_ROOT / "openspec_graph" / "graph.py").read_text(encoding="utf-8")
    assert "[:200]" not in source, "graph.py must use NODE_TEXT_LIMIT, not [:200]"
    assert "NODE_TEXT_LIMIT" in source, "graph.py must define NODE_TEXT_LIMIT"


def test_gate_scripts_have_no_duplicated_repo_root_literal() -> None:
    # AC-PR-4: no gate script may re-derive the repo root with the inline
    # Path(__file__).resolve().parent.parent literal; the scripts that need it
    # import repo_root() from tools/_common.py instead. (Scripts that take root
    # as a CLI arg are unaffected.)
    import glob

    scripts = glob.glob(str(REPO_ROOT / "tools" / "check_*.py"))
    assert scripts, "expected at least one tools/check_*.py script"
    for script in scripts:
        text = Path(script).read_text(encoding="utf-8")
        assert "Path(__file__).resolve().parent.parent" not in text, (
            f"{script} must use tools/_common.repo_root(), not the literal"
        )


def test_common_module_is_stdlib_only() -> None:
    # AC-PR-6: tools/_common.py must import only stdlib modules (no third-party
    # deps), so the gate scripts stay runnable in a bare CI runner.
    import ast

    tree = ast.parse((REPO_ROOT / "tools" / "_common.py").read_text(encoding="utf-8"))
    allowed = {"__future__", "pathlib", "os", "sys"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    third_party = imported - allowed
    assert not third_party, f"_common.py must be stdlib-only, found: {third_party}"


def test_pre_push_hook_is_not_forced_into_makefile_or_ci() -> None:
    # AC-PR-8: the pre-push hook is optional/docs-only; the Makefile and CI
    # workflow must never reference or install it (a forced slow hook is rejected).
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pre-push" not in makefile, "Makefile must not reference pre-push"
    assert "pre-push" not in ci, "ci.yml must not reference pre-push"
