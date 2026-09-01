# Spec: SpecKit Dialect

> **Change:** `add-speckit-dialect`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

`planlint` recognizes spec files only at
`openspec/changes/<name>/specs/<capability>/spec.md`, in one of two markdown
dialects (`upstream`/OpenSpec, `harness`). A repo using GitHub's SpecKit tool
writes files at `specs/<NNN-feature>/spec.md` at the repo root — no
`openspec/` ancestor at all — in a materially different grammar
(`FR-00N`/`SC-00N` identifiers, no delta/ADDED-MODIFIED-REMOVED concept,
Given/When/Then as inline prose inside prioritized user stories rather than a
dedicated level-4 `Scenario:` heading). Every `planlint` verb that touches specs
hard-fails before any dialect logic runs: a SpecKit-only repo is invisible to
`planlint`, not mis-parsed.

**Evidence:** `openspec_graph/detect.py:493-497` hardcodes
`openspec_root = root / "openspec"` and gates all spec discovery on
`has_openspec = openspec_root.is_dir()`. `openspec_graph/cli.py:168-170`
(`cmd_validate`), `cli.py:287-289` (`cmd_graph`'s `--change` guard), and
`cli.py:328-330` (`cmd_waivers`) each print
`"no openspec/ directory; run \`\`planlint init\`\` first"` and exit 2 before
any spec is read. `openspec_graph/graph.py:233-239`
(`build_graph`'s `NoOpenSpecTreeError` guard, and its own
`detect.find_spec_files(profile.openspec_root)` internal gather)
independently hard-codes the identical `openspec_root`-only assumption a
second time. Separately, `openspec_graph/parse_semantics.py`'s
`HARD_THRESHOLD` regex (`r"(?:≥|>=|>)\s*\d{2,3}\s*%?|\b\d{2,3}\s*%"`) matches
the `95%` in a completely conventional SpecKit Success Criterion bullet
(`SC-001: 95% of new users complete onboarding without contacting support`),
and `THRESHOLD_ALLOWLIST` has no token that exempts it — confirmed by direct
inspection of both, not assumed — so G003 (ERROR, default `--fail-on` level)
would fail nearly every real SpecKit spec's Success Criteria section without
a dedicated fix.

---

## Requirements

- R-SK-1: `StackProfile` MUST gain `speckit_root: Path | None = None` and
  `feature_dirs: tuple[Path, ...] = ()` fields, appended strictly after
  `current_sha` (the current last field) — never inserted earlier, per this
  module's own positional-dataclass append-only discipline.
- R-SK-2: `find_speckit_spec_files(speckit_root)` MUST discover every
  `specs/<feature>/spec.md` file directly under `speckit_root`, one segment
  shallower than `find_spec_files`'s `changes/*/specs/*/spec.md`.
- R-SK-3: `filter_speckit_by_feature(spec_files, feature)` MUST narrow a
  SpecKit spec-file list to one feature's own `spec.md`, mirroring
  `filter_by_change`'s fixed-position anchor one level shallower.
- R-SK-4: `profile()` MUST set `speckit_root` only when `root / "specs"` is a
  directory **and** `find_speckit_spec_files()` finds at least one
  `*/spec.md` beneath it; a bare `specs/` directory with no `spec.md` files
  MUST NOT set `speckit_root`.
- R-SK-5: `profile()` MUST union every spec file discovered under
  `openspec_root` and `speckit_root` before calling `detect_dialect()`, and
  both roots MUST be able to coexist on the same `StackProfile`
  simultaneously.
- R-SK-6: `StackProfile.as_dict()`/`to_card()` and
  `dialect_card._COMPARABLE_FIELDS` MUST expose `speckit_root`/
  `feature_dirs` so a change in either is caught by `detect --diff`.
- R-SK-7: `parse_semantics.py` MUST expose shared marker predicates
  (`is_upstream_marked`, `is_harness_marked`, `is_speckit_marked`) that both
  `detect.detect_dialect()` and `parse.parse_spec()`'s pre-resolution branch
  call, replacing the two independently duplicated marker-string checks that
  exist today (`detect.py:413-416`, `parse.py:66-71`).
- R-SK-8: `detect_dialect()` MUST classify a spec file as speckit-marked when
  it contains `### Functional Requirements` together with an `FR-\d+` id, or
  `## Success Criteria` together with an `SC-\d+` id.
- R-SK-9: `detect_dialect()` MUST report `"mixed"` whenever more than one of
  the three dialect predicates matches across the tree's spec files
  (`present > 1`), not via an enumerated set of pairwise combinations.
- R-SK-10: `detect_dialect()` MUST remain byte-identical, on the pre-existing
  two-dialect golden fixture used by `tests/test_decomposition.py`'s hash
  test, after the 3-way rewrite.
- R-SK-11: `parse.py::parse_spec()` MUST dispatch `dialect == "speckit"` to a
  new `parse_speckit()` via an explicit `elif` branch, distinct from the
  existing harness `else` branch.
- R-SK-12: `parse_spec()`'s `mixed`/`unknown`/`auto` pre-resolution MUST
  check upstream markers first, then speckit markers, else fall back to
  harness — matching `detect_dialect()`'s own precedence.
- R-SK-13: `parse_speckit(text)` MUST return the same
  `(tuple[Requirement,...], tuple[Criterion,...])` shape
  `parse_harness()`/`parse_upstream()` already return.
- R-SK-14: `parse_speckit()` MUST map each `FR-00N` bullet under
  `### Functional Requirements` to a `Requirement`, each `SC-00N` bullet
  under `## Success Criteria` to a `Criterion`, and Given/When/Then prose
  inside each `### User Story N` block to a synthesized `Criterion` with a
  `US<n>-AS<m>` id, reusing `parse.scenario_has_gwt()` for WHEN/THEN
  detection rather than a new implementation.
- R-SK-15: the speckit dispatch branch MUST get its own escape hatch (an
  empty parse plus a `_REQUIREMENT`-pattern match reclassifying the spec as
  upstream), matching the existing harness branch's equivalent hatch; no
  reciprocal hatch reclassifying a harness-dispatched spec as speckit MUST
  be added.
- R-SK-16: `rules_speckit.py` MUST implement S001 (ERROR: an unresolved
  `[NEEDS CLARIFICATION]` marker is present), S002 (ERROR: a duplicate
  `FR-`/`SC-` identifier), S003 (WARN: a requirement with no SHALL/MUST, via
  `Requirement.is_normative`), and S004 (WARN: a scenario missing
  WHEN/THEN, via `scenario_has_gwt()`).
- R-SK-17: `rules.py` MUST register `SPECKIT_RULES` additively:
  `NON_WITNESS_RULES = GENERIC_RULES + HARNESS_RULES + UPSTREAM_RULES + SPECKIT_RULES`.
- R-SK-18 (mandatory fix): G002's `dialects` tuple MUST narrow from
  `("*",)` to `("harness", "upstream")`.
- R-SK-19 (mandatory fix): G003 MUST exempt the `## Success Criteria`
  section body from the hard-coded-threshold scan when
  `dialect == "speckit"`.
- R-SK-20: `cmd_validate`'s and `cmd_waivers`'s guard clauses MUST only fail
  (exit 2) when both `prof.openspec_root` and `prof.speckit_root` are
  absent; both commands' spec-file gathering MUST union
  `find_spec_files()` and `find_speckit_spec_files()` results.
- R-SK-21: `graph.py`'s `NoOpenSpecTreeError` guard and its internal
  spec-file gather MUST receive the identical union treatment as
  `cmd_validate`/`cmd_waivers`.
- R-SK-22: `cli.py`'s `--dialect` argparse choices MUST gain `"speckit"` on
  the `validate` and `waivers` subparsers only.
- R-SK-23: `cmd_detect`'s text output MUST include a
  `specs/ (SpecKit)  present/ABSENT` line.
- R-SK-24: every doc/source location that states the total rule count or a
  rule family's id range (README's rules table, `docs/architecture/c4.md`'s
  module map + rule count + range comment, `docs/agents-skills-harness.md`,
  `docs/next-steps.md`, `docs/differentiation-roadmap.md`, `rules.py`'s own
  module docstring) MUST be updated to include the new `S` family and match
  `rules.RULES` exactly, mechanically verified by
  `tests/test_rule_registry_docs.py`.
