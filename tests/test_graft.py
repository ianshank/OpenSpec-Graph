"""Tests for openspec-graph.

The important tests are the negative ones: a linter that never fails is a
decoration. Each rule gets a fixture that violates it and an assertion that
the rule fires on exactly that violation.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from openspec_graph import detect, rules, scaffold
from openspec_graph.cli import main
from openspec_graph.parse import parse_spec

MAKEFILE = textwrap.dedent(
    """\
    .PHONY: help test regression ci
    help: ## show help
    \t@echo hi
    test: ## run tests
    \tpytest
    regression: ## regression tier
    \tpytest tests/regression
    ci: test regression ## full
    \t@echo ok
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

CONTRACT = "# Contract\n\n- INV-1 no unattested writes\n- INV-2 gates are ordered\n"

GOOD_HARNESS = textwrap.dedent(
    """\
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

    ## Validation Matrix

    | Stage | Make Target | Pass Criteria |
    |---|---|---|
    | Focused | `make regression` | AC-DMO-1..2 |
    """
)

GOOD_UPSTREAM = textwrap.dedent(
    """\
    # Spec delta — Demo capability

    ## ADDED Requirements

    ### Requirement: the writer SHALL attest every write

    Prose obligation.

    #### Scenario: attested writes record an evidence id

    - **GIVEN** an attested writer
    - **WHEN** `make regression` runs the suite
    - **THEN** an evidence id is recorded

    #### Scenario: an unattested write is caught before merge

    - **GIVEN** a writer with no attestation
    - **WHEN** the suite runs
    - **THEN** the check fails and names the offending file
    """
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(MAKEFILE)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "CONTRACT.md").write_text(CONTRACT)
    return tmp_path


def write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def findings_for(repo: Path, body: str, dialect: str = "auto") -> list[rules.Finding]:
    path = write_spec(repo, "demo-change", "demo-capability", body)
    prof = detect.profile(repo)
    return rules.evaluate(parse_spec(path, dialect), prof)


def rule_ids(found: list[rules.Finding]) -> set[str]:
    return {f.rule for f in found}


# --- detection -------------------------------------------------------------


def test_detect_reads_threshold_from_pyproject(repo: Path) -> None:
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 90
    assert "pyproject.toml" in prof.threshold.locator


def test_detect_prefers_governance_policy_over_pyproject(repo: Path) -> None:
    (repo / "governance-policy.json").write_text(json.dumps({"coverage": {"lines": 85}}))
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 85
    assert "governance-policy.json" in prof.threshold.locator


