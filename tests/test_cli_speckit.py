"""CLI-level tests for a SpecKit-only repo -- no openspec/ ancestor at all
(add-speckit-dialect, Milestone 3).

Every rule active before Milestone 4's G002/G003 exemption lands must still
pass cleanly against this fixture, so these tests exercise a genuine exit 0,
not just "didn't hit the discovery guard": no bare percentage/threshold
(G003), at least one negative-phrased criterion (G002), and at least one
requirement/criterion recognized at all (G001).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from tests.support import run_cli, write_speckit_spec, write_spec

GOOD_SPECKIT = textwrap.dedent(
    """\
    # Feature Specification: Demo Capability

    **Feature Branch**: `001-demo-capability`
    **Status**: Draft

    ## User Scenarios & Testing

    ### User Story 1 - Reject unattested writes (Priority: P1)

    **Acceptance Scenarios**:

    1. **Given** an unattested write, **When** validation runs, **Then** the write is rejected.

    ## Requirements

    ### Functional Requirements

    - **FR-001**: The system MUST attest every write.

    ## Success Criteria

    - **SC-001**: Every write is attested before acknowledgment.
    """
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


# --- AC-SK-19: validate/waivers succeed on a SpecKit-only repo -------------


def test_cmd_validate_succeeds_on_a_speckit_only_repo(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "validate", "--fail-on", "ERROR")
    assert result.returncode == 0, result.stdout + result.stderr


def test_cmd_waivers_succeeds_on_a_speckit_only_repo(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "waivers")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no waivers found" in result.stdout


# --- AC-SK-20 (non-success): still exit 2 with neither tree ----------------


def test_cmd_validate_exits_2_with_neither_openspec_nor_speckit(repo: Path) -> None:
    result = run_cli(repo, "validate")
    assert result.returncode == 2
    assert "no openspec/ directory" in result.stderr
    assert "no SpecKit specs/ tree" in result.stderr


def test_cmd_waivers_exits_2_with_neither_openspec_nor_speckit(repo: Path) -> None:
    result = run_cli(repo, "waivers")
    assert result.returncode == 2
    assert "no openspec/ directory" in result.stderr
    assert "no SpecKit specs/ tree" in result.stderr


# --- AC-SK-21: graph succeeds on a SpecKit-only repo ------------------------


def test_build_graph_succeeds_on_a_speckit_only_repo(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "graph", "--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    graph = json.loads(result.stdout)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert any("FR-001" in nid for nid in node_ids)


def test_cmd_graph_exits_2_with_neither_openspec_nor_speckit(repo: Path) -> None:
    result = run_cli(repo, "graph")
    assert result.returncode == 2


# --- AC-SK-22 (non-success): cmd_graph --change stays openspec-only -------


def test_cmd_graph_change_stays_openspec_only_on_a_speckit_only_repo(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "graph", "--change", "some-change")
    assert result.returncode == 2
    assert "no openspec/ directory" in result.stderr


# --- AC-SK-25: cmd_detect reports SpecKit presence --------------------------


def test_cmd_detect_text_output_reports_speckit_presence(repo: Path) -> None:
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "detect")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "specs/ (SpecKit)  present" in result.stdout


def test_cmd_detect_text_output_reports_speckit_absence(repo: Path) -> None:
    result = run_cli(repo, "detect")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "specs/ (SpecKit)  ABSENT" in result.stdout


# --- AC-SK-6/AC-SK-27: coexistence + no regression for openspec-only -------


def test_cmd_validate_unions_both_roots_when_both_present(repo: Path) -> None:
    write_spec(
        repo, "c1", "cap1",
        "# Spec: Demo\n\n## Requirements\n\n- R-DMO-1: x MUST y.\n\n"
        "## Acceptance Criteria\n\n- [ ] **AC-DMO-1:** z is verified.\n"
        "  _Verified by:_ `pytest -k test_z`\n",
    )
    write_speckit_spec(repo, "001-demo-capability", GOOD_SPECKIT)
    result = run_cli(repo, "validate", "--json")
    payload = json.loads(result.stdout)
    assert payload["specs_checked"] == 2
