"""Tests for the SpecKit parser and parse_spec()'s dispatch fix
(add-speckit-dialect, Milestone 2).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from openspec_graph import parse, parse_semantics
from openspec_graph.parse import parse_spec, scenario_has_gwt
from openspec_graph.parse_speckit import parse_speckit

GOOD_SPECKIT = Path(__file__).resolve().parent.joinpath("fixtures", "good_speckit.md").read_text(
    encoding="utf-8"
)


@pytest.fixture
def spec_path(tmp_path: Path) -> Path:
    path = tmp_path / "spec.md"
    path.write_text(GOOD_SPECKIT, encoding="utf-8")
    return path


# --- AC-SK-14: FR-/SC- mapping ----------------------------------------------


def test_parse_speckit_maps_fr_and_sc_ids() -> None:
    reqs, criteria = parse_speckit(GOOD_SPECKIT)
    req_idents = {r.ident for r in reqs}
    assert req_idents == {"FR-001", "FR-002"}
    assert all(r.kind == "functional" for r in reqs)
    crit_idents = {c.ident for c in criteria}
    assert "SC-001" in crit_idents


def test_parse_speckit_fr_decl_does_not_match_a_sibling_nfr_bullet() -> None:
    text = textwrap.dedent(
        """\
        ## Requirements

        ### Functional Requirements

        - **FR-001**: The system MUST do X.

        ### Non-Functional Requirements

        - **NFR-001**: The system SHOULD be fast.
        """
    )
    reqs, _ = parse_speckit(text)
    assert {r.ident for r in reqs} == {"FR-001"}


# --- AC-SK-15: Given/When/Then synthesis ------------------------------------


def test_parse_speckit_synthesizes_user_story_criteria() -> None:
    _, criteria = parse_speckit(GOOD_SPECKIT)
    gwt_criteria = [c for c in criteria if c.ident.startswith("US1-AS")]
    assert len(gwt_criteria) == 1
    assert gwt_criteria[0].ident == "US1-AS1"
    assert scenario_has_gwt(gwt_criteria[0])


def test_parse_speckit_synthesizes_a_multi_line_gwt_scenario() -> None:
    # Milestone 5 finding: Given/When/Then each on their own line, within
    # the same numbered item, is an equally plausible SpecKit authoring
    # style GWT_SCENARIO's original single-line-only form missed.
    text = textwrap.dedent(
        """\
        ## User Scenarios & Testing

        ### User Story 1 - Do X (Priority: P1)

        1. **Given** an attested writer
           **When** a write occurs
           **Then** an evidence id is recorded

        ## Requirements

        ### Functional Requirements

        - **FR-001**: The system MUST do X.
        """
    )
    _, criteria = parse_speckit(text)
    gwt = [c for c in criteria if c.ident.startswith("US1-AS")]
    assert len(gwt) == 1
    assert scenario_has_gwt(gwt[0])
    assert "an evidence id is recorded" in gwt[0].note


def test_parse_speckit_bounds_each_story_block_at_the_next_story_heading() -> None:
    text = textwrap.dedent(
        """\
        ## User Scenarios & Testing

        ### User Story 1 - Do X (Priority: P1)

        1. **Given** a precondition, **When** an action, **Then** an outcome.

        ### User Story 2 - Do Y (Priority: P2)

        1. **Given** another precondition, **When** another action, **Then** another outcome.

        ## Requirements

        ### Functional Requirements

        - **FR-001**: The system MUST do X.
        """
    )
    _, criteria = parse_speckit(text)
    story1 = [c for c in criteria if c.ident.startswith("US1-AS")]
    story2 = [c for c in criteria if c.ident.startswith("US2-AS")]
    assert len(story1) == 1
    assert len(story2) == 1
    assert "another precondition" in story2[0].note


def test_parse_speckit_bounds_a_trailing_story_block_at_the_next_h2_section() -> None:
    # The last (only) user story has no following "### User Story" heading
    # to bound it -- it must still not sweep the unrelated "## Requirements"
    # section's FR bullets into its own scenario-scanning span.
    text = textwrap.dedent(
        """\
        ## User Scenarios & Testing

        ### User Story 1 - Do X (Priority: P1)

        1. **Given** a precondition, **When** an action, **Then** an outcome.

        ## Requirements

        ### Functional Requirements

        - **FR-001**: The system MUST do X.
        """
    )
    reqs, criteria = parse_speckit(text)
    assert len(reqs) == 1
    gwt_criteria = [c for c in criteria if c.ident.startswith("US1-AS")]
    assert len(gwt_criteria) == 1


# --- AC-SK-17 (non-success): requirement_refs always empty ------------------


def test_speckit_criteria_have_no_requirement_refs() -> None:
    _, criteria = parse_speckit(GOOD_SPECKIT)
    assert criteria
    assert all(c.requirement_refs == () for c in criteria)


# --- AC-SK-12/13: parse_spec() dispatch -------------------------------------


def test_parse_spec_dispatches_speckit_to_its_own_parser(spec_path: Path) -> None:
    spec = parse_spec(spec_path, "speckit")
    assert spec.dialect == "speckit"
    assert {r.ident for r in spec.requirements} == {"FR-001", "FR-002"}


def test_parse_spec_auto_resolution_checks_upstream_then_speckit_then_harness(
    spec_path: Path,
) -> None:
    for dialect in ("auto", "mixed", "unknown"):
        spec = parse_spec(spec_path, dialect)
        assert spec.dialect == "speckit"


# --- AC-SK-16 (non-success): the speckit branch's own escape hatch ---------


def test_speckit_branch_rescues_to_upstream(tmp_path: Path) -> None:
    # Explicitly dialect="speckit", but the text has no FR-/SC- markers at
    # all -- parse_speckit() finds nothing -- while an upstream-style
    # "### Requirement:" heading is present. Must reclassify as upstream,
    # matching (not exceeding) the existing harness branch's own hatch.
    text = textwrap.dedent(
        """\
        ## ADDED Requirements

        ### Requirement: the writer SHALL attest every write

        Prose obligation.
        """
    )
    path = tmp_path / "spec.md"
    path.write_text(text, encoding="utf-8")
    spec = parse_spec(path, "speckit")
    assert spec.dialect == "upstream"
    assert len(spec.requirements) == 1


def test_no_reciprocal_speckit_rescue_hatch_for_harness(tmp_path: Path) -> None:
    # Explicitly dialect="harness" on text with real speckit content
    # (FR-/SC- bullets) but no harness R-/AC- declarations. parse_harness()
    # finds nothing, but there's no upstream "### Requirement:" heading
    # either, so the existing harness->upstream hatch doesn't fire, and no
    # harness->speckit hatch exists to fire instead (R-SK-15) -- the spec
    # stays classified harness with zero requirements/criteria recognized.
    path = tmp_path / "spec.md"
    path.write_text(GOOD_SPECKIT, encoding="utf-8")
    spec = parse_spec(path, "harness")
    assert spec.dialect == "harness"
    assert spec.requirements == ()
    assert spec.criteria == ()


# --- AC-SK-41 (parse.py half): shared predicates, not a local reimplementation


def test_parse_py_uses_shared_marker_predicates_not_local_copies() -> None:
    assert parse.is_upstream_marked is parse_semantics.is_upstream_marked
    assert parse.is_speckit_marked is parse_semantics.is_speckit_marked
