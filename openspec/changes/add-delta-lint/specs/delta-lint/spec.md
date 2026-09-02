# Spec: Delta Lint

> **Change:** `add-delta-lint`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

When a repository's machinery moves — the coverage floor is raised, a make
target is deleted, an invariant is retired — every spec that cited the old
world becomes a lie, and nothing in this tool says *why*. `validate` will
report some of those specs (G001 for a hard-coded threshold, G004 for a
missing make target, G005 for an undeclared invariant), but it reports them
identically to a spec that was wrong the day it was written. The operator's
actual question — "I changed the floor; which specs still cite the old
number?" — has no verb.

**Evidence:** every rule that reads a spec's citations compares them against
the *live* profile only. `rules_generic._unknown_make_target` computes
`known = set(profile.make_targets)`; `_unknown_invariant` reads
`profile.invariant_ids`; `_hard_coded_threshold` reads
`profile.threshold.value`. No function in `openspec_graph/` accepts a
previously-saved card and a current `StackProfile` together, so no code path
can attribute a stale citation to the change that made it stale.
`dialect_card.diff_cards` knows what changed in the machinery and knows
nothing about specs; `ParsedSpec.make_refs`/`invariant_refs`/`adr_refs`/
`hard_coded_thresholds` (`openspec_graph/parse_model.py`) know what each spec
cites and nothing about history. The join does not exist.

---

## Requirements

- R-DL-1: `planlint delta --baseline CARD.json` MUST report, for every parsed
  spec in the target tree, each citation that the **baseline card's**
  machinery satisfied and the **live profile's** machinery does not.
- R-DL-2: A citation the baseline card did **not** satisfy MUST NOT be
  reported. `delta` reports staleness caused by a machinery change since the
  baseline; a citation that was already broken in the baseline is G004's or
  G005's finding at HEAD and is not this verb's subject.
- R-DL-3: Every reported entry MUST correspond to a field that
  `dialect_card.diff_cards(baseline, profile.to_card())` also reports as
  changed. An entry with no corresponding machinery change is, by definition,
  not a delta.
- R-DL-4: The reportable entry kinds MUST be exactly these four, and no
  others:
  - `make_target` — a cited `make <target>` present in the baseline's
    `make_targets` and absent from the live profile's; the entry names the
    target.
  - `invariant` — a cited `INV-n` present in the baseline's `invariant_ids`
    and absent now; the entry names the id.
  - `adr` — a cited `ADR-n` present in the baseline's `adr_ids` and absent
    now; the entry names the id.
  - `threshold` — a hard-coded threshold value in the spec equal to the
    baseline's `threshold.value` when the live `threshold.value` differs; the
    entry names both the old and the new value.
- R-DL-5: A `threshold` entry MUST be raised only when the offending line
  yields exactly one threshold-shaped value and that value equals the
  baseline's floor. A line carrying two or more such values MUST NOT be
  reported — the same single-unambiguous-match rule
  `rules_generic._hard_coded_threshold` already applies, computed through the
  same `parse_semantics.threshold_values` helper.
- R-DL-6: A field entirely **absent** from the baseline card (a card saved
  before that field existed) MUST be skipped for that entry kind, exactly as
  `dialect_card.diff_cards` skips it. An older schema MUST NOT be read as
  "every citation of that kind went stale".
- R-DL-7: `delta --format json` MUST emit an object carrying exactly
  `schema_version`, `tool_version`, `target` (absolute, the base its relative
  paths resolve against), `machinery_changes` (the `diff_cards` list,
  verbatim) and `stale` (the entries) -- and nothing else. In particular it
  MUST NOT carry the baseline's own path (`DEC-DL-007`): that is whatever
  string the operator typed, frequently absolute, and it would make two runs
  of the same comparison differ by nothing but where the card happened to
  sit. The entry list MUST be stable-ordered and the whole payload MUST be
  byte-identical across re-runs on an unchanged repository.
- R-DL-8: `delta` MUST exit `0` when no citation went stale, `1` when at
  least one did, and `2` when the baseline file cannot be read, is not JSON,
  or is not a JSON object.
- R-DL-9: The exit-2 message shape MUST be copied from `cmd_detect`'s
  `--diff` handling — `cannot read --baseline <path>: <reason>` for an
  unreadable or malformed file, and the `expected a JSON object, got <type>`
  form for a JSON value that is not an object.
- R-DL-10: `delta.py` MUST be pure and stdlib-only: no `subprocess`, no
  file I/O, no git. Reading the baseline, discovering and parsing specs, and
  building the live profile are the CLI layer's job, mirroring how
  `cli.cmd_waivers` owns those for `ledger.py`.
