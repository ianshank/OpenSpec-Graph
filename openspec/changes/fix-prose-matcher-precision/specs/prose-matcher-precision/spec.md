# Spec: Prose Matcher Precision

> **Change:** `fix-prose-matcher-precision`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

G002 and U004/S003 are the two rules that read English prose rather than
structure, and both were wrong in kind. G002's detector was a flat list of
bare lexical triggers; `Requirement.is_normative` was a bare case-insensitive
substring test for SHALL/MUST.

Both fail silently, and they fail in opposite directions. G002 asks only
whether a spec carries **at least one** non-success criterion
(`rules_generic._needs_negative` yields nothing when
`spec.has_negative_criterion` is true), so one false positive anywhere
switches the rule off for the entire document — "The block renders below the
header" was enough. U004 fires when a requirement is *not* normative, so every
substring false positive ("shallow clone", "Marshalling", "mustard",
`MUST_ROTATE_KEYS`) silently excused the requirement containing it.

Neither failure was measurable. Coverage proves the code runs and a fixture
proves each rule *can* fire; neither says how often either fires on the wrong
sentence.

**Evidence:** the README's "And what it got wrong" section records four
linter-fault findings, two of them this class — a G002 false negative on
`cloud-egress` ("a partial GCP block **opens no** egress channel"), and the
U004 body-blind check that affected 20 of 34 requirements across four change
packages and was found by hand rather than by a gate. Measured against a
hand-labelled probe set and recorded in `docs/eval-corpus-plan.md` appendix B:
`Criterion.is_negative` scored precision 0.38 and recall 0.42;
`Requirement.is_normative` scored precision 0.47 (its 0.39 recall counted
eleven rows that are normative without SHALL/MUST — a contract the rule never
made, see DEC-PM-009 — so a boundary fix could not and did not raise it). The
same appendix names `\bblock(s|ed|ing)?\b` (6 false positives against 1 true) and
`\bzero\b` (5 against 1, and redundant with `non-?zero`) as the worst
offenders, and records that every structural pattern scored zero false
positives on the scored set — the split this change's tiering is built on.
Two of the eleven set-aside sentences would fire `never` and `neither`, which
is part of why they are set aside.

---

## Requirements

- R-PM-1: Non-success detection MUST be a table of **named, tiered** patterns
  (`NEGATION_PATTERNS`), and each tier MUST be applied to the field it was
  written for. The `annotation` tier MUST match only a criterion's own
  parenthesised marker, never its prose; `structural` and `lexical` patterns
  MUST see the criterion's prose.
- R-PM-2: Both matchers' measured precision and recall MUST meet the floors
  declared in `pyproject.toml` `[tool.specgraph]`
  (`g002_min_precision_pct`, `g002_min_recall_pct`, `u004_min_precision_pct`,
  `u004_min_recall_pct`). Those floors MUST NOT be written into the Makefile,
  a workflow, the scorer, or a test — this repo's own rule G003, applied to
  itself.
- R-PM-3: A floor that is absent from config MUST fail loudly. The gate MUST
  NOT pass, skip, or default when it cannot find the number it is enforcing.
- R-PM-4: A negation pattern MUST NOT produce more false positives than true
  positives over the scored criterion corpus. A pattern that is wrong more
  often than it is right is not a detector.
- R-PM-5: Every negation pattern MUST be case-insensitive, so G002's verdict
  MUST NOT depend on how a criterion happens to be capitalised.
- R-PM-6: `Requirement.is_normative` MUST test SHALL/MUST on word boundaries
  and MUST NOT count a hyphenated noun compound ("must-have") as a modal.
- R-PM-7: `Criterion.negation_evidence` MUST report the names of the patterns
  that matched, so a G002 finding can be argued with rather than re-derived by
  hand. `Criterion.is_negative` MUST remain a `bool` derived from it.
- R-PM-8: The labelled corpus MUST be committed, MUST carry both labels for
  each scored file, and MUST keep the undecidable and out-of-contract rows in
  separate files that are scored by nothing.
- R-PM-9: The scorer MUST measure the shipped matcher by importing
  `openspec_graph`, never a reimplementation of it, and the reporting path and
  the gating path MUST agree about what was measured.
- C-PM-1: `NEGATIVE_PATTERNS` MUST remain importable from
  `openspec_graph.parse`, and MUST exclude annotation-tier patterns — applied
  to free text those would reproduce the bare-word false positives the tiering
  exists to remove.
- C-PM-2: No rule's id, severity, dialect set, or message MUST change, no rule
  MUST enter or leave `RULES`, and `graph.py` MUST NOT be touched.
