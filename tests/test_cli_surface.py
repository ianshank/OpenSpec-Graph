"""CP-1: CLI surface contract — `planlint` verbs, entry points, deprecation alias.

These guard the product's wedge (``AC-RP-3``): planlint is a read-only linter
under ``openspec validate``, never an authoring framework. The verb allow-list
must not grow ``propose``/``apply``/chat verbs — adding one fails this suite.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from openspec_graph.cli import build_parser, main, main_deprecated
from tests.support import run_cli, write_spec

# The closed set of verbs planlint exposes. Adding a verb here is a deliberate,
# reviewed product decision — never an accident. Authoring verbs (propose,
# apply, chat) are explicitly excluded (the non-success criterion of AC-RP-3).
ALLOWED_VERBS = {"detect", "init", "new", "validate", "graph", "rules"}
REJECTED_VERBS = {"propose", "apply", "chat", "generate", "draft"}


def _subcommand_names(parser: argparse.ArgumentParser) -> set[str]:
    """Extract the registered subcommand names from an argparse parser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices.keys())
    return set()


# --- AC-RP-3: verb allow-list (closed surface) -----------------------------


def test_cli_verbs_are_exactly_the_allow_list() -> None:
    """The CLI surface is a closed set — no surprise verbs, none missing."""
    names = _subcommand_names(build_parser())
    assert names == ALLOWED_VERBS, (
        f"verb surface drifted: got {sorted(names)}, expected {sorted(ALLOWED_VERBS)}"
    )


def test_cli_rejects_authoring_verbs() -> None:
    """Non-success (AC-RP-3): no authoring/chat verbs may be registered."""
    names = _subcommand_names(build_parser())
    leaked = names & REJECTED_VERBS
    assert not leaked, (
        f"planlint must not author specs; leaked authoring verbs: {sorted(leaked)}"
    )


# --- VER-1: --version/-V ----------------------------------------------------


def test_version_flag_prints_version_and_exits_zero(repo: Path) -> None:
    result = run_cli(repo, "--version")
    assert result.returncode == 0
    assert result.stdout.strip()


def test_short_version_flag_matches_long_form(repo: Path) -> None:
    assert run_cli(repo, "-V").stdout == run_cli(repo, "--version").stdout


def test_version_flag_does_not_require_a_subcommand(repo: Path) -> None:
    # --version must short-circuit before argparse's required-subcommand
    # check, so it works with no verb at all.
    result = run_cli(repo, "--version")
    assert "usage" not in result.stderr.lower()


def test_version_flag_is_not_a_registered_subcommand() -> None:
    # A top-level optional flag like --target/--verbose, never a verb --
    # must not appear in or expand the closed subcommand allow-list.
    assert "version" not in _subcommand_names(build_parser())


def test_version_string_falls_back_when_package_metadata_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AC-VER-4 (non-success): an uninstalled checkout must not crash --
    # falls back to the package's own __version__ constant.
    import importlib.metadata

    from openspec_graph import __version__
    from openspec_graph.cli import _version_string

    def _raise(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    assert _version_string() == f"%(prog)s {__version__}"


# --- AC-RP-1: entry points wired + deprecation alias ------------------------


def test_entry_points_wired_in_pyproject(repo_root: Path) -> None:
    """pyproject must ship `planlint` (primary) and `specgraph` (legacy alias)."""
    text = (repo_root / "pyproject.toml").read_text()
    assert 'planlint = "openspec_graph.cli:main"' in text, "primary planlint entry missing"
    assert (
        'specgraph = "openspec_graph.cli:main_deprecated"' in text
    ), "deprecated specgraph alias missing"


def test_planlint_module_runs(repo: Path, fixtures: dict[str, Path]) -> None:
    """`python -m openspec_graph.cli` still works (the in-process entry path)."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    result = run_cli(repo, "validate")
    assert result.returncode == 0, result.stderr


def test_primary_command_emits_no_deprecation_warning(repo: Path, fixtures: dict[str, Path]) -> None:
    """The `planlint` path must NOT carry the legacy-alias deprecation warning."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    result = run_cli(repo, "--verbose", "validate", "--json")
    assert result.returncode == 0
    assert "deprecated" not in result.stderr.lower(), (
        "the primary command must not warn about itself"
    )


def test_deprecated_alias_warns_to_stderr_and_delegates(repo: Path, fixtures: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    """`specgraph` (alias) warns to stderr, then runs and preserves exit code."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    rc = main_deprecated(["--target", str(repo), "validate", "--fail-on", "ERROR"])
    assert rc == 0, "clean repo must exit 0 through the alias"
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()
    assert "planlint" in err.lower()


def test_deprecated_alias_preserves_failure_exit_code(repo: Path, fixtures: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    """The alias never silently passes — a real ERROR still exits 1."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    body = (fixtures["good_harness"]).read_text().replace("make regression", "make nope")
    write_spec(repo, "c1", "cap", body)
    rc_direct = main(["--target", str(repo), "validate", "--fail-on", "ERROR"])
    capsys.readouterr()  # flush
    rc_alias = main_deprecated(["--target", str(repo), "validate", "--fail-on", "ERROR"])
    assert rc_direct == 1, "direct invocation must fail on the bad stage"
    assert rc_alias == 1, "alias must preserve the failure exit code, not swallow it"
    err = capsys.readouterr().err
    assert "deprecated" in err.lower(), "alias must still emit the deprecation warning"


def test_deprecated_alias_keeps_stdout_parseable(repo: Path, fixtures: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    """The alias warning goes to stderr only; stdout stays valid JSON."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    rc = main_deprecated(["--target", str(repo), "validate", "--json"])
    assert rc == 0
    out = capsys.readouterr()
    assert out.err, "deprecation warning must land on stderr"
    assert "is deprecated; use `planlint`" in out.err.lower(), (
        "the specific deprecation warning must appear on stderr"
    )
    # The warning text must never leak into stdout; only pure JSON may appear.
    assert "is deprecated; use `planlint`" not in out.out.lower(), (
        "deprecation warning leaked into stdout JSON"
    )
    json.loads(out.out), "stdout must remain parseable JSON through the alias"


def test_planlint_log_level_env_var_works(repo: Path, fixtures: dict[str, Path]) -> None:
    """The new PLANLINT_LOG_LEVEL env var enables debug logging (not just legacy)."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    result = run_cli(
        repo, "validate", "--json",
        env={**os.environ, "PLANLINT_LOG_LEVEL": "DEBUG"},
    )
    assert result.returncode == 0
    assert "planlint" in result.stderr.lower(), "DEBUG must surface the planlint logger"
    json.loads(result.stdout), "stdout stays parseable even with debug logging"


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir(parents=True, exist_ok=True)
    return r


@pytest.fixture
def fixtures() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    return {
        "makefile": root / "fixtures" / "Makefile",
        "good_harness": root / "fixtures" / "good_harness.md",
    }


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
