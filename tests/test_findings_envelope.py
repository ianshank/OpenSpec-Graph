"""`validate --json` is a portable, versioned artifact — `AC-FE-1..9`.

The defect these pin: the payload carried no schema version and no tool
version, and `Finding.as_dict()` emitted an absolute, native-separator path.
Both `.github/workflows/ci.yml` and the adopter-facing `templates/spec-gate.yml`
upload that file as a build artifact produced on a runner and read elsewhere,
where `/home/runner/work/...` resolves to nothing.

That absolute path was a deliberate decision (``DEC-PS-002``) whose premise was
that no consumer compares the field across two checkouts. The shipped CI
template refutes it; ``DEC-FE-001`` supersedes it on that evidence. These tests
are the fence around the new contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from openspec_graph import __version__
from openspec_graph.rule_types import FINDINGS_SCHEMA_VERSION, Finding
from tests.support import normalize_root, run_cli, write_spec

FX = Path(__file__).resolve().parent / "fixtures"

# A spec body that trips rules, so the envelope under test actually carries
# findings rather than passing vacuously on an empty list.
FINDING_BEARING = "# Nothing normative here\n\nProse only.\n"


def _repo(root: Path, *, with_findings: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (FX / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_spec(root, "c1", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    if with_findings:
        # Two of them, in deliberately non-alphabetical creation order, so the
        # ordering assertions below have something real to sort.
        write_spec(root, "zeta", "cap", FINDING_BEARING)
        write_spec(root, "alpha", "cap", FINDING_BEARING)
    return root


def _envelope(repo: Path) -> dict:
    result = run_cli(repo, "validate", "--json")
    assert result.returncode in (0, 1), result.stderr
    return json.loads(result.stdout)


def test_envelope_carries_a_schema_version(tmp_path: Path) -> None:
    """AC-FE-1: a consumer can tell which shape it received."""
    payload = _envelope(_repo(tmp_path))

    assert payload["schema_version"] == FINDINGS_SCHEMA_VERSION


def test_envelope_carries_the_tool_version(tmp_path: Path) -> None:
    """AC-FE-2: and which build produced it."""
    payload = _envelope(_repo(tmp_path))

    assert payload["tool_version"] == __version__


def test_existing_keys_keep_their_spelling(tmp_path: Path) -> None:
    """AC-FE-3: renaming a key is a second break that buys nothing. The
    envelope is additive over the shape callers already parse."""
    payload = _envelope(_repo(tmp_path))

    assert set(payload) == {
        "schema_version",
        "tool_version",
        "target",
        "specs_checked",
        "findings",
        "blocking",
    }


def test_target_stays_absolute(tmp_path: Path) -> None:
    """AC-FE-4: it is the base the relative finding paths resolve against, so
    relativizing it would leave nothing to resolve them from."""
    repo = _repo(tmp_path)

    payload = _envelope(repo)

    assert Path(payload["target"]).is_absolute()


def test_every_finding_path_is_relative_and_posix(tmp_path: Path) -> None:
    """AC-FE-5: the fix itself. No absolute prefix, no backslashes."""
    repo = _repo(tmp_path)

    payload = _envelope(repo)

    assert payload["findings"], "fixture produced no findings; the assertion would be vacuous"
    for finding in payload["findings"]:
        path = finding["path"]
        assert path is not None
        assert not Path(path).is_absolute(), path
        assert "\\" not in path, path
        assert str(repo) not in path
        # And it still resolves against the target the envelope reports.
        assert (Path(payload["target"]) / path).exists(), path


def test_two_checkout_paths_produce_identical_json(tmp_path: Path) -> None:
    """AC-FE-6: the property the CI template actually needs. The same logical
    repository, cloned to two different directories, yields byte-identical
    findings once the target field is normalized — which is what makes the
    uploaded artifact comparable across machines."""
    first = _repo(tmp_path / "checkout-one")
    second = _repo(tmp_path / "a-different-length-path")

    one = normalize_root(run_cli(first, "validate", "--json").stdout, first)
    two = normalize_root(run_cli(second, "validate", "--json").stdout, second)

    assert one == two


def test_normalize_root_handles_raw_and_json_escaped_forms(tmp_path: Path) -> None:
    """Direct unit pin for the helper: a bare native-path replace is POSIX-only
    (json.dumps doubles every backslash on Windows), so both forms must go."""
    raw = str(tmp_path)
    escaped = raw.replace("\\", "\\\\")
    text = f'plain {raw} and quoted "{escaped}"'
    out = normalize_root(text, tmp_path)
    assert raw not in out and escaped not in out
    assert out.count("<ROOT>") == 2


def test_findings_are_sorted_like_the_text_renderer(tmp_path: Path) -> None:
    """AC-FE-7: the two renderings of one run agreed on content but not on
    order — JSON emitted evaluation order while the text path sorted. Any
    third projection built on findings inherits this order too."""
    repo = _repo(tmp_path)

    payload = _envelope(repo)
    text = run_cli(repo, "validate").stdout

    json_order = [(f["path"], f["rule"]) for f in payload["findings"]]
    assert json_order == sorted(json_order), "JSON findings are not in sorted order"

    # And the same order the human-readable rendering used.
    text_order = [
        (line.split()[2].rstrip(":").rsplit(":", 1)[0], line.split()[1])
        for line in text.splitlines()
        if line[:5].strip() in {"ERROR", "WARN", "INFO"}
    ]
    assert text_order == json_order


def test_blocking_count_still_matches_the_findings(tmp_path: Path) -> None:
    """Sorting must not disturb what the envelope reports."""
    repo = _repo(tmp_path)

    payload = _envelope(repo)

    assert payload["blocking"] == sum(
        1 for f in payload["findings"] if f["severity"] == "ERROR"
    )


# --- Non-success criteria (G002) ---


def test_a_finding_outside_the_target_is_emitted_not_dropped(tmp_path: Path) -> None:
    """AC-FE-8 (non-success): relativizing must never silently discard a
    finding it cannot relativize.

    Reachable only by constructing a Finding directly — every CLI path
    resolves under the spec root — so this test constructs one rather than
    asserting a condition the CLI can never produce. Without that note the
    criterion would look satisfied by a test that can never fail.
    """
    outside = Path("/somewhere/else/spec.md").resolve()

    rendered = Finding("G001", "ERROR", "msg", path=outside).as_dict(tmp_path)

    assert rendered["path"] is not None, "finding was dropped"
    assert rendered["path"] == outside.as_posix()


def test_as_dict_without_a_root_is_unchanged(tmp_path: Path) -> None:
    """AC-FE-9 (non-success): the root argument is opt-in. A caller that
    passes nothing gets exactly the previous absolute rendering, so no other
    call site changed behavior when this landed."""
    path = tmp_path / "openspec" / "spec.md"

    rendered = Finding("G001", "ERROR", "msg", path=path).as_dict()

    assert rendered["path"] == str(path)


def test_a_finding_with_no_path_stays_none(tmp_path: Path) -> None:
    """A pathless finding is still serialized as null, not as the string
    "None" and not omitted."""
    rendered = Finding("G006", "WARN", "orphan", path=None).as_dict(tmp_path)

    assert rendered["path"] is None


def test_clean_repo_still_reports_an_empty_findings_list(tmp_path: Path) -> None:
    """The envelope does not manufacture findings on a passing tree."""
    repo = _repo(tmp_path, with_findings=False)

    payload = _envelope(repo)

    assert payload["findings"] == []
    assert payload["blocking"] == 0


# --- A2b: the legacy detect --json shape ---


def test_detect_json_warns_that_it_is_deprecated(tmp_path: Path) -> None:
    """AC-FE-10: removing a flag after the first release is a break for real
    adopters. Say so before anyone can depend on it."""
    repo = _repo(tmp_path, with_findings=False)

    result = run_cli(repo, "detect", "--json")

    assert result.returncode == 0
    assert "deprecated" in result.stderr
    assert "--format json" in result.stderr
    assert result.stderr.strip().count("\n") == 0, result.stderr


def test_detect_json_stdout_is_unchanged(tmp_path: Path) -> None:
    """AC-FE-10 (non-success): the deprecation is a notice, not a behavior
    change. stdout stays byte-identical, so an existing caller keeps working
    and the warning goes only to the stream that is not being parsed."""
    repo = _repo(tmp_path, with_findings=False)

    result = run_cli(repo, "detect", "--json")

    payload = json.loads(result.stdout)
    assert payload["root"] == str(repo)
    assert "deprecated" not in result.stdout


def test_detect_format_json_is_not_deprecated(tmp_path: Path) -> None:
    """The portable replacement must not inherit the warning."""
    repo = _repo(tmp_path, with_findings=False)

    result = run_cli(repo, "detect", "--format", "json")

    assert result.returncode == 0
    assert "deprecated" not in result.stderr


# --- The version lookup behind tool_version ---


def test_package_version_is_the_single_lookup_site(tmp_path: Path) -> None:
    """The envelope's `tool_version` must not cost a second metadata lookup.

    argparse resolves the version whenever a parser is built — on every
    invocation of every verb — and the envelope needs the same value again.
    Before the lookup was memoized it ran twice, so in an environment with a
    stale `openspec-graph` install alongside `planlint` a single
    `validate --json` printed the ambiguity warning *twice*: the one place a
    reader most needs a clear signal, delivered as noise.

    Runs in a subprocess with a patched `importlib.metadata` so the ambiguity
    is real rather than mocked at the call site.
    """
    repo = _repo(tmp_path, with_findings=False)
    script = f"""