- C-PM-3: This change MUST NOT add a runtime dependency. Any Makefile target
  it adds MUST be a convenience over `tools/matcher_accuracy.py`, composed into
  neither `ci` nor `pre-pr`; the enforcing gate MUST remain
  `tests/test_matcher_accuracy.py` inside `make test`.
- C-PM-4: A waiver comment's reason text MUST NOT reach either matcher
  through `Criterion.text`, `Criterion.note`, or `Requirement.body`.

---

## Decisions

- **DEC-PM-001:** three tiers, not one flat list and not a purely structural
  matcher. The measurement forced the split rather than decorating it: every
  structural pattern scored zero false positives on the scored set, while the
  bare lexical ones carried all the damage. Deleting the lexical tier outright was the obvious
  alternative and was rejected because the probe's false-negative families are
  mostly lexical — stop/abort verbs (aborted, halts, declines; skipped,
  dropped and ignored in their passive forms), "error" as a noun, status
  codes as the outcome. Dropping
  them would have traded G002's precision problem for a recall problem of the
  same size. The tier is the design, not a label: it records *why* a pattern is
  trusted, which is what tells a future author where a new pattern belongs.
- **DEC-PM-002:** the annotation tier reads the criterion's parenthesised
  marker and nothing else, as a full match of the stripped marker rather than
  a search. Harness ACs are written `**AC-WM-3 (non-success):**`, and the
  parser already splits that marker into `Criterion.note`; upstream scenarios
  and speckit snippets put a whole block of prose in `note`, and a search over
  it simply moved the bare-word false positive to those dialects (found by
  adversarial review). This repo's own tree uses `(non-success)` well over a
  hundred times and `(negative)` a handful, so the marker is an author's
  explicit declaration, not
  prose to interpret — a different kind of evidence from a word turning up in
  a sentence. Collapsing the two is precisely how the bare word "negative"
  earned its false positives, since a criterion about negative *numbers* is not
  a criterion about a failure path.
- **DEC-PM-003:** lexical patterns refuse a following hyphen (`(?!-)`) and are
  restricted to verbal inflections — passive-only for verbs that are ordinary
  software vocabulary in the active voice (skip, drop, ignore, kill,
  terminate), an error or exception object for `raise`, an outcome position
  for `failure` — rather than carrying an
  exclusion list of known-bad nouns. A hyphen is the grammar of attributive
  use in software prose, and it is what separates "the write is denied" from
  "denied-list entries", "the run fails" from `--cov-fail-under`, and "the
  request is blocked" from "blocking I/O". An exclusion list would have to
  grow once per compound anyone invents; the hyphen rule is one character of
  regex covering the whole class. `blocked` goes further and is
  copula-anchored, because "block" is overwhelmingly a noun here.
- **DEC-PM-004:** five patterns were removed or re-anchored on evidence rather
  than argued about — bare `zero` (1 true positive against 5 false, and
  already covered by `non-zero`), bare `block` (1 against 6), bare `without` (0
  against 2), bare `nothing`, and bare `negative`. Two of those were
  individually plausible and collectively switched G002 off. Keeping a pattern
  because it reads sensible is how the flat list was built in the first place;
  the per-pattern breakdown in `tools/matcher_accuracy.py` exists so that
  argument can never be made again without a number attached.
- **DEC-PM-005:** the floors live in `pyproject.toml` `[tool.specgraph]`, as
  integer percentages, and are set **below** the measured figures by a
  recorded tolerance. Config
  rather than the Makefile because a governance tool that hard-codes its own
  thresholds is the worst possible advertisement for G003, and
  `tools/check_no_hardcoded_thresholds.py` would catch it anyway. Integers
  rather than floats so they reuse `tools/_common.read_pyproject_int`, the
  same reader the coverage gates use, instead of introducing a second config
  parser. Each floor is chosen by how many additional errors it tolerates at
  the current corpus size, and that count is written beside it: at the time
  of writing G002's floors tolerate two more false positives and five misses,
  U004's two more false positives and one miss. A floor that tolerates zero is
  a floor at the measurement whatever its nominal distance. Slack exists
  because a recall-gaining pattern normally costs a little precision and
  because adversarial corpus rows are meant to keep being added — raising a
  floor should be a deliberate act, and lowering one should need a reason in
  the commit message.
- **DEC-PM-006:** the one surviving U004 false positive is counted, not
  special-cased. "Shall we keep the legacy endpoint?" is a question rather
  than an obligation, and distinguishing an interrogative from a modal needs
  more than a lexical test. Special-casing it would improve the reported
  number without improving the matcher, which is the failure mode this whole
  change exists to make impossible.
