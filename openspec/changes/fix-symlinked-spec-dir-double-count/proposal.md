# Change: Fix Symlinked Spec Dir Double Count

## Why

`Path.glob()` follows a *valid* directory symlink. A
`specs/002-alias -> specs/001-foo` link therefore yields two distinct `Path`
entries for the same underlying `spec.md`, and every count derived from
discovery reports work that does not exist: `StackProfile.feature_dirs` says
2 features where there is 1, `validate`'s `specs_checked` over-reports, and
`graph.build_graph()` renders duplicate `FR-001`/`SC-001` nodes for a single
requirement. The spec graph — the artifact this tool exists to make
trustworthy — shows phantom work.

**Evidence:** `docs/next-steps.md` item 4a records the defect in exactly
those terms: "`Path.glob()` follows a *valid* directory symlink, so a
`specs/002-alias -> specs/001-foo` link yielded two distinct `Path` entries
for one `spec.md`: `feature_dirs` reported 2 features for 1, and
`graph.build_graph()` rendered duplicate `FR-001`/`SC-001` nodes." It was
confirmed by construction during the `add-speckit-dialect` PR review, against
the discovery function that change introduced
(`detect.find_speckit_spec_files`, whose glob is `speckit_root.glob("*/spec.md")`).
The behaviour is not SpecKit-specific: `detect.find_spec_files`' own
`openspec_root.glob("changes/*/specs/*/spec.md")` had the identical latent
behaviour for `openspec/changes/`, and no test in the suite covered either.
The item was deferred out of that PR rather than patched into it precisely
because the fix is symmetric across both discovery functions and belonged in
its own scoped change. This is that change.

A second, related fact the same investigation surfaced only after the fix was
written — item 4a itself did not anticipate it: `detect.profile()` computes
`change_dirs` from its *own* separate glob of `openspec/changes/*`, not from
`find_spec_files()`. In `docs/next-steps.md`'s words, "fixing only the two
spec-file functions left it still double-counting. A test caught it; reading
the code had not." The glob stays separate — a change package with no
`spec.md` yet is still a change package — and simply gets the same dedup.

## What Changes

- `openspec_graph/detect.py`: new private `_dedupe_by_identity(paths) ->
  list[Path]` helper. Keys each candidate on `Path.resolve()` and keeps the
  **first** logical path per distinct real file, in the caller's own order.
  A candidate whose real path cannot be resolved keeps its logical path
  rather than being dropped (`except OSError`, carrying a
  `# pragma: no cover` since the branch is platform-dependent), and each
  skipped duplicate is recorded at `logger.debug` naming the path —
  `detect.py`'s established diagnostic style.
- `openspec_graph/detect.py`: `find_spec_files` wraps its existing
  `sorted(openspec_root.glob("changes/*/specs/*/spec.md"))` in the helper.
- `openspec_graph/detect.py`: `find_speckit_spec_files` wraps its
  `sorted(speckit_root.glob("*/spec.md"))` in the helper, *before* the
  per-file `is_speckit_marked()` content gate, so the gate sees each real
  file exactly once and its `skipped` diagnostic cannot list one file twice.
- `openspec_graph/detect.py`: `profile()`'s `change_dirs` glob
  (`(openspec_root / "changes").glob("*")`, filtered to directories and
  sorted) goes through the same helper, with a comment recording why the
  glob stays separate from `find_spec_files()` rather than being derived
  from it.
- `tests/test_spec_discovery_identity.py`: one new module, 11 tests, covering
  the helper in isolation (dedup, first-path-wins, identical-content
  non-collapse, no-op without links), both discovery functions, both
  `profile()` counts, `validate --json`'s `specs_checked`, and the graph node
  count that made the defect visible. Module-level
  `pytestmark = pytest.mark.skipif(not supports_symlinks(), ...)`, reusing
  the existing `tests.support.supports_symlinks()` capability probe.

## Non-Goals

- No change to what a spec *is*. Identity is the resolved path, never file
  content: two genuinely distinct files with byte-identical text are two
  specs and both must be linted. Content-hash dedup would silently drop a
  real spec from every gate, which is the failure this tool exists to
  prevent.
- No read-error handling. Whether a discovered path can actually be opened
  stays the read guard's decision downstream — `parse.SpecReadError`, from
  the `fix-unreadable-spec-exit-code` change (`DEC-RE-008` there names this
  change as the owner of the discovery layer, and this change returns the
  favour by not touching the read layer).
- No dangling-symlink diagnostic, and no attempt to tell an alias apart from
  a real directory in operator-facing output. Discovery reports one path per
  file; naming which alias lost is a diagnostic (`logger.debug`) rather than
  a report.
- No `--follow-symlinks`/`--no-follow-symlinks` flag or configuration. There
  is no legitimate reading in which one file is two specs, so there is
  nothing for an operator to choose between.
- No new rule. Nothing here is a spec-quality finding, so the `RULES` tuple
  in `openspec_graph/rules.py` and the 26-row rules table in `README.md`
  are unchanged.

## Affected Capabilities

- `spec-discovery-identity`
