# Spec: Architecture Drift Lint

> **Change:** `add-architecture-drift-lint`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`planlint` checks that a spec's `INV-n` citations are declared, and that
every declared invariant is cited by *some* living spec (G005/G006). Nothing
extends that same discipline to architecture decision records — a spec can
cite an ADR that doesn't exist, or a repo's ADR log can drift out of sync
with what any spec still references, and neither is caught.

**Evidence:** a repo-wide grep for `ADR`/`operationId`/`event.?schema` finds
zero existing citation convention anywhere in this codebase.

This capability's original motivation — `docs/architecture/c4.md` stating a
stale rule count and G-range — no longer held by the time this design began;
both had already been fixed by prior commits on this branch (component table
correctly said "18 deterministic rules" at the time; module map correctly
said "G001–G007" — both now further updated to 20/G001-G009 by this very
change, once G008/G009 exist). A fresh investigation before this design began
found the *identical* defect shape
alive elsewhere instead: `openspec_graph/rules.py`'s own module docstring
still read "universal rules G001-G005" — untouched by any commit on this
branch, and the third independent recurrence of this exact drift class in
this codebase's history (c4.md pre-`decompose-god-files`, fixed by
`fix-adopter-artifact-drift`; c4.md again post-CP-GV, fixed this session;
now `rules.py`'s own docstring). Three recurrences is the "value proven"
trigger `fix-adopter-artifact-drift`'s own Non-Goals named as the condition
for adding protection — resolved here as a single test, not new tooling
(`DEC-AD-006`).

---

## Requirements

- R-AD-1: A spec citing an ADR id not declared in the detected ADR source
  MUST be reported (G008).
- R-AD-2: A declared ADR id cited by no living spec anywhere, and not
  waived, MUST be reported (G009).
- R-AD-3: ADR discovery MUST support both a directory of per-decision files
  and a single index file, trying a fixed, most-specific-first candidate
  list.
- R-AD-4: ADR ids MUST be extracted by scanning each discovery candidate's
  own text content, never parsed from filenames.
- R-AD-5: The G009 check MUST NOT evaluate against a `--change`-filtered
  subset of the spec tree — doing so would report every ADR outside the
  filtered view as falsely orphaned (mirrors R-WL-5/`DEC-WL-003`).
- R-AD-6: `graph --change` MUST keep the G009 check running unscoped and
  include its results, printing its own `INFO` note (mirrors R-GV-5/6 and
  `DEC-GV-002`).
- R-AD-7: `graph`'s `broken_links` count MUST continue to equal `validate`'s
  finding count for an unscoped run with G008/G009 present (AC-GR-4).
- R-AD-8: Every doc/source location that states the total rule count or a
  rule family's id range MUST match `rules.RULES` itself, mechanically
  verified.
- R-AD-9: An orphan ADR (G009) MUST be represented as a node in `graph`
  output, styled consistently with every other orphan node type.
- C-AD-1: New `ParsedSpec`/`StackProfile` fields MUST be additive only —
  existing JSON shapes only grow, never change (mirrors C-WL-1).
- C-AD-2: No rule ident is reserved for OpenAPI or event-schema
  citation-checking by this change (mirrors `DEC-MP-003`).

---

## Decisions

- **DEC-AD-001:** `ParsedSpec.adr_refs: tuple[str, ...] = ()` is additive and
  defaulted, appended after `waivers` — deliberately *not* copying
  `invariant_refs`'s positional/no-default shape. That shape predates this
  project's own later, better-considered rule (`C-WL-1`, CP-4): "New
  Finding/ParsedSpec fields MUST be additive only." A positional field would
  break any existing keyword-only `ParsedSpec(...)` test-fixture construction
  that doesn't already pass it. **Amended (GitHub automated review on PR
  #13):** the first implementation still inserted `adr_refs` *before* the
  existing `raw` field, which is not actually additive — it shifts `raw`'s
  own positional index for any caller of the publicly-exported `ParsedSpec`
  still constructing it positionally, silently binding `raw` to the wrong
  value. Fixed by moving `adr_refs` to strictly after `raw`, the true last
  field — "additive" means appended after *every* existing field, not just
  after the ones added most recently.
