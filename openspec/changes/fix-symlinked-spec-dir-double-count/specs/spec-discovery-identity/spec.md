# Spec: Spec Discovery Identity

> **Change:** `fix-symlinked-spec-dir-double-count`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

`Path.glob()` follows a *valid* directory symlink. Both of this package's
discovery functions glob for spec files —
`detect.find_spec_files`'s `openspec_root.glob("changes/*/specs/*/spec.md")`
and `detect.find_speckit_spec_files`'s `speckit_root.glob("*/spec.md")` — so
a `specs/002-alias -> specs/001-foo` directory link yields two distinct
`Path` entries for one underlying `spec.md`. One spec is then parsed twice,
and every count downstream of discovery reports work that does not exist:
`StackProfile.feature_dirs` and `StackProfile.change_dirs` over-count,
`validate`'s `specs_checked` over-reports, and `graph.build_graph()` renders
duplicate `FR-001`/`SC-001` nodes for a single requirement — a spec graph
showing phantom obligations, which is the exact failure mode this tool exists
to catch in other repositories.

**Evidence:** `docs/next-steps.md` item 4a records the defect in these terms:
"`Path.glob()` follows a *valid* directory symlink, so a
`specs/002-alias -> specs/001-foo` link yielded two distinct `Path` entries
for one `spec.md`: `feature_dirs` reported 2 features for 1, and
`graph.build_graph()` rendered duplicate `FR-001`/`SC-001` nodes." It was
confirmed by construction during the `add-speckit-dialect` PR review, against
the discovery function that change introduced, and deferred out of that PR
rather than patched into it because the correct fix is symmetric across both
discovery functions. `find_spec_files` had the identical latent behaviour for
`openspec/changes/` — same glob semantics, one path segment deeper — and no
test in the suite covered either function's behaviour under a symlink.

A second fact surfaced only during implementation, which item 4a did not
anticipate: `detect.profile()` computes `change_dirs` from its *own*
separate glob of `openspec/changes/*`, not from `find_spec_files()`. Fixing
only the two spec-file functions left `change_dirs` still double-counting.
`docs/next-steps.md` records how it was found: "A test caught it; reading the
code had not."

---

## Requirements

- R-SDI-1: Discovery MUST return at most one path per underlying file.
  `detect.find_spec_files` and `detect.find_speckit_spec_files` MUST each
  yield exactly one entry for a `spec.md` reachable through more than one
  logical path, however many directory symlinks reach it.
- R-SDI-2: The deduplication MUST be one shared helper
  (`detect._dedupe_by_identity`) applied by both discovery functions, not a
  dialect-specific patch in either. The two functions MUST NOT carry
  independent copies of the identity rule.
- R-SDI-3: `detect.profile()`'s `change_dirs` MUST be deduplicated by that
  same helper. It MUST keep its own glob of `openspec/changes/*` rather than
  being derived from `find_spec_files()`, because a change package with no
  `spec.md` yet is still a change package and MUST NOT disappear from
  `change_dirs`.
- R-SDI-4: Identity MUST be the resolved real path (`Path.resolve()`), never
  file content. Two genuinely distinct files with byte-identical text MUST
  both survive discovery.
- R-SDI-5: The **first** logical path in the caller's own order MUST win.
  Callers sort their globs, so the surviving path MUST be deterministic
  across runs rather than depending on filesystem enumeration order.
- R-SDI-6: A candidate whose real path cannot be resolved MUST keep its
  logical path and MUST NOT be dropped. Discovery MUST never silently lose a
  spec; whether the path can actually be read is the downstream read guard's
  decision (`parse.SpecReadError`), which fails closed at exit 2.
- R-SDI-7: Each skipped duplicate MUST be recorded at `logger.debug` naming
  the path, matching `detect.py`'s existing diagnostic style — a spec that
  vanishes from a report with no observable reason is indistinguishable from
  a spec the tool never saw.
