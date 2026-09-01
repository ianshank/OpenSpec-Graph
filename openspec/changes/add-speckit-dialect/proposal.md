# Change: Add SpecKit Dialect

## Why

`planlint` only recognizes spec files at `openspec/changes/<name>/specs/<capability>/spec.md`,
in one of two markdown dialects (`upstream`/OpenSpec, `harness`). A repo using
GitHub's SpecKit tool writes files at `specs/<NNN-feature>/spec.md` at the
repo root (no `openspec/` ancestor at all) in a materially different grammar
(`FR-00N`/`SC-00N` identifiers, no delta/ADDED-MODIFIED-REMOVED concept,
Given/When/Then as inline prose inside prioritized user stories, not a
dedicated level-4 `Scenario:` heading). A SpecKit-only repo is currently
**invisible** to `planlint`, not mis-parsed — it never gets past the
`openspec/`-only gate to be parsed at all.

**Evidence:** `openspec_graph/detect.py:493-497` hardcodes
`openspec_root = root / "openspec"` and gates all spec discovery on
`has_openspec = openspec_root.is_dir()`. `openspec_graph/cli.py:168-170`
(`cmd_validate`), `cli.py:287-289` (`cmd_graph`'s `--change` guard), and
`cli.py:328-330` (`cmd_waivers`) all hard-fail with `"no openspec/
directory; run \`\`planlint init\`\` first"` and exit 2 before any
dialect logic runs. `openspec_graph/graph.py:233-239` (`build_graph`'s
`NoOpenSpecTreeError` guard and its own `detect.find_spec_files(profile
.openspec_root)` gather) hard-codes the identical `openspec_root`-only
assumption a second time, independently of `cli.py`.

## What Changes

- **`openspec_graph/detect.py`** — `StackProfile` gains
  `speckit_root: Path | None = None` and `feature_dirs: tuple[Path, ...] = ()`,
  appended strictly after `current_sha` (the current last field), per this
  module's own positional-dataclass append-only discipline (documented at
  `parse_model.py:80-86` for `ParsedSpec`'s equivalent field, and followed
  by `StackProfile` itself for every prior additive field —
  `adr_source`/`adr_ids`/`witnesses`/`current_sha`). New functions:
  `find_speckit_spec_files(speckit_root) -> list[Path]` (`specs/<feature>/spec.md`
  — one segment shallower than `find_spec_files`'s `changes/*/specs/*/spec.md`,
  since SpecKit has no `changes/` nesting — **and content-gated per file**:
  a file only qualifies if it also matches `is_speckit_marked()`) and
  `filter_speckit_by_feature(spec_files, feature) -> list[Path]` (mirrors
  `filter_by_change`'s fixed-position anchor, one level shallower). The
  SpecKit fingerprint is content-gated at both the root and the file level,
  not a bare `is_dir()` check like `openspec_root`'s: `root / "specs"` must
  be a directory **and** `find_speckit_spec_files()` must find at least one
  qualifying file beneath it — a bare `specs/` directory is too common a
  name (OpenAPI, RSpec, JSON-schema conventions all use it) to trust
  structurally, and an unrelated `spec.md` sitting alongside genuine
  SpecKit files under the same `specs/` dir must not be swept in either.
  `profile()` unions both roots' discovered spec files before calling
  `detect_dialect()`; both roots can coexist on the same profile (a
  mid-migration repo). `feature_dirs` is derived as the distinct sorted
  parent directories of `find_speckit_spec_files()`'s results — not every
  structural subdirectory of `speckit_root`.
- **`openspec_graph/dialect_card.py`** — `_COMPARABLE_FIELDS` gains
  `"has_speckit_root"` and `"feature_dirs"` — never the raw `"speckit_root"`
  path. `detect.py`'s `StackProfile.as_dict()` exposes `speckit_root` as an
  absolute-path string (mirroring `openspec_root`) and `feature_dirs` as
  `[d.name for d in self.feature_dirs]` (mirroring `change_dirs`);
  `to_card()` derives `has_speckit_root: bool` from it (mirroring
  `has_openspec_root`) and passes `feature_dirs` through unchanged — it
  never re-exposes the raw path, preserving the byte-identical-across-
  checkout-paths contract `add-dialect-cards`' `AC-DC-4` established. No
  `SCHEMA_VERSION` bump — matches the existing precedent of an old card
  simply not comparing a field it predates (`diff_cards()`'s absent-key
  skip).
- **`openspec_graph/parse_semantics.py`** — new shared marker predicates
  (`is_upstream_marked`, `is_harness_marked`, `is_speckit_marked`) and
  regexes `FR_ID = re.compile(r"\bFR-\d+\b")`, `SC_ID = re.compile(r"\bSC-\d+\b")`,
  used by both `detect.detect_dialect()` and `parse.parse_spec()`'s
  pre-resolution branch. This also fixes a pre-existing defect this change
  otherwise would have compounded: the upstream/harness marker strings are
  today duplicated verbatim between `detect.py:413-416` and
  `parse.py:66-71`; extracting shared predicates here removes that
  duplication instead of adding a third copy. New grammar regexes for
  SpecKit's own shape: `FR_DECL`, `SC_DECL` (anchored so a sibling
  `**NFR-001**:` bullet can't match), `NEEDS_CLARIFICATION`,
  `USER_STORY_HEADING`, `GWT_SCENARIO`.
- **`openspec_graph/detect.py`** — `detect_dialect()` becomes a 3-way marker
  sniff: `is_speckit_marked` fires on (`### Functional Requirements` +
  `FR_ID` match) or (`## Success Criteria` + `SC_ID` match). `"mixed"`
  generalizes to `present > 1` across all three predicates (not an
  enumerated set of pairwise combinations). `[NEEDS CLARIFICATION]` is
  deliberately **not** the fingerprint — it's transient by design; a clean,
  fully-resolved spec would have zero occurrences and would be
  misclassified `unknown` if it were load-bearing. Must stay byte-identical
  on the existing two-dialect golden fixture used by
  `tests/test_decomposition.py`'s hash test.
- **`openspec_graph/parse.py`** — `parse_spec()`'s dispatch gets an explicit
  `elif resolved == "speckit"` branch, not a dict/registry refactor of the
  existing `if upstream / else harness` shape. The `mixed`/`unknown`/`auto`
  pre-resolution checks upstream first, then speckit, else harness, using
  the new §`parse_semantics` predicates. The speckit branch gets its own
  harness-style escape hatch (empty parse + `_REQUIREMENT` match →
  reclassify upstream), matching but not exceeding the existing
  asymmetric-guard convention; no reciprocal speckit-rescue hatch is added
  for the harness branch.
- **`openspec_graph/parse_speckit.py`** (new) — mirrors
  `parse_upstream.py`/`parse_harness.py`'s shape:
  `parse_speckit(text) -> tuple[tuple[Requirement,...], tuple[Criterion,...]]`.
  `FR-00N` bullets under `### Functional Requirements` → `Requirement`;
  `SC-00N` bullets under `## Success Criteria` → `Criterion`; Given/When/Then
  prose inside `### User Story N` blocks → synthesized `Criterion` entries
  (`US<n>-AS<m>` ids), reusing the existing `parse.scenario_has_gwt()`
  rather than reimplementing WHEN/THEN detection. `GWT_SCENARIO` is a
  prose-scrape, not a rigid heading match like upstream's level-4
  `Scenario:` heading — treated as provisional until validated against real corpus content
  (Milestone 5). `Criterion.requirement_refs` stays honestly empty for
  SpecKit-derived entries: no FR↔SC citation convention exists in SpecKit's
  grammar, and synthesizing a fake link would make an orphan-requirement
  rule fire on every requirement, always — the same reasoning behind
  dropping that rule candidate entirely (see Non-Goals).
- **`openspec_graph/rules_speckit.py`** (new) — rule family prefix `S` (the
  only unused single-letter prefix; G/H/U/W are taken):

  | ID | Severity | Check |
  |---|---|---|
  | S001 | ERROR | Unresolved `[NEEDS CLARIFICATION]` marker present (scans `strip_waiver_comments(spec.raw)`, not raw text — a waiver's own free-text reason quoting the marker must not itself count) |
  | S002 | ERROR | Duplicate `FR-`/`SC-` identifier — its criterion-duplicate half mirrors H004's existing pattern; its requirement-duplicate half is the first such check in the codebase (neither harness's R-/C- idents nor upstream's Requirement idents have a duplicate-id check today), justified on its own merits |
  | S003 | WARN | Requirement has no SHALL/MUST (reuses `Requirement.is_normative` unchanged; mirrors U004 exactly) |
  | S004 | WARN, not ERROR | Scenario missing WHEN/THEN (reuses `scenario_has_gwt()`; held below upstream's U003 ERROR precedent specifically because `GWT_SCENARIO` is unvalidated against real content) |

- **`openspec_graph/rules.py`** — registered purely additively:
  `NON_WITNESS_RULES = GENERIC_RULES + HARNESS_RULES + UPSTREAM_RULES + SPECKIT_RULES`.
- **Mandatory fix, not optional polish — spans two modules, not one.**
  `HARD_THRESHOLD = re.compile(r"(?:≥|>=|>)\s*\d{2,3}\s*%?|\b\d{2,3}\s*%")`
  matches the `95%` in a completely conventional SpecKit bullet like
  `SC-001: 95% of new users complete onboarding in under 5 minutes`, and
  `THRESHOLD_ALLOWLIST` has no token that exempts it. G003 is ERROR and
  `--fail-on ERROR` is the default; shipping without this fix means every
  real SpecKit spec with a measurable Success Criterion fails `validate` by
  default. G002 (requires ≥1 negative-phrased criterion repo-wide) fails
  most SpecKit specs too, whose Success Criteria are conventionally
  positive-phrased.
  - **`openspec_graph/rules_generic.py`**: G002 narrows `dialects` from
    `("*",)` to `("harness", "upstream")` — explicit opt-out. This part
    is a pure `rules_generic.py` change.
  - **`openspec_graph/parse_semantics.py` + `openspec_graph/parse.py`**:
    G003's check function only ever sees `spec.hard_coded_thresholds` —
    already-extracted, already-truncated offending-line strings, with no
    section metadata to recover after the fact. The real fix lives one
    layer down, where the extraction happens: `hard_coded(text)` in
    `parse_semantics.py` gains a `dialect: str = ""` parameter and exempts
    the `## Success Criteria` section body (blank-the-span, same
    technique `strip_waiver_comments()` already uses) when
    `dialect == "speckit"`; `parse.py::parse_spec()`'s one call site
    (`hard_coded_thresholds=hard_coded(text)`) is updated to
    `hard_coded(text, resolved)`. `rules_generic.py`'s `_hard_coded_threshold`
    check function itself does not change. Zero behavior change for
    harness/upstream (neither existing fixture has that heading).
- **`openspec_graph/cli.py`** — `cmd_validate` (`cli.py:168`) and
  `cmd_waivers` (`cli.py:328`) guards become
  `if not prof.openspec_root and not prof.speckit_root: ...; return 2`;
  their spec-file gathering becomes
  `(find_spec_files(...) if openspec_root else []) + (find_speckit_spec_files(...) if speckit_root else [])`.
  `cmd_graph`'s `--change`-scoped inner guard (`cli.py:287`) stays
  **openspec-only, deliberately** — `--change` is OpenSpec vocabulary with
  no SpecKit equivalent. `--dialect` argparse choices gain `"speckit"` on
  `p_val` (`cli.py:443`) and `p_waivers` (`cli.py:467`) only — NOT `p_new`
  (scaffolding is out of scope) and NOT `cmd_graph` (has no `--dialect`
  flag today). `cmd_detect` text output gets a
  `specs/ (SpecKit)  present/ABSENT` line. No new `--feature` CLI flag —
  `filter_speckit_by_feature` exists for shape-parity/future use but
  nothing wires it to the CLI yet.
- **`openspec_graph/graph.py`** — `graph.py:233-239` gets the identical
  union treatment as `cli.py`'s guards, both in its `NoOpenSpecTreeError`
  guard and in its own internal `detect.find_spec_files(profile.openspec_root)`
  gather — verified directly to need the same fix, not "zero changes" as an
  earlier draft assumed.
- **Docs/test infra** — `tests/test_rule_registry_docs.py`'s `_FAMILIES`
  tuple and README-table regex (both hardcoded to exactly G/H/U/W today)
  gain the `S` prefix **before** `rules_speckit.py` is wired into
  `rules.py`, so the repo's own `planlint-add-rule` doc-drift discipline
  actually validates the new family instead of silently passing over it.
  README's rules table, `docs/architecture/c4.md`'s module map + rule count
  + range comment, `docs/agents-skills-harness.md`, `docs/next-steps.md`,
  and `docs/differentiation-roadmap.md` all updated to match `rules.RULES`.
  `tests/baseline_rules.json` regenerated; `test_decomposition.py`'s
  `_EXPECTED_HASHES["rules"]` re-pinned (`["validate"]`/`["graph"]` stay
  unchanged, confirmed empirically against the canonical fixture, which has
  no `specs/` directory).

## Non-Goals

- **`planlint new`/`init` scaffolding SpecKit packages** — out of scope,
  confirmed with the requester; `scaffold.py`/`scaffold_templates.py`
  untouched. Note as an aside, not a task: `scaffold.py:76-78`'s
  `{"unknown", "mixed"} -> "harness"` fallback doesn't include `"speckit"`,
  so a pure-SpecKit repo's `profile.dialect` would pass through and
  `planlint new` would silently scaffold a harness-shaped package —
  confusing, not crashing, deliberately not fixed here since scaffolding a
  SpecKit-shaped package at all is the excluded capability.
- **Parsing `plan.md`/`tasks.md`** — v1 reads `spec.md` only, matching
  existing precedent: harness/upstream never read `proposal.md`/`tasks.md`
  back either.
- **A `--feature` CLI flag for change-scoping** — `filter_speckit_by_feature`
  exists for shape-parity with `filter_by_change` and future use, but this
  change does not wire it to any CLI surface; no committed acceptance
  criterion needs it yet.
- **Fine-grained "mixed" dialect states** — `detect_dialect()`'s `"mixed"`
  stays a single, undifferentiated value (`present > 1`) rather than
  enumerating which specific pair or triple of dialects co-occurs; the
  existing two-dialect precedent already collapses to one `"mixed"` value,
  and a repo mixing dialects is itself the finding, not the specific
  combination.
- **An "orphaned requirement" SpecKit rule** — SpecKit's grammar has no
  FR↔SC citation convention to check an orphan against; a rule modeled on
  H003/U002 would be 100% false positive on every real SpecKit spec, since
  `Criterion.requirement_refs` for SpecKit-derived criteria is honestly
  empty by design (see What Changes, `parse_speckit.py`).

## Affected Capabilities

- `speckit-dialect`
