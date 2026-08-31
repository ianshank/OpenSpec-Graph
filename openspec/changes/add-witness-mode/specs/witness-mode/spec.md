# Spec: Witness Mode

> **Change:** `add-witness-mode`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`planlint` checks that a spec's `_Verified by:_` line *cites* a real make
target (H001; the `MAKE_REF` regex generally) — but never checks that the
cited target actually *ran*, let alone that it passed. A spec can cite
`` `make test` `` and pass every existing lint check while the tests it
references have never once executed. "Verified by" is, today, purely a
citation-hygiene claim, not an execution claim.

**Evidence:** a repo-wide grep for `witness`/`.planlint` finds zero existing
code, test, or change-package footprint anywhere in this repository —
witness mode exists only as a roadmap sketch (`docs/differentiation-roadmap.md`'s
`CP-7` section) until this change. That sketch is real product intent but not
literal architecture: its own `witness record --target test` flag collides
with the global `--target` (repo path) every other verb already uses
identically; its "H001 verifies witness when flag set" touch-map note is
architecturally impossible as written (`Rule.check(spec, profile)` has no
access to CLI flags, and no existing rule conditionally activates on a
runtime one); its "signed (hash-chained)" claim names no key-management
story anywhere; and it says nothing about `--change` interaction,
`AC-GR-4`/graph parity, or where a new rule family should live — exactly the
questions this project's own established discipline requires answering
before code is written, not after (mirrors every prior capability's own
Problem Statement grounding, most recently `add-architecture-drift-lint`).

A first design draft was itself put through adversarial review before
implementation and found a real HIGH-severity bug introduced during that
draft: a short-commit-sha comparison that would silently defeat freshness
checking for any CI script using an abbreviated sha (`git rev-parse --short
HEAD`, `${GITHUB_SHA:0:7}` — both ordinary CI patterns) — technically still
"failing closed," but indistinguishable from "you never recorded a witness
at all," an undiagnosable dead end. That review also surfaced that the
pre-existing `Criterion.verified_by` waiver-comment leak (open since before
this change, for both dialects) is *wider* for the upstream dialect than the
harness one — the dialect this design most deliberately supports (`DEC-WM-005`)
— making it a real, gate-defeating hole rather than a cosmetic one once
W001/W002 exist. Both are resolved below, not silently carried forward.

---

## Requirements

- R-WM-1: A spec's cited stage with no fresh, exit-0 witness MUST be
  reported (W001), evaluated only when `--require-witness` is passed to
  `validate`.
- R-WM-2: A witness matching a cited stage but recording coverage below the
  detected floor MUST be reported (W002), evaluated only when
  `--require-witness` is passed to `validate`.
- R-WM-3: `validate`'s default (no `--require-witness`) behavior MUST be
  unchanged — W001/W002 MUST NOT be evaluated at all, not merely suppressed
  after the fact, when the flag is absent.
- R-WM-4: `graph`'s `broken_links` count MUST NOT include W001/W002
  findings, and `graph` output MUST NOT represent witnesses as nodes or
  edges, under any flag.
- R-WM-5: `planlint witness` MUST record one witness per invocation (stage,
  exit code, optional coverage, commit sha) as a content-addressed file
  under `.planlint/witnesses/`.
- R-WM-6: `witness`'s own flag naming the stage MUST NOT collide with the
  global `--target` flag every verb already uses for the repo path.
- R-WM-7: `--sha` MUST be validated as exactly 40 hexadecimal characters;
  anything shorter or malformed MUST be rejected before a witness is
  written.
- R-WM-8: `--coverage`, when given, MUST be validated as a finite number in
  `[0, 100]`; an out-of-range or non-finite value MUST be rejected before a
  witness is written.
- R-WM-9: `load_witnesses()` MUST fail closed: any witness file that is
  unreadable, malformed, hash-mismatched, or of an unrecognized
  `schema_version` MUST be silently skipped — never raised as an error, and
  never treated as a passing witness.
