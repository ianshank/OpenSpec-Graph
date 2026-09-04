"""End-to-end: the installed CLI over the new corpora and matcher behaviour.

The unit and corpus tests call ``detect.profile()`` and the parsers in
process. This module drives the real command the way CI and an adopter do --
``python -m openspec_graph.cli`` as a subprocess through
``tests/support.run_cli`` -- so every fix on this branch is proven at the exit
code and stdout boundary, not only at the function boundary. It is the mock
track of ``docs/aqa.md``'s two-track e2e, extended to the labelled corpora.

Each test states which shipped defect it would have caught.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support import normalize_root, run_cli

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "tests" / "corpus" / "targets"
CANARY_PLACEHOLDER = "@@CANARY@@"


def _card(repo: Path) -> dict[str, object]:
    result = run_cli(repo, "detect", "--format", "json")
    assert result.returncode == 0, result.stderr
    card = json.loads(result.stdout)
    assert isinstance(card, dict)
    return card


def _harness_spec(repo: Path, body: str, change: str = "c1") -> Path:
    spec = repo / "openspec" / "changes" / change / "specs" / "cap" / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(body, encoding="utf-8")
    return spec


# --- detect, over every labelled shape, through the CLI --------------------


@pytest.mark.parametrize(
    "shape", sorted(p for p in CORPUS.iterdir() if (p / "expected.json").is_file()),
    ids=lambda p: p.name,
)
def test_detect_json_matches_the_labelled_card_through_the_cli(shape: Path) -> None:
    """The in-process corpus test proves ``profile()``; this proves the verb
    that ships emits the same card, byte-parseable, exit 0."""
    from openspec_graph import dialect_card

    expected = json.loads((shape / "expected.json").read_text(encoding="utf-8"))
    expected["schema_version"] = dialect_card.SCHEMA_VERSION
    drift = dialect_card.diff_cards(expected, _card(shape / "repo"))
    assert not drift, f"{shape.name}: " + "; ".join(drift)


def test_bom_makefile_no_longer_produces_a_false_g004(tmp_path: Path) -> None:
    """The headline defect: a valid repo told it cited a target it lacked."""
    shutil.copytree(CORPUS / "bom-rule-first" / "repo", tmp_path / "r")
    repo = tmp_path / "r"
    _harness_spec(
        repo,
        "## Requirements\n\n- R-XY-1: Builds are gated.\n\n## Acceptance Criteria\n\n"
        "- [ ] **AC-XY-1:** The build runs. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_a` · stage: `make all`\n"
        "- [ ] **AC-XY-2 (non-success):** A broken build fails `make all`. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_b` · stage: `make all`\n",
    )
    result = run_cli(repo, "validate", "--fail-on", "ERROR", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(normalize_root(result.stdout, repo))
    assert not [f for f in payload["findings"] if f["rule"] == "G004"], payload


def test_fractional_floor_round_trips_through_detect_diff(tmp_path: Path) -> None:
    """A saved baseline with 85.5 must diff clean against a live 85.5, and
    report drift -- exit 1 -- when the floor moves."""
    shutil.copytree(CORPUS / "float-coverage-floor" / "repo", tmp_path / "r")
    repo = tmp_path / "r"
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(_card(repo)), encoding="utf-8")
    assert run_cli(repo, "detect", "--diff", str(baseline)).returncode == 0

    (repo / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n\n[tool.coverage.report]\nfail_under = 86\n'
    )
    drifted = run_cli(repo, "detect", "--diff", str(baseline))
    assert drifted.returncode == 1
    assert "threshold" in drifted.stdout


def test_exact_fractional_citation_is_not_a_g003_through_the_cli(tmp_path: Path) -> None:
    """Before ``threshold_values`` learned fractions, this exited 1."""
    shutil.copytree(CORPUS / "float-coverage-floor" / "repo", tmp_path / "r")
    repo = tmp_path / "r"
    (repo / "Makefile").write_text("test:\n\t@echo t\n", encoding="utf-8")
    _harness_spec(
        repo,
        "## Requirements\n\n- R-XY-1: Coverage holds.\n\n## Acceptance Criteria\n\n"
        "- [ ] **AC-XY-1:** Line coverage is >= 85.5% as pyproject.toml gates it. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_a` · stage: `make test`\n"
        "- [ ] **AC-XY-2 (non-success):** A drop below the floor fails `make test`. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_b` · stage: `make test`\n",
    )
    result = run_cli(repo, "validate", "--fail-on", "ERROR")
    assert result.returncode == 0, result.stdout


def test_a_directory_named_makefile_exits_zero_not_traceback(tmp_path: Path) -> None:
    (tmp_path / "Makefile").mkdir()
    (tmp_path / "pyproject.toml").mkdir()
    result = run_cli(tmp_path, "detect")
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_hostile_makefile_is_inert_through_the_cli(tmp_path: Path) -> None:
    """The safety invariant at the process boundary, with a real path."""
    shutil.copytree(CORPUS / "hostile-makefile" / "repo", tmp_path / "r")
    repo = tmp_path / "r"
    canary = tmp_path / "canary"
    canary.mkdir()
    (canary / "keep.txt").write_text("must survive", encoding="utf-8")
    makefile = repo / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8").replace(CANARY_PLACEHOLDER, canary.as_posix()),
        encoding="utf-8",
    )
    card = _card(repo)
    assert (canary / "keep.txt").is_file()
    assert not any(canary.glob("*-touched.txt"))
    assert card["make_targets"] == ["all", "build", "test"]


# --- the prose matchers, through validate --------------------------------


def test_g002_is_not_satisfied_by_ordinary_prose_anymore(tmp_path: Path) -> None:
    """Under the flat pattern list, 'the block renders' and 'zero-downtime'
    satisfied G002 and the rule went silent. Now the spec draws the finding."""
    (tmp_path / "Makefile").write_text("test:\n\t@echo t\n", encoding="utf-8")
    _harness_spec(
        tmp_path,
        "## Requirements\n\n- R-XY-1: Pages render.\n\n## Acceptance Criteria\n\n"
        "- [ ] **AC-XY-1:** The block renders below the header. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_a` · stage: `make test`\n"
        "- [ ] **AC-XY-2:** The zero-downtime deploy completes. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_b` · stage: `make test`\n",
    )
    result = run_cli(tmp_path, "validate", "--fail-on", "ERROR", "--json")
    assert result.returncode == 1
    payload = json.loads(normalize_root(result.stdout, tmp_path))
    assert "G002" in {f["rule"] for f in payload["findings"]}, payload["findings"]


def test_waiver_reason_text_cannot_silence_g002_through_the_cli(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("test:\n\t@echo t\n", encoding="utf-8")
    _harness_spec(
        tmp_path,
        "## Requirements\n\n- R-XY-1: Pages render.\n\n## Acceptance Criteria\n\n"
        "- [ ] **AC-XY-1:** The page renders. "
        "<!-- specgraph:allow G003 the coverage floor fails otherwise --> (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_a` · stage: `make test`\n",
    )
    result = run_cli(tmp_path, "validate", "--fail-on", "ERROR", "--json")
    assert result.returncode == 1
    payload = json.loads(normalize_root(result.stdout, tmp_path))
    assert "G002" in {f["rule"] for f in payload["findings"]}


def test_u004_fires_on_shallow_clone_and_not_on_mustnt(tmp_path: Path) -> None:
    """Upstream dialect, through the CLI at WARN: the substring bug made
    'shallow' normative; the contraction is a real prohibition."""
    (tmp_path / "Makefile").write_text("test:\n\t@echo t\n", encoding="utf-8")
    _harness_spec(
        tmp_path,
        "## ADDED Requirements\n\n"
        "### Requirement: Clone depth\nA shallow clone of depth 1 is used for CI.\n\n"
        "#### Scenario: Depth\n- **WHEN** CI clones\n- **THEN** depth is 1 and the clone is not full\n\n"
        "### Requirement: Retries\nThe client mustn't retry a non-idempotent request.\n\n"
        "#### Scenario: Retry\n- **WHEN** a request is not idempotent\n- **THEN** it is not retried\n",
    )
    result = run_cli(tmp_path, "validate", "--fail-on", "WARN", "--json")
    assert result.returncode == 1
    payload = json.loads(normalize_root(result.stdout, tmp_path))
    u004 = [f["message"] for f in payload["findings"] if f["rule"] == "U004"]
    assert len(u004) == 1 and "Clone depth" in u004[0], payload["findings"]


# --- the tools and targets an adopter or contributor runs -----------------


def test_matcher_accuracy_tool_runs_headless_and_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "tools/matcher_accuracy.py", "--check", "--patterns"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "every configured floor met" in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(shutil.which("make") is None, reason="make not on PATH (capability probe)")
def test_make_matcher_accuracy_target_runs() -> None:
    result = subprocess.run(
        ["make", "matcher-accuracy"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "G002:" in result.stdout


def test_detect_debug_logging_names_the_rejected_floor(tmp_path: Path) -> None:
    """The 'why did planlint not see my floor?' answer, at the CLI boundary."""
    (tmp_path / "pyproject.toml").write_text("[tool.other]\nfail_under = 50\n", encoding="utf-8")
    result = run_cli(tmp_path, "detect", env={**os.environ, "PLANLINT_LOG_LEVEL": "DEBUG"})
    assert result.returncode == 0
    assert "fail_under found under [tool.other]" in result.stderr
