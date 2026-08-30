# Spec: Waiver Ledger and Invariant Lints

> **Change:** `add-waiver-ledger-and-inv-lints`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

Waivers are silently downgraded to INFO today with no record of what was waived, no enforcement that a reason was given (the regex already captures one; `suppressions()` discards it), and invariant citation is checked in only one direction — a declared invariant no spec cites at all is invisible.

**Evidence:** `parse_semantics.SUPPRESS`'s second capture group (the reason) was parsed but never read by any caller before this change; `rules_generic._unknown_invariant` (G005) only ever checks "a cited invariant is declared," never "a declared invariant is cited."

---

## Requirements

- R-WL-1: A waiver comment's reason text and line position MUST be captured, not discarded.
- R-WL-2: A waiver with no reason text MUST fail the gate.
- R-WL-3: The reason-enforcement rule MUST NOT be suppressible by waiving itself with no reason.
- R-WL-4: A declared invariant cited by no living spec, and not waived, MUST be reported.
- R-WL-5: The orphan-invariant check MUST NOT evaluate against a `--change`-filtered subset of the spec tree — doing so would report every invariant outside the filtered view as falsely orphaned.
- R-WL-6: `planlint waivers --format json` MUST emit a ledger of every waived rule across the tree, with file, line, reason, and owning change package, in stable order.
- C-WL-1: New `Finding`/`ParsedSpec` fields MUST be additive only — existing JSON shapes only grow, never change.
- C-WL-2: The existing waive-to-INFO downgrade mechanism (`rules.evaluate`) MUST NOT change for any already-waivable rule.

---

## Decisions

- **DEC-WL-001:** No existing `Rule.check: Callable[[ParsedSpec, StackProfile], Iterable[str]]` can express "cited by *any* spec in the tree" — every other rule answers a question local to one file. Proven concretely: `tests/test_graft.py`'s own `repo` fixture declares both `INV-1`/`INV-2`, but `GOOD_HARNESS` only cites `INV-1` — a naive per-spec G006 would spuriously fire on dozens of existing tests the moment it's registered. Resolved via a new `rules.evaluate_tree(specs, profile)`, a sibling to `evaluate()`, called once per `validate`/`graph` run after every living spec is parsed. G006 still gets a `Rule` registry entry (an inert stub `check`) purely for `planlint rules` discoverability.
- **DEC-WL-002:** AC-WL-3 (a waiver needs a reason) gets its own new rule, **G007** — G006 is the only ID the roadmap itself reserves, and this project's philosophy is that every violation is a numbered Finding, never a side channel.
- **DEC-WL-003 (found by adversarial review before implementation):** `cmd_validate` filters `spec_files` by `--change` before its per-spec loop. Naively feeding that filtered set into `evaluate_tree()` would make G006 report every invariant outside the filtered view as falsely orphaned. Resolved: G006 is skipped entirely when `--change` narrows the view, with an explicit `INFO` note on stderr — a `--change`-scoped review's contract is "does this one package pass," which a tree-wide check breaks the locality of either way. `graph.py`'s `build_graph()` has no `--change` filtering at all, so it is unaffected and always runs G006 unscoped.
- **DEC-WL-004 (found by adversarial review before implementation):** An unset `path` on a `Finding` defaults to `None`; `cmd_validate`'s text renderer sorts by `(str(f.path), f.rule)`, and `str(None) == "None"` sorts before every real lowercase path. Resolved: G006's `Finding` always sets `path=profile.invariant_source` — the file the orphaned invariant is actually declared in — so it sorts and renders like every other rule's finding.
- **DEC-WL-005:** G007 is exempt from being suppressed by waiving *itself* with no reason (`rules._NON_WAIVABLE`) — without this, the enforcement rule could trivially silence its own violation report.

---

## Acceptance Criteria

- [x] **AC-WL-3 (non-success):** A waiver with no reason text fails `make test`/`validate`. `<!-- specgraph:allow ... -->` naming a rule with no reason now fails the gate via G007. (R-WL-1, R-WL-2)
  _Verified by:_ `pytest -k test_cli_validate_fails_when_a_waiver_has_no_reason` · stage: `make test`

- [x] **AC-WL-4:** The named rule's own waive-to-INFO downgrade is completely unchanged — an unreasoned waiver both downgrades the named rule to INFO *and* independently fires G007 ERROR naming it. (C-WL-2)
  _Verified by:_ `pytest -k test_unreasoned_waiver_downgrades_the_named_rule_and_also_fires_g007` · stage: `make test`

- [x] **AC-WL-5 (non-success):** A properly-reasoned waiver does not trip G007. (R-WL-2)
  _Verified by:_ `pytest -k test_reasoned_waiver_does_not_trip_g007` · stage: `make test`

- [x] **AC-WL-6:** G007 fires identically in both dialects (the waiver syntax has no dialect branching). (R-WL-2)
  _Verified by:_ `pytest -k test_g007_fires_regardless_of_dialect` · stage: `make test`

- [x] **AC-WL-7 (non-success):** G007 cannot be silenced by waiving itself with no reason. (R-WL-3, DEC-WL-005)
  _Verified by:_ `pytest -k test_g007_is_not_suppressible_by_waiving_itself_without_a_reason` · stage: `make test`

- [x] **AC-WL-8:** A single comment naming multiple rules with no reason fires one independent G007 finding per rule name. (R-WL-1, R-WL-2)
  _Verified by:_ `pytest -k test_multi_rule_waiver_with_no_reason_fires_one_g007_per_waived_rule` · stage: `make test`

- [x] **AC-WL-9 (non-success):** `suppressions()`'s signature/behavior is unchanged after being refactored to derive from `parse_waivers()`. (C-WL-1)
  _Verified by:_ `pytest -k test_suppressions_unchanged_behavior_after_waiver_refactor` · stage: `make test`

- [ ] **AC-WL-2:** New rule G006 (WARN): a declared invariant cited by no living spec and not waived is reported as an orphan invariant. (R-WL-4)
  _Verified by:_ `pytest -k test_g006_fires_for_a_declared_invariant_no_spec_cites` · stage: `make test`

- [ ] **AC-WL-10 (non-success):** G006 does not fire once an invariant is cited anywhere in the tree. (R-WL-4)
  _Verified by:_ `pytest -k test_g006_does_not_fire_once_cited_anywhere_in_the_tree` · stage: `make test`

- [ ] **AC-WL-11:** G006 downgrades to INFO when waived anywhere in the tree. (R-WL-4)
  _Verified by:_ `pytest -k test_g006_is_downgraded_to_info_when_waived_anywhere_in_the_tree` · stage: `make test`

- [ ] **AC-WL-12 (non-success):** G006 is skipped (with an INFO note) when `--change` narrows a `validate` run, rather than producing false positives. (R-WL-5, DEC-WL-003)
  _Verified by:_ `pytest -k test_g006_is_skipped_under_change_scoping` · stage: `make test`

- [ ] **AC-WL-13:** `graph --format json`'s `broken_links` count still equals the total finding count (including tree-level findings) with G006 present — the AC-GR-4 invariant holds. (C-WL-1)
  _Verified by:_ `pytest -k test_graph_matches_validate_findings_with_an_orphan_invariant` · stage: `make test`

- [ ] **AC-WL-1:** `planlint waivers --format json` emits a ledger of every waived rule with file, line, reason, and the owning change package, in stable order. (R-WL-6)
  _Verified by:_ `pytest -k test_cli_waivers_json_lists_reason_file_line_and_change` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-WL-1..13 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
