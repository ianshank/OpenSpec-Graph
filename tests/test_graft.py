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

from openspec_graph import detect, dialect_card, rules, scaffold
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


def tree_findings_for(repo: Path, bodies: list[tuple[str, str, str]], dialect: str = "auto") -> list[rules.Finding]:
    """bodies: (change, capability, body) tuples, each written as its own spec."""
    specs = [parse_spec(write_spec(repo, change, capability, body), dialect) for change, capability, body in bodies]
    return rules.evaluate_tree(specs, detect.profile(repo))


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


def test_detect_ignores_malformed_governance_policy_json(repo: Path) -> None:
    (repo / "governance-policy.json").write_text("{not valid json")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 90
    assert "pyproject.toml" in prof.threshold.locator


def test_detect_ignores_malformed_coveragerc(repo: Path) -> None:
    # No [section] header at all -- reliably raises configparser's
    # MissingSectionHeaderError, unlike text that might parse leniently.
    (repo / ".coveragerc").write_text("this is not valid ini content at all")
    prof = detect.profile(repo)
    assert prof.threshold is not None
    assert prof.threshold.value == 90
    assert "pyproject.toml" in prof.threshold.locator


def test_detect_finds_make_targets_and_ignores_phony(repo: Path) -> None:
    prof = detect.profile(repo)
    assert {"test", "regression", "ci", "help"} <= set(prof.make_targets)
    assert ".PHONY" not in prof.make_targets


def test_g004_stays_silent_when_the_target_repo_has_no_makefile_at_all(repo: Path) -> None:
    (repo / "Makefile").unlink()
    prof = detect.profile(repo)
    assert prof.make_targets == ()
    assert prof.make_target_confidence == "high"  # vacuous: nothing was seen to lower confidence
    body = GOOD_HARNESS.replace("make regression", "make nope")
    found = findings_for(repo, body)
    assert "G004" not in rule_ids(found)


def test_make_targets_json_shape_is_a_list_of_strings(repo: Path) -> None:
    # AC-MP-7: byte-identical shape (list[str], sorted), regardless of how
    # machinery.py computes the underlying values.
    payload = detect.profile(repo).as_dict()
    assert isinstance(payload["make_targets"], list)
    assert all(isinstance(t, str) for t in payload["make_targets"])
    assert payload["make_targets"] == sorted(payload["make_targets"])


def test_to_card_excludes_absolute_paths(repo: Path) -> None:
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    card = detect.profile(repo).to_card()
    assert "root" not in card
    assert "openspec_root" not in card
    assert card["has_openspec_root"] is True
    assert card["schema_version"] == dialect_card.SCHEMA_VERSION


def test_to_card_reports_no_openspec_root_when_absent(repo: Path) -> None:
    card = detect.profile(repo).to_card()
    assert card["has_openspec_root"] is False


def test_detect_format_json_emits_a_dialect_card_with_schema_version(
    repo: Path, capsys
) -> None:
    assert main(["--target", str(repo), "detect", "--format", "json"]) == 0
    card = json.loads(capsys.readouterr().out)
    assert card["schema_version"] == dialect_card.SCHEMA_VERSION
    assert "root" not in card


def test_detect_format_json_is_byte_identical_across_runs(repo: Path, capsys) -> None:
    main(["--target", str(repo), "detect", "--format", "json"])
    first = capsys.readouterr().out
    main(["--target", str(repo), "detect", "--format", "json"])
    second = capsys.readouterr().out
    assert first == second


def test_detect_format_json_card_is_identical_across_different_checkout_paths(
    tmp_path_factory, capsys
) -> None:
    # The strongest proof of the portability property AC-DC-1/2 need: the
    # same logical repo at two different absolute paths must yield a
    # byte-identical card end-to-end, not just at the to_card() unit level.
    def _build(root: Path) -> None:
        (root / "Makefile").write_text(MAKEFILE)
        (root / "pyproject.toml").write_text(PYPROJECT)
        write_spec(root, "c1", "cap1", GOOD_HARNESS)

    root_a = tmp_path_factory.mktemp("checkout_a")
    root_b = tmp_path_factory.mktemp("checkout_b_longer_name")
    _build(root_a)
    _build(root_b)

    main(["--target", str(root_a), "detect", "--format", "json"])
    card_a = capsys.readouterr().out
    main(["--target", str(root_b), "detect", "--format", "json"])
    card_b = capsys.readouterr().out
    assert card_a == card_b


