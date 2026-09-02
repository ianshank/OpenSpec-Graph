"""The distributable Agent Skill's claims, held to the CLI's real behavior.

``skills/planlint-spec-governance/SKILL.md`` tells an agent three things it
cannot verify for itself: which verbs never write, what each exit code means,
and what a given failure message looks like. Prose asserting any of those
drifts silently the moment the CLI changes -- and a skill that wrongly
promises "read-only" is not a documentation bug, it is an agent writing files
into a repository it was asked only to inspect.

Every test here pins one of those claims to the thing it claims about:
filesystem state hashed before and after, stderr compared against the exact
strings the skill quotes, manifests compared against the package's own
version. Mirrors ``tests/test_rule_registry_docs.py``'s reason for existing --
the doc is only as good as the check behind it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from support import run_cli, write_spec

from openspec_graph import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "planlint-spec-governance"
SKILL_MD = SKILL_DIR / "SKILL.md"
EXIT_CODES_DOC = SKILL_DIR / "references" / "exit-codes.md"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CATALOG = SKILL_DIR / "references" / "rule-catalog.md"
RENDERER = REPO_ROOT / "tools" / "render_rule_catalog.py"

# Placeholder for a dialect card written outside the target repo. Substituted
# in the read-only test rather than hardcoded, because the path is only known
# once tmp_path exists -- and because the file must not live inside the tree
# whose byte-for-byte stability the test is measuring.
_BASELINE_PLACEHOLDER = "<BASELINE>"

# Exactly the verbs SKILL.md's own read-only table lists, in its order. If a
# verb moves between that table and the "writes files" one, this list must
# move with it -- that is the point.
READ_ONLY_INVOCATIONS: tuple[tuple[str, ...], ...] = (
    ("detect",),
    ("detect", "--format", "json"),
    ("validate",),
    ("validate", "--json"),
    ("validate", "--fail-on", "WARN"),
    ("graph", "--format", "json"),
    ("graph", "--format", "mermaid"),
    ("rules",),
    ("rules", "--json"),
    ("waivers",),
    ("waivers", "--format", "json"),
    # `delta` needs a baseline card. _BASELINE_PLACEHOLDER is substituted at run
    # time with a path *outside* the target tree, so the read-only digest
    # below stays a genuine measurement: a baseline written inside the repo
    # would show up as a created file and mask what the verb itself did.
    ("delta", "--baseline", _BASELINE_PLACEHOLDER),
    ("delta", "--baseline", _BASELINE_PLACEHOLDER, "--format", "json"),
    # The only read-only invocation that reaches the witness store at all.
    # Without it the store's directory is never touched during this test, so
    # the empty-directory case above would be untested in practice.
    ("validate", "--require-witness"),
)

# Exit codes a read-only verb may legitimately return: 0 (clean) or 1
# (findings). A 2 means it refused to run, which would make the
# tree-unchanged assertion true for the wrong reason.
_ALLOWED_READ_ONLY_EXITS = frozenset({0, 1})

# The two messages the skill quotes verbatim for a repo with no spec tree.
_NO_TREE_SHORT = (
    "no openspec/ directory and no SpecKit specs/ tree; run ``planlint init`` first"
)


def _tree_digest(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to a hash of its bytes.

    Deliberately not ``git status``: a git-based check is blind to writes into
    ignored paths (``.planlint/witnesses/`` is itself gitignored, so a stray
    witness would be invisible) and useless on a target that is not a git
    repository at all. Dotfiles and dot-directories are walked, not skipped,
    for the same reason.
    """
    digest: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Directories are recorded too. The likeliest read-only regression is
        # not a stray file but a stray `mkdir`: witness.py creates
        # `.planlint/witnesses/` with parents=True before writing, so a verb
        # that started touching the witness store would leave an *empty*
        # directory a file-only digest cannot see -- and the witness store is
        # the exact case this function's docstring claims to cover.
        for name in dirnames:
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            digest[rel + "/"] = "<dir>"
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            digest[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir(parents=True, exist_ok=True)
    return r


@pytest.fixture
def populated_repo(repo: Path) -> Path:
    """A target repo with a Makefile, a coverage floor, and one real spec."""
    fixtures = Path(__file__).resolve().parent / "fixtures"
    (repo / "Makefile").write_text(
        (fixtures / "Makefile").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "pyproject.toml").write_text(
        (fixtures / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_spec(
        repo,
        "c1",
        "cap",
        (fixtures / "good_harness.md").read_text(encoding="utf-8"),
    )
    return repo


# --- AC-SD-4: the read-only claim -------------------------------------------


def test_read_only_verbs_leave_tree_byte_identical(populated_repo: Path) -> None:
    """AC-SD-4 (non-success): no read-only verb creates, removes, or edits a file."""
    before = _tree_digest(populated_repo)
    assert before, "fixture repo is empty; the comparison would be vacuous"

    # One real card, written outside the tree under test.
    baseline = populated_repo.parent / "read-only-baseline.json"
    card = run_cli(populated_repo, "detect", "--format", "json")
    assert card.returncode == 0, card.stderr
    baseline.write_text(card.stdout, encoding="utf-8")

    for argv in READ_ONLY_INVOCATIONS:
        argv = tuple(str(baseline) if a == _BASELINE_PLACEHOLDER else a for a in argv)
        result = run_cli(populated_repo, *argv)
        # Without this the test passes vacuously if a verb regresses into an
        # immediate refusal: it would touch nothing precisely because it did
        # nothing, and the read-only claim would look proven.
        assert result.returncode in _ALLOWED_READ_ONLY_EXITS, (
            f"{' '.join(argv)} exited {result.returncode}, so it never ran; "
            f"an unchanged tree proves nothing here. stderr: {result.stderr!r}"
        )

    after = _tree_digest(populated_repo)
    created = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    assert not (created or removed or modified), (
        "a verb SKILL.md documents as read-only touched the target tree: "
        f"created={created} removed={removed} modified={modified}"
    )


def test_read_only_invocations_cover_every_verb_the_skill_calls_read_only() -> None:
    """The list above is only meaningful if it matches SKILL.md's own table.

    Parses through the shared helper rather than splitting inline: an
    unguarded ``split(...)[1]`` raises IndexError if a heading is reworded,
    reporting a crash instead of the drift that caused it. The helper exists
    for exactly that reason, so it is used here too.
    """
    documented, _ = _skill_verb_tables()
    exercised = {argv[0] for argv in READ_ONLY_INVOCATIONS}
    assert documented == exercised, (
        f"SKILL.md's read-only table {sorted(documented)} and this test's "
        f"exercised set {sorted(exercised)} disagree"
    )


def _skill_verb_tables() -> tuple[set[str], set[str]]:
    """The read-only and write verb sets SKILL.md documents.

    Asserts each section marker exists before splitting: a bare ``split(...)[1]``
    raises IndexError rather than failing an assertion if a heading is reworded,
    which reports a crash instead of the drift that caused it.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    for marker in ("Read-only.", "Writes files.", "## Repairing"):
        assert marker in text, f"SKILL.md no longer contains the {marker!r} marker"
    read_only = text.split("Read-only.", 1)[1].split("Writes files.", 1)[0]
    writes = text.split("Writes files.", 1)[1].split("## Repairing", 1)[0]
    row = re.compile(r"^\| `([a-z]+)` \|", re.MULTILINE)
    return set(row.findall(read_only)), set(row.findall(writes))


def test_write_verbs_are_documented_as_writing() -> None:
    """The complement: every verb that writes is in the writes-files table."""
    _, documented = _skill_verb_tables()
    assert documented == {"init", "new", "witness"}, (
        f"SKILL.md's write-verb table lists {sorted(documented)}"
    )


def test_skill_tables_cover_every_verb_the_cli_actually_has() -> None:
    """No verb may exist that the skill classifies as neither read nor write.

    The two table tests each compare a section against a known set, so both
    stay green when a *new* verb is added to the CLI and documented nowhere --
    and an agent reading the skill would then treat an unlisted verb as safe
    by omission. This closes that gap by asking the parser itself.
    """
    import argparse

    from openspec_graph.cli import build_parser

    subparsers = next(
        action for action in build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    real = set(subparsers.choices)
    read_only, writes = _skill_verb_tables()
    documented = read_only | writes

    assert not (real - documented), (
        f"CLI verb(s) {sorted(real - documented)} appear in neither of SKILL.md's "
        "tables; an agent would treat them as safe by omission"
    )
    assert not (documented - real), (
        f"SKILL.md documents verb(s) {sorted(documented - real)} the CLI does not have"
    )
    assert not (read_only & writes), (
        f"verb(s) {sorted(read_only & writes)} are in both tables"
    )


def test_dry_run_writes_nothing(populated_repo: Path) -> None:
    """SKILL.md tells agents `--dry-run` previews safely; prove it.

    The existing CLI tests assert only that these exit 0. That is not the
    claim an agent acts on: the claim is that the tree is untouched, and it is
    the claim that makes `--dry-run` the safe way to inspect scaffolding.
    """
    before = _tree_digest(populated_repo)
    for argv in (("init", "--dry-run"),
                 ("new", "preview-only", "--capability", "preview-cap", "--dry-run")):
        result = run_cli(populated_repo, *argv)
        assert result.returncode == 0, f"{argv} failed: {result.stderr!r}"
        assert "dry run" in result.stdout.lower()
    assert _tree_digest(populated_repo) == before, (
        "a --dry-run invocation modified the target tree"
    )


def test_write_verbs_actually_write(populated_repo: Path) -> None:
    """The affirmative complement, so the read-only test cannot pass by inertia.

    If `init` and `new` also left the tree untouched, every read-only
    assertion here would be trivially true and prove nothing about the
    read/write split the skill is built on.
    """
    before = _tree_digest(populated_repo)
    assert run_cli(populated_repo, "init").returncode == 0
    assert run_cli(
        populated_repo, "new", "really-written", "--capability", "written-cap"
    ).returncode == 0
    after = _tree_digest(populated_repo)
    created = set(after) - set(before)
    assert created, "init and new wrote nothing; the read/write split is not real"


# --- AC-SD-5 / AC-SD-6: the exit-code contract ------------------------------


@pytest.mark.parametrize("verb", ["validate", "waivers"])
def test_exit_two_messages_match_the_documented_contract(repo: Path, verb: str) -> None:
    """AC-SD-5: the short no-spec-tree message is exactly what the doc quotes."""
    assert _NO_TREE_SHORT in EXIT_CODES_DOC.read_text(encoding="utf-8"), (
        "references/exit-codes.md no longer quotes the message this test pins"
    )
    result = run_cli(repo, verb)
    assert result.returncode == 2, f"{verb} on an empty repo should exit 2"
    assert result.stderr.strip() == _NO_TREE_SHORT


def test_graph_exit_two_message_names_both_absolute_paths(repo: Path) -> None:
    """AC-SD-5: `graph` prints a different, longer message than validate does.

    Pinned separately and deliberately: a skill quoting only validate's
    message would fail to recognize graph's, which is the whole reason
    exit-codes.md documents them apart.
    """
    result = run_cli(repo, "graph", "--format", "json")
    assert result.returncode == 2
    assert result.stderr.strip() != _NO_TREE_SHORT
    assert "no openspec/ directory found at" in result.stderr
    assert "no SpecKit specs/ tree found at" in result.stderr
    doc = EXIT_CODES_DOC.read_text(encoding="utf-8")
    assert "no openspec/ directory found at" in doc


def test_unknown_change_package_exits_two(populated_repo: Path) -> None:
    """AC-SD-5: `--change` naming no package is a usage error, not a finding."""
    result = run_cli(populated_repo, "validate", "--change", "nope")
    assert result.returncode == 2
    assert result.stderr.strip() == "no specs found for change 'nope'"


def test_missing_target_directory_exits_two(tmp_path: Path) -> None:
    """AC-SD-6 (non-success): a bad --target is a usage error (DEC-SD-001).

    Before this change it exited 1 -- the same code as "findings were
    reported" -- so a mistyped path was indistinguishable from a real spec
    failure to anything reading only the exit code.
    """
    result = run_cli(tmp_path / "does-not-exist", "validate")
    assert result.returncode == 2, (
        "a --target that is not a directory must exit 2, never 1 "
        f"(got {result.returncode}: {result.stderr!r})"
    )
    assert "target is not a directory" in result.stderr
    assert "FAIL" not in result.stdout


def test_a_real_finding_still_exits_one(populated_repo: Path) -> None:
    """The other half of AC-SD-6: exit 1 still means findings, unchanged."""
    spec = populated_repo / "openspec/changes/c1/specs/cap/spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace("make regression", "make nope"),
        encoding="utf-8",
    )
    result = run_cli(populated_repo, "validate", "--fail-on", "ERROR")
    assert result.returncode == 1
    assert "G004" in result.stdout


# --- R-SD-4, the remainder: exit-2 claims the doc made but nothing checked ---
#
# `references/exit-codes.md` documents five more exit-2 cases than the tests
# above pin. Every one of them is factually correct today -- verified by hand
# against the CLI -- which is exactly the problem: R-SD-4 says the messages an
# agent reads are "mechanically verified rather than asserted", and by-hand is
# how a claim stays true until the day it silently stops being.


def test_graph_unknown_change_exits_two(populated_repo: Path) -> None:
    """`graph --change` shares validate's message; the doc quotes it once."""
    result = run_cli(populated_repo, "graph", "--change", "nope", "--format", "json")
    assert result.returncode == 2
    assert result.stderr.strip() == "no specs found for change 'nope'"
    assert "no specs found for change 'name'" in EXIT_CODES_DOC.read_text(encoding="utf-8")


def test_graph_format_dot_exits_two(populated_repo: Path) -> None:
    """Rendering is out of scope, and refusing it is a usage error, not a finding.

    Checked before the target is profiled, so it exits 2 even against a repo
    that would otherwise validate -- which is what makes it a usage error
    rather than a result.
    """
    result = run_cli(populated_repo, "graph", "--format", "dot")
    assert result.returncode == 2
    assert "dot" in result.stderr.lower()
    assert "graph --format dot" in EXIT_CODES_DOC.read_text(encoding="utf-8")


def test_detect_diff_missing_baseline_exits_two(populated_repo: Path, tmp_path: Path) -> None:
    """An unreadable baseline is a usage error; drift is the exit-1 case."""
    result = run_cli(populated_repo, "detect", "--diff", str(tmp_path / "absent.json"))
    assert result.returncode == 2
    assert "cannot read --diff baseline" in result.stderr


def test_detect_diff_malformed_baseline_exits_two(populated_repo: Path, tmp_path: Path) -> None:
    """Valid JSON of the wrong shape is still not a dialect card."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text("[]", encoding="utf-8")
    result = run_cli(populated_repo, "detect", "--diff", str(baseline))
    assert result.returncode == 2
    assert "object" in result.stderr.lower()


@pytest.mark.parametrize(
    "argv, why",
    [
        (("--stage", "Not A Target", "--exit", "0", "--sha", "a" * 40), "stage identifier"),
        (("--stage", "test", "--exit", "0", "--sha", "abc"), "short sha"),
        (("--stage", "test", "--exit", "0", "--sha", "z" * 40), "non-hex sha"),
        (("--stage", "test", "--exit", "0", "--sha", "a" * 40, "--coverage", "101"), "coverage above 100"),
        (("--stage", "test", "--exit", "0", "--sha", "a" * 40, "--coverage", "nan"), "coverage not finite"),
    ],
    ids=["bad-stage", "short-sha", "non-hex-sha", "coverage-over-100", "coverage-nan"],
)
def test_witness_boundary_checks_exit_two(populated_repo: Path, argv, why: str) -> None:
    """The doc promises every `witness` boundary check exits 2. Each one, then.

    The unwritable-store case the doc also names is left to
    ``tests/test_witness.py``: reproducing it needs a permission change that is
    a no-op for a root-owned test runner and unavailable on Windows, so pinning
    it here would pass by accident on the machines that matter least.
    """
    result = run_cli(populated_repo, "witness", *argv)
    assert result.returncode == 2, (
        f"witness with a bad {why} must exit 2, got {result.returncode}: {result.stderr!r}"
    )


@pytest.mark.parametrize(
    "argv",
    [("init",), ("new", "some-change", "--capability", "some-cap")],
    ids=["init", "new"],
)
def test_write_verbs_exit_two_when_the_target_cannot_be_written(
    populated_repo: Path, monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...],
) -> None:
    """An unwritable target is a precondition failure, not a spec failure.

    ``witness`` already guarded its own store this way and returned 2. ``init``
    and ``new`` let the ``OSError`` escape, which printed a traceback and
    exited **1** -- the code the contract reserves for "findings were reported
    at or above --fail-on". A read-only checkout or a full disk was therefore
    indistinguishable from a failing gate to any caller reading only the exit
    code, which is the defect DEC-SD-001 fixed for a bad ``--target``.

    The fault is injected rather than produced with ``chmod``: the test runner
    here is root, for whom the permission bits on a directory are advisory, so
    a filesystem-level reproduction would silently succeed and assert nothing.
    """
    from openspec_graph import cli, scaffold

    def _explode(*_args: object, **_kwargs: object) -> list[Path]:
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(scaffold, "apply", _explode)
    code = cli.main(["--target", str(populated_repo), *argv])
    assert code == 2, f"{argv[0]} on an unwritable target must exit 2, got {code}"


def test_write_verbs_still_exit_zero_when_the_target_is_writable(
    populated_repo: Path,
) -> None:
    """The affirmative half, so the guard above cannot pass by refusing always."""
    from openspec_graph import cli

    assert cli.main(["--target", str(populated_repo), "init"]) == 0


# --- AC-SD-2 / AC-SD-3: the generated catalog -------------------------------


def _load_tool(name: str, filename: str):
    """Import a ``tools/`` script by path, in-process.

    In-process rather than by subprocess for two reasons: coverage sees it
    (``tools/`` scripts invoked as subprocesses are measured by nothing), and
    module attributes can be monkeypatched so a test never has to write to a
    tracked file to exercise a failure path.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "tools" / filename)
    assert spec and spec.loader, f"cannot load tools/{filename}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_renderer(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RENDERER), *args],
        capture_output=True, text=True, check=False, encoding="utf-8",
    )


def test_rule_catalog_is_fresh() -> None:
    """AC-SD-2: the committed catalog matches the live rule registry."""
    result = _run_renderer("--check")
    assert result.returncode == 0, (
        f"{result.stdout}{result.stderr}\nrun `make skill-catalog` to regenerate"
    )


def test_rule_catalog_check_fails_when_stale(tmp_path: Path, monkeypatch) -> None:
    """AC-SD-3 (non-success): --check reports staleness rather than hiding it.

    Runs against a redirected copy under tmp_path, never the tracked file. An
    earlier version mutated the real catalog and restored it in a ``finally``:
    a hard interrupt then left an invented rule row in the contributor's tree,
    it raced the two sibling tests that read the same file under xdist, and it
    failed outright on a read-only checkout.
    """
    module = _load_tool("rrc", "render_rule_catalog.py")
    staged = tmp_path / "rule-catalog.md"
    monkeypatch.setattr(module, "CATALOG_PATH", staged)

    # Missing entirely.
    assert module.main(["--check"]) == 1

    # Present but stale.
    staged.write_text(module.render() + "| Z999 | ERROR | any | invented |\n", encoding="utf-8")
    assert module.main(["--check"]) == 1

    # Written by the generator, then fresh -- proves --write and --check agree.
    assert module.main(["--write"]) == 0
    assert module.main(["--check"]) == 0
    assert CATALOG.read_text(encoding="utf-8"), "the tracked catalog must be untouched"


def test_rule_catalog_render_is_deterministic() -> None:
    """The pure function's own contract, exercised in-process.

    Every other check here runs the tool as a subprocess, which measures no
    coverage of the module and cannot see this property at all.
    """
    module = _load_tool("rrc", "render_rule_catalog.py")
    assert module.render() == module.render()
    assert module.render().endswith("\n")


def test_rule_catalog_lists_every_registered_rule() -> None:
    """The catalog is generated, so this asserts the generator's coverage."""
    from openspec_graph.rules import RULES

    text = CATALOG.read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| ([A-Z]\d{3}) \|", text, re.MULTILINE))
    assert listed == {rule.ident for rule in RULES}


def test_rule_catalog_states_no_total_count() -> None:
    """DEC-SD-003: a count here would be the one number nothing guards."""
    text = CATALOG.read_text(encoding="utf-8")
    assert not re.search(r"\b\d+\s+(?:deterministic\s+)?rules\b", text), (
        "the generated catalog must not state a rule total -- "
        "tests/test_rule_registry_docs.py cannot see this file"
    )


# --- AC-SD-7: manifest agreement --------------------------------------------


def test_plugin_manifests_agree() -> None:
    """AC-SD-7: manifests, skill directory, and package version are one story."""
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))

    assert plugin["name"] == SKILL_DIR.name
    assert plugin["version"] == __version__, (
        f"plugin.json version {plugin['version']!r} != package {__version__!r}"
    )

    entries = [p for p in marketplace["plugins"] if p["name"] == plugin["name"]]
    assert len(entries) == 1, (
        f"marketplace.json must list {plugin['name']!r} exactly once"
    )
    assert entries[0]["source"] == "./", (
        "the plugin's source is the repo root, so skills/ ships with it"
    )
    assert entries[0]["version"] == __version__