- R-SDI-8: Every count derived from discovery MUST reflect real files once:
  `StackProfile.feature_dirs`, `validate --json`'s `specs_checked`, and the
  `type: "spec"` node set `graph.build_graph()` renders.
- C-SDI-1: This change MUST NOT add, remove, or re-scope a rule. The `RULES`
  registry in `openspec_graph/rules.py` and the rules table in `README.md`
  MUST be unchanged, and no new finding MUST be emitted for a symlinked
  directory.
- C-SDI-2: A tree containing no symlinks MUST behave exactly as before. The
  helper MUST be a no-op on such input, preserving order and every element.
- C-SDI-3: `find_speckit_spec_files`' per-file `is_speckit_marked()` content
  gate MUST NOT change. Deduplication MUST run before the gate, so the gate
  evaluates each real file exactly once.
- C-SDI-4: Deduplication MUST NOT collapse two genuinely distinct change
  packages or features. Two real features MUST remain two spec files, two
  spec nodes, and two entries in `feature_dirs`.

---

## Decisions

- **DEC-SDI-001:** identity is `Path.resolve()`, not a content hash and not
  `os.stat()`'s `(st_dev, st_ino)` pair. A content hash is wrong on the
  merits: two genuinely separate specs that happen to read the same are two
  specs, both of which must be linted, and collapsing them would silently
  drop one from every gate — a false green, which is worse than the
  over-count being fixed here. `(st_dev, st_ino)` would additionally catch
  hard links, but costs a `stat()` per candidate, cannot be computed at all
  for a path that does not exist, and answers a question nobody asked: the
  observed defect is a *directory* symlink, which `resolve()` collapses
  exactly. `resolve()` is also what `profile()` already applies to `root`,
  so the notion of "the same place" stays one notion package-wide.
- **DEC-SDI-002:** the survivor is the candidate that **is its own real
  path**, with the caller's order breaking any remaining tie.

  This decision was first written the other way round — first-in-sorted-order
  wins, with "prefer the real directory" considered and rejected as answering
  a question no consumer asks. Reproducing the behaviour refuted that. The
  question is asked, by `--change`: with `changes/alias -> changes/real`,
  "alias" sorts first, so the alias survived and `--change real` reported *no
  specs found* while `--change alias` passed. A rule that leaves the real
  package unaddressable by its own name is arbitrary, not deterministic.

  The rejection's second objection does survive and is handled rather than
  dismissed: when two links both point at a third target, no candidate is its
  own real path, so the caller's order decides and the result stays stable.
  Determinism is preserved for every input; only the choice between a real
  path and an alias is now made on meaning instead of on spelling.

  The cost is one `Path.resolve()` comparison per duplicate — resolve() is
  already called on every candidate to establish identity, so no extra
  syscall is introduced.
- **DEC-SDI-003:** an unresolvable candidate keeps its logical path instead
  of being dropped. Dropping it would make a spec disappear from a gate that
  never examined it — silent and green, the worst available outcome, and the
  same reasoning `DEC-RE-004` used to make the parse layer fail closed while
  `detect.py`'s optional-input reads fail open. A discovered spec is a
  mandatory input. Keeping the path hands the decision to
  `parse.SpecReadError`, which already renders one line and exits 2. The
  branch carries `# pragma: no cover` because it is reachable only on
  platforms and filesystems where `resolve()` itself raises; the fallback is
  cheap, and pretending it is unreachable would be the worse trade.
- **DEC-SDI-004:** deduplication runs inside each discovery function, not in
  `profile()` and not at each consumer. `profile()`, `cmd_validate`,
  `cmd_waivers`, and `build_graph` all gather spec files independently;
  putting the guard at the consumers means the next consumer inherits the
  defect for free, which is the exact shape of the original bug. One helper
  called at the source gives every present and future caller the property
  without opting in.