- R-WM-10: `write_witness()` MUST write atomically (a temp file, then a
  rename) so a concurrently-running reader never observes a
  partially-written witness file.
- R-WM-11: Freshness MUST be determined by exact-string comparison between a
  witness's recorded `sha` and the target repo's actual current commit sha,
  never a prefix or abbreviated match.
- R-WM-12: The target repo's current commit sha MUST be computed lazily —
  only when at least one witness already exists in the store — via the only
  new `subprocess` call site anywhere in `openspec_graph/`.
- R-WM-13: A criterion citing more than one backtick-fenced stage (e.g. a
  GWT scenario mentioning more than one `` `make X` ``) MUST require a
  witness for every citation — no heuristic selecting "the real one."
- R-WM-14: The pre-existing `Criterion.verified_by` waiver-comment leak MUST
  be fixed, for both dialects, before W001/W002 exist.
- R-WM-15: An unwritable `.planlint/witnesses/` (permission denied,
  read-only filesystem) MUST produce a clear, non-traceback error at exit
  code 2.
- R-WM-16: Every doc/source location that states the total rule count MUST
  match `rules.RULES` itself, mechanically verified, extending the existing
  doc-drift guard to the new `W` family.
- C-WM-1: New `StackProfile`/`Witness` fields MUST be additive only
  (mirrors `C-WL-1`/`C-AD-1`).
- C-WM-2: `witnesses`/`current_sha` MUST NOT be added to
  `StackProfile.to_card()`/`as_dict()`/`dialect_card._COMPARABLE_FIELDS` —
  `current_sha` changes on every commit by design and would manufacture
  false `detect --diff` drift.
- C-WM-3: No new CLI verb beyond the single, flat `witness` verb — no nested
  sub-actions.

---

## Decisions