def test_detect_reads_threshold_from_coveragerc(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (repo / ".coveragerc").write_text("[report]\nfail_under = 88\n")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 88
    assert ".coveragerc" in prof.threshold.locator


def test_detect_reads_threshold_from_setup_cfg(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (repo / "setup.cfg").write_text("[coverage:report]\nfail_under = 82\n")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 82
    assert "setup.cfg" in prof.threshold.locator


def test_detect_prefers_coveragerc_over_setup_cfg(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (repo / ".coveragerc").write_text("[report]\nfail_under = 88\n")
    (repo / "setup.cfg").write_text("[coverage:report]\nfail_under = 70\n")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 88


def test_detect_still_prefers_pyproject_over_coveragerc(repo: Path) -> None:
    # repo fixture's pyproject.toml already sets fail_under = 90 -- confirms
    # the additive-only precedence: pyproject.toml keeps winning.
    (repo / ".coveragerc").write_text("[report]\nfail_under = 70\n")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 90


def test_detect_finds_make_targets_and_ignores_phony(repo: Path) -> None:
    prof = detect.profile(repo)
    assert {"test", "regression", "ci", "help"} <= set(prof.make_targets)
    assert ".PHONY" not in prof.make_targets


def test_detect_collects_invariant_ids(repo: Path) -> None:
    prof = detect.profile(repo)
    assert prof.invariant_ids == ("INV-1", "INV-2")


def test_dialect_detection_distinguishes_both_forms(repo: Path) -> None:
    harness = write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    upstream = write_spec(repo, "c2", "cap2", GOOD_UPSTREAM)
    assert detect.detect_dialect([harness]) == "harness"
    assert detect.detect_dialect([upstream]) == "upstream"
    assert detect.detect_dialect([harness, upstream]) == "mixed"


def test_dialect_unknown_when_no_specs() -> None:
    assert detect.detect_dialect([]) == "unknown"


# --- clean baselines -------------------------------------------------------


def test_good_harness_spec_has_no_errors(repo: Path) -> None:
    found = findings_for(repo, GOOD_HARNESS)
    assert [f for f in found if f.severity == "ERROR"] == []


def test_good_upstream_spec_has_no_errors(repo: Path) -> None:
    found = findings_for(repo, GOOD_UPSTREAM)
    assert [f for f in found if f.severity == "ERROR"] == []


# --- negative cases, one per rule -----------------------------------------


def test_g001_fires_when_no_criteria(repo: Path) -> None:
    body = "# Spec: Empty\n\n## Requirements\n\n- R-DMO-1: MUST do a thing.\n"
    assert "G001" in rule_ids(findings_for(repo, body, "harness"))


def test_g002_fires_when_every_criterion_is_a_happy_path(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "**AC-DMO-2 (non-success):** An unattested write is denied and the\n  error names INV-1.",
        "**AC-DMO-2:** A second attested write also records an id.",
    )
    found = rule_ids(findings_for(repo, body))
    assert "G002" in found, "spec with no failure path must be rejected"


def test_g003_fires_on_hard_coded_threshold(repo: Path) -> None:
    # 95%, not the repo fixture's real floor of 90 -- this line has exactly
    # one threshold-shaped number, and it does NOT match, so it stays a
    # genuine violation after the value-comparison suppression lands.
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Line coverage is at least 95% for the new module.",
    )
    assert "G003" in rule_ids(findings_for(repo, body))


def test_g003_suppresses_a_bare_number_that_matches_the_real_threshold(repo: Path) -> None:
    # The repo fixture's real floor is 90 -- a single, unambiguous, matching
    # number needs no locator name to be excused.
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Line coverage is at least 90% for the new module.",
    )
    assert "G003" not in rule_ids(findings_for(repo, body))


def test_g003_still_fires_on_the_non_matching_number_in_a_same_line_collision(repo: Path) -> None:
    # Two threshold-shaped numbers on one line, only one matching the real
    # floor -- must never suppress on a coincidental match to unrelated text.
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Coverage moved from 80% to 90% after the refactor.",
    )
    assert "G003" in rule_ids(findings_for(repo, body))


def test_g003_allows_a_threshold_read_from_the_policy_locator(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Coverage meets the floor in `pyproject.toml` (currently 90%).",
    )
    assert "G003" not in rule_ids(findings_for(repo, body))


def test_g003_allows_a_threshold_read_from_coveragerc(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (repo / ".coveragerc").write_text("[report]\nfail_under = 90\n")
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Coverage meets the floor in `.coveragerc` (currently 90%).",
    )
    assert "G003" not in rule_ids(findings_for(repo, body))


def test_g004_fires_on_a_make_target_the_target_repo_lacks(repo: Path) -> None:
    body = GOOD_HARNESS.replace("make regression", "make test-governance")
    found = findings_for(repo, body)
    assert "G004" in rule_ids(found)
    assert any("test-governance" in f.message for f in found)


def test_g004_does_not_fire_on_a_bare_english_use_of_make(repo: Path) -> None:
    # Lowercase "make sure"/"make progress" in ordinary prose, with no
    # backtick-fencing, must not be treated as a stage citation.
    body = GOOD_HARNESS.replace(
        "An attested write records an evidence id.",
        "Reviewers make sure every write is attested, so the team can make progress.",
    )
    assert "G004" not in rule_ids(findings_for(repo, body))


