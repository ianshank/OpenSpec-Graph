"""External-target corpus: foreign package shapes and per-rule negatives (XTV M2).

Two gaps this closes:

1. Every change package in this repository is exactly three files
   (``proposal.md``, ``tasks.md``, ``specs/<capability>/spec.md``). Other repos
   author OpenSpec packages in a five-file shape that also carries ``design.md``
   and ``review.md``. Nothing here had ever been run against one.
2. The rule set is only trustworthy if each rule has a fixture that *fails* it.
   Every negative below is a single targeted mutation of the passing fixture, so
   the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openspec_graph import detect, rules
from openspec_graph.cli import main
from openspec_graph.parse import parse_spec
from tests.support import write_spec

# --- base fixtures ---------------------------------------------------------

GOOD_HARNESS = """\
# Spec: Demo Capability

> **Status:** DRAFT

## Problem Statement

**Evidence:** `demo/mod.py::run` writes without attestation.

## Requirements

- R-DMO-1: The system MUST attest every write.
- C-DMO-1: The change MUST NOT weaken INV-1.

## Acceptance Criteria

- [ ] **AC-DMO-1:** An attested write records an evidence id. (R-DMO-1)
  _Verified by:_ `pytest -k test_attested_write` · stage: `make regression`

- [ ] **AC-DMO-2 (non-success):** An unattested write is denied and the
  error names INV-1. (C-DMO-1)
  _Verified by:_ `pytest -k test_unattested_denied` · stage: `make regression`

## Invariants Touched

- INV-1: preserved, proven by AC-DMO-2.

## Open Questions