- **DEC-PM-007:** `negation_evidence` is additive and `is_negative` keeps its
  boolean type. Every existing caller — G002 and `graph.py`'s node attributes
  — asks a yes/no question and should keep asking it; widening the return type
  would have made an unrelated module change to deliver an explanation nobody
  had requested yet. The names exist because "which word made this count?"
  previously had no answer short of re-deriving the regex list by hand.
- **DEC-PM-008:** `NEGATIVE_PATTERNS` stays as a derived alias rather than
  being deleted. It is re-exported through `parse.py`'s `__all__`, so it is
  public surface, and this repo has an explicit compatibility posture for
  public symbols (`tests/test_decomposition.py::test_public_import_compatibility`).
  Annotation-tier patterns are excluded from the alias deliberately: a caller
  holding a bare list of compiled patterns will apply all of them to free
  text, which is exactly the bare-word behaviour the tiering removes.
- **DEC-PM-009:** the undecidable rows are kept in a file that asserts nothing,
  rather than deleted or forced into a label: they carry a `leaning`, and the
  corpus loader refuses to score a row without a `label`. Eleven of the
  original ninety-seven sentences could not be labelled confidently, and that
  ratio is the honest floor on how
  much a second labeller would agree with the first; deleting them would hide
  it and flatter every score computed from what remains. The same reasoning
  keeps `requirements-modal-variants.jsonl` unscored — measuring U004 against
  requirements that are normative in spirit without SHALL/MUST would score the
  rule against a contract it never made.
- **DEC-PM-010:** the scorer imports `openspec_graph` rather than
  reimplementing the match, breaking most `tools/` scripts' stdlib-only habit.
  `tools/render_rule_catalog.py` already sets that precedent for the same
  reason: a copy of the matcher inside the tool would measure a copy, and the
  copy would drift from the thing that ships — leaving a green gate over a
  matcher nobody had measured.
- **DEC-PM-011:** `make matcher-accuracy` is a report target, not the gate.
  It exists because the two contributor skills and the Claude Code hook need a
  one-word command to point at, and it runs `--check --patterns` so a human
  sees the misfire column and a non-zero exit on a breach. The gate that
  cannot be forgotten is `tests/test_matcher_accuracy.py` inside `make test`;
  the target is composed into neither `ci` nor `pre-pr`, one test pins that,
  and one test asserts `--check`'s exit code agrees with the scores, so the
  friendly path and the gating path cannot diverge.
- **DEC-PM-012:** the waiver-reason leak is fixed here rather than deferred.
  It is a pre-existing gap, but this package is the precision fix for exactly
  the two matchers it feeds, and shipping a measured 0.92 precision while a
  comment's reason text could still switch G002 off would be a number that
  did not describe the behaviour. The fix is the one `strip_waiver_comments`
  already applies to `verified_by`, extended to the three fields the matchers
  read.

---

## Acceptance Criteria

- [x] **AC-PM-1:** G002's measured precision and recall over
  `tests/fixtures/phrasing/criteria.jsonl` meet the floors declared in
  `pyproject.toml` `[tool.specgraph]`, with the false positives and misses
  named in the failure message when they do not. (R-PM-2)
  _Verified by:_ `pytest -k test_g002_meets_its_configured_accuracy_floors` · stage: `make test`

- [x] **AC-PM-2:** U004/S003's measured precision and recall over
  `tests/fixtures/phrasing/requirements.jsonl` meet their configured floors,
  with the word-bounded modal in place. (R-PM-2, R-PM-6)
  _Verified by:_ `pytest -k test_u004_meets_its_configured_accuracy_floors` · stage: `make test`

- [x] **AC-PM-3 (non-success):** no negation pattern produces more false
  positives than true positives over the scored criterion corpus — the exact
  defect that made the flat list score 0.38, where bare `zero` and bare
  `block` were each wrong more often than right. (R-PM-1, R-PM-4)
  _Verified by:_ `pytest -k test_no_negation_pattern_misfires_more_than_it_fires` · stage: `make test`

- [x] **AC-PM-4:** the annotation tier fires on a declared `(non-success)`
  marker and does **not** fire on the word "negative" appearing in ordinary
  prose about numbers. (R-PM-1)
  _Verified by:_ `pytest -k test_annotation_tier_never_fires_on_prose` · stage: `make test`

- [x] **AC-PM-5:** every pattern in the table is compiled case-insensitively,
  checked structurally as well as behaviourally, so a pattern added without
  the flag fails for an obvious reason. (R-PM-5)
  _Verified by:_ `pytest -k "test_every_negation_pattern_is_case_insensitive or test_is_negative_depends_on_wording_not_casing_or_padding"` · stage: `make test`

