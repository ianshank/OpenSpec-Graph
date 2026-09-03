"""Hold the prose matchers to measured accuracy floors (CP-MA).

G002 and U004/S003 are the two rules that read English rather than structure,
and both have already shipped a defect of exactly that kind. Coverage proves
their code runs; a fixture proves each rule *can* fire. Neither says how often
either fires on the wrong sentence, which for G002 is the number that decides
whether the rule works at all: it asks only whether a spec carries **at least
one** non-success criterion, so one false positive anywhere switches it off.

The floors live in ``pyproject.toml`` under ``[tool.specgraph]`` -- never in
the Makefile or a workflow, which is this project's own rule G003 applied to
itself and enforced by ``tools/check_no_hardcoded_thresholds.py``.

Scoring lives in ``tools/matcher_accuracy.py`` so the gate and the
human-readable report can never disagree about what was measured.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "phrasing"


def _load_tool(name: str, filename: str) -> ModuleType:
    """Import a ``tools/`` script by path, in-process.

    Mirrors the helper of the same name in ``test_skill_contract.py`` and
    ``test_agent_artifacts.py``: in-process rather than as a subprocess so
    coverage sees the module and its functions can be called directly.
    """
    path = REPO_ROOT / "tools" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


accuracy = _load_tool("matcher_accuracy", "matcher_accuracy.py")


@pytest.fixture(scope="module")
def criteria_rows() -> list[dict[str, object]]:
    return accuracy.load_rows(accuracy.CRITERIA_CORPUS)


@pytest.fixture(scope="module")
def requirement_rows() -> list[dict[str, object]]:
    return accuracy.load_rows(accuracy.REQUIREMENTS_CORPUS)


# --- the corpus is real -----------------------------------------------------


def test_corpora_are_present_and_balanced(
    criteria_rows: list[dict[str, object]], requirement_rows: list[dict[str, object]]
) -> None:
    """A one-sided corpus scores well while proving nothing.

    Precision needs negatives to be wrong about and recall needs positives to
    miss, so a set that is all one label makes both metrics vacuous.
    """
    for name, rows in (("criteria", criteria_rows), ("requirements", requirement_rows)):
        assert len(rows) >= 20, f"{name} corpus is too small to measure anything"
        positives = sum(1 for r in rows if r["label"])
        assert 0 < positives < len(rows), f"{name} corpus is single-label"


def test_every_corpus_row_is_well_formed(
    criteria_rows: list[dict[str, object]], requirement_rows: list[dict[str, object]]
) -> None:
    """A row missing ``label`` would be silently scored as a negative."""
    for rows in (criteria_rows, requirement_rows):
        for row in rows:
            assert isinstance(row.get("text"), str) and row["text"].strip()
            assert isinstance(row.get("label"), bool)


def test_the_ambiguous_and_variant_files_assert_nothing() -> None:
    """Two files are kept as documentation, deliberately outside the score.

    ``criteria-ambiguous.jsonl`` holds the sentences the labeller could not
    decide -- an honest floor on inter-rater agreement that would be hidden by
    deleting them. ``requirements-modal-variants.jsonl`` holds requirements
    that are normative in spirit without using SHALL/MUST, which is a separate
    design question from the one U004's message actually claims to answer.
    Scoring either would measure a contract the rules never made.
    """
    for name in ("criteria-ambiguous.jsonl", "requirements-modal-variants.jsonl"):
        rows = accuracy.load_rows(CORPUS_DIR / name)
        assert rows, f"{name} exists but is empty"
    scored = {r["text"] for r in accuracy.load_rows(accuracy.CRITERIA_CORPUS)}
    documented = {r["text"] for r in accuracy.load_rows(CORPUS_DIR / "criteria-ambiguous.jsonl")}
    assert not (scored & documented), "a sentence is both scored and set aside as ambiguous"


# --- the floors -------------------------------------------------------------


@pytest.mark.parametrize("rule", sorted(accuracy.FLOOR_KEYS))
@pytest.mark.parametrize("metric", ["precision", "recall"])
def test_a_floor_is_configured_for_every_rule_and_metric(rule: str, metric: str) -> None:
    """A missing floor is a misconfiguration, never a skip.

    The same posture ``check_branch_coverage.py`` takes: a gate that passes
    because nobody configured it still reports green, which is worse than no
    gate at all.
    """
    precision_key, recall_key = accuracy.FLOOR_KEYS[rule]
    key = precision_key if metric == "precision" else recall_key
    assert accuracy._floor(key) is not None, (
        f"{key} is not set in pyproject.toml {accuracy.SPECGRAPH_TABLE}"
    )


def test_g002_meets_its_configured_accuracy_floors(
    criteria_rows: list[dict[str, object]],
) -> None:
    score = accuracy.score_criteria(criteria_rows)
    failures = accuracy._check(score)
    assert not failures, "\n".join(
        [*failures, f"false positives: {score.false_alarms}", f"misses: {score.misses}"]
    )


def test_u004_meets_its_configured_accuracy_floors(
    requirement_rows: list[dict[str, object]],
) -> None:
    score = accuracy.score_requirements(requirement_rows)
    failures = accuracy._check(score)
    assert not failures, "\n".join(
        [*failures, f"false positives: {score.false_alarms}", f"misses: {score.misses}"]
    )


def test_the_check_mode_exit_code_matches_the_scores() -> None:
    """The reporting path and the gating path must agree.

    ``--check`` is what a human runs and what a future make target would call;
    if it could pass while the assertions above fail, the report would be
    reassuring nonsense.
    """
    assert accuracy.main(["matcher_accuracy.py", "--check"]) == 0


# --- the pattern table is data, and stays honest ----------------------------


def test_no_negation_pattern_misfires_more_than_it_fires(
    criteria_rows: list[dict[str, object]],
) -> None:
    """The specific defect that made the flat pattern list score 0.38.

    ``\\bzero\\b`` scored 1 true positive against 5 false ones, and
    ``\\bblock(s|ed|ing)?\\b`` 1 against 6. Each was individually plausible and
    collectively they switched G002 off. A pattern that is wrong more often
    than it is right is not a detector.
    """
    offenders = {
        name: (hits, misfires)
        for name, (hits, misfires, _tier) in accuracy.pattern_breakdown(criteria_rows).items()
        if misfires > hits
    }
    assert not offenders, f"patterns that misfire more than they fire: {offenders}"


def test_every_negation_pattern_is_case_insensitive() -> None:
    """G002 must not depend on capitalisation.

    ``tests/test_properties.py`` proves this behaviourally over generated
    input; this proves it structurally, so a pattern added without the flag
    fails for an obvious reason rather than an obscure one.
    """
    import re

    from openspec_graph.parse_semantics import NEGATION_PATTERNS

    uncased = [p.name for p in NEGATION_PATTERNS if not p.pattern.flags & re.IGNORECASE]
    assert not uncased, f"negation patterns compiled without IGNORECASE: {uncased}"


def test_negation_pattern_names_are_unique() -> None:
    """Names are the reporting key; a duplicate would silently merge two rows."""
    from openspec_graph.parse_semantics import NEGATION_PATTERNS

    names = [p.name for p in NEGATION_PATTERNS]
    assert len(names) == len(set(names)), "duplicate negation pattern name"


def test_annotation_tier_never_fires_on_prose() -> None:
    """The tier boundary, stated as a test.

    "negative" declared as a criterion's own marker is an author saying so;
    "negative" in a sentence about numbers is not. Collapsing the two is how
    the bare word earned its false positives in the first place.
    """
    from openspec_graph.parse_semantics import negation_matches

    assert "annotated_non_success" in negation_matches("non-success", "anything")
    assert "annotated_non_success" not in negation_matches("", "Negative numbers are formatted.")
