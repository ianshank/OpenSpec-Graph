# Milestones

## Milestone 1 — Discovery + 3-way dialect detection [DONE]

- `openspec_graph/parse_semantics.py`: new marker predicates
  (`is_upstream_marked`, `is_harness_marked`, `is_speckit_marked`) and
  regexes `FR_ID`, `SC_ID`, replacing the currently duplicated marker
  strings in `detect.py`/`parse.py`.
- `openspec_graph/detect.py`: `StackProfile` gains `speckit_root: Path | None
  = None` and `feature_dirs: tuple[Path, ...] = ()`, appended after
  `current_sha`; new `find_speckit_spec_files()` — content-gated **per
  file** (each `specs/<feature>/spec.md` must also match
  `is_speckit_marked()`, not just exist at the right path) and
  `filter_speckit_by_feature()`; `detect_dialect()` rewritten as a 3-way
  marker sniff (`"mixed"` = `present > 1`); `profile()` sets `speckit_root`
  only when content-gated (`root/"specs"` is a dir **and**
  `find_speckit_spec_files()` finds ≥1 qualifying file), unions both
  roots' spec files before calling `detect_dialect()`, and derives
  `feature_dirs` as the distinct sorted parent directories of
  `find_speckit_spec_files()`'s (content-gated) results.
- `openspec_graph/dialect_card.py`: `_COMPARABLE_FIELDS` gains
  `"has_speckit_root"` and `"feature_dirs"` — never the raw
  `"speckit_root"` path. `StackProfile.as_dict()` exposes `speckit_root`
  as an absolute-path string (mirrors `openspec_root`) and `feature_dirs`
  as `[d.name for d in self.feature_dirs]` (mirrors `change_dirs`);
  `to_card()` derives `has_speckit_root: bool` and passes `feature_dirs`
  through — it never re-exposes the raw path, preserving the
  byte-identical-across-checkout-paths contract `AC-DC-4` established.
- New `tests/test_detect_speckit.py`: fingerprint gating (positive and
  content-gated-negative cases), an unmarked `spec.md` alongside genuinely
  marked ones under the same `specs/` dir excluded from
  `find_speckit_spec_files()` even though `speckit_root` is set (the exact
  fixture `spec-adversary` constructed against the pre-fix design),
  `feature_dirs` derived only from content-gated results, coexistence of
  both roots, 3-way `detect_dialect()` classification including a genuine
  three-way `"mixed"` case, byte-identity on the existing two-dialect
  golden fixture, confirmation that `detect.py`/`parse.py` share one
  predicate implementation (no duplicated marker strings), and that
  `find_speckit_spec_files()`'s glob never returns a `plan.md`/`tasks.md`
  sibling.
- `tests/test_dialect_card.py` extended for `has_speckit_root`/
  `feature_dirs`, including a case asserting `to_card()`'s output never
  contains a raw `speckit_root` path.
- `tests/test_graft.py` (or the relevant `StackProfile`-construction test
  module) extended, mirroring
  `test_stack_profile_construction_still_works_without_witness_fields`, for
  the new speckit fields.
- **Gate:** `make test` — AC-SK-1..11, AC-SK-41, AC-SK-44..47.

## Milestone 2 — `parse_speckit.py` + dispatch fix [DONE]

- `openspec_graph/parse_semantics.py`: grammar regexes `FR_DECL`, `SC_DECL`
  (anchored against a sibling `**NFR-001**:` bullet false-matching),
  `NEEDS_CLARIFICATION`, `USER_STORY_HEADING`, `GWT_SCENARIO`.
- New `openspec_graph/parse_speckit.py`: `parse_speckit(text) ->
  tuple[tuple[Requirement,...], tuple[Criterion,...]]`; `FR-00N` bullets →
  `Requirement`, `SC-00N` bullets → `Criterion`, Given/When/Then prose
  inside `### User Story N` blocks → synthesized `US<n>-AS<m>` `Criterion`
  entries via `parse.scenario_has_gwt()`; `Criterion.requirement_refs` left
  empty for every SpecKit-derived entry.
- `openspec_graph/parse.py`: explicit `elif resolved == "speckit"` dispatch
  branch (not a dict/registry refactor); `mixed`/`unknown`/`auto`
  pre-resolution checks upstream, then speckit, else harness; speckit
  branch gets its own harness-style rescue-to-upstream escape hatch, no
  reciprocal hatch added for harness.
- `tests/support.py`: new `write_speckit_spec()` helper, mirroring the
  existing harness/upstream fixture writers.
- New `tests/fixtures/good_speckit.md`.
- New `tests/test_parse_speckit.py`: FR/SC mapping, user-story GWT
  synthesis, the escape hatch (and its asymmetry), empty
  `requirement_refs`, and a source-inspection check that the dispatch
  stays `if`/`elif`-shaped (no dict/registry backing it).
- Confirm golden hashes for validate/graph/rules in
  `tests/test_decomposition.py` are unchanged (`rules.py` not yet touched
  by this milestone).
- **Gate:** `make test` — AC-SK-12..18, AC-SK-43.