def test_g005_fires_on_an_undeclared_invariant(repo: Path) -> None:
    body = GOOD_HARNESS.replace("INV-1", "INV-99")
    found = findings_for(repo, body)
    assert "G005" in rule_ids(found)
    assert any("INV-99" in f.message for f in found)


def test_h001_fires_when_an_ac_has_no_verification(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "  _Verified by:_ `pytest -k test_attested_write` · stage: `make regression`\n",
        "",
    )
    assert "H001" in rule_ids(findings_for(repo, body, "harness"))


def test_h001_fires_when_verification_names_no_stage(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "`pytest -k test_attested_write` · stage: `make regression`",
        "`pytest -k test_attested_write`",
    )
    found = findings_for(repo, body, "harness")
    assert "H001" in rule_ids(found)


def test_h003_fires_on_an_orphan_requirement(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "- C-DMO-1: The change MUST NOT weaken INV-1.",
        "- C-DMO-1: The change MUST NOT weaken INV-1.\n- R-DMO-9: MUST also do an untested thing.",
    )
    found = findings_for(repo, body, "harness")
    assert "H003" in rule_ids(found)
    assert any("R-DMO-9" in f.message for f in found)


def test_h004_fires_on_duplicate_criterion_ids(repo: Path) -> None:
    body = GOOD_HARNESS.replace("**AC-DMO-2 (non-success):**", "**AC-DMO-1 (non-success):**")
    assert "H004" in rule_ids(findings_for(repo, body, "harness"))


def test_h005_fires_when_a_blocking_question_survives_draft(repo: Path) -> None:
    body = GOOD_HARNESS.replace("**Status:** DRAFT", "**Status:** APPROVED")
    body += "\n## Open Questions\n\n> **DEC-DMO-001 (BLOCKING):** unresolved.\n"
    assert "H005" in rule_ids(findings_for(repo, body, "harness"))


def test_h006_fires_on_a_missing_required_section(repo: Path) -> None:
    body = GOOD_HARNESS.replace("## Validation Matrix", "## Notes")
    assert "H006" in rule_ids(findings_for(repo, body, "harness"))


def test_u001_fires_without_a_delta_header(repo: Path) -> None:
    body = GOOD_UPSTREAM.replace("## ADDED Requirements", "## Requirements")
    assert "U001" in rule_ids(findings_for(repo, body, "upstream"))


def test_u002_fires_on_a_requirement_with_no_scenario(repo: Path) -> None:
    body = GOOD_UPSTREAM + "\n### Requirement: the reader SHALL verify ids\n\nProse.\n"
    found = findings_for(repo, body, "upstream")
    assert "U002" in rule_ids(found)


def test_u003_fires_on_a_scenario_missing_then(repo: Path) -> None:
    body = GOOD_UPSTREAM.replace("- **THEN** an evidence id is recorded", "- it works")
    assert "U003" in rule_ids(findings_for(repo, body, "upstream"))


def test_u004_fires_on_a_non_normative_requirement(repo: Path) -> None:
    body = GOOD_UPSTREAM.replace(
        "### Requirement: the writer SHALL attest every write",
        "### Requirement: the writer attests writes",
    )
    assert "U004" in rule_ids(findings_for(repo, body, "upstream"))


def test_u004_does_not_fire_when_the_modal_verb_is_only_in_the_body(repo: Path) -> None:
    # Regression: Requirement.text used to be populated from the heading match
    # alone, so a heading with no SHALL/MUST but a normative body still
    # false-fired U004 -- the common real-world authoring style.
    body = GOOD_UPSTREAM.replace(
        "### Requirement: the writer SHALL attest every write",
        "### Requirement: the writer attests every write",
    ).replace(
        "Prose obligation.",
        "The writer SHALL record an evidence id for every write.",
    )
    assert "U004" not in rule_ids(findings_for(repo, body, "upstream"))


# --- scaffolding -----------------------------------------------------------


