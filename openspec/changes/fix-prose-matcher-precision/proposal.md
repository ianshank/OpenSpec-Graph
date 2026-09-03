# Change: Fix Prose Matcher Precision

## Why

Two rules read English prose rather than structure, and both were wrong in
kind rather than merely under-tuned. G002 asked whether a criterion names a
non-success outcome using a flat list of bare lexical triggers (`zero`,
`block`, `fail`, `without`); U004/S003 asked whether a requirement is
normative using a bare case-insensitive *substring* test for SHALL/MUST.

Both failure modes are silent, and G002's is the dangerous one:
`rules_generic._needs_negative` fires only when a spec has **no** negative
criterion at all (`if spec.criteria and not spec.has_negative_criterion`), so
a single false positive anywhere in a document switches the rule off for the
whole document. "The block renders below the header" satisfied it. U004 is the
mirror image — it fires when a requirement is *not* normative, so "shallow
clone", "Marshalling", "mustard" and an env var named `MUST_ROTATE_KEYS` each
silently excused the requirement that contained them.

**Evidence:** the README's "And what it got wrong" section records four
findings that were the linter's fault, and two of them are exactly this class:
finding 1 is a G002 false negative on `cloud-egress` ("a partial GCP block
**opens no** egress channel"), and finding 4 is the U004 body-blind check that
affected 20 of 34 requirements across four change packages and was found by
hand. Measured directly and recorded in `docs/eval-corpus-plan.md` appendix B
against a hand-labelled probe set: `Criterion.is_negative` scored precision
0.38 and recall 0.42 (18 true positives against 29 false ones), and
`Requirement.is_normative` scored precision 0.47 and recall 0.39. The same
document's ground-truth table names the offending regexes —
`\bblock(s|ed|ing)?\b` at 6 false positives against 1 true, `\bzero\b` at 5
against 1 and redundant with `non-?zero` — and records that every *structural*
pattern (`opens no`, `no X is created`, `neither`, `cannot`, `never`,
`non-success`) scored zero false positives. `docs/eval-corpus-plan.md`'s D4
decision is the planning artifact this change implements.

## What Changes

- `openspec_graph/parse_semantics.py`: the flat `NEGATIVE_PATTERNS` list
  becomes `NEGATION_PATTERNS`, a tuple of named, tiered `NegationPattern(name,
  tier, pattern)` records, plus a `negation_matches(note, text)` function that
  applies each tier to the field it was written for. Three tiers —
  `annotation` (matched against the criterion's own parenthesised marker
  only), `structural` (grammar meaning absence or refusal, wherever it
  appears), `lexical` (words whose verb forms mean failure, restricted to
  genuinely verbal inflections and refusing a following hyphen). Bare `zero`,
  bare `block`, bare `without`, bare `nothing` and bare `negative` are removed
  or re-anchored on the measured evidence. `NEGATIVE_PATTERNS` survives as a
  derived, backwards-compatible alias excluding the annotation tier, still
  re-exported through `parse.py`'s `__all__`.
- `openspec_graph/parse_semantics.py`: new `NORMATIVE_MODAL`, word-bounded
  with a `(?!-)` guard so the hyphenated noun compound "must-have" is not a
  modal, replacing the substring test.
- `openspec_graph/parse_model.py`: new `Criterion.negation_evidence` returning
  the names of every matching pattern, so a G002 finding can be argued with;
  `Criterion.is_negative` derives from it and stays a `bool`, leaving
  `graph.py` and G002 itself untouched. `Requirement.is_normative` uses
  `NORMATIVE_MODAL`.
- `tests/fixtures/phrasing/`: a new hand-labelled corpus —
  `criteria.jsonl` (86 scored rows), `criteria-ambiguous.jsonl` (11 rows the
  labeller could not decide, scored by nothing), `requirements.jsonl` (21
  scored rows), `requirements-modal-variants.jsonl` (11 rows normative in
  spirit without SHALL/MUST, a separate open design question), and a
  `README.md` recording the measurement, the labelling rule, and three honest
  limitations.
- `tools/matcher_accuracy.py`: new scorer. Imports `openspec_graph` and
  measures the shipped matcher rather than a reimplementation, following
  `tools/render_rule_catalog.py`'s precedent. Reports precision, recall and a
  per-pattern true/false-positive breakdown; `--check` enforces the configured
  floors.
- `pyproject.toml` `[tool.specgraph]`: four new integer-percentage floors —
  `g002_min_precision_pct`, `g002_min_recall_pct`, `u004_min_precision_pct`,
  `u004_min_recall_pct` — beside the existing `branch_fail_under`, read with
  the same `tools/_common.read_pyproject_int` the coverage gates use.
- `tests/test_matcher_accuracy.py`: 14 new tests holding both matchers to
  those floors, proving no pattern misfires more than it fires, pinning the
  tier boundary and the case-insensitivity of every pattern, and asserting
  that a missing floor is a loud failure rather than a skip.
- `docs/eval-corpus-plan.md`: the "What was implemented from this plan" table
  records this package against plan item 4, with the before/after figures.

## Non-Goals

- No widening of what counts as normative. U004's own message says the
  requirement "uses no SHALL/MUST", so that is the contract measured. "is
  required to", "ought to", and bare imperatives are a genuinely open design
  question; they live in `requirements-modal-variants.jsonl` and are scored by
  nothing rather than counted as misses against a promise the rule never made.
  Widening U004 is a change package of its own.
- No new rule, and no change to any rule's id, severity, dialect set, or
  message. Nothing enters the `RULES` registry or the README rules table; this
  is a precision fix beneath two existing rules, so a reader's mental model of
  the rule set is unchanged.
- No new Makefile target. The gate rides in the existing pytest suite, which
  `make test` already runs; the scorer's `--check` mode exists for a human
  asking the same question interactively, and adding a target for one script
  the suite already exercises would be a second place for the two to disagree.
- No floor set at the measured value. A floor equal to the current figure
  turns every future pattern addition into a failure even when it improves
  things, so each is set deliberately below the measurement.
- No special case for the one remaining U004 false positive. The interrogative
  "Shall we keep the legacy endpoint?" is a question rather than an
  obligation; telling the two apart needs more than a lexical test, so it is
  counted honestly against the score.
- No harvested corpus. These sentences were composed for this purpose, and the
  fixtures README says so: they are a regression net, not a benchmark.

## Affected Capabilities

- `prose-matcher-precision`