- **DEC-DMO-001 (BLOCKING):** unresolved while the status stays DRAFT.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make regression` | AC-DMO-1..2 |
"""

GOOD_UPSTREAM = """\
# Spec delta — Demo capability

## ADDED Requirements

### Requirement: the writer SHALL attest every write

Prose obligation.

#### Scenario: attested writes record an evidence id

- **GIVEN** an attested writer
- **WHEN** `make regression` runs the suite
- **THEN** an evidence id is recorded

#### Scenario: an unattested write is caught before merge

- **WHEN** the suite runs without attestation
- **THEN** the check fails and names the offending file
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(
        ".PHONY: help test regression ci\n"
        "help: ## h\n\t@echo hi\n"
        "test: ## t\n\tpytest\n"
        "regression: ## r\n\tpytest tests/regression\n"
        "ci: test regression ## c\n\t@echo ok\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n\n[tool.coverage.report]\nfail_under = 90\n'
    )
    (tmp_path / "CONTRACT.md").write_text(
        "# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n"
    )
    return tmp_path


def _findings(repo: Path, body: str, dialect: str) -> set[str]:
    path = write_spec(repo, "demo-change", "demo-capability", body)
    return {f.rule for f in rules.evaluate(parse_spec(path, dialect), detect.profile(repo))}


# --- per-rule mutated negatives (AC-XTV-6) ---------------------------------
#
# (rule, dialect, base, find, replace). Each entry is ONE targeted substitution.

# The full acceptance-criteria block, so G001's negative can remove *all*
# criteria in one substitution -- dropping only one leaves the other and the
# rule correctly stays silent.
_AC_BLOCK = """\
- [ ] **AC-DMO-1:** An attested write records an evidence id. (R-DMO-1)
  _Verified by:_ `pytest -k test_attested_write` \u00b7 stage: `make regression`

- [ ] **AC-DMO-2 (non-success):** An unattested write is denied and the
  error names INV-1. (C-DMO-1)
  _Verified by:_ `pytest -k test_unattested_denied` \u00b7 stage: `make regression`
"""

MUTATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("G001", "harness", GOOD_HARNESS, _AC_BLOCK, "To be written.\n"),
    ("G002", "harness", GOOD_HARNESS,
     "**AC-DMO-2 (non-success):** An unattested write is denied and the\n  error names INV-1.",
     "**AC-DMO-2:** A second attested write also records an id."),
    ("G003", "harness", GOOD_HARNESS,
     "| Focused | `make regression` | AC-DMO-1..2 |",
     "| Focused | `make regression` | AC-DMO-1..2 at 95% |"),
    ("G004", "harness", GOOD_HARNESS,
     "stage: `make regression`\n\n- [ ] **AC-DMO-2",
     "stage: `make nonexistent`\n\n- [ ] **AC-DMO-2"),
    ("G005", "harness", GOOD_HARNESS,
     "- INV-1: preserved, proven by AC-DMO-2.",
     "- INV-99: preserved, proven by AC-DMO-2."),
    ("G007", "harness", GOOD_HARNESS,
     "## Validation Matrix",
     "<!-- specgraph:allow G003 -->\n\n## Validation Matrix"),
    ("H001", "harness", GOOD_HARNESS,
     "  _Verified by:_ `pytest -k test_attested_write` · stage: `make regression`\n", ""),
    ("H002", "harness", GOOD_HARNESS,
     "An attested write records an evidence id. (R-DMO-1)",
     "An attested write records an evidence id."),
    ("H003", "harness", GOOD_HARNESS,
     "- R-DMO-1: The system MUST attest every write.",
     "- R-DMO-1: The system MUST attest every write.\n- R-DMO-9: The system MUST rotate keys."),
    ("H004", "harness", GOOD_HARNESS,
     "- [ ] **AC-DMO-2 (non-success):**", "- [ ] **AC-DMO-1 (non-success):**"),
    ("H005", "harness", GOOD_HARNESS,
     "> **Status:** DRAFT", "> **Status:** APPROVED"),
    ("H006", "harness", GOOD_HARNESS, "## Validation Matrix", "## Notes"),
    ("U001", "upstream", GOOD_UPSTREAM, "## ADDED Requirements", "## Requirements"),
    ("U002", "upstream", GOOD_UPSTREAM,
     "#### Scenario: attested writes record an evidence id",
     "### Requirement: the reader SHALL verify ids\n\nProse.\n\n#### Scenario: attested writes record an evidence id"),
    ("U003", "upstream", GOOD_UPSTREAM,
     "- **THEN** an evidence id is recorded", "- it works"),
    ("U004", "upstream", GOOD_UPSTREAM,
     "### Requirement: the writer SHALL attest every write\n\nProse obligation.",
     "### Requirement: the writer attests every write\n\nProse."),
    ("U005", "upstream", GOOD_UPSTREAM,
     "#### Scenario: attested writes record an evidence id",
     "##### Scenario: attested writes record an evidence id"),
)

# G006 is a tree-level rule: it reports invariants declared in the target repo
# that no *living spec* cites, so it cannot fire from a single parsed spec and
# has its own test below rather than an entry in the per-spec table.
_TREE_LEVEL_RULES = {"G006"}


@pytest.mark.parametrize(
    ("rule_id", "dialect", "base", "find", "replace"), MUTATIONS, ids=[m[0] for m in MUTATIONS]
)
def test_every_rule_has_a_mutated_negative_fixture(
    repo: Path, rule_id: str, dialect: str, base: str, find: str, replace: str
) -> None:
    """AC-XTV-6: the passing fixture is clean of this rule; one mutation trips it."""
    assert base.count(find) == 1, f"{rule_id}: mutation anchor must be unique"
    mutated = base.replace(find, replace)
    assert mutated != base, f"{rule_id}: mutation changed nothing"

    assert rule_id not in _findings(repo, base, dialect), f"{rule_id} fired on the passing fixture"
    assert rule_id in _findings(repo, mutated, dialect), f"{rule_id} did not fire on its negative"


def test_g006_fires_on_an_invariant_no_living_spec_cites(repo: Path) -> None:
    """AC-XTV-6 (tree level): INV-2 is declared in CONTRACT.md and cited nowhere."""
    path = write_spec(repo, "demo-change", "demo-capability", GOOD_HARNESS)
    found = rules.evaluate_tree([parse_spec(path, "harness")], detect.profile(repo))
    assert "G006" in {f.rule for f in found}


def test_the_mutation_table_covers_every_rule() -> None:
    """AC-XTV-6: no rule may be added without a negative fixture."""
    covered = {m[0] for m in MUTATIONS} | _TREE_LEVEL_RULES
    assert covered == {r.ident for r in rules.RULES}


# --- foreign package shape (AC-XTV-4, AC-XTV-5) ----------------------------


def _five_file_package(repo: Path, body: str) -> Path:
    """A package in the five-file shape other repositories author."""
    spec = write_spec(repo, "five-file", "foreign-capability", body)
    base = spec.parent.parent.parent
    (base / "proposal.md").write_text("# Change: Foreign\n\n## Why\n\nProse.\n")
    (base / "tasks.md").write_text("# Milestones\n\n## Milestone 1 — Do it  [TODO]\n")
    (base / "design.md").write_text("# Design\n\nNo required sections at all.\n")
    (base / "review.md").write_text("# Review\n\nLGTM. No Requirements heading here.\n")
    return spec


def test_five_file_package_shape_classifies_and_validates(repo: Path) -> None:
    """AC-XTV-4: design.md and review.md neither break detection nor validation."""
    _five_file_package(repo, GOOD_HARNESS)
    profile = detect.profile(repo)
    assert profile.dialect == "harness"
    assert main(["--target", str(repo), "validate", "--fail-on", "ERROR"]) == 0


def test_h006_scopes_required_sections_to_capability_specs(repo: Path) -> None:
    """AC-XTV-5: H006 judges spec.md only, but still fires on a real omission.

    Spec discovery is ``changes/*/specs/*/spec.md``, so design.md and review.md
    are never parsed and cannot be reported for missing a section they were
    never meant to carry.
    """
    _five_file_package(repo, GOOD_HARNESS)
    assert "H006" not in {f.rule for f in _all_findings(repo)}

    _five_file_package(repo, GOOD_HARNESS.replace("## Validation Matrix", "## Notes"))
    assert "H006" in {f.rule for f in _all_findings(repo)}


def _all_findings(repo: Path) -> list[rules.Finding]:
    """Compose findings the way ``cmd_validate`` does.

    ``evaluate()`` is per spec; ``evaluate_tree()`` returns only whole-tree
    findings (today just G006). Calling either alone silently drops half the
    rule set -- which is exactly the mistake this helper exists to avoid.
    """
    profile = detect.profile(repo)
    specs = [parse_spec(p, "auto") for p in detect.find_spec_files(repo / "openspec")]
    findings: list[rules.Finding] = []
    for spec in specs:
        findings.extend(rules.evaluate(spec, profile))
    findings.extend(rules.evaluate_tree(specs, profile))
    return findings


def test_external_corpus_run_modifies_neither_tree(repo: Path, tmp_path: Path) -> None:
    """AC-XTV-7: validating a foreign target leaves it byte-identical."""
    import hashlib

    _five_file_package(repo, GOOD_HARNESS)

    def fingerprint(root: Path) -> dict[str, str]:
        return {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    before = fingerprint(repo)
    assert main(["--target", str(repo), "validate", "--fail-on", "ERROR"]) in (0, 1)
    assert fingerprint(repo) == before