## Milestone 3 — CLI + graph.py wiring

- `openspec_graph/cli.py`: `cmd_validate`/`cmd_waivers` guards become
  `if not prof.openspec_root and not prof.speckit_root: ...; return 2`;
  spec-file gathering unions `find_spec_files()`/`find_speckit_spec_files()`
  results; `--dialect` argparse choices gain `"speckit"` on `p_val`/
  `p_waivers` only; `cmd_detect` text output gains a
  `specs/ (SpecKit)  present/ABSENT` line. `cmd_graph`'s `--change`-scoped
  inner guard is left untouched (openspec-only, deliberately).
- `openspec_graph/graph.py`: `NoOpenSpecTreeError` guard and internal
  `detect.find_spec_files(profile.openspec_root)` gather receive the
  identical union treatment.
- New SpecKit-only fixture-repo tests for `validate`/`graph`/`waivers`,
  including the deliberate `--change` non-union behavior for `cmd_graph`,
  and a negative case (neither `openspec/` nor a content-gated `specs/`
  still exits 2).
- Confirm golden hashes for validate/graph in `test_decomposition.py` are
  unchanged for the canonical fixture repo (no `specs/` dir).
- **Gate:** `make test` — AC-SK-19..27.

## Milestone 4 — `rules_speckit.py` + registry + doc sync

Internal order matters — later steps depend on earlier ones passing first:

1. Fix the test-infrastructure landmine first: `tests/test_rule_registry_docs.py`'s
   `_FAMILIES` tuple (currently hardcoded to exactly G/H/U/W, `~line 27-32`)
   and its README-table regex (currently hardcoded to
   `G\d{3}|H\d{3}|U\d{3}|W\d{3}`, `~line 42`) both gain the `S` prefix
   before anything else — otherwise this repo's own doc-drift discipline
   silently validates nothing about the new family.
2. Add `openspec_graph/rules_speckit.py` (S001-S004; S001 scans
   `strip_waiver_comments(spec.raw)`, not raw text, so a waiver's own
   free-text reason quoting `[NEEDS CLARIFICATION]` doesn't self-trigger
   it); wire `SPECKIT_RULES` into `rules.py`'s `NON_WITNESS_RULES` as a
   pure append (confirm `GENERIC_RULES`/`HARNESS_RULES`/`UPSTREAM_RULES`
   are unchanged).
3. Apply the mandatory G002/G003 fix — spans two modules, not one:
   - `openspec_graph/rules_generic.py`: G002's `dialects` narrows to
     `("harness", "upstream")`.
   - `openspec_graph/parse_semantics.py`: `hard_coded(text)` gains a
     `dialect: str = ""` parameter and exempts the level-2 `Success
     Criteria` section body from the hard-coded-threshold scan when
     `dialect == "speckit"`, using the same blank-span technique
     `strip_waiver_comments()` already uses. `rules_generic.py`'s
     `_hard_coded_threshold` check function itself is unchanged — it only
     ever sees the already-extracted `spec.hard_coded_thresholds`.
   - `openspec_graph/parse.py`: `parse_spec()`'s one call site
     (`hard_coded_thresholds=hard_coded(text)`) is updated to
     `hard_coded(text, resolved)`, threading the resolved dialect through.
4. Run `tests/test_rule_registry_docs.py`; fix every location it flags:
   README's rules table, `docs/architecture/c4.md` module map + rule count
   + range comment, `docs/agents-skills-harness.md`, `docs/next-steps.md`,
   `docs/differentiation-roadmap.md`.
5. Regenerate `tests/baseline_rules.json` via
   `planlint rules --json > tests/baseline_rules.json`.
6. Re-pin `tests/test_decomposition.py`'s `_EXPECTED_HASHES["rules"]` only
   (this test has been re-pinned before for the same reason, per its own
   comments); confirm `["validate"]`/`["graph"]` hashes stay unchanged
   empirically against the canonical fixture, which has no `specs/`
   directory.
- New `tests/test_rules_speckit.py`: one fixture per rule (S001-S004),
  including S002's requirement-id coverage (the first duplicate-id check
  for requirements in the codebase; its criterion half mirrors H004) and
  S004's WARN (not ERROR)
  severity; new G002/G003 fixture cases for a positive-only /
  Success-Criteria-percentage speckit spec; a regression case confirming
  G002/G003 are byte-unchanged for the existing harness/upstream fixtures.
- **Gate:** `make test` — AC-SK-28..39, AC-SK-42.

## Milestone 5 — Corpus validation

- Collect/hand-author several real/representative spec-kit-shaped
  `spec.md` files.
- Run the full rule set against them; add a `good_speckit.md`-style
  zero-unexpected-findings regression test.
- Decide on `GWT_SCENARIO` tightening from the real results; keep S004 (and
  any other `GWT_SCENARIO`-dependent check) at WARN until this milestone's
  findings are in — no promotion to ERROR ships as part of this change.
- **Gate:** `make pre-pr` — AC-SK-40, and the full enterprise AQA gate
  (test, lint, typecheck, security, validate, docs) green end to end.