- **DEC-SDI-005 (found by a test during implementation, not by reading the
  code):** `profile()`'s `change_dirs` needed the same treatment and did not
  get it from the two spec-file fixes, because it is computed from its own
  separate glob of `openspec/changes/*`. The glob deliberately stays
  separate rather than being derived from `find_spec_files()`: a change
  package that has a `proposal.md` and `tasks.md` but no `spec.md` yet is
  still a change package, and deriving `change_dirs` from spec files would
  erase it from `detect`'s report and from the dialect card. It simply gets
  the same dedup applied. `docs/next-steps.md` item 4a is amended to record
  this, since the item as written did not anticipate it.
- **DEC-SDI-006:** deduplication happens *before*
  `find_speckit_spec_files`' `is_speckit_marked()` content gate, not after.
  After-the-gate dedup would read and classify the same bytes twice per
  alias, and would let the function's own `skipped` debug line name one
  unmarked file two times — a diagnostic that misdescribes the tree it is
  diagnosing. Before-the-gate also keeps the gate's contract (`DEC-SK-002`)
  untouched: it still decides per file, on content, exactly as it did.
- **DEC-SDI-007:** no operator-facing output changes and no rule is added. A
  symlinked change directory is a legitimate repository layout, not a spec
  defect, so it is not a finding; the duplicate was an artifact of *this
  tool's* discovery, and the honest fix is to stop producing it rather than
  to report the user's own filesystem back at them. The skip is therefore a
  `logger.debug` record (R-SDI-7) reachable with the existing logging
  configuration, not a new `WARN`.
- **DEC-SDI-008:** the whole test module is skipped where symlink creation
  is unprivileged, via `pytestmark` and the existing
  `tests.support.supports_symlinks()` capability probe. This is a **real
  coverage caveat, not a passing test**: on Windows without Administrator
  rights or Developer Mode, none of these 11 tests runs, and the suite
  reports skips rather than green assertions. A capability probe is used
  rather than a `sys.platform` check so a Windows box that *does* hold
  `SeCreateSymbolicLinkPrivilege` still runs them, and the product code
  itself is platform-neutral (`Path.resolve()` collapses a Windows directory
  junction the same way).

---

## Acceptance Criteria

- [x] **AC-SDI-1:** A change package reachable through a directory symlink
  (`openspec/changes/alias-change -> openspec/changes/real-change`) is
  discovered once by `find_spec_files`, and a SpecKit feature reachable
  through `specs/002-alias -> specs/001-real` is discovered once by
  `find_speckit_spec_files` — one shared helper, both call sites.
  (R-SDI-1, R-SDI-2)
  _Verified by:_ `pytest -k "test_a_symlinked_change_package_is_discovered_once or test_a_symlinked_feature_is_discovered_once"` · stage: `make test`

- [x] **AC-SDI-2:** `detect.profile()` reports one entry in `change_dirs`
  for a change directory reachable through two paths, while the glob that
  produces it stays independent of `find_spec_files()`. (R-SDI-3,
  DEC-SDI-005)
  _Verified by:_ `pytest -k test_profile_does_not_double_count_change_dirs` · stage: `make test`

- [x] **AC-SDI-3:** Every count downstream of discovery reflects the real
  file once: `feature_dirs` holds one entry, `validate --json`'s
  `specs_checked` reads 1, and `graph --format json` renders exactly one
  `type: "spec"` node, for a tree whose single real spec has an alias
  directory beside it. (R-SDI-8)
  _Verified by:_ `pytest -k "test_profile_does_not_double_count_feature_dirs or test_validate_reports_one_spec_checked or test_the_graph_renders_one_node_per_real_requirement"` · stage: `make test`

- [x] **AC-SDI-4 (non-success):** identity is the file, never its bytes —
  two real files with byte-identical content both survive the helper, and
  two real SpecKit features stay two discovered spec files. If either
  assertion ever fails, the fix has started hiding real specs. (R-SDI-4,
  C-SDI-4)
  _Verified by:_ `pytest -k "test_dedupe_keeps_genuinely_distinct_files_with_identical_content or test_two_real_features_are_still_two_nodes"` · stage: `make test`

