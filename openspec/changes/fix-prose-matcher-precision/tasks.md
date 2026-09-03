# Milestones

## Milestone 1 — Tier the negation table  [DONE]

- `openspec_graph/parse_semantics.py`: replace the flat `NEGATIVE_PATTERNS`
  list with `NEGATION_PATTERNS`, a tuple of frozen `NegationPattern(name,
  tier, pattern)` records built through a `_negation()` helper that compiles
  every pattern with `re.IGNORECASE` without exception (R-PM-5). Three tier
  constants: `ANNOTATION_TIER`, `STRUCTURAL_TIER`, `LEXICAL_TIER`
  (DEC-PM-001).
- `openspec_graph/parse_semantics.py`: add `negation_matches(note, text)`,
  which applies annotation-tier patterns to `note` alone and every other tier
  to the joined blob, and returns matching pattern **names** in table order
  (R-PM-1, DEC-PM-002).
- `openspec_graph/parse_semantics.py`: re-anchor or remove the patterns the
  probe convicted — bare `zero` (redundant with the exit-anchored
  `non_zero_exit`), bare `block` (now copula-anchored `blocked`), bare
  `without`, bare `nothing` (now verb-anchored), bare `negative` (now
  `negative_case`, plus the annotation tier) — and give each lexical pattern
  its verbal inflections and a `(?!-)` guard (DEC-PM-003, DEC-PM-004).
- `openspec_graph/parse_semantics.py`: keep `NEGATIVE_PATTERNS` as a derived
  tuple of compiled patterns excluding the annotation tier, with a comment
  saying why the exclusion is deliberate; it stays re-exported through
  `parse.py`'s `__all__` (C-PM-1, DEC-PM-008).
- **Gate:** `make test`

## Milestone 2 — Word-bound the modal, make the evidence reportable  [DONE]

- `openspec_graph/parse_semantics.py`: add `NORMATIVE_MODAL =
  re.compile(r"\b(?:SHALL|MUST)\b(?!-)", re.IGNORECASE)`, with the comment
  recording the substring failures it removes ("shallow clone",
  "Marshalling", "mustard", `MUST_ROTATE_KEYS`, "must-have") and the one
  interrogative it knowingly keeps (R-PM-6, DEC-PM-006).
- `openspec_graph/parse_model.py`: add `Criterion.negation_evidence`
  delegating to `negation_matches(self.note, self.text)`; redefine
  `Criterion.is_negative` as `bool(self.negation_evidence)` so it keeps its
  type and G002 and `graph.py` need no edit (R-PM-7, C-PM-2, DEC-PM-007).
- `openspec_graph/parse_model.py`: `Requirement.is_normative` searches
  `NORMATIVE_MODAL` across `text` and `body`, preserving the body-aware
  behaviour `fix-u004-body-blind-modal-check` established.
- **Gate:** `make test`

## Milestone 3 — Build the labelled corpus  [DONE]

- `tests/fixtures/phrasing/criteria.jsonl`: 86 hand-labelled criterion
  sentences, roughly half of them success sentences deliberately seeded with
  a trigger word the old matcher used ("zero-downtime deploy completes", "the
  failover succeeds", "blocked-user list is exported"). One JSON object per
  line: `text`, `label`, `note`.
- `tests/fixtures/phrasing/criteria-ambiguous.jsonl`: the 11 sentences the
  labeller could not decide, kept as the honest floor on inter-rater
  agreement and scored by nothing (R-PM-8, DEC-PM-009).
- `tests/fixtures/phrasing/requirements.jsonl`: 21 labelled requirement texts,
  including the substring traps that used to read as normative.
- `tests/fixtures/phrasing/requirements-modal-variants.jsonl`: 11 rows that
  are normative in spirit without SHALL/MUST, kept as documentation of an
  open design question rather than scored as misses against a contract U004
  never made (DEC-PM-009).
- `tests/fixtures/phrasing/README.md`: the label definitions, the measured
  before/after table, and three stated limitations — the set is adversarial,
  eleven rows are undecidable, and the sentences are synthetic — plus the
  rule for adding a row: label from the sentence before running the matcher
  against it.
- **Gate:** `make test`

## Milestone 4 — Score it, then gate it  [DONE]

- `tools/matcher_accuracy.py`: new scorer importing `openspec_graph`
  (following `tools/render_rule_catalog.py`'s precedent, DEC-PM-010). A
  `Score` dataclass carrying the confusion matrix plus the sentences that
  produced its errors; `score_criteria`, `score_requirements`, and
  `pattern_breakdown` for the per-pattern true/false-positive table; `--check`
  to enforce the floors and `--patterns` to print the breakdown (R-PM-9).
- `pyproject.toml` `[tool.specgraph]`: add `g002_min_precision_pct`,
  `g002_min_recall_pct`, `u004_min_precision_pct`, `u004_min_recall_pct`
  beside `branch_fail_under`, each set below the measured figure, with a
  comment saying that raising one is deliberate and lowering one needs a
  reason in the commit message (R-PM-2, DEC-PM-005).
- `tools/matcher_accuracy.py`: read each floor through
  `tools/_common.read_pyproject_int` — the reader the coverage gates already
  use — and treat a missing key as a reported failure, never a skip, matching
  `tools/check_branch_coverage.py`'s posture (R-PM-3).
- `tests/test_matcher_accuracy.py`: 14 tests loading the tool in-process the
  way `test_skill_contract.py` does, covering the two floor checks, the
  per-pattern misfire check, the case-insensitivity and name-uniqueness
  structural checks, the annotation-tier boundary, corpus shape and balance,
  the unscored files, the configured-floor check for every rule/metric pair,
  and the agreement between `--check`'s exit code and the reported scores
  (AC-PM-1..9).
- **Gate:** `make test`

## Milestone 5 — Record the measurement and close the loop  [DONE]

- `docs/eval-corpus-plan.md`: the "What was implemented from this plan" table
  names this package against plan item 4 and records the before/after figures
  for both matchers, so the plan's D4 decision and the shipped result sit in
  one place.
- Confirm the rule surface is untouched: no id, severity, dialect set, or
  message moved; nothing entered or left `RULES`; the README rules table and
  `graph.py` are unedited; no Makefile target was added (C-PM-2, C-PM-3,
  DEC-PM-011).
- Dogfood: run `planlint validate` against this repo with this change package
  present, so the retuned G002 is exercised against this document's own
  `(non-success)` criteria.
- **Gate:** `make pre-pr` green; `make validate` clean.