- **DEC-WM-001:** `witness`'s own stage-name flag is `--stage`, not the
  roadmap's literal `--target` — that name is already the global flag every
  verb uses for the repo path (`cli.py`), and reusing it on `witness` would
  silently collide. `--stage` matches vocabulary this codebase already uses
  for the same concept (`graph.py::_stages_cited()`, and every fixture
  spec's own `` stage: `make X` `` citation convention).
- **DEC-WM-002:** `witness` is a single flat verb, not a nested `witness
  record`/`witness verify`. Every existing verb is a single-level leaf,
  `ALLOWED_VERBS`'s exact-set-equality test only inspects one level, and
  `validate --require-witness` is the only consumer of "verify" logic this
  version needs — this project has repeatedly declined to build ahead of a
  committed acceptance criterion (`DEC-PR-002`, `DEC-AD-007`).
- **DEC-WM-003:** `--sha` requires the full 40-character hex commit sha,
  rejecting anything shorter, and is never auto-derived from git even
  though `_current_sha()` exists. Requiring the full sha closes a real bug:
  `_current_sha()`'s `git rev-parse HEAD` always returns the full sha, never
  abbreviated, so an exact-equality freshness comparison against a
  caller-supplied *short* sha would never match, silently defeating the
  freshness check on every run for any pipeline using an abbreviated one —
  every mainstream CI system already exposes the full sha by default
  (`GITHUB_SHA`, `CI_COMMIT_SHA`, `BUILD_SOURCEVERSION`), so nothing real is
  lost. Prefix-matching was considered and rejected: unlike git's own
  abbreviation resolution, a bare `str.startswith()` comparison has no
  visibility into whether a short prefix is actually unique in the repo's
  history, trading an always-loud failure for an occasionally *silent* one.
  `--sha` stays explicit and required rather than reusing `_current_sha()`
  at record time too, so the freshness comparison's two values stay
  independently obtained — deriving both sides from the same code path
  would degenerate the check into "did I call git twice and get the same
  answer."
- **DEC-WM-004:** W001/W002 live in a new `rules_witness.py` module, not
  `rules_generic.py`. The precedent this needs to engage honestly is
  `DEC-AD-008` (`add-architecture-drift-lint`), whose *primary* argument was
  that a new rule pair with new `StackProfile` fields is, by itself, *not*
  sufficient justification for a new module — G008/G009 stayed in
  `rules_generic.py` precisely because of that argument. W001/W002 fit that
  rejected shape on the surface. The distinction that survives scrutiny: G008/
  G009 only ever consumed two pre-existing-shaped `StackProfile` scalar
  fields with no dedicated supporting module behind them; W001/W002 are the
  rule-layer half of a genuinely new, non-trivial, dedicated supporting
  module (`witness.py` — its own schema, hashing, atomic-write I/O) that
  exists regardless of where its consuming rules live. The real precedent
  this matches is `machinery.py` (a complex supporting module with its own
  clearly-scoped consuming code nearby), not "a new rule pair alone earns a
  module."
- **DEC-WM-005:** `dialects=("*",)`, not harness-only, despite the roadmap's
  own touch-map naming `rules_harness.py`/H001. Verified directly:
  `Criterion.verified_by` for an upstream Scenario is already the entire
  Scenario block text, so the same `MAKE_REF`-based stage extraction
  `graph.py::_stages_cited()` already uses dialect-agnostically works for
  W001/W002 with no changes. H001 itself stays untouched — it is inherently
  harness-only and has no way to see a runtime flag.
- **DEC-WM-006:** W001/W002 iterate per-criterion (mirrors H001), not
  per-spec deduplicated (mirrors G004) — the product claim is about one
  criterion's own citation, and no existing rule's `Finding` carries a real
  line number, so naming the criterion's own `ident` in the message is the
  only available pointer.
- **DEC-WM-007:** `rules.evaluate()` gains an optional
  `rule_set: Sequence[Rule] = RULES` parameter, single-sourcing both the
  `--require-witness` gate and `graph.py`'s exclusion of witness findings
  through one `NON_WITNESS_RULES` constant, rather than two independently
  maintained post-hoc filters. The honest cost: `evaluate()`'s public
  signature grows a third, defaulted parameter — fully backward compatible
  (every existing call site passes exactly two positional arguments) but
  real API surface growth. **Known future integration point, not resolved
  here:** `add-rule-pack-plugins`'s own (not yet re-grounded) design
  independently plans to reuse the same parameter name for plugin
  filtering — that change's own future design pass must reconcile the two,
  not silently collide with this one.
- **DEC-WM-008:** the target repo's current commit sha is computed by a new
  `detect._current_sha()` — the only new `subprocess` call site anywhere in
  `openspec_graph/` — via `git rev-parse HEAD`, timeout-guarded, every
  failure mode (non-git repo, git missing, timeout, non-zero exit, malformed
  stdout) folding uniformly to `None`. Justified as a narrow, safe exception
  to this project's general "never shell out" posture: `git rev-parse HEAD`
  is read-only plumbing that never evaluates arbitrary content from the
  target repo's own tracked files, unlike `make` (which evaluates
  `$(shell ...)` unconditionally at parse time) — `DEC-MP-001`'s specific
  danger doesn't transfer. Computed lazily, only when at least one witness
  already exists, since `detect.profile()` runs on every `detect`/
  `validate`/`graph` invocation (including this project's own 300+-test
  suite) and the sha is meaningless with zero witnesses to compare against.
- **DEC-WM-009:** a new static guard test generalizes the existing
  `test_machinery_never_imports_subprocess` AST-based approach: no module in
  `openspec_graph/` except `detect.py` may import `subprocess`. `tools/`/
  `tests/` stay out of scope — a different, already-accepted trust boundary
  (`tools/check_secrets.py` already uses `subprocess` against *this* repo,
  not an untrusted target).
