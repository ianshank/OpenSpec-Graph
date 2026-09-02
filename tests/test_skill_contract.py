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
)

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
    for dirpath, _dirnames, filenames in os.walk(root):
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

    for argv in READ_ONLY_INVOCATIONS:
        run_cli(populated_repo, *argv)

    after = _tree_digest(populated_repo)
    created = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    assert not (created or removed or modified), (
        "a verb SKILL.md documents as read-only touched the target tree: "
        f"created={created} removed={removed} modified={modified}"
    )


def test_read_only_invocations_cover_every_verb_the_skill_calls_read_only() -> None:
    """The list above is only meaningful if it matches SKILL.md's own table."""
    text = SKILL_MD.read_text(encoding="utf-8")
    read_only_section = text.split("Read-only.", 1)[1].split("Writes files.", 1)[0]
    documented = set(re.findall(r"^\| `([a-z]+)` \|", read_only_section, re.MULTILINE))
    exercised = {argv[0] for argv in READ_ONLY_INVOCATIONS}
    assert documented == exercised, (
        f"SKILL.md's read-only table {sorted(documented)} and this test's "
        f"exercised set {sorted(exercised)} disagree"
    )


def test_write_verbs_are_documented_as_writing() -> None:
    """The complement: every verb that writes is in the writes-files table."""
    text = SKILL_MD.read_text(encoding="utf-8")
    writes_section = text.split("Writes files.", 1)[1].split("## Repairing", 1)[0]
    documented = set(re.findall(r"^\| `([a-z]+)` \|", writes_section, re.MULTILINE))
    assert documented == {"init", "new", "witness"}, (
        f"SKILL.md's write-verb table lists {sorted(documented)}"
    )


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


# --- AC-SD-2 / AC-SD-3: the generated catalog -------------------------------


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


def test_rule_catalog_check_fails_when_stale(tmp_path: Path) -> None:
    """AC-SD-3 (non-success): --check reports staleness rather than hiding it."""
    original = CATALOG.read_text(encoding="utf-8")
    try:
        CATALOG.write_text(original + "| Z999 | ERROR | any | invented |\n", encoding="utf-8")
        result = _run_renderer("--check")
        assert result.returncode == 1
        assert "STALE" in result.stderr
    finally:
        CATALOG.write_text(original, encoding="utf-8")


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
    assert dev_skills == {"planlint-add-rule"}


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
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "nht", REPO_ROOT / "tools" / "check_no_hardcoded_thresholds.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    workflows = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    assert len(workflows) > 1, (
        "this repo has only one workflow, so the glob fix is untestable here"
    )

    # The guard must flag a pinned floor in *any* workflow, not just ci.yml.
    for workflow in workflows:
        findings = mod.check_workflow(workflow)
        assert findings == [], f"{workflow.name} already trips the guard: {findings}"

    probe = REPO_ROOT / ".github" / "workflows" / "release.yml"
    assert probe.exists(), "release.yml is the non-ci workflow this pins"
    assert mod.check_workflow(probe) == []


def test_threshold_guard_flags_a_pinned_floor_in_a_non_ci_workflow(tmp_path: Path) -> None:
    """The matching half of AC-SD-13, on a file that is not ci.yml."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "nht", REPO_ROOT / "tools" / "check_no_hardcoded_thresholds.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fake = tmp_path / "release.yml"
    fake.write_text("jobs:\n  x:\n    steps:\n      - run: pytest --cov-fail-under=90\n")
    findings = mod.check_workflow(fake)
    assert findings, "a pinned coverage floor in a release workflow must be flagged"


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