- **DEC-AD-002:** ADR discovery (`detect._adrs()`) supports a directory
  candidate (one numbered file per decision — the dominant real-world
  convention) tried before a single-file index fallback, unlike
  `_invariants()`'s file-only template. Ids are still extracted by
  regex-scanning each candidate's own text (mirroring `_invariants()`'s
  proven mechanism), never parsed from filenames — a zero-padded filename
  (`0007-....md`) and a spec's bare citation (`ADR-7`) would otherwise
  silently mismatch. **Amended (GitHub automated review on PR #13):** the
  first implementation scanned a directory candidate's *entire* file for
  every `ADR-n` occurrence, which conflates a declaration with a mere
  reference — a decision record's own prose routinely cites another
  decision ("Supersedes ADR-99") without declaring it. Fixed: a directory
  candidate's declared id is now only its *first* mention (its own title),
  never a later in-body reference; a single-index file is unaffected —
  scanning its whole text for every mention is still correct there, since
  that form is a declaration list by convention (mirroring
  `_invariants()`'s own CONTRACT.md assumption). Separately, reference
  *extraction* (`ADR_REF`/`INV_REF`/`MAKE_REF` scanning a spec's own text)
  now excludes waiver-comment spans first — a waiver's own reason text
  must not be able to satisfy the citation it exists to waive, the same
  bug class already present, unfixed, for `INV_REF` since CP-4.
  **Amended (adversarial code review on PR #13):** two further gaps in the
  fix above. First, `glob("*.md")` lists directory entries by name pattern
  only, not readability — a dangling symlink still matches and made
  `read_text()` raise an uncaught `FileNotFoundError`, crashing
  `detect.profile()` (and therefore every CLI verb) on any target repo with
  a broken symlink under its ADR directory; the read is now wrapped and an
  unreadable entry is skipped like any other non-declaring file (the same
  guard was added to `_invariants()`'s read for the equivalent
  permission-denied case, and to `_adrs()`'s single-file branch). Second,
  "first mention = declaration" still assumed a file's own title always
  precedes any reference to a related decision in its body; a file whose
  body opens with "Related: ADR-1" *before* its own `# ADR-2: ...` heading
  broke that assumption and got `ADR-1` captured as its declared id. Fixed
  by preferring the first `ADR-n` mention that appears on a markdown
  heading line, falling back to the first mention anywhere only when no
  heading contains an id at all (`detect._declared_adr_id()`).
- **DEC-AD-003:** `rules.evaluate_tree()` gains a second parallel block for
  G009, identical in shape to the existing G006 block — not generalized into
  a tree-rule registry. Two instances doesn't justify a dispatch mechanism;
  this project has separately decided against a *dynamic* rule-pack
  interface (`DEC-PR-002`), and the same taste (concrete code over
  indirection for a handful of cases) applies here even though this is an
  internal structuring question, not that exact external-plugin one. Revisit
  if a third whole-tree check ever arrives.
- **DEC-AD-004:** G009 is `--change`-unsafe exactly like G006 (`DEC-WL-003`):
  `cmd_validate --change` skips it with its own `INFO` line; `cmd_graph
  --change` keeps it unscoped and prints its own note (`DEC-GV-002`'s
  reasoning generalizes without modification).
- **DEC-AD-005:** `graph.py` gains a sixth node type, `adr`, reusing the
  existing `declares` edge type rather than inventing a new one. An orphaned
  ADR gets a synthesized node via the same `_add_tree_finding_edges`
  mechanism G006 already uses for orphan invariants, made rule-aware via a
  small `{rule_ident: node_kind}` dispatch table rather than a hardcoded
  single type. Existing G006 behavior is unchanged — the dispatch table's
  `"G006"` entry returns exactly what the prior hardcode did.
- **DEC-AD-006:** the doc-drift guard is a single new pytest test
  (`tests/test_rule_registry_docs.py`), not a new `tools/` script or Makefile
  target. `fix-adopter-artifact-drift`'s own Non-Goals rejected permanent
  CI-gate tooling for this problem class but explicitly pre-authorized "the
  cheapest form... a single test" once recurrence is demonstrated — this
  change's own Problem Statement is that demonstration (three independent
  recurrences). The guard computes ground truth once from `rules.RULES` and
  checks it against README's rules table, `c4.md`'s count and per-family
  range comments, `docs/agents-skills-harness.md`, `docs/next-steps.md`
  (×2), and `rules.py`'s own module docstring. `CHANGELOG.md` is
  deliberately excluded — its dated entries are historical record, correct
  when written; guarding it would fight its own purpose.
- **DEC-AD-007:** OpenAPI operationId and event-schema id citation-checking
  are deferred to their own, later, separately-reviewed change packages; no
  rule idents are reserved for either (mirrors `DEC-MP-003`'s own
  precedent). Both need real-external-repo validation of their discovery
  convention before any candidate-path list is locked in — OpenAPI's
  realistic file-location convention is at least as unvalidated as
  event-schema's, and OpenAPI documents are overwhelmingly YAML in real
  repos, which this zero-runtime-dependency project has no parser for.
- **DEC-AD-008:** G008/G009 stay in `rules_generic.py`; no new rule module.
  A heuristic considered during design — "a rule pair with its own
  `StackProfile` discovery fields warrants its own module" — turns out to
  have no real precedent: G005/G006, the only existing analog, *reused*
  pre-existing fields and added none. The actual triggers behind every real
  module split in this codebase's history are new output-schema/
  aggregation-domain/file-format-grammar concerns (`dialect_card.py`,
  `ledger.py`, `mermaid.py`, `machinery.py`), not "a new rule pair." A
  separate module would also break the current clean 1:1
  ident-prefix-to-module mapping that makes `c4.md`'s module map trivially
  checkable. Revisit only if/when OpenAPI+event-schema land and this file's
  size or checkability actually degrades.
- **DEC-AD-009 (found by GitHub's automated review on PR #13):**
  `dialect_card.diff_cards()` compared a field entirely absent from an
  older card's keys against the new card's default value for that field —
  reporting every additive schema growth (not just this change's own
  `adr_source`/`adr_ids`, but every prior one back to CP-2) as false
  repository drift the first time a pre-upgrade snapshot was diffed
  against a newer `planlint`, on an otherwise-unchanged repo. This directly
  threatened `C-AD-1`'s own guarantee ("existing JSON shapes only grow,
  never change") in the one place a consumer would actually observe it
  break: `detect --diff`'s output. Fixed generally, not just for ADR
  fields: a field missing as a *key* from the previous card is now skipped
  in comparison entirely, regardless of the current card's value for it —
  a schema addition is not drift. No `SCHEMA_VERSION` bump; consistent
  with this project's established additive-fields-don't-need-a-version-bump
  discipline (`C-WL-1`).

---

## Acceptance Criteria

- [x] **AC-AD-1:** A spec citing an ADR id not declared in the detected ADR
  source is reported by G008. (R-AD-1)
  _Verified by:_ `pytest -k test_g008_fires_on_an_undeclared_adr` · stage: `make test`

- [x] **AC-AD-2:** A declared ADR cited by no living spec, and not waived,
  is reported by G009. (R-AD-2)
  _Verified by:_ `pytest -k test_g009_fires_for_a_declared_adr_no_spec_cites` · stage: `make test`

- [x] **AC-AD-3 (non-success):** G009 does not fire once the ADR is cited
  anywhere in the tree. (R-AD-2)
  _Verified by:_ `pytest -k test_g009_does_not_fire_once_cited_anywhere_in_the_tree` · stage: `make test`

- [x] **AC-AD-4:** G009 downgrades to INFO when waived anywhere in the tree.
  (R-AD-2)
  _Verified by:_ `pytest -k test_g009_is_downgraded_to_info_when_waived_anywhere_in_the_tree` · stage: `make test`

- [x] **AC-AD-5 (non-success):** G009 is skipped, with an INFO note, under
  `validate --change`. (R-AD-5, DEC-AD-004)
  _Verified by:_ `pytest -k test_g009_is_skipped_under_change_scoping` · stage: `make test`

- [x] **AC-AD-6:** `graph --change` keeps G009 unscoped, includes its
  results, and prints its own INFO note. (R-AD-6, DEC-AD-004)
  _Verified by:_ `pytest -k test_graph_change_prints_a_g009_unscoped_heads_up` · stage: `make test`

- [x] **AC-AD-7:** ADR ids are discovered from a directory of numbered
  per-decision files. (R-AD-3, DEC-AD-002)
  _Verified by:_ `pytest -k test_adrs_discovered_from_a_directory_of_numbered_files` · stage: `make test`

- [x] **AC-AD-8:** ADR ids are discovered from a single index file when no
  directory candidate exists. (R-AD-3, DEC-AD-002)
  _Verified by:_ `pytest -k test_adrs_discovered_from_a_single_index_file` · stage: `make test`

- [x] **AC-AD-9 (non-success):** a zero-padded ADR filename does not cause a
  mismatch against a spec's bare citation. (R-AD-4, DEC-AD-002)
  _Verified by:_ `pytest -k test_adr_ids_do_not_mismatch_on_zero_padded_filenames` · stage: `make test`

- [x] **AC-AD-10:** `graph --format json`'s `broken_links` count still equals
  the total finding count with G008/G009 present — the AC-GR-4 invariant
  holds. (R-AD-7)
  _Verified by:_ `pytest -k test_graph_matches_validate_findings_with_an_orphan_adr` · stage: `make test`

- [x] **AC-AD-11 (non-success):** an ADR cited only by a spec outside a
  `--change`-rendered scope is not falsely reported as orphaned. (R-AD-6, DEC-AD-004)
  _Verified by:_ `pytest -k test_graph_change_does_not_falsely_orphan_an_adr_cited_outside_the_scope` · stage: `make test`

- [x] **AC-AD-12:** a genuinely orphaned ADR still surfaces as a node and
  finding under `--change` scoping. (R-AD-6, DEC-AD-004)
  _Verified by:_ `pytest -k test_graph_change_still_surfaces_a_genuinely_orphaned_adr` · stage: `make test`

- [x] **AC-AD-13:** an orphaned ADR renders in Mermaid output with the same
  `orphan` styling as any other orphan node type, with zero changes to
  `mermaid.py`. (R-AD-9, DEC-AD-005)
  _Verified by:_ `pytest -k test_orphan_adr_node_gets_the_orphan_class` · stage: `make test`

- [x] **AC-AD-16 (non-success):** `planlint rules --json` lists exactly
  `G008`/`G009` as this change's new rule idents — no `OPENAPI-`/`EVENT-`-
  prefixed or otherwise reserved-but-unbuilt ident appears anywhere in the
  registry. (C-AD-2)
  _Verified by:_ `pytest -k test_no_openapi_or_event_schema_idents_are_reserved` · stage: `make test`

- [x] **AC-AD-14:** README's rules table, `c4.md`'s rule count and per-family
  range comments, `docs/agents-skills-harness.md`, `docs/next-steps.md`, and
  `rules.py`'s own module docstring all match `rules.RULES`'s real contents,
  mechanically verified. (R-AD-8, DEC-AD-006)
  _Verified by:_ `pytest tests/test_rule_registry_docs.py` · stage: `make test`

- [x] **AC-AD-15:** a change to `adr_source`/`adr_ids` is detected by
  `dialect_card.diff_cards()` — the new fields are threaded into both
  `to_card()` and `_COMPARABLE_FIELDS`. (C-AD-1)
  _Verified by:_ `pytest -k test_diff_cards_detects_an_adr_source_change` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-AD-1..16 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