- **DEC-WM-010:** the roadmap's "signed (hash-chained)" framing is dropped
  for plain content-addressing. "Signed" and "self-verifying" are different
  guarantees: signing proves authorship/non-repudiation and requires a key
  someone holds; content-addressed self-verification (filename =
  `sha256(content)`) proves only that a file hasn't been corrupted since it
  was written. The roadmap sketch never named a key-management story
  anywhere, so dropping "signed" is an honest correction, not a scope cut.
  Hash-*chaining* (linking each witness to the previous one) is dropped
  separately: it only has teeth against a *persistent* history with an
  externally-anchored tip, and an ephemeral, gitignored store (`DEC-WM-011`)
  has no such history to chain — it would solve a problem this data model
  doesn't have.
- **DEC-WM-011:** `.planlint/witnesses/` is gitignored, ephemeral, and
  per-checkout — consistent with this project's existing `coverage.json`/
  `spec-graph.json` precedent. Nothing about this design requires witnesses
  to be recorded in the *same* job/container that later runs
  `validate --require-witness` — `planlint` only ever reads whatever's in
  `.planlint/witnesses/` at validate time, agnostic to how it got there. If
  recording and validating happen in different CI jobs (the common case for
  anything beyond a trivial pipeline), wiring them together uses the CI
  system's own artifact-passing mechanism (e.g. GitHub Actions
  `upload-artifact`/`download-artifact`, a shared cache) — the same pattern
  already routine for `coverage.json`/`spec-graph.json`, not a new concept
  this tool needs to solve itself.
- **DEC-WM-012:** `write_witness()` writes via a temp file in the same
  directory, then `os.rename()` into place — atomic, not a direct write.
  Closes a real, if narrow, transient window: a direct write leaves a
  moment between truncate-and-open and the completed write where a
  concurrently-running `load_witnesses()` call could observe a partial
  file — which its own "skip corrupt files silently" contract (`DEC-WM-009`
  fail-closed discipline) would then swallow as an ordinary skip, producing
  a transient, hard-to-reproduce false W001 with no error message.
- **DEC-WM-013:** `graph.py` never represents witnesses as nodes or edges,
  and W001/W002 never contribute to `broken_links`, under any flag — the
  same `NON_WITNESS_RULES` mechanism as `DEC-WM-007`, not a second one.
  This is a *stronger* exclusion than the existing precedent it's closest
  to: H001-H006/U001-U005 findings, when they fire, still flow into
  `graph.py`'s `broken_links` count today (via the same unfiltered
  `rules.evaluate()` call graph.py made before this change) even without a
  dedicated node/edge type — W001/W002 are excluded from `broken_links`
  entirely, genuinely new territory rather than directly precedented.
- **DEC-WM-014:** `witnesses`/`current_sha` are excluded from
  `StackProfile.to_card()`/`as_dict()`/`dialect_card._COMPARABLE_FIELDS`.
  `to_card()`'s whole purpose is a checkout-path-independent portable
  snapshot; `current_sha` changes on every commit by design, so including
  it would manufacture constant false "drift" on every `detect --diff`.
  Both dict methods are hand-written literals, so omitting the fields costs
  zero extra code.
- **DEC-WM-015:** `<!-- specgraph:allow W001/W002 ... -->` works with zero
  code changes — the waiver-comment regex and `evaluate()`'s suppression
  logic are already fully generic over rule ident, and `ledger.py`'s
  `build_ledger()` is independently generic over `waiver.rule` too, so
  `planlint waivers` surfaces a W001/W002 waiver with zero changes there
  either. Documented explicitly that such a waiver is inert on any
  `validate` run without `--require-witness`, since the rules aren't
  evaluated at all then — worth stating so it doesn't read as a bug later.