# --- AC-SD-10 / AC-SD-11: the shipped CI asset ------------------------------


def test_skill_asset_matches_template() -> None:
    """AC-SD-10: the bundled workflow is a byte-identical copy (DEC-SD-004)."""
    template = (REPO_ROOT / "templates" / "spec-gate.yml").read_bytes()
    asset = (SKILL_DIR / "assets" / "spec-gate.yml").read_bytes()
    assert asset == template, (
        "skills/planlint-spec-governance/assets/spec-gate.yml has drifted from "
        "templates/spec-gate.yml; copy the template over it"
    )


def test_spec_gate_template_triggers_on_speckit_trees() -> None:
    """AC-SD-11: a SpecKit repo must trigger the gate it just installed."""
    text = (REPO_ROOT / "templates" / "spec-gate.yml").read_text(encoding="utf-8")
    paths_block = text.split("paths:", 1)[1].split("workflow_dispatch", 1)[0]
    assert '"specs/**"' in paths_block, (
        "the template triggers only on openspec/**, so a SpecKit repo would "
        "never run the gate"
    )
    assert '"openspec/**"' in paths_block


# --- C-SD-1 / C-SD-2: the boundaries ----------------------------------------


def test_runtime_dependencies_stay_empty() -> None:
    """AC-SD-15 (non-success): the zero-dependency boundary is load-bearing."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies = \[\]$", text, re.MULTILINE), (
        "runtime dependencies must stay empty (docs/architecture/c4.md)"
    )


def test_distributable_skill_is_not_copied_into_claude_skills() -> None:
    """AC-SD-16 (non-success): .claude/skills/ stays contributor tooling.

    A repo-root skills/ tree is not auto-loaded; the distributable skill
    reaches its audience through the plugin. Copying it into .claude/ would
    give this repo's own contributors a second, drifting copy for no gain.
    """
    dev_skills = {p.name for p in (REPO_ROOT / ".claude" / "skills").iterdir() if p.is_dir()}
    assert SKILL_DIR.name not in dev_skills, (
        f"{SKILL_DIR.name} must not be duplicated under .claude/skills/"
    )
    # Deliberately not asserting the exact set: a second legitimate
    # contributor skill is fine, a copy of the distributable one is not.


# --- AC-SD-12 / AC-SD-13 / AC-SD-14: packaging and gate coverage ------------


def test_version_has_a_single_source() -> None:
    """AC-SD-12: pyproject reads the package attribute, never a second literal.

    Two literals with nothing binding them is the drift class
    tests/test_rule_registry_docs.py exists for, and a release is the worst
    place to find it (DEC-SD-009).
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert 'version = { attr = "openspec_graph.__version__" }' in text
    assert not re.search(r'^version = "\d', text, re.MULTILINE), (
        "pyproject.toml carries its own version literal again"
    )