- R-SK-25: `tests/test_rule_registry_docs.py`'s `_FAMILIES` tuple and its
  README-table regex MUST be updated to accept the `S` prefix before
  `rules_speckit.py` is registered into `rules.py` — not after.
- R-SK-26: `tests/baseline_rules.json` MUST be regenerated and
  `tests/test_decomposition.py::_EXPECTED_HASHES["rules"]` MUST be
  re-pinned once `SPECKIT_RULES` is registered; the
  `["validate"]`/`["graph"]` hashes MUST stay unchanged, confirmed
  empirically against the existing canonical fixture (which has no
  `specs/` directory).
- R-SK-27: S004, and any other check that depends on `GWT_SCENARIO`, MUST
  stay at WARN severity until validated against a real/representative
  SpecKit corpus (Milestone 5); no dependent check MAY be promoted to
  ERROR as part of this change.
- C-SK-1: `[NEEDS CLARIFICATION]` MUST NOT be used as part of the SpecKit
  dialect fingerprint (`detect_dialect()`'s speckit predicate).
- C-SK-2: `parse.py::parse_spec()`'s three-way dispatch MUST NOT be
  refactored into a dict/registry-based mechanism.
- C-SK-3: `Criterion.requirement_refs` MUST stay empty (`()`) for every
  `Criterion` `parse_speckit()` produces — no FR↔SC link may be
  synthesized.
- C-SK-4: no "orphaned requirement" rule MAY be added for the speckit
  dialect.
- C-SK-5: `cmd_graph`'s `--change`-scoped inner guard MUST remain gated on
  `prof.openspec_root` alone, never unioned with `prof.speckit_root`.
- C-SK-6: `--dialect` argparse choices MUST NOT gain `"speckit"` on the
  `new` subparser (`p_new`); `cmd_graph` MUST NOT gain a `--dialect` flag
  as part of this change.
- C-SK-7: no `--feature` CLI flag MAY be added in this change;
  `filter_speckit_by_feature()` MUST exist unwired to any CLI flag.
- C-SK-8: G002/G003's existing behavior for the harness and upstream
  dialects MUST be byte-unchanged by this change.
- C-SK-9: `scaffold.py`/`scaffold_templates.py` MUST NOT be modified by
  this change; `planlint new`/`init` MUST NOT gain SpecKit scaffolding.
- C-SK-10: `planlint` MUST NOT parse `plan.md` or `tasks.md` under any
  feature directory as part of this change; only `spec.md` is read.

---

## Decisions

- **DEC-SK-001:** `speckit_root`/`feature_dirs` are appended strictly after
  `current_sha`, the true current last field of `StackProfile` — mirrors
  `ParsedSpec.adr_refs`'s own documented discipline (`parse_model.py:80-86`):
  a positional dataclass's new fields must go after *every* existing field,
  not just after the ones added most recently, or an existing keyword-only
  (or positional) call site could silently shift.
- **DEC-SK-002:** the SpecKit fingerprint is content-gated
  (`root / "specs"` is a directory **and** `find_speckit_spec_files()`
  finds ≥1 `*/spec.md`), not a bare `is_dir()` check like `openspec_root`'s.
  `specs/` alone is too common a directory name (OpenAPI, RSpec,
  JSON-schema conventions all use it) to trust structurally — an
  `is_dir()`-only fingerprint would set `speckit_root` on any repo with an
  unrelated `specs/` directory and misreport its dialect.
- **DEC-SK-003:** `openspec_root` and `speckit_root` can coexist on the same
  profile; `profile()` unions both roots' discovered spec files before
  calling `detect_dialect()` rather than picking one exclusively. This
  supports a mid-migration repo (one still carrying legacy `openspec/`
  packages while adopting SpecKit) without forcing an either/or choice
  neither this tool nor the target repo's own migration state actually has.
- **DEC-SK-004:** `speckit_root`/`feature_dirs` are added to
  `dialect_card._COMPARABLE_FIELDS`/`to_card()`/`as_dict()` with no
  `SCHEMA_VERSION` bump — mirrors the `adr_source`/`adr_ids` precedent
  (`DEC-AD-009`): `diff_cards()`'s existing absent-key skip already treats a
  field missing from an older card as a schema addition, not drift, so an
  old card simply doesn't compare a field it predates.
- **DEC-SK-005:** `graph.py:233-239` gets the identical union fix as
  `cli.py`'s three guards, both in its `NoOpenSpecTreeError` raise and in
  its own internal `detect.find_spec_files(profile.openspec_root)` gather
  — verified directly by reading `graph.py`, which independently hardcodes
  the same `openspec_root`-only assumption `cli.py` does, rather than
  delegating to a shared helper. An earlier draft of this design assumed
  "zero changes needed" here on the theory that `cli.py`'s fix alone would
  suffice; that assumption did not survive reading `graph.py`'s own source.
- **DEC-SK-006:** `cmd_graph`'s `--change`-scoped inner guard stays
  openspec-only, deliberately not unioned with `speckit_root`. `--change`
  is OpenSpec vocabulary (a `changes/<name>/` directory) with no SpecKit
  equivalent; unioning it would let a SpecKit-only repo pass the guard and
  then produce a less informative "no specs found for change X" error
  instead of the more accurate "this repo has no change packages at all."
- **DEC-SK-007:** no `--feature` CLI flag is added in v1.
  `filter_speckit_by_feature()` exists for shape-parity with
  `filter_by_change` and for future use, but nothing wires it to the CLI —
  this project has repeatedly declined to build ahead of a committed
  acceptance criterion (mirrors `DEC-WM-002`/`DEC-AD-007`'s precedent), and
  no AC in this spec names a `--feature`-scoped verb.
- **DEC-SK-008:** `--dialect` argparse choices gain `"speckit"` on `p_val`/
  `p_waivers` only — not `p_new` (scaffolding SpecKit packages is out of
  scope, see proposal Non-Goals) and not `cmd_graph` (which has no
  `--dialect` flag today to extend at all).
- **DEC-SK-009:** shared marker predicates (`is_upstream_marked`,
  `is_harness_marked`, `is_speckit_marked`) are extracted into
  `parse_semantics.py`, fixing the pre-existing duplication between
  `detect.py:413-416` and `parse.py:66-71` as a byproduct of adding the
  third dialect, rather than adding a third independently-duplicated copy
  of the same two marker checks.
- **DEC-SK-010:** `[NEEDS CLARIFICATION]` is deliberately **not** part of
  the SpecKit dialect fingerprint. It's transient by design — SpecKit's own
  authoring convention resolves and removes these markers before a spec is
  considered complete — so a clean, fully-resolved SpecKit spec would have
  zero occurrences and would be misclassified `unknown` if detection
  depended on it.
- **DEC-SK-011:** `"mixed"` generalizes to `present > 1` across all three
  predicates, not an enumerated set of pairwise/triple combinations
  (upstream+harness, upstream+speckit, harness+speckit, all three). A
  single count comparison scales to N dialects without combinatorial
  branching, and the existing two-dialect precedent already collapses to
  one undifferentiated `"mixed"` value rather than naming which pair.
- **DEC-SK-012:** `detect_dialect()` must stay byte-identical on the
  existing two-dialect golden fixture after the 3-way rewrite — a hard
  compatibility constraint on this change, verified by the pre-existing
  `tests/test_decomposition.py` hash test, not merely a nice-to-have.
- **DEC-SK-013:** `parse.py::parse_spec()`'s dispatch gets an explicit
  `elif resolved == "speckit"` branch, not a dict/registry-based mechanism,
  despite now handling three dialects. This codebase has an on-the-record
  precedent against genericizing 2-3-instance special cases: `rules.py`'s
  `evaluate_tree()` docstring on G006/G009 cites `DEC-AD-003` ("generalizing
  this into a dynamic dispatch mechanism isn't warranted for two
  instances"), and `graph.py`'s `_TREE_FINDING_NODE_KIND` comment states
  the same for its own two-entry literal. Three instances still doesn't
  cross that threshold.
- **DEC-SK-014:** the speckit dispatch branch gets its own harness-style
  escape hatch (empty parse + `_REQUIREMENT` match → reclassify upstream)
  — matching, but not exceeding, the existing asymmetric-guard convention
  already present for the harness branch's rescue-to-upstream hatch. No
  reciprocal hatch reclassifying a harness-dispatched spec as speckit is
  added, deliberately: mirroring the existing asymmetry, not inventing a
  new one that this codebase has no other precedent for.
- **DEC-SK-015:** `parse_speckit()`'s Given/When/Then synthesis reuses
  `parse.scenario_has_gwt()` rather than reimplementing WHEN/THEN detection
  — single-sourced across all three dialects' GWT-shape checking (U003 for
  upstream, S004 for speckit), so a future fix to WHEN/THEN detection
  logic doesn't need to be applied twice.
- **DEC-SK-016:** `Criterion.requirement_refs` stays honestly empty for
  every SpecKit-derived `Criterion`. No FR↔SC citation convention exists in
  SpecKit's own grammar; synthesizing a fake link to satisfy some future
  orphan-style check would make that check fire on every requirement,
  always — a 100% false-positive rate, which is exactly why the
  orphan-requirement rule candidate below was dropped rather than built on
  a fabricated link.
- **DEC-SK-017:** no "orphaned requirement" SpecKit rule is added, unlike
  H003 (harness)/U002 (upstream)'s analogous checks. SpecKit's grammar has
  no FR↔SC citation convention to check an orphan against; building such a
  rule would require exactly the kind of fabricated link `DEC-SK-016`
  rejects, and without it the rule would report every requirement in every
  real SpecKit spec as orphaned.
- **DEC-SK-018:** the new rule family's prefix is `S` — the only unused
  single-letter prefix; `G`/`H`/`U`/`W` are all already claimed by
  `rules.RULES`'s existing families.
- **DEC-SK-019:** S001/S002 are ERROR — unresolved clarification markers and
  duplicate ids are unambiguous authoring defects, the same bar as
  G001/G004/H004. S003 is WARN, mirroring U004 exactly: a missing modal
  verb degrades review quality without making the document's claims false.
  S004 is WARN, not ERROR, specifically because `GWT_SCENARIO` is a
  prose-scrape unvalidated against real SpecKit corpus content — held
  below U003's ERROR precedent (which enforces the analogous GWT-shape
  check for upstream, where the corresponding level-4 `Scenario:` heading
  match is a rigid, already-validated regex, not a prose scrape) until
  Milestone 5 validates it against real content.
- **DEC-SK-020:** the G002/G003 fix is mandatory for this change to ship at
  all, not optional polish deferred to a later milestone. G003 is ERROR and
  `--fail-on ERROR` is `planlint validate`'s default; `HARD_THRESHOLD`'s
  bare-percentage alternative (`\b\d{2,3}\s*%`) matches the `95%` in a
  completely conventional SpecKit Success Criterion bullet, and
  `THRESHOLD_ALLOWLIST` has no token that exempts it. Shipping SpecKit
  support without this fix would make `planlint validate` fail nearly every
  real SpecKit spec by default — net-negative for adoption, not merely an
  incomplete feature. G002 (≥1 negative-phrased criterion repo-wide) fails
  most SpecKit specs too, since SpecKit's own Success Criteria convention
  is positive-phrased by design.
- **DEC-SK-021:** G002's fix is dialect-narrowing
  (`dialects=("*",) -> ("harness", "upstream")`), an explicit opt-out for
  speckit, rather than teaching G002 a second, speckit-specific
  positive-phrasing heuristic. Narrowing scope is simpler and more honest
  than inventing a new detection heuristic this design has no validated
  corpus to build from yet (the same caution behind holding S004 at WARN,
  `DEC-SK-019`).
- **DEC-SK-022:** G003's fix exempts only the `## Success Criteria` section
  body, using the same blank-the-span-preserve-line-numbers technique
  `strip_waiver_comments()` already uses in `parse_semantics.py`, when
  `dialect == "speckit"`. Zero behavior change for harness/upstream, since
  neither existing fixture (`good_harness.md`, `good_upstream.md`) has that
  heading.

---

## Acceptance Criteria

- [ ] **AC-SK-1:** `StackProfile` still constructs via every existing
  keyword-only call site without passing `speckit_root`/`feature_dirs` —
  both default, so the new fields are additive, not breaking. (R-SK-1)
  _Verified by:_ `pytest -k test_stack_profile_construction_still_works_without_speckit_fields` · stage: `make test` (test not yet written)

- [ ] **AC-SK-2:** `find_speckit_spec_files()` discovers every
  `specs/<feature>/spec.md` file directly under a `speckit_root`, ignoring
  any `changes/` nesting. (R-SK-2)
  _Verified by:_ `pytest -k test_find_speckit_spec_files_discovers_feature_spec_files` · stage: `make test` (test not yet written)

- [ ] **AC-SK-3:** `filter_speckit_by_feature()` narrows a SpecKit spec-file
  list to exactly one feature's own `spec.md`. (R-SK-3)
  _Verified by:_ `pytest -k test_filter_speckit_by_feature_narrows_to_one_feature` · stage: `make test` (test not yet written)

- [ ] **AC-SK-4 (non-success):** a repo whose only `specs/` directory is an
  OpenAPI/RSpec/JSON-schema layout (a `specs/` dir with no `*/spec.md`
  beneath it) does not get `speckit_root` set. (R-SK-4)
  _Verified by:_ `pytest -k test_profile_does_not_set_speckit_root_for_a_specs_dir_with_no_spec_md` · stage: `make test` (test not yet written)

- [ ] **AC-SK-5:** a repo with a genuine `specs/<feature>/spec.md` tree gets
  `speckit_root` populated and its spec files unioned with any
  openspec-discovered ones. (R-SK-4, R-SK-5)
  _Verified by:_ `pytest -k test_profile_sets_speckit_root_and_unions_spec_files` · stage: `make test` (test not yet written)

- [ ] **AC-SK-6:** a repo with both an `openspec/` tree and a `specs/`
  SpecKit tree populates both roots simultaneously (the mid-migration
  case). (R-SK-5, DEC-SK-003)
  _Verified by:_ `pytest -k test_profile_supports_both_openspec_root_and_speckit_root_together` · stage: `make test` (test not yet written)

- [ ] **AC-SK-7:** `detect_dialect()` classifies a spec file as speckit
  given `### Functional Requirements` + an `FR-\d+` id, or
  `## Success Criteria` + an `SC-\d+` id. (R-SK-8)
  _Verified by:_ `pytest -k test_detect_dialect_classifies_speckit_markers` · stage: `make test` (test not yet written)

- [ ] **AC-SK-8:** `detect_dialect()` reports `"mixed"` when a tree contains
  files matching more than one of the three dialect predicates, including
  a genuine three-way case. (R-SK-9, DEC-SK-011)
  _Verified by:_ `pytest -k test_detect_dialect_reports_mixed_for_more_than_one_dialect_present` · stage: `make test` (test not yet written)

- [ ] **AC-SK-9:** `detect_dialect()` is byte-identical on the existing
  two-dialect golden fixture after the 3-way rewrite. (R-SK-10, DEC-SK-012)
  _Verified by:_ `pytest tests/test_decomposition.py -k hash` · stage: `make test` (test not yet written)

- [ ] **AC-SK-10 (non-success):** a spec with `[NEEDS CLARIFICATION]`
  markers but none of the other speckit markers is not classified as
  speckit. (C-SK-1, DEC-SK-010)
  _Verified by:_ `pytest -k test_needs_clarification_alone_does_not_classify_as_speckit` · stage: `make test` (test not yet written)

- [ ] **AC-SK-11:** a change to `speckit_root`/`feature_dirs` is detected by
  `dialect_card.diff_cards()` — the fields are threaded into `to_card()`/
  `_COMPARABLE_FIELDS` with no `SCHEMA_VERSION` bump. (R-SK-6, DEC-SK-004)
  _Verified by:_ `pytest -k test_diff_cards_detects_a_speckit_root_change` · stage: `make test` (test not yet written)

- [ ] **AC-SK-12:** `parse_spec()` dispatches `dialect == "speckit"` to
  `parse_speckit()` via its own explicit branch. (R-SK-11)
  _Verified by:_ `pytest -k test_parse_spec_dispatches_speckit_to_its_own_parser` · stage: `make test` (test not yet written)

- [ ] **AC-SK-13:** `parse_spec()`'s `mixed`/`unknown`/`auto` resolution
  checks upstream, then speckit, then harness, matching
  `detect_dialect()`'s own precedence. (R-SK-12)
  _Verified by:_ `pytest -k test_parse_spec_auto_resolution_checks_upstream_then_speckit_then_harness` · stage: `make test` (test not yet written)

- [ ] **AC-SK-14:** `parse_speckit()` maps `FR-00N` bullets to `Requirement`
  entries and `SC-00N` bullets to `Criterion` entries. (R-SK-13, R-SK-14)
  _Verified by:_ `pytest -k test_parse_speckit_maps_fr_and_sc_ids` · stage: `make test` (test not yet written)

- [ ] **AC-SK-15:** `parse_speckit()` synthesizes `US<n>-AS<m>` `Criterion`
  entries from Given/When/Then prose inside a `### User Story N` block,
  using `scenario_has_gwt()` unmodified. (R-SK-14, DEC-SK-015)
  _Verified by:_ `pytest -k test_parse_speckit_synthesizes_user_story_criteria` · stage: `make test` (test not yet written)

- [ ] **AC-SK-16 (non-success):** the speckit branch's escape hatch
  reclassifies an empty speckit-parse spec containing an upstream
  `### Requirement:` heading as upstream; no reciprocal hatch reclassifies
  a harness-dispatched spec as speckit. (R-SK-15, DEC-SK-014)
  _Verified by:_ `pytest -k "test_speckit_branch_rescues_to_upstream or test_no_reciprocal_speckit_rescue_hatch_for_harness"` · stage: `make test` (test not yet written)

- [ ] **AC-SK-17 (non-success):** every `Criterion` `parse_speckit()`
  produces has an empty `requirement_refs` tuple. (C-SK-3, DEC-SK-016)
  _Verified by:_ `pytest -k test_speckit_criteria_have_no_requirement_refs` · stage: `make test` (test not yet written)

- [ ] **AC-SK-18:** golden hashes for validate/graph/rules in
  `test_decomposition.py` are unchanged after the parser milestone
  (`rules.py` not yet touched). (R-SK-10)
  _Verified by:_ `pytest tests/test_decomposition.py` · stage: `make test` (test not yet written)

- [ ] **AC-SK-19:** `cmd_validate` and `cmd_waivers` succeed against a
  SpecKit-only repo (no `openspec/`, a content-gated `specs/` tree
  present), unioning discovered spec files. (R-SK-20)
  _Verified by:_ `pytest -k test_cmd_validate_succeeds_on_a_speckit_only_repo` · stage: `make test` (test not yet written)

- [ ] **AC-SK-20 (non-success):** `cmd_validate` and `cmd_waivers` still
  exit 2 on a repo with neither `openspec/` nor a content-gated `specs/`
  tree. (R-SK-20)
  _Verified by:_ `pytest -k test_cmd_validate_exits_2_with_neither_openspec_nor_speckit` · stage: `make test` (test not yet written)

- [ ] **AC-SK-21:** `build_graph()` succeeds against a SpecKit-only repo —
  the `NoOpenSpecTreeError` guard and file-gather receive the same union
  fix. (R-SK-21, DEC-SK-005)
  _Verified by:_ `pytest -k test_build_graph_succeeds_on_a_speckit_only_repo` · stage: `make test` (test not yet written)

- [ ] **AC-SK-22 (non-success):** `cmd_graph --change` still exits 2 on a
  SpecKit-only repo with no `openspec/`, even though `speckit_root` is
  populated. (C-SK-5, DEC-SK-006)
  _Verified by:_ `pytest -k test_cmd_graph_change_stays_openspec_only_on_a_speckit_only_repo` · stage: `make test` (test not yet written)

- [ ] **AC-SK-23:** `--dialect` argparse choices include `"speckit"` on
  `validate` and `waivers`. (R-SK-22)
  _Verified by:_ `pytest -k test_cli_dialect_choices_include_speckit_on_validate_and_waivers` · stage: `make test` (test not yet written)

- [ ] **AC-SK-24 (non-success):** `--dialect` choices on `new` do not
  include `"speckit"`; `graph` has no `--dialect` flag at all. (C-SK-6,
  DEC-SK-008)
  _Verified by:_ `pytest -k test_cli_new_and_graph_do_not_gain_speckit_dialect_surface` · stage: `make test` (test not yet written)

- [ ] **AC-SK-25:** `cmd_detect`'s text output prints a
  `specs/ (SpecKit)  present/ABSENT` line. (R-SK-23)
  _Verified by:_ `pytest -k test_cmd_detect_text_output_reports_speckit_presence` · stage: `make test` (test not yet written)

- [ ] **AC-SK-26 (non-success):** no `--feature` flag exists on any
  subparser; `filter_speckit_by_feature()` is reachable only via direct
  import. (C-SK-7, DEC-SK-007)
  _Verified by:_ `pytest -k test_no_feature_cli_flag_exists` · stage: `make test` (test not yet written)

- [ ] **AC-SK-27:** golden hashes for validate/graph in
  `test_decomposition.py` are unchanged for the canonical fixture repo
  (which has no `specs/` dir) after the CLI-wiring milestone. (R-SK-20,
  R-SK-21)
  _Verified by:_ `pytest tests/test_decomposition.py` · stage: `make test` (test not yet written)

- [ ] **AC-SK-28:** `tests/test_rule_registry_docs.py`'s `_FAMILIES` tuple
  and README-table regex accept the `S` prefix, landed before
  `rules_speckit.py` is registered into `rules.py`. (R-SK-25)
  _Verified by:_ `pytest tests/test_rule_registry_docs.py` · stage: `make test` (test not yet written)

- [ ] **AC-SK-29:** S001 fires on an unresolved `[NEEDS CLARIFICATION]`
  marker. (R-SK-16)
  _Verified by:_ `pytest -k test_s001_fires_on_unresolved_needs_clarification` · stage: `make test` (test not yet written)

- [ ] **AC-SK-30:** S002 fires on a duplicate `FR-`/`SC-` identifier.
  (R-SK-16)
  _Verified by:_ `pytest -k test_s002_fires_on_duplicate_fr_or_sc_id` · stage: `make test` (test not yet written)

- [ ] **AC-SK-31:** S003 fires on a requirement with no SHALL/MUST.
  (R-SK-16)
  _Verified by:_ `pytest -k test_s003_fires_on_a_non_normative_requirement` · stage: `make test` (test not yet written)

- [ ] **AC-SK-32 (non-success):** S004 fires at WARN, not ERROR, on a
  scenario missing WHEN/THEN. (R-SK-16, R-SK-27, DEC-SK-019)
  _Verified by:_ `pytest -k test_s004_fires_at_warn_not_error` · stage: `make test` (test not yet written)

- [ ] **AC-SK-33 (non-success):** a SpecKit spec with only positive-phrased
  Success Criteria does not trigger G002. (R-SK-18, DEC-SK-021)
  _Verified by:_ `pytest -k test_g002_does_not_fire_on_a_positive_only_speckit_spec` · stage: `make test` (test not yet written)

- [ ] **AC-SK-34 (non-success):** a conventional
  `SC-001: 95% of new users...` bullet under `## Success Criteria` in a
  speckit-dialect spec does not trigger G003. (R-SK-19, DEC-SK-022)
  _Verified by:_ `pytest -k test_g003_does_not_fire_on_a_success_criteria_percentage` · stage: `make test` (test not yet written)

- [ ] **AC-SK-35 (non-success):** G002/G003 behavior on the existing
  harness/upstream fixtures (`good_harness.md`, `good_upstream.md`) is
  byte-unchanged. (C-SK-8)
  _Verified by:_ `pytest -k "test_g002 or test_g003"` · stage: `make test` (test not yet written)

- [ ] **AC-SK-36:** README's rules table, `c4.md`'s module map + rule count
  + range comment, `docs/agents-skills-harness.md`, `docs/next-steps.md`,
  and `docs/differentiation-roadmap.md` all match `rules.RULES` including
  the new `S` family. (R-SK-24)
  _Verified by:_ `pytest tests/test_rule_registry_docs.py` · stage: `make test` (test not yet written)

- [ ] **AC-SK-37:** `tests/baseline_rules.json` is regenerated and
  `_EXPECTED_HASHES["rules"]` is re-pinned; `["validate"]`/`["graph"]`
  hashes stay unchanged, confirmed empirically. (R-SK-26)
  _Verified by:_ `pytest tests/test_decomposition.py` · stage: `make test` (test not yet written)

- [ ] **AC-SK-38 (non-success):** no "orphaned requirement" rule exists for
  the speckit dialect; `planlint rules --json` lists exactly S001-S004 as
  the new speckit family. (C-SK-4, DEC-SK-017)
  _Verified by:_ `pytest -k test_no_orphan_requirement_rule_exists_for_speckit` · stage: `make test` (test not yet written)

- [ ] **AC-SK-39 (non-success):** `scaffold.py`/`scaffold_templates.py` are
  untouched by this change; `planlint new`/`init` still only offer
  harness/upstream. (C-SK-9)
  _Verified by:_ `pytest -k test_scaffold_still_only_offers_harness_and_upstream` · stage: `make test` (test not yet written)

- [ ] **AC-SK-40:** a hand-authored/collected `good_speckit.md`-style
  fixture, representative of real SpecKit output, produces zero unexpected
  findings end to end. (Milestone 5, R-SK-27)
  _Verified by:_ `pytest -k test_good_speckit_fixture_has_no_unexpected_findings` · stage: `make test` (test not yet written)

- [ ] **AC-SK-41:** `parse.py` no longer contains its own copies of the
  upstream/harness marker-string checks; `detect.detect_dialect()` and
  `parse.parse_spec()`'s pre-resolution branch both call the same
  `is_upstream_marked`/`is_harness_marked`/`is_speckit_marked` functions
  imported from `parse_semantics.py`. (R-SK-7)
  _Verified by:_ `pytest -k test_marker_predicates_are_not_duplicated_between_detect_and_parse` · stage: `make test` (test not yet written)

- [ ] **AC-SK-42:** `rules.RULES` contains every `SPECKIT_RULES` entry, and
  `NON_WITNESS_RULES` is exactly `GENERIC_RULES + HARNESS_RULES +
  UPSTREAM_RULES + SPECKIT_RULES` — an append, not an interleave or a
  replacement of any existing family. (R-SK-17)
  _Verified by:_ `pytest -k test_rules_py_registers_speckit_rules_additively` · stage: `make test` (test not yet written)

- [ ] **AC-SK-43 (non-success):** `inspect.getsource(parse.parse_spec)`
  still shows explicit `if`/`elif` comparisons against the three dialect
  string literals — no dict/mapping keyed by dialect name backs the
  dispatch. (C-SK-2)
  _Verified by:_ `pytest -k test_parse_spec_dispatch_is_not_dict_based` · stage: `make test` (test not yet written)

- [ ] **AC-SK-44 (non-success):** `find_speckit_spec_files()`'s glob
  matches `spec.md` only; a `plan.md`/`tasks.md` sibling in the same
  feature directory is never returned by discovery and never reaches a
  parser. (C-SK-10)
  _Verified by:_ `pytest -k test_speckit_discovery_never_returns_plan_or_tasks_md` · stage: `make test` (test not yet written)

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-SK-1..44 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
