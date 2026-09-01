"""Tests for SpecKit discovery: the speckit_root/feature_dirs fields on
StackProfile, find_speckit_spec_files()/filter_speckit_by_feature(), and the
3-way detect_dialect() rewrite (add-speckit-dialect, Milestone 1).

A real SpecKit repo has no openspec/ ancestor at all -- files live at
specs/<NNN-feature>/spec.md, at the repo root. These tests construct that
shape directly, distinct from every existing fixture in test_graft.py, which
all assume an openspec/ tree.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from openspec_graph import detect, parse_semantics
from tests import support
from tests.support import write_spec, write_speckit_spec

_CAN_SYMLINK = support.supports_symlinks()

GOOD_SPECKIT = textwrap.dedent(
    """\
    # Feature Specification: Demo Capability

    **Feature Branch**: `001-demo-capability`
    **Status**: Draft

    ## Requirements

    ### Functional Requirements

    - **FR-001**: The system MUST attest every write.

    ## Success Criteria

    - **SC-001**: 95% of writes are attested within 1 second.
    """
)

# An OpenAPI-style pointer doc that happens to sit at a path shaped exactly
# like a SpecKit spec.md, but carries none of SpecKit's own markers -- the
# false-positive spec-adversary demonstrated against the pre-fix design.
UNMARKED_SPEC_MD = textwrap.dedent(
    """\
    # user-service API

    See `openapi.yaml` in this directory for the full contract.
    """
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


# --- AC-SK-2: per-file content-gated discovery ------------------------------


def test_find_speckit_spec_files_discovers_feature_spec_files(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    found = detect.find_speckit_spec_files(repo / "specs")
    assert found == [repo / "specs" / "001-demo-capability" / "spec.md"]


def test_find_speckit_spec_files_returns_empty_for_a_bare_specs_dir(repo: Path) -> None:
    (repo / "specs").mkdir()
    assert detect.find_speckit_spec_files(repo / "specs") == []


# --- AC-SK-45 (non-success): per-file content gate excludes unmarked files --


def test_find_speckit_spec_files_excludes_unmarked_spec_md_even_alongside_genuine_ones(
    repo: Path,
) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    write_speckit_spec(repo, "user-service", UNMARKED_SPEC_MD)
    found = detect.find_speckit_spec_files(repo / "specs")
    assert found == [repo / "specs" / "001-demo-capability" / "spec.md"]


# --- AC-SK-3: filter_speckit_by_feature -------------------------------------


def test_filter_speckit_by_feature_narrows_to_one_feature(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    write_speckit_spec(repo, "002-other-capability", GOOD_SPECKIT)
    all_files = detect.find_speckit_spec_files(repo / "specs")
    assert len(all_files) == 2
    narrowed = detect.filter_speckit_by_feature(all_files, "001-demo-capability")
    assert narrowed == [repo / "specs" / "001-demo-capability" / "spec.md"]


# --- AC-SK-44 (non-success): plan.md/tasks.md never returned/parsed --------


def test_speckit_discovery_never_returns_plan_or_tasks_md(repo: Path) -> None:
    feature_dir = repo / "specs" / "001-demo-capability"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(GOOD_SPECKIT, encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nFR-001 implementation plan.", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n- [ ] Task 1", encoding="utf-8")
    found = detect.find_speckit_spec_files(repo / "specs")
    assert found == [feature_dir / "spec.md"]


# --- AC-SK-4 (non-success) / AC-SK-4: profile()'s root-level content gate --


def test_profile_does_not_set_speckit_root_for_a_specs_dir_with_no_spec_md(repo: Path) -> None:
    (repo / "specs" / "some-dir").mkdir(parents=True)
    (repo / "specs" / "some-dir" / "openapi.yaml").write_text("openapi: 3.0.0", encoding="utf-8")
    prof = detect.profile(repo)
    assert prof.speckit_root is None
    assert prof.feature_dirs == ()


def test_profile_sets_speckit_root_and_unions_spec_files(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    prof = detect.profile(repo)
    assert prof.speckit_root == repo / "specs"
    assert prof.dialect == "speckit"


def test_profile_supports_both_openspec_root_and_speckit_root_together(repo: Path) -> None:
    write_spec(repo, "c1", "cap1", "# Spec: Demo\n\n## Requirements\n\n- R-DMO-1: x MUST y.\n")
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    prof = detect.profile(repo)
    assert prof.openspec_root == repo / "openspec"
    assert prof.speckit_root == repo / "specs"


# --- AC-SK-47: feature_dirs derives from content-gated results only --------


def test_feature_dirs_derives_from_content_gated_spec_files_only(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    write_speckit_spec(repo, "user-service", UNMARKED_SPEC_MD)
    prof = detect.profile(repo)
    assert prof.feature_dirs == (repo / "specs" / "001-demo-capability",)


# --- AC-SK-7: detect_dialect() classifies speckit markers -------------------


def test_detect_dialect_classifies_speckit_markers(repo: Path) -> None:
    fr_only = textwrap.dedent(
        """\
        ## Requirements

        ### Functional Requirements

        - **FR-001**: The system MUST do X.
        """
    )
    sc_only = textwrap.dedent(
        """\
        ## Success Criteria

        - **SC-001**: 95% of users do Y.
        """
    )
    for body in (fr_only, sc_only, GOOD_SPECKIT):
        path = write_speckit_spec(repo, "001-demo-capability", body)
        assert detect.detect_dialect([path]) == "speckit"


# --- AC-SK-8: 3-way "mixed" = present > 1 -----------------------------------


def test_detect_dialect_reports_mixed_for_more_than_one_dialect_present(repo: Path) -> None:
    harness_path = write_spec(
        repo, "c1", "cap1", "# Spec: Demo\n\n## Acceptance Criteria\n\n- [ ] **AC-DMO-1:** x. \n"
    )
    speckit_path = write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    assert detect.detect_dialect([harness_path, speckit_path]) == "mixed"

    upstream_path = write_spec(
        repo, "c2", "cap2", "## ADDED Requirements\n\n#### Scenario: x\n"
    )
    assert detect.detect_dialect([harness_path, speckit_path, upstream_path]) == "mixed"


def test_detect_dialect_reports_speckit_alone_as_speckit(repo: Path) -> None:
    path = write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    assert detect.detect_dialect([path]) == "speckit"


# --- AC-SK-10 (non-success): [NEEDS CLARIFICATION] alone is not a marker ---


def test_needs_clarification_alone_does_not_classify_as_speckit(repo: Path) -> None:
    body = "# Feature Specification\n\nSome text [NEEDS CLARIFICATION: what threshold?].\n"
    path = write_speckit_spec(repo, "001-demo-capability", body)
    # find_speckit_spec_files itself excludes this (not is_speckit_marked),
    # so exercise detect_dialect directly against the raw path list, mirroring
    # what a caller bypassing discovery (e.g. an explicit --dialect auto) sees.
    assert detect.detect_dialect([path]) == "unknown"


# --- AC-SK-41 (partial -- detect.py half; parse.py half lands in Milestone 2)


# --- defensive OSError branches (mirrors test_adr_directory_read_error_is_
# skipped_not_crashed's broken-symlink technique for the pre-existing ADR
# scan) ------------------------------------------------------------------


@pytest.mark.skipif(not _CAN_SYMLINK, reason="platform/user lacks symlink-creation privilege")
def test_detect_dialect_skips_an_unreadable_spec_path_not_crashes(repo: Path) -> None:
    good = write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    broken = repo / "specs" / "002-broken" / "spec.md"
    broken.parent.mkdir(parents=True)
    broken.symlink_to(repo / "specs" / "002-broken" / "does-not-exist.md")
    assert detect.detect_dialect([good, broken]) == "speckit"


def test_find_speckit_spec_files_skips_an_unreadable_candidate_not_crashes(repo: Path) -> None:
    # A directory literally named "spec.md" still matches the glob (the
    # entry exists) but read_text() raises IsADirectoryError -- an OSError
    # subclass -- portable across platforms, unlike a broken symlink: glob's
    # own existence check (os.path.exists(), which follows symlinks) excludes
    # a dangling symlink from "*/spec.md" results before the loop body ever
    # runs, so that construction can't reach this except-branch at all.
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    (repo / "specs" / "002-broken" / "spec.md").mkdir(parents=True)
    found = detect.find_speckit_spec_files(repo / "specs")
    assert found == [repo / "specs" / "001-demo-capability" / "spec.md"]


def test_detect_dialect_uses_shared_marker_predicates_not_local_copies() -> None:
    # detect.py must import parse_semantics's predicates, not reimplement
    # them inline a third time -- confirmed by identity, not just behavior,
    # so a future accidental local redefinition in detect.py is caught even
    # if it happens to behave the same on today's fixtures.
    assert detect.is_upstream_marked is parse_semantics.is_upstream_marked
    assert detect.is_harness_marked is parse_semantics.is_harness_marked
    assert detect.is_speckit_marked is parse_semantics.is_speckit_marked
