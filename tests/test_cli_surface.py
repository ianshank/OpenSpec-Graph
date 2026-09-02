"""CP-1: CLI surface contract — `planlint` verbs, entry points, deprecation alias.

These guard the product's wedge (``AC-RP-3``): planlint is a read-only linter
under ``openspec validate``, never an authoring framework. The verb allow-list
must not grow ``propose``/``apply``/chat verbs — adding one fails this suite.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from openspec_graph.cli import build_parser, main, main_deprecated
from tests import support
from tests.support import run_cli, write_spec

# The closed set of verbs planlint exposes. Adding a verb here is a deliberate,
# reviewed product decision — never an accident. Authoring verbs (propose,
# apply, chat) are explicitly excluded (the non-success criterion of AC-RP-3).
ALLOWED_VERBS = {"detect", "init", "new", "validate", "graph", "rules", "waivers", "witness"}
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


# --- AC-SK-23/24: --dialect surface for the speckit dialect -----------------


def _subparser(parser: argparse.ArgumentParser, verb: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[verb]
    raise AssertionError(f"no subparsers action found while looking for {verb!r}")


def _dialect_choices(parser: argparse.ArgumentParser, verb: str) -> list[str] | None:
    """The ``--dialect`` argument's ``choices`` for one subcommand, or
    ``None`` if that subcommand has no ``--dialect`` argument at all."""
    sub = _subparser(parser, verb)
    for action in sub._actions:
        if "--dialect" in action.option_strings:
            return list(action.choices) if action.choices else None
    return None


def test_cli_dialect_choices_include_speckit_on_validate_and_waivers() -> None:
    parser = build_parser()
    assert _dialect_choices(parser, "validate") == ["harness", "upstream", "speckit", "auto"]
    assert _dialect_choices(parser, "waivers") == ["harness", "upstream", "speckit", "auto"]


def test_cli_new_and_graph_do_not_gain_speckit_dialect_surface() -> None:
    # C-SK-6 (non-success): scaffolding a SpecKit package is out of scope --
    # `new`'s --dialect choices must not gain "speckit", and `graph` must
    # not gain a --dialect flag at all (it has none today).
    parser = build_parser()
    assert _dialect_choices(parser, "new") == ["harness", "upstream"]
    assert _dialect_choices(parser, "graph") is None


def test_no_feature_cli_flag_exists() -> None:
    # C-SK-7 (non-success): filter_speckit_by_feature() exists for
    # shape-parity with filter_by_change but is reachable only via direct
    # import -- no subcommand may register a --feature flag.
    parser = build_parser()
    for verb in ALLOWED_VERBS:
        sub = _subparser(parser, verb)
        flags = {opt for action in sub._actions for opt in action.option_strings}
        assert "--feature" not in flags, f"{verb} unexpectedly registers --feature"


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


def test_version_string_falls_back_when_top_level_package_is_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A distinct failure mode from the PackageNotFoundError case above:
    # packages_distributions() succeeding but simply not containing
    # "openspec_graph" at all (KeyError), not finding it but failing to
    # resolve its version.
    import importlib.metadata

    from openspec_graph import __version__
    from openspec_graph.cli import _version_string

    monkeypatch.setattr(importlib.metadata, "packages_distributions", dict)
    assert _version_string() == f"%(prog)s {__version__}"


# --- run_cli()'s COVERAGE_PROCESS_START env-override contract --------------
#
# Inspect the env dict run_cli() actually builds (by intercepting
# subprocess.run) rather than relying on the subprocess's exit code:
# coverage.process_startup() silently swallows a missing/bad config path
# either way, so exit-code-only assertions couldn't actually distinguish
# "the custom value was honored" from "it was silently overridden."


def test_run_cli_injects_coverage_process_start_by_default(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    captured: dict[str, object] = {}

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(support.subprocess, "run", _fake_run)
    support.run_cli(repo, "--version")
    assert "COVERAGE_PROCESS_START" in captured["env"]


def test_run_cli_never_overrides_a_caller_supplied_coverage_process_start(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    captured: dict[str, object] = {}

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(support.subprocess, "run", _fake_run)
    custom_env = {**os.environ, "COVERAGE_PROCESS_START": "/custom/path/pyproject.toml"}
    support.run_cli(repo, "--version", env=custom_env)
    assert captured["env"]["COVERAGE_PROCESS_START"] == "/custom/path/pyproject.toml"


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


# --- Defect D: stdout/stderr forced to UTF-8 (fixes UnicodeEncodeError) ----


def test_common_verbs_do_not_crash_under_ascii_stdout_encoding(
    repo: Path, fixtures: dict[str, Path]
) -> None:
    """Confirmed reproducible pre-fix: PYTHONIOENCODING=ascii planlint
    validate raised UnicodeEncodeError from the summary line's "*" separator.
    Every verb that prints one of this package's hardcoded non-ASCII
    characters must survive stdout being forced to ASCII."""
    ascii_env = {**os.environ, "PYTHONIOENCODING": "ascii"}

    assert run_cli(repo, "detect", env=ascii_env).returncode == 0

    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    assert run_cli(repo, "init", "--dry-run", env=ascii_env).returncode == 0
    assert (
        run_cli(
            repo, "new", "add-thing", "--capability", "thing-cap", "--dry-run", env=ascii_env
        ).returncode
        == 0
    )

    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    pass_result = run_cli(repo, "validate", env=ascii_env)
    assert pass_result.returncode == 0, pass_result.stderr

    bad = (fixtures["good_harness"]).read_text().replace("make regression", "make nope")
    write_spec(repo, "c1", "cap", bad)
    fail_result = run_cli(repo, "validate", env=ascii_env)
    assert fail_result.returncode == 1, fail_result.stderr


def test_arbitrary_non_ascii_spec_content_survives_graph_mermaid_under_ascii_encoding(
    repo: Path, fixtures: dict[str, Path]
) -> None:
    """Not just this package's own literals: arbitrary non-ASCII text a user
    writes into a criterion flows verbatim into `graph --format mermaid`'s
    printed node text -- and must come through intact, not just non-crashing."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    body = (fixtures["good_harness"]).read_text().replace(
        "An attested write records an evidence id.",
        "An attested write records an évidence id (café, 日本語).",
    )
    write_spec(repo, "c1", "cap", body)
    result = run_cli(
        repo, "graph", "--format", "mermaid",
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "évidence id (café, 日本語)" in result.stdout


def test_non_ascii_target_path_error_survives_ascii_stdout_encoding(tmp_path: Path) -> None:
    """A non-ASCII absolute path embedded in an error message (not a
    hardcoded literal) must not crash stderr either. The target directory
    never needs to exist for this error path, so this is fully deterministic
    and does not depend on the OS username itself containing non-ASCII
    characters."""
    nonexistent = tmp_path / "café-does-not-exist"
    result = run_cli(nonexistent, "detect", env={**os.environ, "PYTHONIOENCODING": "ascii"})
    assert result.returncode == 1
    assert "café-does-not-exist" in result.stderr


def test_json_output_is_unaffected_by_the_stdout_encoding_fix(
    repo: Path, fixtures: dict[str, Path]
) -> None:
    """validate --json already ASCII-escapes via json.dumps(ensure_ascii=True)
    by default -- confirm the encoding fix changes nothing about JSON mode."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    normal = run_cli(repo, "validate", "--json")
    ascii_env_result = run_cli(
        repo, "validate", "--json", env={**os.environ, "PYTHONIOENCODING": "ascii"}
    )
    assert normal.returncode == ascii_env_result.returncode == 0
    assert json.loads(normal.stdout) == json.loads(ascii_env_result.stdout)


class _ReconfigureRaises:
    """A minimal stdout replacement whose reconfigure() always raises with
    a caller-chosen exception type -- ``main()``'s guard catches both
    ``ValueError`` (a real already-closed ``TextIOWrapper``'s genuine
    behavior -- verified directly) and ``OSError`` (a stream that simply
    doesn't support reconfiguration). Writing/flushing still work
    normally, isolating "reconfigure failed" from "the stream is
    unusable"."""

    def __init__(self, exc_type: type[Exception]) -> None:
        self.chunks: list[str] = []
        self._exc_type = exc_type

    def write(self, s: str) -> int:
        self.chunks.append(s)
        return len(s)

    def flush(self) -> None:
        pass

    def reconfigure(self, **_kwargs: object) -> None:
        raise self._exc_type("reconfiguration not supported by this test double")


@pytest.mark.parametrize("exc_type", [ValueError, OSError])
def test_main_tolerates_a_stream_whose_reconfigure_raises(
    exc_type: type[Exception],
    monkeypatch: pytest.MonkeyPatch, repo: Path, fixtures: dict[str, Path]
) -> None:
    """R-SE-3/DEC-SE-004: main() must not crash before any subcommand runs
    just because reconfiguring stdout's encoding itself failed -- covering
    both exception types the guard's except clause names."""
    (repo / "Makefile").write_text((fixtures["makefile"]).read_text())
    write_spec(repo, "c1", "cap", (fixtures["good_harness"]).read_text())
    fake_stdout = _ReconfigureRaises(exc_type)
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    assert main(["--target", str(repo), "validate"]) == 0
    assert "".join(fake_stdout.chunks), "the command must still print through the fallback stream"


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