- [x] **AC-PM-6 (non-success):** a floor missing from `pyproject.toml`
  `[tool.specgraph]` is a failure, not a skip — every rule/metric pair the
  gate enforces is asserted to be configured, and the scorer reports the
  missing key by name rather than passing. (R-PM-3)
  _Verified by:_ `pytest -k test_a_floor_is_configured_for_every_rule_and_metric` · stage: `make test`

- [x] **AC-PM-7:** the scorer's `--check` exit code agrees with the scores the
  same module reports, so the human-readable report and the gate cannot
  disagree about the same measurement. (R-PM-9)
  _Verified by:_ `pytest -k test_the_check_mode_exit_code_matches_the_scores` · stage: `make test`

- [x] **AC-PM-8 (non-success):** `criteria-ambiguous.jsonl` and
  `requirements-modal-variants.jsonl` are present, non-empty, and score
  nothing; no sentence is both scored and set aside as ambiguous. (R-PM-8)
  _Verified by:_ `pytest -k test_the_ambiguous_and_variant_files_assert_nothing` · stage: `make test`

- [x] **AC-PM-9:** both scored corpora are large enough to measure and carry
  both labels — a single-label set makes precision and recall vacuous. (R-PM-8)
  _Verified by:_ `pytest -k "test_corpora_are_present_and_balanced or test_every_corpus_row_is_well_formed"` · stage: `make test`

- [x] **AC-PM-10:** `Criterion.negation_evidence` returns the names of the
  matching patterns in table order, and `Criterion.is_negative` is still a
  `bool` equal to whether that tuple is non-empty. (R-PM-7)
  _Verified by:_ `pytest -k test_negation_evidence_names_the_matching_patterns` · stage: `make test`

- [x] **AC-PM-11 (non-success):** `NEGATIVE_PATTERNS` is still importable from
  `openspec_graph.parse` and contains no annotation-tier pattern, so a caller
  applying the whole list to free text does not inherit the bare-word
  behaviour. (C-PM-1)
  _Verified by:_ `pytest -k test_negative_patterns_alias_excludes_the_annotation_tier` · stage: `make test`

- [x] **AC-PM-12 (non-success):** the substring false passes are gone — a
  requirement whose only SHALL/MUST-shaped text is "shallow", "Marshalling",
  "mustard", `MUST_ROTATE_KEYS` or "must-have" is no longer read as normative,
  and each of those rows is scored rather than exempted. (R-PM-6)
  _Verified by:_ `pytest -k test_u004_meets_its_configured_accuracy_floors` · stage: `make test`

- [x] **AC-PM-13:** the rule surface is unchanged — no rule id, severity,
  dialect set, or message moved, no rule entered or left `RULES`, and this
  repo's own change packages still validate clean under the retuned matchers.
  (C-PM-2)
  _Verified by:_ `make validate` · stage: `make validate`

- [x] **AC-PM-14:** `make matcher-accuracy` is `.PHONY`, carries `##` help,
  and appears in neither the `ci:` nor the `pre-pr:` line. (C-PM-3, DEC-PM-011)
  _Verified by:_ `pytest -k test_makefile_has_matcher_accuracy_report_target` · stage: `make test`

- [x] **AC-PM-15 (non-success):** an upstream scenario whose WHEN/THEN prose
  mentions negative numbers is not promoted to non-success by the annotation
  tier; only a whole marker (`non-success`, `negative`) is. (R-PM-1, DEC-PM-002)
  _Verified by:_ `pytest -k test_annotation_tier_matches_the_whole_marker_only` · stage: `make test`

- [x] **AC-PM-16 (non-success):** a waiver comment whose reason reads "the
  coverage floor fails otherwise" leaves `negation_evidence` empty in all three
  dialects, and one reading "the number MUST stay in pyproject" leaves the
  requirement non-normative. (C-PM-4, DEC-PM-012)
  _Verified by:_ `pytest -k test_waiver_reason_text_is_invisible_to_both_matchers` · stage: `make test`

- [x] **AC-PM-17:** the contracted prohibition "mustn't" (straight or curly
  apostrophe) is normative; the compound "must-fix" is not. (R-PM-6)
  _Verified by:_ `pytest -k test_contracted_prohibition_is_normative` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-PM-1..12, AC-PM-14..17 |
| Self-check | `make validate` | AC-PM-13 — this repo's own change packages stay clean under the retuned matchers |
| Config discipline | `make thresholds` | no accuracy floor appears in the Makefile or any workflow YAML; every one is read from `pyproject.toml` |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, thresholds |
