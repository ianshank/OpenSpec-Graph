"""A discovered spec that cannot be read is a precondition failure (exit 2),
never a finding (exit 1) and never a silent pass (exit 0) — `AC-RE-1..6`.

The defect these pin: `parse.parse_spec` read its bytes with no guard, so a
spec path that exists but cannot be opened (a permission-denied file, a
dangling mount, a directory where a file belongs) let an ``OSError`` escape to
the top of ``validate``/``waivers``/``graph``. That printed a traceback and
exited 1 — the code the contract reserves for "findings were reported at or
above --fail-on" — so a CI job could not tell a broken checkout from a failing
gate. Same defect class as ``DEC-SD-001`` (``init``/``new`` on an unwritable
target), one verb further in.

Every verb that parses specs is covered, not just ``validate``: the bug was in
the shared parse layer, so a test for one verb would have passed while the
other three stayed broken.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openspec_graph.parse import SpecReadError, parse_spec
from tests.support import run_cli, write_spec, write_speckit_spec

FX = Path(__file__).resolve().parent / "fixtures"

# Every verb that parses spec bodies. `graph` and `waivers` reach `parse_spec`
# by different call paths than `validate` (build_graph and a list
# comprehension respectively), which is exactly why all three are listed.
PARSING_VERBS = [
    ("validate",),
    ("validate", "--json"),
    ("waivers",),
    ("waivers", "--format", "json"),
    ("graph", "--format", "json"),
    ("graph", "--format", "mermaid"),
]


def _repo(root: Path) -> Path:
    """A minimal, valid target: real machinery plus one clean spec."""
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (FX / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_spec(root, "c1", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    return root


def _make_unreadable(repo: Path, change: str = "broken", capability: str = "cap") -> Path:
    """Put an unreadable spec where discovery will find one.

    A *directory* named ``spec.md`` is the portable way to do this: opening it
    raises ``IsADirectoryError`` on POSIX and ``PermissionError`` on Windows,
    both ``OSError`` subclasses, with no need for a privileged chmod that CI
    running as root would silently ignore.
    """
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize("verb", PARSING_VERBS, ids=lambda v: " ".join(v))
def test_unreadable_spec_exits_2_from_every_parsing_verb(tmp_path: Path, verb: tuple) -> None:
    """AC-RE-1: exit 2, the code reserved for "could not run"."""
    repo = _repo(tmp_path)
    _make_unreadable(repo)

    result = run_cli(repo, *verb)

    assert result.returncode == 2, (
        f"`{' '.join(verb)}` returned {result.returncode}; an unreadable spec is a "
        f"precondition failure (2), not a finding (1) or a pass (0).\n{result.stderr}"
    )


@pytest.mark.parametrize("verb", PARSING_VERBS, ids=lambda v: " ".join(v))
def test_unreadable_spec_never_prints_a_traceback(tmp_path: Path, verb: tuple) -> None:
    """AC-RE-2: a clean one-line diagnostic, not a stack dump."""
    repo = _repo(tmp_path)
    _make_unreadable(repo)

    result = run_cli(repo, *verb)

    assert "Traceback" not in result.stderr, result.stderr
    assert "IsADirectoryError" not in result.stderr
    assert result.stderr.strip().count("\n") == 0, (
        f"expected exactly one diagnostic line, got:\n{result.stderr}"
    )


def test_message_names_the_path_root_relative_and_the_reason(tmp_path: Path) -> None:
    """AC-RE-3: the line identifies which spec and why, without leaking the
    absolute checkout path (two machines cloning the same repo to different
    directories get the identical line)."""
    repo = _repo(tmp_path)
    _make_unreadable(repo)

    result = run_cli(repo, "validate")

    assert "openspec/changes/broken/specs/cap/spec.md" in result.stderr
    assert str(repo) not in result.stderr, "absolute checkout path leaked into the message"
    # The OS's own reason, surfaced rather than swallowed. Both spellings are
    # accepted so this passes on POSIX and Windows alike.
    assert any(
        reason in result.stderr for reason in ("Is a directory", "Permission denied", "Access is denied")
    ), result.stderr


def test_json_output_is_not_emitted_alongside_the_error(tmp_path: Path) -> None:
    """AC-RE-4: a consumer piping stdout gets nothing to misparse as a clean
    result — the failure is not half a report."""
    repo = _repo(tmp_path)
    _make_unreadable(repo)

    result = run_cli(repo, "validate", "--json")

    assert result.stdout.strip() == ""


# --- Non-success criteria (G002): the guard must not swallow real results ---


def test_a_spec_with_real_findings_still_exits_1(tmp_path: Path) -> None:
    """AC-RE-5 (non-success): the new exit-2 path must not capture ordinary
    rule failures. A spec that genuinely violates a rule still exits 1 — if
    this ever returns 2, the guard has started eating findings."""
    repo = _repo(tmp_path)
    write_spec(repo, "empty", "cap", "# Nothing normative here\n\nProse only.\n")

    result = run_cli(repo, "validate", "--fail-on", "ERROR")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_a_clean_tree_still_exits_0(tmp_path: Path) -> None:
    """AC-RE-5 (non-success): and it must not turn a passing repo into a
    failure either."""
    repo = _repo(tmp_path)

    result = run_cli(repo, "validate", "--fail-on", "ERROR")

    assert result.returncode == 0, result.stdout + result.stderr


def test_one_unreadable_spec_does_not_let_the_others_pass_silently(tmp_path: Path) -> None:
    """AC-RE-6: the run aborts rather than reporting on the specs it could
    read. Skipping the unreadable one would let a spec pass a gate that never
    actually saw it — the exact lie this project exists to catch."""
    repo = _repo(tmp_path)
    _make_unreadable(repo)

    result = run_cli(repo, "validate")

    assert result.returncode == 2
    assert "PASS" not in result.stdout


# --- The exception itself ---


def test_spec_read_error_carries_path_and_reason(tmp_path: Path) -> None:
    """AC-RE-7: callers render the diagnostic from typed attributes rather
    than re-parsing the message string."""
    unreadable = tmp_path / "spec.md"
    unreadable.mkdir()

    with pytest.raises(SpecReadError) as caught:
        parse_spec(unreadable, "harness")

    assert caught.value.path == unreadable
    assert caught.value.reason
    assert str(unreadable) in str(caught.value)


def test_spec_read_error_chains_the_original_oserror(tmp_path: Path) -> None:
    """AC-RE-7: the OS error is translated, not discarded — `--verbose` and a
    debugger both still reach the original cause."""
    unreadable = tmp_path / "spec.md"
    unreadable.mkdir()

    with pytest.raises(SpecReadError) as caught:
        parse_spec(unreadable, "harness")

    assert isinstance(caught.value.__cause__, OSError)


def test_a_readable_spec_still_parses(tmp_path: Path) -> None:
    """The guard is a translation layer, not a behavior change."""
    body = (FX / "good_harness.md").read_text(encoding="utf-8")
    path = tmp_path / "spec.md"
    path.write_text(body, encoding="utf-8")

    spec = parse_spec(path, "harness")

    assert spec.requirements or spec.criteria


# --- `--change` on a SpecKit-only target ---


def test_change_on_a_speckit_only_target_names_the_limitation(tmp_path: Path) -> None:
    """AC-RE-8: `--change` scopes OpenSpec change packages. On a SpecKit tree
    the generic "no specs found" reads as "your feature is missing"; the real
    answer is that the flag does not apply here yet. This is the first thing a
    SpecKit adopter hits following the Agent Skill's repair loop."""
    repo = tmp_path
    (repo / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    write_speckit_spec(repo, "001-thing", (FX / "good_speckit.md").read_text(encoding="utf-8"))

    result = run_cli(repo, "validate", "--change", "001-thing")

    assert result.returncode == 2
    assert "--change" in result.stderr
    assert "SpecKit" in result.stderr
    assert "re-run without --change" in result.stderr


def test_change_on_an_openspec_target_keeps_the_original_message(tmp_path: Path) -> None:
    """AC-RE-8 (non-success): the SpecKit wording must not leak onto an
    OpenSpec target, where `--change` genuinely applies and a missing package
    really is the user's error."""
    repo = _repo(tmp_path)

    result = run_cli(repo, "validate", "--change", "no-such-change")

    assert result.returncode == 2
    assert "no specs found for change 'no-such-change'" in result.stderr
    assert "SpecKit" not in result.stderr


def test_graph_still_reports_a_missing_tree_distinctly(tmp_path: Path) -> None:
    """The new handler sits beside the existing NoOpenSpecTreeError one; an
    absent tree must still produce its own message, not the read-error one."""
    (tmp_path / "Makefile").write_text("test:\n\techo hi\n", encoding="utf-8")

    result = run_cli(tmp_path, "graph", "--format", "json")

    assert result.returncode == 2
    assert "cannot read spec" not in result.stderr
    assert "planlint init" in result.stderr


def test_graph_json_stays_valid_when_every_spec_is_readable(tmp_path: Path) -> None:
    """Guard against the try/except swallowing the success path."""
    repo = _repo(tmp_path)

    result = run_cli(repo, "graph", "--format", "json")

    assert result.returncode == 0
    assert json.loads(result.stdout)["nodes"]