- R-DL-11: `delta` MUST reuse `dialect_card.diff_cards` for the
  `machinery_changes` half rather than re-deriving what changed.
- C-DL-1: A `DeltaEntry` MUST NOT be a `rules.Finding` and MUST NOT reach any
  finding stream: not `rules --json`, not `validate`'s `findings` array or
  `blocking` count, not `graph --format json`'s `broken_links`, not the
  Mermaid rendering. `openspec_graph/rules.py`'s `RULES` tuple and
  `README.md`'s rules table MUST be unchanged.
- C-DL-2: `delta` MUST write nothing to the target tree, in any output mode —
  the same read-only guarantee `detect` carries (`AC-DC-3`).
- C-DL-3: This change MUST NOT add a `subprocess` call site anywhere in
  `openspec_graph/`. `detect._current_sha` MUST remain the only one and
  `tests/test_decomposition.py::test_only_detect_imports_subprocess` MUST pass
  unmodified.
- C-DL-4: No existing verb's output, exit code, or golden hash may change.
  `_EXPECTED_HASHES["validate"]`, `["graph"]`, and `["rules"]` MUST be
  unchanged.

---

## Decisions

- **DEC-DL-001 (rejects the roadmap's own `--since <ref>` sketch):**
  `docs/differentiation-roadmap.md`'s CP-5 section specifies
  `planlint delta --since <ref> --format json` and a touch map reading "git
  diff of machinery files". That form is rejected, not deferred, on three
  independent grounds — any one of them would be sufficient.
  *First, the subprocess safety argument does not transfer.* Reading machinery
  at an old ref needs `git show`, a second `subprocess` call site.
  `detect._current_sha` is the only one in the package today, and its docstring
  earns that exemption specifically on the grounds that "the argument vector is
  a fixed literal with no target-controlled input" — which is why
  `DEC-MP-001`'s ban on shelling out to inspect an untrusted repository does
  not reach it. A `--since <ref>` takes a *user-supplied* ref straight into the
  argv, so the fixed-literal premise is exactly what is lost, and the
  exemption cannot be reused.
  `tests/test_decomposition.py::test_only_detect_imports_subprocess` enforces
  the boundary statically, and it globs dynamically, so a new `delta.py`
  importing `subprocess` fails the suite the moment it is written — correctly.
  *Second, `profile()` is not addressable by ref.* `detect.profile()` takes a
  filesystem root, and `_threshold`, `_invariants`, and `_adrs` are multi-file
  discovery over that root (candidate lists tried in priority order —
  `INVARIANT_SOURCES`, the ADR directory-then-index fallback, the
  governance-policy-then-`pyproject.toml` chain), not single files a
  `git show <ref>:<path>` could hand back. A ref-based design would have to
  re-implement every one of those discovery walks over git objects, and would
  then have two implementations of "where does this repo keep its floor" to
  drift apart.
  *Third, the capability already exists by composition.* The saved-card idiom
  is established: `detect --diff PREV_CARD.json` (`cli.cmd_detect`). And "since
  a ref" is available for free through the worktree pattern
  `.github/workflows/ci.yml`'s graph-diff job already uses —
  `git worktree add /tmp/base "$BASE"`, then
  `planlint --target /tmp/base detect --format json > base.json`. Git stays in
  the CI harness, where it belongs and where it is already present, and the
  tool stays a pure function of two filesystem trees.
- **DEC-DL-002 (what makes `delta` not a rename of `validate`):** the
  distinction is **attribution**, and it is a requirement (`R-DL-2`), not a
  matter of taste. Citing a make target that does not exist is *already* a
  G004 finding at HEAD; citing a missing invariant is *already* G005. If
  `delta` reported those, it would emit the same set `validate` already emits,
  under a second verb, with a different exit-code contract — strictly worse
  than not existing. What `delta` adds is the causal claim: this citation is
  stale *because the machinery changed since the baseline*. That claim is only
  true when the baseline satisfied the citation and the live profile does not,
  which is why the baseline-satisfied precondition is written into every entry
  kind in `R-DL-4` rather than left to the implementation. `R-DL-3` makes the
  claim mechanically checkable: no entry may exist without a corresponding
  `diff_cards` change.
- **DEC-DL-003 (entries are not Findings):** `DeltaEntry` is its own frozen
  dataclass, not a `rules.Finding`. A `Finding` is the output of evaluating a
  numbered rule at a severity; `delta` evaluates no rule and has no severity to
  assign — its output is a report about two points in time. The practical
  consequence of smuggling it into the finding stream would be immediate and
  bad: `validate`'s `blocking` count and `graph --format json`'s
  `broken_links` would grow (breaking `AC-GR-4`'s equality), `rules --json`
  would advertise a rule id that does not exist in `RULES`, and all three
  golden hashes in `tests/test_decomposition.py` would need re-pinning for a
  verb that changes none of those outputs. `C-DL-1` states the separation and
  `AC-DL-11` pins it.
- **DEC-DL-004 (threshold matching reuses G001's rule):** the `threshold`
  entry kind is computed through `parse_semantics.threshold_values` with the
  same "exactly one value on the line, and it matches" condition
  `rules_generic._hard_coded_threshold` uses to suppress itself. Two
  implementations of "does this line cite the floor" would eventually disagree,
  and the disagreement would be silent: `delta` would report a line G001
  excuses, or excuse a line G001 reports. The condition also protects the
  headline case from its own worst false positive — G001's own comment names
  it, a delta *description* carrying two threshold-shaped values on one line
  ("raised from the old floor to the new one"), which must not itself be
  reported as stale.
- **DEC-DL-005 (`was`/`now` are values, not presence flags):** each entry
  carries `was` and `now` as the baseline and live values of the machinery
  fact the citation depends on, with `now` rendered as JSON `null` for a
  removal. A removed make target is `was: "test-fast", now: null`; a moved
  floor carries the old number in `was` and the new one in `now`. The
  alternative — booleans, or the strings `"present"`/`"absent"` — reads
  identically for all four kinds and throws away the only number the headline
  case exists to print. One field pair serves all four kinds, so a consumer
  does not branch on `kind` to find the values.
- **DEC-DL-006 (an older baseline is not drift):** a key absent from the
  baseline card is skipped for that entry kind entirely, inheriting
  `dialect_card.diff_cards`'s documented rule verbatim rather than restating
  it. That rule exists because of a real regression class found in review on
  PR #13: a pre-`CP-AD` card carrying no `adr_ids` key, diffed after a tool
  upgrade, would otherwise report `adr_ids changed: None -> []` on an
  unchanged repository. The same trap is strictly worse here — reading an
  absent `invariant_ids` as an empty baseline set would make every cited
  `INV-n` look newly stale, producing a fabricated list of exactly the shape
  this verb exists to make trustworthy.
- **DEC-DL-007 (the JSON envelope):** `--format json` emits an object, not the
  bare list `waivers --format json` emits, because `delta` has two things to
  say: what changed in the machinery, and which citations that broke. It
  carries `schema_version` from a `DELTA_SCHEMA_VERSION` constant declared in
  `delta.py` — the module that owns the shape — following the three existing
  precedents (`dialect_card.SCHEMA_VERSION`, `witness.WITNESS_SCHEMA_VERSION`,
  `rule_types.FINDINGS_SCHEMA_VERSION`) rather than inventing a fourth home,
  and starting at `1` for the same reason `DEC-FE-010` gives. The baseline's
  own path is deliberately **not** a field: it is whatever string the operator
  typed, frequently absolute, and including it would make the payload
  non-byte-identical across two checkouts — the same portability argument
  `R-DC-1`/`R-DC-2` make for the card this envelope reports on.
- **DEC-DL-008 (exit 1 is the report):** a stale citation is not a
  precondition failure and not a rule finding; it is `delta` working. This is
  the same posture `detect --diff` already takes, which
  `skills/planlint-spec-governance/references/exit-codes.md` documents under
  "The one exit-1 case that is not a finding". That section becomes two cases
  and must be updated in the same change, or the reference will describe the
  CLI incorrectly the moment this ships — precisely the drift this tool
  fails other repositories for.
- **DEC-DL-009 (`--baseline`, not a positional):** the flag form mirrors
  `detect --diff PREV_CARD_JSON`, so the two card-consuming surfaces read the
  same way, and leaves the positional slot free. It is required rather than
  defaulted to a conventional path: `delta` with no baseline has no question
  to answer, and guessing a path would let a typo silently compare against a
  stale card. There is no `--fail-on`, because there are no severities to
  threshold on.
- **DEC-DL-010 (ordering is `(path, kind, subject)`):** path first so the
  output reads as a per-file list, which is how the operator will act on it
  ("open these seven specs"); `kind` before `subject` so that a spec with
  several stale citations groups them by category rather than interleaving an
  `INV-3` between two make targets. Ordering is a property of `build_delta`,
  not of the renderer, so the text and JSON outputs cannot disagree the way
  `validate`'s two branches once did (`DEC-FE-007`).

- **DEC-DL-011 (a spec added since the baseline is still reported, and this is
  a known limitation):** the predicate is "the cited thing was supported at
  the baseline and is not now". It says nothing about whether the *spec* was
  present at the baseline, because the dialect card does not record spec
  paths -- only the machinery. So a spec written after the baseline was taken,
  citing a target removed after the baseline was taken, is reported.

  Found by adversarial review, and worth stating plainly rather than
  discovering later: the report's framing ("what your change left behind")
  over-claims for that spec, since its citation was never satisfied by any
  tree the spec existed in. What each entry's message actually asserts is
  narrower and remains true -- the *target* existed at the baseline and does
  not now -- so the output is not false, but a reader inferring "I broke this
  spec" would be wrong about one case.

  Fixing it properly means recording the spec set in the card, which widens
  the card's schema and its `--diff` semantics for a narrow gain. Deferred
  deliberately. If it becomes a real annoyance, the fix is a card field, not
  a heuristic in `build_delta`.

---

## Acceptance Criteria

- [ ] **AC-DL-1:** With a baseline card whose floor is the old value and a
  live floor that differs, a spec hard-coding the old number is reported as a
  stale `threshold` entry naming both values, and the entry's `path` is the
  spec's repository-relative POSIX path. (R-DL-1, R-DL-4, DEC-DL-005)
  _Verified by:_ `pytest -k test_delta_reports_a_spec_citing_the_old_coverage_floor` · stage: `make test` (test not yet written)

- [ ] **AC-DL-2:** A spec citing `make <target>` that is in the baseline's
  `make_targets` and absent from the live profile's is reported as a
  `make_target` entry naming the removed target, with `now` as `null`.
  (R-DL-1, R-DL-4, DEC-DL-005)
  _Verified by:_ `pytest -k test_delta_names_the_removed_make_target` · stage: `make test` (test not yet written)

- [ ] **AC-DL-3:** A spec citing an `INV-n` present in the baseline's
  `invariant_ids` and absent now is reported as an `invariant` entry naming
  the id; the same holds for an `ADR-n` against `adr_ids`. (R-DL-1, R-DL-4)
  _Verified by:_ `pytest -k "test_delta_names_the_removed_invariant or test_delta_names_the_removed_adr"` · stage: `make test` (test not yet written)

- [ ] **AC-DL-4:** Every entry `build_delta` returns names a field that
  `dialect_card.diff_cards(baseline, profile.to_card())` also reports as
  changed — checked over a fixture with all four entry kinds present at once.
  (R-DL-3, R-DL-11, DEC-DL-002)
  _Verified by:_ `pytest -k test_every_delta_entry_corresponds_to_a_machinery_change` · stage: `make test` (test not yet written)

- [ ] **AC-DL-5 (non-success):** A baseline card taken from the *same,
  unchanged* repository yields an empty `stale` list and exit 0 —
  `delta` manufactures nothing. Asserted both at the `build_delta` level and
  end-to-end through the CLI, over a fixture that is first asserted to contain
  real citations, so the criterion cannot pass vacuously on an empty tree.
  (R-DL-1, R-DL-8)
  _Verified by:_ `pytest -k "test_delta_on_an_identical_baseline_is_empty or test_cli_delta_exits_zero_on_an_identical_baseline"` · stage: `make test` (test not yet written)

- [ ] **AC-DL-6 (non-success):** A spec citing a make target that is absent
  from the baseline's `make_targets` **and** absent from the live profile's
  is **not** reported as a delta, even though `validate` reports it
  as a G004 finding in the same fixture. The test asserts both halves — the
  delta list is empty and the G004 finding is present — so the boundary
  between the two verbs is pinned, not merely implied. The same holds for an
  `INV-n` undeclared in both. (R-DL-2, DEC-DL-002)
  _Verified by:_ `pytest -k test_delta_ignores_a_citation_already_broken_in_the_baseline` · stage: `make test` (test not yet written)

- [ ] **AC-DL-7:** `delta --format json` emits `schema_version`,
  `machinery_changes`, and `stale`; entries are ordered by
  `(path, kind, subject)`; and two consecutive runs over an unchanged
  repository produce byte-identical stdout. Entry order is asserted against a
  fixture whose specs are created in an order that differs from the sorted
  one, so a run that happened to be sorted by accident does not pass.
  (R-DL-7, DEC-DL-007, DEC-DL-010)
  _Verified by:_ `pytest -k "test_delta_entries_are_stable_ordered or test_cli_delta_json_is_byte_identical_across_runs or test_cli_delta_json_lists_stale_citations_with_schema_version"` · stage: `make test` (test not yet written)

- [ ] **AC-DL-8 (non-success):** A baseline card with `invariant_ids`,
  `adr_ids`, and `threshold` keys entirely absent — an older schema — yields
  no entries of those kinds, rather than reporting every cited `INV-n`,
  `ADR-n`, and threshold as newly stale. The card is otherwise valid and the
  live profile does declare all three. (R-DL-6, DEC-DL-006)
  _Verified by:_ `pytest -k test_delta_skips_a_field_absent_from_an_older_baseline_card` · stage: `make test` (test not yet written)

- [ ] **AC-DL-9 (non-success):** A line carrying two threshold-shaped values
  — a delta description of the floor move itself — is not reported as a stale
  `threshold` entry, matching `rules_generic._hard_coded_threshold`'s own
  single-unambiguous-match condition. (R-DL-5, DEC-DL-004)
  _Verified by:_ `pytest -k test_delta_ignores_an_ambiguous_threshold_line` · stage: `make test` (test not yet written)

- [ ] **AC-DL-10 (non-success):** A `--baseline` path that does not exist, one
  whose contents are not JSON, and one whose JSON top level is a list each
  exit 2 with the `cmd_detect --diff` message shape — never a traceback and
  never exit 1. (R-DL-8, R-DL-9)
  _Verified by:_ `pytest -k "test_cli_delta_with_missing_baseline_is_a_usage_error or test_cli_delta_with_a_non_object_baseline_is_a_usage_error"` · stage: `make test` (test not yet written)

- [ ] **AC-DL-11 (non-success):** A `DeltaEntry` is not a `rules.Finding` and
  reaches no finding stream: over a fixture with stale citations,
  `validate --json`'s `findings`/`blocking`, `graph --format json`'s
  `broken_links`, and `rules --json` are identical with and without the
  `delta` verb exercised; the three golden hashes are unchanged; and the
  `RULES` registry baseline is untouched. (C-DL-1, C-DL-4, DEC-DL-003)
  _Verified by:_ `pytest -k "test_delta_entries_never_reach_the_finding_stream or test_output_byte_identical or test_rule_registry_baseline_is_unchanged"` · stage: `make test` (`test_delta_entries_never_reach_the_finding_stream` not yet written; the other two exist)

- [ ] **AC-DL-12 (non-success):** `delta` writes nothing to the target tree in
  either output mode, asserted by the recursive before/after snapshot
  `test_detect_never_writes_to_the_target_repo` already uses. (C-DL-2)
  _Verified by:_ `pytest -k test_cli_delta_never_writes_to_the_target_repo` · stage: `make test` (test not yet written)

- [ ] **AC-DL-13 (non-success):** `delta.py` imports no non-stdlib module and
  no `subprocess`; `detect.py` remains the only `subprocess` importer in the
  package; and `delta.py` imports neither `cli` nor `graph`. Covered by the
  existing dynamic guards once `"delta"` is added to `_NEW_MODULES`.
  (R-DL-10, C-DL-3, DEC-DL-001)
  _Verified by:_ `pytest -k "test_only_detect_imports_subprocess or test_new_modules_stdlib_only or test_import_boundary_discipline"` · stage: `make test` (all three exist; they cover the new module once it is registered)

- [ ] **AC-DL-14:** `delta` appears in `tests/test_cli_surface.py`'s
  `ALLOWED_VERBS` and in the parser, and no authoring verb leaks in beside it.
  (R-DL-1)
  _Verified by:_ `pytest -k "test_cli_verbs_are_exactly_the_allow_list or test_cli_rejects_authoring_verbs"` · stage: `make test` (both exist; the allow-list must be updated for them to pass)

- [ ] **AC-DL-15:** `README.md` documents the `delta` verb with a worked
  two-step example (`detect --format json > base.json`, then
  `delta --baseline base.json`), the exit-codes reference documents `delta`'s
  exit 1 as a second non-finding exit-1 case beside `detect --diff`, and
  `docs/differentiation-roadmap.md`'s CP-5 section records that `--since` was
  rejected and what shipped instead. No doc still describes CP-5 as
  `--since <ref>`. (R-DL-8, DEC-DL-001, DEC-DL-008)
  _Verified by:_ manual review · stage: `make docs-check`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-DL-1..14 |
| Core | `make ci` | AC-DL-1..14, plus lint and this repo's own `planlint validate` |
| Docs | `make docs-check` | AC-DL-15 (manual review; no automated content check covers README/reference prose) |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