import importlib.metadata as md, sys
md.packages_distributions = lambda: {{"openspec_graph": ["openspec-graph", "planlint"]}}
md.version = lambda dist: "0.0.1-stale" if dist == "openspec-graph" else {__version__!r}
from openspec_graph import cli
sys.argv = ["planlint", "--target", {str(repo)!r}, "validate", "--json"]
try:
    cli.main()
except SystemExit:
    pass
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8"
    )

    assert result.stderr.count("WARNING:") == 1, (
        f"expected exactly one ambiguity warning, got {result.stderr.count('WARNING:')}:\n"
        f"{result.stderr}"
    )
    # And the reported version is the live one, not the stale distribution's.
    assert json.loads(result.stdout)["tool_version"] == __version__


def test_version_flag_output_is_unchanged(tmp_path: Path) -> None:
    """Splitting the bare lookup out of the argparse template must not change
    what `--version` prints — it is the preflight step the Agent Skill tells
    every agent to run first."""
    result = run_cli(tmp_path, "--version")

    assert result.returncode == 0
    assert result.stdout.split() == ["planlint", __version__]


def test_run_cli_normalizes_tool_version() -> None:
    """The golden-output helper must erase `tool_version` before hashing.

    Without it every release would re-pin the stored hash on a version bump
    that changed no output shape, and the hash would quietly stop meaning
    "the findings projection is stable".
    """
    from tests.test_decomposition import _TOOL_VERSION

    sample = '{\n  "tool_version": "9.9.9",\n  "findings": []\n}'

    assert _TOOL_VERSION.sub('"tool_version": "<VERSION>"', sample) == (
        '{\n  "tool_version": "<VERSION>",\n  "findings": []\n}'
    )