- **DEC-WM-016:** every backtick-fenced `` `make X` `` citation requires its
  own witness, including a scenario that mentions more than one — no
  heuristic picks "the real one." A natural GWT scenario (*GIVEN a build
  stage has succeeded, WHEN the test stage is run...*, each naming its own
  fenced make-target citation) cites two distinct stages from one block;
  treating both as required citations is
  strict, but is consistent with citation already being deliberately opt-in
  via backtick-fencing (the same reason `MAKE_REF` requires it at all — to
  exclude ordinary prose). A spec author who doesn't want a mention to gate
  the build simply doesn't fence it. Considered and rejected a "smarter"
  heuristic (only the last-mentioned stage counts, or only stages inside
  WHEN count) — this project already paid for exactly that kind of fragile
  "guess which mention is the real one" heuristic once, for ADR
  first-mention-vs-heading detection, and two rounds of review were needed
  to get it right; not worth repeating for a lower-stakes problem.
- **DEC-WM-017:** `--exit` is always the *verifying harness's own* exit
  status — 0 whenever the criterion's own assertion held, including for a
  criterion asserting a negative outcome (this project's `NEGATIVE_PATTERNS`
  grammar exists specifically because "fails/is refused/does not happen"
  ACs are a real, supported convention here) — never a raw inner command's
  exit code passed through unexamined. Nothing in the CLI can enforce this;
  it is a documented convention so a CI script that got it wrong for a
  negative-outcome AC doesn't produce a confusing "no witness" for a
  criterion that was, in fact, correctly verified.