def test_installed_distribution_version_matches_the_package_attribute() -> None:
    """The single source, proven end to end through the installed metadata."""
    import importlib.metadata

    try:
        installed = importlib.metadata.version("planlint")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        pytest.skip("planlint is not installed in this environment")
    assert installed == __version__


def test_cli_version_flag_reports_the_package_version() -> None:
    """`planlint --version` is the preflight step SKILL.md tells agents to run."""
    result = subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--version"],
        capture_output=True, text=True, check=False, encoding="utf-8",
    )
    assert result.returncode == 0
    assert __version__ in result.stdout


def test_threshold_guard_scans_every_workflow() -> None:
    """AC-SD-13 (non-success): a workflow other than ci.yml cannot escape it.

    The guard named ci.yml alone, so any workflow added later -- a release
    job, a scheduled scan -- went unscanned while the guard still printed
    PASS. Asserting on the resolved target list rather than on a temp file
    keeps this honest: the bug was in target selection, not in matching.
    """
    mod = _load_tool("nht", "check_no_hardcoded_thresholds.py")

    # Assert on the guard's OWN target selection. Re-globbing the directory
    # here instead would pass against the broken version too: the bug was
    # never in matching, it was in which files were handed to the matcher.
    selected = {p.name for p in mod.targets()}
    assert {"Makefile", "ci.yml", "release.yml"} <= selected, (
        f"the guard scans {sorted(selected)}; it must cover every workflow, "
        "not a named subset"
    )
    on_disk = {p.name for p in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml")}
    assert on_disk <= selected, (
        f"workflow(s) {sorted(on_disk - selected)} exist but are not scanned"
    )
    for target in mod.targets():
        checker = mod.check_makefile if target.name == "Makefile" else mod.check_workflow
        assert checker(target) == [], f"{target.name} already trips the guard"


def test_threshold_guard_flags_a_pinned_floor_in_a_non_ci_workflow(tmp_path: Path) -> None:
    """The matching half of AC-SD-13, on a file that is not ci.yml."""
    mod = _load_tool("nht", "check_no_hardcoded_thresholds.py")

    body = "jobs:\n  x:\n    steps:\n      - run: pytest --cov-fail-under=90\n"
    # Both spellings GitHub Actions accepts. A guard covering only one is the
    # same bug one rename away.
    for name in ("release.yml", "scheduled.yaml"):
        fake = tmp_path / name
        fake.write_text(body, encoding="utf-8")
        assert mod.check_workflow(fake), (
            f"a pinned coverage floor in {name} must be flagged"
        )


def test_required_docs_are_linked() -> None:
    """AC-SD-14: the skill is a required doc and the README links it."""
    check_docs = REPO_ROOT / "tools" / "check_docs.py"
    text = check_docs.read_text(encoding="utf-8")
    assert "skills/planlint-spec-governance/SKILL.md" in text, (
        "the skill must be listed in REQUIRED_DOCS"
    )
    result = subprocess.run(
        [sys.executable, str(check_docs)],
        capture_output=True, text=True, check=False, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_skill_quotes_no_credential_shaped_literals() -> None:
    """`make security` scans every tracked file; an example token would fail it.

    Cheaper to catch here, where the message says why, than in a gitleaks run
    whose output points at a documentation file with no explanation.
    """
    patterns = (r"AKIA[0-9A-Z]{16}", r"gh[pousr]_[A-Za-z0-9]{20,}",
                r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9]{20,}",
                r"xox[bpras]-[A-Za-z0-9-]{10,}")
    for path in sorted(SKILL_DIR.glob("**/*")):
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            assert not re.search(pattern, body), (
                f"{path.relative_to(REPO_ROOT)} contains a credential-shaped "
                f"literal matching {pattern!r}; make security scans this file"
            )


# --- backwards compatibility: the distribution rename ------------------------


def test_version_lookup_prefers_the_named_distribution_over_list_order(monkeypatch) -> None:
    """A stale `openspec-graph` install must not be able to report its version.

    Two distributions can provide the import name `openspec_graph` at once --
    exactly what an upgrade from before the rename leaves behind if the old
    editable install is not removed. `packages_distributions()` returns them in
    no defined order, so selecting by index could report the old code's version
    indefinitely. `--version` is the preflight step the Agent Skill tells every
    agent to run first, which makes a wrong answer here the worst one
    available.
    """
    import importlib.metadata as md

    from openspec_graph import cli

    monkeypatch.setattr(
        md, "packages_distributions",
        lambda: {"openspec_graph": ["openspec-graph", "planlint"]},
    )
    monkeypatch.setattr(
        md, "version",
        lambda dist: "0.0.1-stale" if dist == "openspec-graph" else __version__,
    )
    captured: list[str] = []
    monkeypatch.setattr(
        cli, "print",
        lambda *a, **k: captured.append(" ".join(str(x) for x in a)),
        raising=False,
    )

    result = cli._version_string()
    assert __version__ in result, f"reported {result!r} instead of the live version"
    assert "0.0.1-stale" not in result
    assert any("WARNING" in line for line in captured), (
        "an ambiguous environment must say so; silence hides a stale install"
    )


def test_version_lookup_is_silent_when_one_distribution_is_listed_twice(monkeypatch) -> None:
    """Duplicate entries for one name are not ambiguity, and must not warn.

    A repeated editable install can leave several metadata directories for the
    same distribution. Warning there would fire on every invocation of every
    verb for an environment that is in fact fine -- noise that trains a reader
    to ignore the warning that matters.
    """
    import importlib.metadata as md

    from openspec_graph import cli

    monkeypatch.setattr(
        md, "packages_distributions",
        lambda: {"openspec_graph": ["planlint", "planlint"]},
    )
    monkeypatch.setattr(md, "version", lambda dist: __version__)
    captured: list[str] = []
    monkeypatch.setattr(
        cli, "print",
        lambda *a, **k: captured.append(" ".join(str(x) for x in a)),
        raising=False,
    )

    assert __version__ in cli._version_string()
    assert not captured, f"warned about a non-ambiguous environment: {captured}"


def test_scaffolded_project_doc_names_the_current_distribution() -> None:
    """`planlint init` must not write a package name that no longer exists.

    The scaffold template named `openspec-graph` -- the distribution the 0.2.0
    notes tell users to uninstall -- so every repository scaffolded by this
    release would have carried a reference to a package that is gone, and
    contradicted itself two lines later where it says `planlint`.
    """
    source = (REPO_ROOT / "openspec_graph" / "scaffold.py").read_text(encoding="utf-8")
    assert "openspec-graph" not in source, (
        "scaffold.py still writes the pre-rename distribution name into "
        "scaffolded repositories"
    )