def test_scaffold_uses_a_stage_that_exists_in_the_target(repo: Path) -> None:
    prof = detect.profile(repo)
    plans = scaffold.plan_change(prof, "add-thing", "thing-capability", "harness")
    spec = next(p for p in plans if p.path.name == "spec.md")
    assert "make regression" in spec.content
    assert "make test-governance" not in spec.content


def test_scaffolded_spec_passes_its_own_validator(repo: Path) -> None:
    prof = detect.profile(repo)
    for dialect in ("harness", "upstream"):
        plans = scaffold.plan_change(prof, f"add-{dialect}", "demo-capability", dialect)
        scaffold.apply(plans)
    prof = detect.profile(repo)
    errors = []
    for path in detect.find_spec_files(repo / "openspec"):
        errors += [
            f for f in rules.evaluate(parse_spec(path, "auto"), prof) if f.severity == "ERROR"
        ]
    assert errors == [], [f.render() for f in errors]


def test_scaffold_references_the_detected_threshold_locator(repo: Path) -> None:
    prof = detect.profile(repo)
    plans = scaffold.plan_change(prof, "add-thing", "thing-capability", "harness")
    spec = next(p for p in plans if p.path.name == "spec.md")
    assert "pyproject.toml" in spec.content


def test_apply_is_idempotent_and_refuses_to_clobber(repo: Path) -> None:
    prof = detect.profile(repo)
    plans = scaffold.plan_change(prof, "add-thing", "thing-capability", "harness")
    first = scaffold.apply(plans)
    assert len(first) == 3
    spec = next(p for p in plans if p.path.name == "spec.md").path
    spec.write_text("EDITED BY HAND")
    replanned = scaffold.plan_change(prof, "add-thing", "thing-capability", "harness")
    assert scaffold.apply(replanned) == []
    assert spec.read_text() == "EDITED BY HAND"
    assert len(scaffold.apply(replanned, force=True)) == 3


def test_init_pins_detected_conventions(repo: Path) -> None:
    prof = detect.profile(repo)
    scaffold.apply(scaffold.plan_init(prof))
    config = json.loads((repo / "openspec" / "specgraph.json").read_text())
    assert config["focused_stage"] == "regression"
    assert "pyproject.toml" in config["threshold_locator"]
    assert config["invariant_source"] == "CONTRACT.md"


# --- CLI contract ----------------------------------------------------------


def test_cli_validate_exits_nonzero_on_a_bad_spec(repo: Path, capsys) -> None:
    write_spec(repo, "bad-change", "bad-cap", GOOD_HARNESS.replace("make regression", "make nope"))
    assert main(["--target", str(repo), "validate"]) == 1
    assert "G004" in capsys.readouterr().out


def test_cli_validate_exits_zero_on_a_clean_spec(repo: Path) -> None:
    write_spec(repo, "ok-change", "ok-cap", GOOD_HARNESS)
    assert main(["--target", str(repo), "validate"]) == 0


def test_cli_validate_fail_on_warn_is_stricter(repo: Path) -> None:
    write_spec(repo, "warn-change", "warn-cap", GOOD_HARNESS.replace("INV-1", "INV-77"))
    assert main(["--target", str(repo), "validate"]) == 0
    assert main(["--target", str(repo), "validate", "--fail-on", "WARN"]) == 1