- [x] **AC-SDI-5:** the survivor is the candidate that *is* its own real
  path — the real directory, never an alias pointing at it — regardless of
  the order the caller supplies. Where no candidate is the real path (two
  aliases onto a file outside the scanned set) the caller's own order decides,
  so the result is stable for every input. (R-SDI-5, DEC-SDI-002)
  _Verified by:_ `pytest -k "test_dedupe_prefers_the_real_path_over_an_alias or test_dedupe_is_stable_when_neither_candidate_is_the_real_path"` · stage: `make test`

- [x] **AC-SDI-6 (non-success):** a tree with no symlinks is unaffected —
  the helper returns its input unchanged, in order, and this repository's own
  byte-identical CLI-output regression stays green. (C-SDI-2)
  _Verified by:_ `pytest -k "test_dedupe_is_a_no_op_without_links or test_output_byte_identical"` · stage: `make test`

- [x] **AC-SDI-7:** a candidate whose real path cannot be resolved keeps its
  logical path rather than being dropped, and each skipped duplicate is
  observable at `logger.debug` naming the path. (R-SDI-6, R-SDI-7,
  DEC-SDI-003)
  _Verified by:_ code review of `detect._dedupe_by_identity`'s `except OSError` fallback (carrying `# pragma: no cover`, reachable only where `Path.resolve()` itself raises) and of its two `logger.debug` records; this suite has no `caplog` harness, so no automated test covers either · stage: `make test`

- [x] **AC-SDI-8 (non-success):** no rule is added, removed, or re-scoped —
  the rules table in `README.md` still matches the registry exactly and every
  prose rule-count claim in the repository still holds, with no finding
  emitted for a symlinked directory. (C-SDI-1, DEC-SDI-007)
  _Verified by:_ `pytest -k "test_readme_rules_table_matches_rules_exactly or test_total_rule_count_matches_every_prose_claim"` · stage: `make test`

- [x] **AC-SDI-9 (non-success):** the SpecKit content gate is unchanged and
  runs after deduplication, not instead of it — an unmarked
  `specs/<name>/spec.md` alongside genuinely marked ones is still excluded,
  and an unreadable candidate is still skipped rather than crashing
  `profile()`. (C-SDI-3, DEC-SDI-006)
  _Verified by:_ `pytest -k "test_find_speckit_spec_files_excludes_unmarked_spec_md_even_alongside_genuine_ones or test_find_speckit_spec_files_skips_an_unreadable_candidate_not_crashes"` · stage: `make test`

- [x] **AC-SDI-10 (observable behaviour change):** two change directories
  symlinked to one target are one package, so only one name addresses it.
  `validate --change <real-name>` passes; `validate --change <alias-name>`
  exits **2** with `no specs found for change '<alias-name>'`. That is
  correct — they were never two packages — but it is observable to anyone who
  scripted the alias name.

  This criterion was originally written the other way round, deduced from
  "the first path in sorted order wins" and never reproduced. Reproducing it
  showed the opposite: `alias-change` sorts before `real-change`, so the
  **alias** survived and the real package became unaddressable by its own
  name. The tie-break in AC-SDI-5 exists because of that measurement, and
  this criterion now records the fixed behaviour rather than the deduced one.
  (R-SDI-1, R-SDI-5, DEC-SDI-002)
  _Verified by:_ `pytest -k "test_the_real_package_keeps_its_own_name_under_change or test_an_alias_name_reports_no_specs_found"` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-SDI-1 through AC-SDI-9 green (AC-SDI-7 by the code review its selector names); the 11 tests in `tests/test_spec_discovery_identity.py` either run or skip wholesale where symlink creation is unprivileged, per DEC-SDI-008 |
| Self-check | `make validate` | this repo's own change packages stay clean at `--fail-on WARN`, this package included |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