def test_detect_json_flag_still_emits_full_profile_unchanged(repo: Path, capsys) -> None:
    assert main(["--target", str(repo), "detect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "root" in payload
    assert "schema_version" not in payload


def test_detect_format_json_takes_precedence_over_legacy_json_flag(repo: Path, capsys) -> None:
    # Passing both --json and --format json together is an edge case a
    # user could plausibly hit (habitually adding --json alongside the
    # newer --format flag). --format json wins: it's the more specific,
    # explicitly-requested output mode. Documented here so the precedence
    # is a tested contract, not an accident of check-ordering.
    assert main(["--target", str(repo), "detect", "--json", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "schema_version" in payload, "the card (--format json) must win over the legacy --json shape"
    assert "root" not in payload


def test_detect_diff_exits_nonzero_and_lists_changed_fields_on_drift(
    repo: Path, tmp_path: Path, capsys
) -> None:
    main(["--target", str(repo), "detect", "--format", "json"])
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(capsys.readouterr().out)

    (repo / "Makefile").write_text(MAKEFILE + "new-target:\n\techo hi\n")
    result = main(["--target", str(repo), "detect", "--diff", str(baseline_path)])
    out = capsys.readouterr().out
    assert result == 1
    assert "make_targets" in out


def test_detect_diff_exits_zero_on_no_drift(repo: Path, tmp_path: Path, capsys) -> None:
    main(["--target", str(repo), "detect", "--format", "json"])
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(capsys.readouterr().out)

    result = main(["--target", str(repo), "detect", "--diff", str(baseline_path)])
    out = capsys.readouterr().out
    assert result == 0
    assert "PASS" in out


def test_detect_diff_with_missing_baseline_is_a_usage_error(repo: Path) -> None:
    result = main(["--target", str(repo), "detect", "--diff", "/nonexistent/baseline.json"])
    assert result == 2


def test_detect_diff_with_valid_json_non_object_baseline_is_a_usage_error(
    repo: Path, tmp_path: Path, capsys
) -> None:
    # A baseline file can be syntactically valid JSON (null, a list, a
    # number) while still not being a card at all. json.loads() succeeds
    # on all of these, so this must be checked explicitly -- without it,
    # dialect_card.diff_cards()'s .get() calls raise AttributeError,
    # which prints a traceback and exits 1, indistinguishable from "real
    # drift found" and violating the documented 0/1/2 exit contract.
    for bad_baseline in ("null", "[]", "42", '"just a string"'):
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(bad_baseline)
        result = main(["--target", str(repo), "detect", "--diff", str(baseline_path)])
        assert result == 2, f"baseline {bad_baseline!r} should be a usage error, got exit {result}"
        assert "expected a JSON object" in capsys.readouterr().err


def test_detect_never_writes_to_the_target_repo(repo: Path) -> None:
    # AC-DC-3 (non-success): detect.py's own module docstring already
    # promises read-only; this proves it holds across every detect output
    # mode, not just the default text one.
    write_spec(repo, "c1", "cap1", GOOD_HARNESS)
    before = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}

    assert main(["--target", str(repo), "detect"]) == 0
    assert main(["--target", str(repo), "detect", "--json"]) == 0
    assert main(["--target", str(repo), "detect", "--format", "json"]) == 0

    after = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}
    assert set(before) == set(after), "detect must never create or delete a file in the target repo"
    assert before == after, "detect must never modify a file in the target repo"


def test_multi_target_makefile_line_resolves_both_targets_end_to_end(repo: Path) -> None:
    (repo / "Makefile").write_text(MAKEFILE + "lint typecheck: test\n\techo ok\n")
    prof = detect.profile(repo)
    assert {"lint", "typecheck"} <= set(prof.make_targets)
    assert prof.make_target_confidence == "high"


def test_define_block_does_not_leak_a_bogus_target_through_the_legacy_widening_fallback(
    repo: Path,
) -> None:
    # A define block lowers machinery.py's confidence, which triggers
    # detect.py's legacy-regex widening fallback -- that fallback has the
    # identical define/endef blindness machinery.py was fixed for, so
    # fixing machinery.py alone is not sufficient end-to-end.
    (repo / "Makefile").write_text(MAKEFILE + "\ndefine HELP_TEXT\nUsage: make test\nendef\n")
    prof = detect.profile(repo)
    assert "Usage" not in prof.make_targets
    assert prof.make_target_confidence == "low"


def test_unterminated_define_block_does_not_hang_detect_end_to_end(repo: Path) -> None:
    # The shared O(n) strip_define_blocks implementation must keep
    # detect.profile() fast even through the legacy-fallback path, not
    # just when calling machinery.parse_makefile directly.
    import time

    (repo / "Makefile").write_text(MAKEFILE + "\ndefine X\n" + ("body line\n" * 20000))
    start = time.monotonic()
    prof = detect.profile(repo)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"detect.profile() took {elapsed:.2f}s on an unterminated define block"
    assert prof.make_target_confidence == "low"


def test_cli_detect_reports_low_confidence_makefile_parse(repo: Path, capsys) -> None:
    (repo / "Makefile").write_text("include extra.mk\nbuild:\n\techo hi\n")
    assert main(["--target", str(repo), "detect"]) == 0
    assert "low confidence" in capsys.readouterr().out.lower()


def test_g004_still_fires_on_a_genuinely_absent_target_at_low_confidence(repo: Path) -> None:
    # AC-MP-4 (non-success): low confidence must never weaken the rule.
    (repo / "Makefile").write_text(MAKEFILE + "include extra.mk\n")
    body = GOOD_HARNESS.replace("make regression", "make totally-nonexistent")
    found = findings_for(repo, body)
    assert "G004" in rule_ids(found)


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


def test_g001_fires_when_neither_requirements_nor_criteria_are_recognized(repo: Path) -> None:
    # Distinct from test_g001_fires_when_no_criteria: that fixture has
    # requirements but no criteria (rules_generic.py's `if` branch); this one
    # has neither (the `else` branch), which was previously untested.
    body = "# Spec: Empty\n\nJust prose; no requirements or acceptance criteria at all.\n"
    found = findings_for(repo, body, "harness")
    matching = [f for f in found if f.rule == "G001"]
    assert matching, "G001 must fire when nothing is recognized"
    assert any("no requirements and no verifiable criteria" in f.message for f in matching), (
        "must hit the 'neither' branch's message, not the 'requirements but no criteria' branch"
    )


def test_harness_dialect_falls_back_to_upstream_when_the_text_is_actually_upstream(
    repo: Path,
) -> None:
    # A repo classified "harness" but this one file is written in upstream
    # form -- _parse_harness finds nothing, but the text matches the
    # upstream REQUIREMENT pattern, so parse_spec must re-parse it as
    # upstream rather than reporting a false G001 "no criteria" finding.
    # This is the per-file misclassification safety net for mixed repos.
    path = write_spec(repo, "demo-change", "demo-capability", GOOD_UPSTREAM)
    parsed = parse_spec(path, "harness")
    assert parsed.dialect == "upstream"
    assert parsed.requirements and parsed.criteria

    found = findings_for(repo, GOOD_UPSTREAM, "harness")
    assert "G001" not in rule_ids(found), "the upstream-form criteria must be recognized, not missed"


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


def test_g006_fires_for_a_declared_invariant_no_spec_cites(repo: Path) -> None:
    # repo's own CONTRACT.md declares INV-1 and INV-2; GOOD_HARNESS only
    # cites INV-1, so INV-2 is a real, pre-existing orphan in this fixture.
    found = tree_findings_for(repo, [("demo-change", "demo-cap", GOOD_HARNESS)])
    g006 = [f for f in found if f.rule == "G006"]
    assert g006 and all(f.severity == "WARN" for f in g006)
    assert any(f.subject == "INV-2" for f in g006)
    assert any("INV-2" in f.message and "CONTRACT.md" in f.message for f in g006)


def test_g006_does_not_fire_once_cited_anywhere_in_the_tree(repo: Path) -> None:
    other = GOOD_HARNESS.replace("INV-1", "INV-2").replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2")
    found = tree_findings_for(
        repo,
        [("c1", "cap1", GOOD_HARNESS), ("c2", "cap2", other)],
    )
    assert "G006" not in rule_ids(found)


def test_g006_is_downgraded_to_info_when_waived_anywhere_in_the_tree(repo: Path) -> None:
    # Reason text deliberately avoids the INV-n pattern itself -- invariant_refs
    # scans the whole raw text unconditionally, so naming the invariant here
    # would make the waiver comment itself count as a citation and resolve
    # the orphan before the waiver-downgrade path is even exercised.
    body = GOOD_HARNESS.replace(
        "## Problem Statement",
        "<!-- specgraph:allow G006 the second contract invariant is a future "
        "gate, not yet wired into any spec -->\n\n## Problem Statement",
    )
    found = tree_findings_for(repo, [("demo-change", "demo-cap", body)])
    g006 = [f for f in found if f.rule == "G006"]
    assert g006 and all(f.severity == "INFO" and "[waived]" in f.message for f in g006)


def test_g006_is_skipped_under_change_scoping(repo: Path, capsys) -> None:
    # other-change alone cites INV-2; a naive --change-filtered evaluate_tree()
    # would falsely call INV-2 orphaned since that citation sits outside the
    # filtered view. Confirms it's skipped outright instead (DEC-WL-003).
    write_spec(repo, "demo-change", "demo-cap", GOOD_HARNESS)
    other = GOOD_HARNESS.replace("INV-1", "INV-2").replace("AC-DMO", "AC-DM2").replace("R-DMO", "R-DM2")
    write_spec(repo, "other-change", "other-cap", other)
    exit_code = main(["--target", str(repo), "validate", "--change", "demo-change"])
    out = capsys.readouterr()
    assert exit_code == 0
    assert "G006" not in out.out
    assert "G006 skipped" in out.err


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


# --- U003: GIVEN is optional (fix-u003-mandatory-given) --------------------
#
# Every negative body below is a single targeted `.replace()` mutation of
# GOOD_UPSTREAM, so the passing and failing fixtures cannot drift (AC-UG-5).

_GIVEN_LINE = "- **GIVEN** an attested writer\n"
_WHEN_LINE = "- **WHEN** `make regression` runs the suite"
_THEN_LINE = "- **THEN** an evidence id is recorded"

NO_GIVEN_UPSTREAM = GOOD_UPSTREAM.replace(_GIVEN_LINE, "")
MISSING_WHEN_UPSTREAM = GOOD_UPSTREAM.replace(_WHEN_LINE, "- the suite runs")
MISSING_THEN_UPSTREAM = GOOD_UPSTREAM.replace(_THEN_LINE, "- it works")


def test_u003_accepts_a_scenario_without_given(repo: Path) -> None:
    """AC-UG-1: WHEN + THEN with no GIVEN is executable and must not fire.

    Regression for a 100% false-positive rate: run against an external
    upstream-dialect corpus, U003 reported 66 of 68 scenarios, and every one
    of them carried WHEN and THEN while omitting only GIVEN.
    """
    assert "GIVEN" not in NO_GIVEN_UPSTREAM.split("#### Scenario:")[1]
    assert "U003" not in rule_ids(findings_for(repo, NO_GIVEN_UPSTREAM, "upstream"))


def test_u003_still_fires_when_when_is_absent(repo: Path) -> None:
    """AC-UG-2: a scenario with no stimulus is still not executable."""
    assert "U003" in rule_ids(findings_for(repo, MISSING_WHEN_UPSTREAM, "upstream"))


def test_u003_still_fires_when_then_is_absent(repo: Path) -> None:
    """AC-UG-3: a scenario that asserts no outcome is still not executable."""
    assert "U003" in rule_ids(findings_for(repo, MISSING_THEN_UPSTREAM, "upstream"))


def test_u003_accepts_a_full_gwt_scenario(repo: Path) -> None:
    """AC-UG-4: the previously accepted three-clause shape is not lost."""
    assert "U003" not in rule_ids(findings_for(repo, GOOD_UPSTREAM, "upstream"))


def test_u003_negative_fixtures_are_mutations_of_the_positive() -> None:
    """AC-UG-5: each failing fixture differs from the passing one by one clause."""
    for mutated, removed in (
        (NO_GIVEN_UPSTREAM, _GIVEN_LINE.strip()),
        (MISSING_WHEN_UPSTREAM, _WHEN_LINE),
        (MISSING_THEN_UPSTREAM, _THEN_LINE),
    ):
        assert mutated != GOOD_UPSTREAM, "mutation must actually change the fixture"
        assert removed in GOOD_UPSTREAM, "the clause must exist in the source fixture"
        assert removed not in mutated, "the mutation must remove exactly that clause"


def test_u003_summary_does_not_require_given() -> None:
    """AC-UG-6: the rule must stop advertising a check it no longer makes."""
    u003 = next(r for r in rules.RULES if r.ident == "U003")
    assert "GIVEN" not in u003.summary.upper()


def test_u002_unchanged_by_the_u003_fix(repo: Path) -> None:
    """AC-UG-7: a requirement with no scenario at all still fires U002."""
    body = NO_GIVEN_UPSTREAM + "\n### Requirement: the reader SHALL verify ids\n\nProse.\n"
    assert "U002" in rule_ids(findings_for(repo, body, "upstream"))


def test_rule_registry_baseline_is_unchanged() -> None:
    """AC-UG-8: no rule id added, no finding emitted for an omitted GIVEN."""
    import json

    baseline = json.loads(
        (Path(__file__).resolve().parent / "baseline_rules.json").read_text(encoding="utf-8")
    )
    assert {r["id"] for r in baseline} == {r.ident for r in rules.RULES}
    assert len(baseline) == len(rules.RULES)


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
    # Reason required (CP-4/G007): a reason-less waiver would now also trip
    # G007, so this fixture must carry one to keep testing what it always
    # meant to test -- a *justified* waiver passing.
    body = GOOD_HARNESS.replace(
        "## Problem Statement",
        "<!-- specgraph:allow G003 95% is this spec's own coverage floor -->\n\n## Problem Statement",
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    write_spec(repo, "waived-change", "waived-cap", body)
    assert main(["--target", str(repo), "validate"]) == 0


def test_cli_validate_fails_when_a_waiver_has_no_reason(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G003 -->\n\n## Problem Statement"
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    write_spec(repo, "waived-change", "waived-cap", body)
    assert main(["--target", str(repo), "validate"]) == 1


def test_unreasoned_waiver_downgrades_the_named_rule_and_also_fires_g007(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G003 -->\n\n## Problem Statement"
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    found = findings_for(repo, body, "harness")
    g003 = [f for f in found if f.rule == "G003"]
    g007 = [f for f in found if f.rule == "G007"]
    assert g003 and all(f.severity == "INFO" and "[waived]" in f.message for f in g003)
    assert g007 and all(f.severity == "ERROR" for f in g007)
    assert any("G003" in f.message for f in g007)


def test_reasoned_waiver_does_not_trip_g007(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement",
        "<!-- specgraph:allow G003 this spec's subject IS the 95% coverage floor -->"
        "\n\n## Problem Statement",
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    assert "G007" not in rule_ids(findings_for(repo, body, "harness"))


def test_g007_fires_regardless_of_dialect(repo: Path) -> None:
    body = GOOD_UPSTREAM.replace(
        "## ADDED Requirements", "<!-- specgraph:allow G002 -->\n\n## ADDED Requirements"
    )
    assert "G007" in rule_ids(findings_for(repo, body, "upstream"))


def test_g007_is_not_suppressible_by_waiving_itself_without_a_reason(repo: Path) -> None:
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G007 -->\n\n## Problem Statement"
    )
    g007 = [f for f in findings_for(repo, body, "harness") if f.rule == "G007"]
    assert g007 and all(f.severity == "ERROR" for f in g007)


def test_multi_rule_waiver_with_no_reason_fires_one_g007_per_waived_rule(repo: Path) -> None:
    # A single comment naming N rules expands to N Waiver records (one per
    # rule, all sharing that comment's reason/line) -- so an unreasoned
    # multi-rule waiver produces one independent G007 finding per name, not
    # one finding for the whole comment.
    body = GOOD_HARNESS.replace(
        "## Problem Statement", "<!-- specgraph:allow G003,G004 -->\n\n## Problem Statement"
    ).replace("An attested write records an evidence id.", "Coverage is at least 95%.")
    g007 = [f for f in findings_for(repo, body, "harness") if f.rule == "G007"]
    assert len(g007) == 2
    messages = " ".join(f.message for f in g007)
    assert "G003" in messages and "G004" in messages


def test_suppressions_unchanged_behavior_after_waiver_refactor() -> None:
    from openspec_graph.parse_semantics import suppressions

    text = "<!-- specgraph:allow G003, G004 because reasons -->"
    assert suppressions(text) == {"G003", "G004"}
