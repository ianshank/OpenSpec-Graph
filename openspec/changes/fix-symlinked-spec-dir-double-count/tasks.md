# Milestones

## Milestone 1 — One identity helper, applied at both discovery functions [DONE]

- `openspec_graph/detect.py`: add private `_dedupe_by_identity(paths:
  Iterable[Path]) -> list[Path]`. Key each candidate on `Path.resolve()`
  (DEC-SDI-001), keep the **first** logical path per distinct real file in
  the caller's own order (DEC-SDI-002), fall back to the logical path in an
  `except OSError` branch carrying `# pragma: no cover` rather than dropping
  the candidate (R-SDI-6, DEC-SDI-003), and emit a `logger.debug` naming the
  path both when a candidate cannot be resolved and when a duplicate is
  skipped (R-SDI-7). Docstring records why identity is the path and not the
  content, why first-wins, and why nothing is ever dropped. `Iterable` joins
  the existing `collections.abc` import.
- `openspec_graph/detect.py`: `find_spec_files` wraps its existing
  `sorted(openspec_root.glob("changes/*/specs/*/spec.md"))` in the helper —
  the sort stays, since first-wins is only deterministic over an ordered
  input (R-SDI-1, R-SDI-5).
- `openspec_graph/detect.py`: `find_speckit_spec_files` wraps
  `sorted(speckit_root.glob("*/spec.md"))` in the helper and iterates the
  deduplicated list, so the per-file `is_speckit_marked()` gate and its
  `skipped` diagnostic each see a real file exactly once (R-SDI-2, C-SDI-3,
  DEC-SDI-006). The gate itself is untouched.
- **Gate:** `make test` — AC-SDI-1, AC-SDI-5, AC-SDI-9.

## Milestone 2 — The third glob nobody was looking at [DONE]

- `openspec_graph/detect.py`: `profile()`'s `change_dirs` computation
  (`sorted(p for p in (openspec_root / "changes").glob("*") if p.is_dir())`)
  goes through the same helper (R-SDI-3). A comment records that the glob
  stays separate from `find_spec_files()` deliberately — a change package
  with no `spec.md` yet is still a change package — rather than being
  derived from the now-deduplicated spec files (DEC-SDI-005).
- Confirm `feature_dirs` needs no separate treatment: it is already derived
  as the distinct sorted parents of `find_speckit_spec_files()`'s results,
  so Milestone 1 fixes it transitively (R-SDI-8).
- **Gate:** `make test` — AC-SDI-2, AC-SDI-3.

## Milestone 3 — Pin the behaviour, including what must *not* collapse [DONE]

- New `tests/test_spec_discovery_identity.py`: 11 tests with a module-level
  `pytestmark = pytest.mark.skipif(not supports_symlinks(), ...)` reusing the
  existing `tests.support.supports_symlinks()` capability probe, and a module
  docstring stating the defect and why the fix is one shared helper rather
  than a dialect-specific patch (DEC-SDI-008).
- Helper-level tests: one entry per underlying file; the first logical path
  wins in both orderings of the same pair; two byte-identical but genuinely
  distinct files both survive; a link-free input is returned unchanged
  (AC-SDI-4, AC-SDI-5, AC-SDI-6).
- Discovery-level tests: a symlinked change package and a symlinked SpecKit
  feature are each discovered once; `profile()` double-counts neither
  `change_dirs` nor `feature_dirs`; `validate --json` reports
  `specs_checked: 1`; `graph --format json` renders one `type: "spec"` node
  (AC-SDI-1, AC-SDI-2, AC-SDI-3).
- Non-success test: two real features stay two discovered spec files, so a
  regression that starts hiding real specs fails here rather than passing
  quietly (C-SDI-4, AC-SDI-4).
- Confirm no golden hash in `tests/test_decomposition.py` needs re-pinning:
  the canonical fixture repo contains no symlink, so the helper is a no-op
  over it and `test_output_byte_identical` must pass untouched (C-SDI-2,
  AC-SDI-6).
- **Gate:** `make test` green; `make pre-pr` green end to end.

## Milestone 4 — Record what the deferral did not anticipate [DONE]

- `docs/next-steps.md`: strike item 4a and record it as shipped in this
  change, keeping the original defect description intact, and append the
  finding the item did not anticipate — that `profile()`'s `change_dirs`
  came from its own separate glob, that a test rather than a code read
  caught it, and that the glob stays separate and simply gets the same
  dedup (DEC-SDI-005).
- Confirm nothing rule-shaped changed: `openspec_graph/rules.py`'s `RULES`
  tuple and `README.md`'s rules table are untouched, and
  `tests/test_rule_registry_docs.py` passes unmodified (C-SDI-1, AC-SDI-8).
- Dogfood: run `planlint validate --fail-on WARN` against this repository
  with this change package present.
- **Gate:** `make validate` clean at `--fail-on WARN`.

## Milestone 5 — Close out the paper trail and the one untested claim

Not yet done. Both items below are known gaps, not oversights to discover
later.

- `CHANGELOG.md`: one entry under the unreleased heading, in the style of
  the neighbouring `fix-unreadable-spec-exit-code` entry — one spec on disk
  is discovered once however many paths reach it, why identity is the
  resolved path rather than the content, and the observable consequence that
  an alias change-directory name is no longer selectable by `--change`. No
  entry exists yet.
- `AC-SDI-10` is unverified: the `--change <alias-name>` exit-2 consequence
  is deduced from `detect.filter_by_change` and
  `cli._report_no_specs_for_change`, not reproduced and not covered by a
  test. Either reproduce it and cite the reproduction the way `DEC-RE-009`
  does, or write the regression test — it belongs with whichever change next
  touches `--change` scoping, where `DEC-RE-009` already left one pending.
- Hand this package to `spec-adversary` before anyone implements against it
  further.
- **Gate:** `make pre-pr` green with the changelog entry present, and
  `AC-SDI-10` either checked with a cited verification or explicitly carried
  forward into another change.