def test_cli_detect_json_is_machine_readable(repo: Path, capsys) -> None:
    assert main(["--target", str(repo), "detect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["threshold"]["value"] == 90


def test_cli_dry_run_writes_nothing(repo: Path) -> None:
    assert main(["--target", str(repo), "new", "x", "--capability", "y", "--dry-run"]) == 0
    assert not (repo / "openspec" / "changes" / "x").exists()


# --- regressions found by running against real repositories ----------------
# Each of these encodes a false positive or misleading message that the first
# version of the rule engine produced against ianshank/Mouse-Droid-AGI.


def test_g002_accepts_a_negation_phrased_as_absence(repo: Path) -> None:
    """'opens no egress channel' is a non-success scenario. G002 must not fire.

    Regression: the original phrase-list detector missed it and reported a
    false positive against openspec/changes/mouse-droid-cloud-egress-default-off.
    """
    body = textwrap.dedent(
        """\
        # Spec delta — Cloud egress

        ## ADDED Requirements

        ### Requirement: egress SHALL default to off

        Prose.

        #### Scenario: a partial GCP block opens no egress channel

        - **GIVEN** a partially configured GCP block
        - **WHEN** `make regression` runs
        - **THEN** the resolver opens no egress channel
        """
    )
    assert "G002" not in rule_ids(findings_for(repo, body, "upstream"))


def test_g002_accepts_mutates_neither(repo: Path) -> None:
    body = GOOD_UPSTREAM.replace(
        "- **THEN** the check fails and names the offending file",
        "- **THEN** it mutates neither the remote nor the local tag list",
    ).replace("caught before merge", "reported in dry-run")
    assert "G002" not in rule_ids(findings_for(repo, body, "upstream"))


def test_g002_still_fires_on_a_genuinely_happy_only_upstream_spec(repo: Path) -> None:
    body = textwrap.dedent(
        """\
        # Spec delta — Happy path only

        ## ADDED Requirements

        ### Requirement: the exporter SHALL emit a metric

        Prose.

        #### Scenario: the metric appears

        - **GIVEN** a running exporter
        - **WHEN** `make regression` runs
        - **THEN** the metric appears in the registry
        """
    )
    assert "G002" in rule_ids(findings_for(repo, body, "upstream"))


def test_shallow_headings_are_parsed_and_reported_as_drift(repo: Path) -> None:
    """`## Requirement:` / `### Scenario:` must parse, then trip U005.

    Regression: openspec/changes/mouse-droid-deploy-repin uses H2/H3 while its
    nine sibling packages use H3/H4. The first version reported 'no criteria
    found', which blamed the author for a parser limitation.
    """
    body = GOOD_UPSTREAM.replace("### Requirement:", "## Requirement:").replace(
        "#### Scenario:", "### Scenario:"
    )
    found = findings_for(repo, body, "upstream")
    ids = rule_ids(found)
    assert "G001" not in ids, "criteria must be recognized at non-canonical depths"
    assert "U005" in ids
    assert any("H2" in f.message or "H3" in f.message for f in found)


def test_numbered_req_headings_are_recognized_as_requirements(repo: Path) -> None:
    """`## REQ 1: ...` is a third in-repo form; report it accurately."""
    body = textwrap.dedent(
        """\
        # Specification: NemoClaw Integration

        ## REQ 1: Live Memory Query

        The bridge SHALL answer a live memory query.

        ## REQ 2: Transport-Identical Gating

        Gating SHALL be identical across transports.
        """
    )
    found = findings_for(repo, body, "upstream")
    assert "G001" in rule_ids(found)
    assert any("no Scenario or acceptance" in f.message for f in found)
    assert "U002" in rule_ids(found), "each REQ should be reported as scenario-less"


def test_waiver_downgrades_a_finding_to_info_and_stays_visible(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement",
        "<!-- specgraph:allow G003 this spec's subject IS the 85% hook floor -->\n\n## Problem Statement",
    ).replace(
        "An attested write records an evidence id.",
        "The documented hook floor stays pinned at 85%.",
    )
    found = findings_for(repo, body, "harness")
    g003 = [f for f in found if f.rule == "G003"]
    assert g003, "the waived rule must still appear in the report"
    assert all(f.severity == "INFO" for f in g003)
    assert all("[waived]" in f.message for f in g003)


def test_waiver_does_not_leak_to_other_rules(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G003 -->\n\n## Problem Statement"
    ).replace("make regression", "make nope")
    found = findings_for(repo, body, "harness")
    assert any(f.rule == "G004" and f.severity == "ERROR" for f in found)


def test_cli_validate_passes_when_the_only_error_is_waived(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G003 -->\n\n## Problem Statement"
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    write_spec(repo, "waived-change", "waived-cap", body)
    assert main(["--target", str(repo), "validate"]) == 0