- **DEC-WM-018:** `load_witnesses()` explicitly compares
  `schema_version == WITNESS_SCHEMA_VERSION` and validates `coverage` is
  finite, rather than relying on incidental dataclass-construction failure
  to catch bad data. This is the identical bug class already found and
  fixed once in this codebase (`dialect_card.diff_cards()` treating a
  schema-absent field as its default, false-positiving "drift" on every
  tool upgrade, fixed on PR #13) — a same-shape-but-different-meaning future
  schema change would otherwise parse successfully and be silently
  misinterpreted rather than cleanly rejected. `json.loads()` round-trips
  `NaN`/`Infinity` as a non-standard extension by default, so a hand-edited
  or cross-version witness file could otherwise carry a value that never
  triggers a floor comparison either way.
- **DEC-WM-019:** there is no single "best match" witness lookup. W001
  checks whether *any* witness matches `(stage, sha, exit_code == 0)`; W002
  checks whether *every* such matching witness has `coverage is None or
  coverage >= floor` — a stricter, safer semantic (one bad run among
  several retries for the same commit still blocks, rather than being
  silently out-voted by a luckier one) that needs no clock trust at all.
  This replaces an earlier draft's `recorded_at`-based "most recent wins"
  tie-break, rejected because it trusted wall-clock time across potentially
  different CI runners with real clock skew — a flaky retry with a later
  timestamp than a correct fresh run could otherwise silently mask the
  correct result. `recorded_at` stays in the schema for debugging/audit
  purposes only.
- **DEC-WM-020:** `--coverage`/`--exit`/`--sha` are trusted as CI-reported
  facts, the same trust model as the "no signing" non-goal — boundary
  validation checks magnitude and format, never semantics. This leaves one
  real, explicitly documented gap: a CI script reporting a raw
  covered-line-count that happens to land in `[0, 100]` (e.g. "97" meaning
  97 lines on a module truly at ~65% coverage) looks plausible and would
  silently clear a floor check while real coverage is well below it. No
  amount of range-checking closes this; the CLI's own `--help` text states
  `--coverage` is a percentage, and `--require-witness` proves "a
  `planlint witness` invocation claimed X," only as strong as the CI script
  that invoked it — not an independent, cryptographic re-verification.

---

## Acceptance Criteria

- [x] **AC-WM-1:** W001 fires when a criterion's cited stage has no witness
  at all. (R-WM-1)
  _Verified by:_ `pytest -k test_w001_fires_when_a_cited_stage_has_no_matching_witness` · stage: `make test`

- [x] **AC-WM-2:** W001 fires when a witness exists for the cited stage but
  its recorded sha doesn't match the current commit. (R-WM-1, R-WM-11)
  _Verified by:_ `pytest -k test_w001_fires_when_the_witness_sha_does_not_match_current_sha` · stage: `make test`

- [x] **AC-WM-3:** W001 fires when the matching witness recorded a nonzero
  exit code. (R-WM-1)
  _Verified by:_ `pytest -k test_w001_fires_when_the_matching_witness_recorded_a_nonzero_exit_code` · stage: `make test`

- [x] **AC-WM-4 (non-success):** W001 fires for every citation when the
  current commit sha can't be determined at all (e.g. no git available). (R-WM-1, R-WM-12)
  _Verified by:_ `pytest -k test_w001_fires_for_every_citation_when_current_sha_is_none` · stage: `make test`

- [x] **AC-WM-5 (non-success):** W001 does not fire once a fresh, exit-0
  witness exists for the cited stage. (R-WM-1)
  _Verified by:_ `pytest -k test_w001_does_not_fire_when_a_fresh_passing_witness_exists` · stage: `make test`

- [x] **AC-WM-6:** W002 fires when a witness matching a cited stage records
  coverage below the detected floor. (R-WM-2)
  _Verified by:_ `pytest -k test_w002_fires_when_witness_coverage_is_below_the_detected_floor` · stage: `make test`

- [x] **AC-WM-7 (non-success):** W002 does not fire when coverage meets the
  floor, when no coverage was recorded, when the repo has no detected
  coverage floor at all, or for a witness that already fails W001's own
  bar. (R-WM-2)
  _Verified by:_ `pytest -k "test_w002_does_not_fire"` · stage: `make test`

- [x] **AC-WM-8:** both rules apply under the upstream dialect too,
  including a scenario citing more than one stage, each requiring its own
  witness. (R-WM-1, R-WM-2, R-WM-13, DEC-WM-005, DEC-WM-016)
  _Verified by:_ `pytest -k "test_witness_rules_apply_to_both_dialects or test_w001_fires_independently_for_each_stage_cited_in_one_upstream_scenario"` · stage: `make test`

- [x] **AC-WM-9 (non-success):** `validate --require-witness` fails closed
  on a repo with no witness store at all — zero witnesses never reads as
  "passed." (R-WM-3, R-WM-9)
  _Verified by:_ `pytest -k test_validate_require_witness_fails_closed_on_a_repo_with_no_witness_store` · stage: `make test`

- [x] **AC-WM-10 (non-success):** `validate` without `--require-witness`
  never evaluates W001/W002 at all — default behavior is unchanged. (R-WM-3)
  _Verified by:_ `pytest -k test_validate_without_require_witness_never_evaluates_w001` · stage: `make test`

- [x] **AC-WM-11:** a real end-to-end round trip — record a witness for the
  current commit, then `validate --require-witness` — exits 0. (R-WM-1, R-WM-2, R-WM-5)
  _Verified by:_ `pytest -k test_validate_require_witness_passes_once_a_matching_fresh_witness_is_recorded` · stage: `make test`

- [x] **AC-WM-12:** `witness`'s own stage-name flag and the global `--target`
  flag populate distinct values through one shared parser, without
  colliding. (R-WM-6)
  _Verified by:_ `pytest -k test_cli_witness_stage_flag_does_not_collide_with_global_target` · stage: `make test`

- [x] **AC-WM-13 (non-success):** an abbreviated (short) `--sha` is rejected
  at the CLI boundary with exit 2. (R-WM-7)
  _Verified by:_ `pytest -k test_cli_witness_verb_rejects_an_abbreviated_sha` · stage: `make test`

- [x] **AC-WM-14 (non-success):** an out-of-range or non-finite `--coverage`
  is rejected at the CLI boundary with exit 2. (R-WM-8)
  _Verified by:_ `pytest -k "test_cli_witness_verb_rejects_an_out_of_range_coverage_value or test_cli_witness_verb_rejects_a_non_finite_coverage_value"` · stage: `make test`

- [x] **AC-WM-15 (non-success):** `--coverage 0` is recorded as `0.0`,
  distinct from "not given." (R-WM-8)
  _Verified by:_ `pytest -k test_cli_witness_records_a_zero_coverage_value_distinctly_from_none` · stage: `make test`

- [x] **AC-WM-16 (non-success):** `load_witnesses()` silently skips a
  corrupt, malformed, hash-mismatched, or unrecognized-`schema_version`
  witness file rather than raising or treating it as a pass. (R-WM-9)
  _Verified by:_ `pytest -k "test_load_witnesses_skips"` · stage: `make test`

- [x] **AC-WM-17:** a concurrently-running reader never observes a
  partially-written witness file. (R-WM-10)
  _Verified by:_ `pytest -k test_write_witness_is_atomic` · stage: `make test`

- [x] **AC-WM-18 (non-success):** an unwritable `.planlint/witnesses/`
  produces a clear exit-2 message, not a traceback. (R-WM-15)
  _Verified by:_ `pytest -k test_cli_witness_reports_a_clean_error_when_the_witness_directory_is_unwritable` · stage: `make test`

- [x] **AC-WM-19 (non-success):** the target repo's current commit sha is
  not computed at all when zero witnesses exist in the store. (R-WM-12)
  _Verified by:_ `pytest -k test_current_sha_is_not_invoked_when_no_witnesses_are_present` · stage: `make test`

- [x] **AC-WM-20 (non-success):** `detect.py` is the only module in
  `openspec_graph/` that imports `subprocess`. (R-WM-12)
  _Verified by:_ `pytest -k test_only_detect_imports_subprocess` · stage: `make test`

- [x] **AC-WM-21 (non-success):** `graph`'s `broken_links` count and
  rendered output never include W001/W002 findings, even with a stale
  witness present. (R-WM-4)
  _Verified by:_ `pytest -k test_graph_never_includes_w001_or_w002_findings_even_with_a_stale_witness_present` · stage: `make test`

- [x] **AC-WM-22 (non-success):** a waiver's own reason text can no longer
  leak a spurious stage citation into a criterion's `verified_by`, for
  either dialect. (R-WM-14)
  _Verified by:_ `pytest -k "test_waiver_reason_text_is_not_scanned_as_a_stage_citation"` · stage: `make test`

- [x] **AC-WM-23:** README's rules table, `c4.md`'s rule count and
  per-family range comments, `docs/agents-skills-harness.md`,
  `docs/next-steps.md`, `docs/differentiation-roadmap.md`, and `rules.py`'s
  own module docstring all match `rules.RULES`'s real contents, including
  the new `W` family. (R-WM-16)
  _Verified by:_ `pytest tests/test_rule_registry_docs.py` · stage: `make test`

- [x] **AC-WM-24:** `StackProfile` still constructs via every existing
  keyword-only call site without passing `witnesses`/`current_sha` — both
  default, so the new fields are additive, not breaking. (C-WM-1)
  _Verified by:_ `pytest -k test_stack_profile_construction_still_works_without_witness_fields` · stage: `make test`

- [x] **AC-WM-25 (non-success):** `witnesses`/`current_sha` are confirmed
  absent from `StackProfile.to_card()`'s output and from
  `dialect_card._COMPARABLE_FIELDS`. (C-WM-2)
  _Verified by:_ `pytest -k test_to_card_excludes_witnesses_and_current_sha` · stage: `make test`

- [x] **AC-WM-26 (non-success):** the CLI verb surface is exactly the
  existing 7 verbs plus `witness` — no other new verb appears. (C-WM-3)
  _Verified by:_ `pytest -k test_cli_verbs_are_exactly_the_allow_list` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-WM-1..26 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
