"""Score planlint's natural-language matchers against a labelled corpus.

Two rules depend on reading English prose rather than structure, and both have
already shipped a defect of exactly that kind (see the README's "And what it
got wrong"): **G002** asks whether a criterion names a non-success outcome, and
**U004**/**S003** ask whether a requirement is normative. A one-fixture-per-rule
map proves such a rule *can* fire. It cannot say how often it fires on the
wrong sentence.

This is the module that says. It scores
:data:`openspec_graph.parse_semantics.NEGATION_PATTERNS` and
``Requirement.is_normative`` against ``tests/fixtures/phrasing/`` and reports
precision and recall per rule, plus a per-pattern true/false-positive
breakdown so a pattern that only ever misfires is visible rather than inferred.

Usage::

    python tools/matcher_accuracy.py            # report, exit 0
    python tools/matcher_accuracy.py --check    # also enforce the floors

The floors live in ``pyproject.toml`` under ``[tool.specgraph]``, never here
and never in the Makefile or a workflow -- this project's own rule G003 says a
threshold belongs in config, and a governance tool that hard-codes its own
thresholds is the worst possible advertisement for the rule. They are integer
percentages so they can reuse ``_common.read_pyproject_int``, the same reader
the coverage gates use, rather than introducing a second config parser.

Unlike most ``tools/`` gate scripts this one imports ``openspec_graph``: it
measures the real matcher, and a reimplementation here would measure a copy
that could drift from the thing shipped. ``render_rule_catalog.py`` sets the
same precedent for the same reason.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import logger, read_pyproject_int, repo_root

sys.path.insert(0, str(repo_root()))

from openspec_graph.parse_model import Criterion, Requirement
from openspec_graph.parse_semantics import (
    ANNOTATION_TIER,
    NEGATION_PATTERNS,
    negation_matches,
)

CORPUS_DIR = repo_root() / "tests" / "fixtures" / "phrasing"
CRITERIA_CORPUS = CORPUS_DIR / "criteria.jsonl"
REQUIREMENTS_CORPUS = CORPUS_DIR / "requirements.jsonl"

SPECGRAPH_TABLE = "[tool.specgraph]"
# (rule, corpus, precision key, recall key) -- the floors this gate enforces.
FLOOR_KEYS = {
    "G002": ("g002_min_precision_pct", "g002_min_recall_pct"),
    "U004": ("u004_min_precision_pct", "u004_min_recall_pct"),
}


@dataclasses.dataclass(frozen=True)
class Score:
    """A confusion matrix plus the sentences that produced its errors."""

    rule: str
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    false_alarms: tuple[str, ...] = ()
    misses: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return (
            self.true_positives
            + self.false_positives
            + self.false_negatives
            + self.true_negatives
        )

    @property
    def precision(self) -> float:
        """Of the sentences the matcher flagged, the share it should have.

        A matcher that flags nothing has nothing to be wrong about, so an
        empty numerator scores 1.0 and :attr:`recall` is what catches it.
        """
        flagged = self.true_positives + self.false_positives
        return self.true_positives / flagged if flagged else 1.0

    @property
    def recall(self) -> float:
        """Of the sentences it should have flagged, the share it did."""
        present = self.true_positives + self.false_negatives
        return self.true_positives / present if present else 1.0

    def precision_pct(self) -> int:
        """Precision as a floored integer percentage, for comparison to config."""
        return int(self.precision * 100)

    def recall_pct(self) -> int:
        return int(self.recall * 100)


def load_rows(path: Path) -> list[dict[str, object]]:
    """Read one JSON object per line, ignoring blank lines."""
    if not path.exists():
        raise FileNotFoundError(f"labelled corpus missing: {path}")
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:  # pragma: no cover - corpus is committed
            raise ValueError(f"{path.name} line {number} is not valid JSON: {exc}") from exc
    return rows


def _tally(rule: str, judgements: Sequence[tuple[str, bool, bool]]) -> Score:
    """Fold ``(sentence, predicted, labelled)`` triples into a :class:`Score`."""
    tp = fp = fn = tn = 0
    false_alarms: list[str] = []
    misses: list[str] = []
    for sentence, predicted, labelled in judgements:
        if predicted and labelled:
            tp += 1
        elif predicted:
            fp += 1
            false_alarms.append(sentence)
        elif labelled:
            fn += 1
            misses.append(sentence)
        else:
            tn += 1
    return Score(rule, tp, fp, fn, tn, tuple(false_alarms), tuple(misses))


def score_criteria(rows: Sequence[dict[str, object]]) -> Score:
    """Score ``Criterion.is_negative`` (G002) over labelled criterion prose.

    The corpus carries prose only, with no annotation, so annotation-tier
    patterns never fire here -- deliberately. The tier exists precisely
    because an author's explicit "(non-success)" marker is a different kind
    of evidence from a word appearing in a sentence, and mixing them would
    measure neither.
    """
    return _tally(
        "G002",
        [
            (str(r["text"]), Criterion(ident="X", text=str(r["text"])).is_negative, bool(r["label"]))
            for r in rows
        ],
    )


def score_requirements(rows: Sequence[dict[str, object]]) -> Score:
    """Score ``Requirement.is_normative`` (U004/S003) over labelled requirements."""
    return _tally(
        "U004",
        [
            (
                str(r["text"]),
                Requirement(
                    ident="R-X-1",
                    text=str(r["text"]),
                    kind="shall",
                    body=str(r.get("body", "")),
                ).is_normative,
                bool(r["label"]),
            )
            for r in rows
        ],
    )


def pattern_breakdown(rows: Sequence[dict[str, object]]) -> dict[str, tuple[int, int, str]]:
    """Per-pattern ``(true positives, false positives, tier)`` over the corpus.

    The number that justifies keeping a pattern. A pattern with no true
    positives is dead weight at best; one whose false positives outnumber its
    true ones is actively switching G002 off, which is how the flat pattern
    list reached precision 0.38 before it was tiered.
    """
    breakdown: dict[str, tuple[int, int, str]] = {}
    for pattern in NEGATION_PATTERNS:
        if pattern.tier == ANNOTATION_TIER:
            continue  # never applicable to bare prose; see score_criteria()
        hits = misfires = 0
        for row in rows:
            if pattern.name in negation_matches("", str(row["text"])):
                if row["label"]:
                    hits += 1
                else:
                    misfires += 1
        breakdown[pattern.name] = (hits, misfires, pattern.tier)
    return breakdown


def _floor(key: str) -> int | None:
    return read_pyproject_int(repo_root() / "pyproject.toml", SPECGRAPH_TABLE, key)


def _render(score: Score) -> list[str]:
    return [
        (
            f"{score.rule}: precision {score.precision:.3f}  recall {score.recall:.3f}"
            f"  (TP {score.true_positives}  FP {score.false_positives}"
            f"  FN {score.false_negatives}  TN {score.true_negatives}  n={score.total})"
        )
    ]


def _check(score: Score) -> list[str]:
    """Compare one score against its configured floors; return failures.

    A missing floor is a misconfiguration, never a skip -- the same posture
    ``check_branch_coverage.py`` takes. A gate that silently passes because
    nobody configured it is worse than no gate, since it reports green.
    """
    precision_key, recall_key = FLOOR_KEYS[score.rule]
    failures: list[str] = []
    for key, actual, name in (
        (precision_key, score.precision_pct(), "precision"),
        (recall_key, score.recall_pct(), "recall"),
    ):
        floor = _floor(key)
        if floor is None:
            failures.append(f"{score.rule}: no {key} configured in pyproject.toml {SPECGRAPH_TABLE}")
            continue
        logger.debug("matcher_accuracy: %s %s=%d floor=%d", score.rule, name, actual, floor)
        if actual < floor:
            failures.append(
                f"{score.rule}: {name} {actual}% is below the configured floor {floor}% "
                f"({key} in pyproject.toml)"
            )
    return failures


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="enforce the configured floors (exit 1 if below)"
    )
    parser.add_argument(
        "--patterns", action="store_true", help="also print the per-pattern breakdown"
    )
    args = parser.parse_args(list(argv[1:]))

    criteria_rows = load_rows(CRITERIA_CORPUS)
    requirement_rows = load_rows(REQUIREMENTS_CORPUS)
    scores = [score_criteria(criteria_rows), score_requirements(requirement_rows)]

    for score in scores:
        for line in _render(score):
            print(line)

    if args.patterns:
        print("\npattern                 tier         TP  FP")
        for name, (hits, misfires, tier) in sorted(pattern_breakdown(criteria_rows).items()):
            print(f"{name:<23} {tier:<11} {hits:>3} {misfires:>3}")

    if not args.check:
        return 0

    failures = [problem for score in scores for problem in _check(score)]
    if failures:
        for problem in failures:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print("matcher-accuracy: every configured floor met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
