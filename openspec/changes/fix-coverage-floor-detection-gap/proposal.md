# Change: Fix Coverage-Floor Detection Gap

## Why

`detect._threshold()` only ever checks a handful of governance-policy.json
candidates and `pyproject.toml` for a coverage floor. `.coveragerc` and
`setup.cfg` are both standard, common places Python projects put coverage
configuration, and `detect` is silently blind to both — it returns no
threshold found, with no error and no warning. Confirmed by constructing
minimal fixtures in each format and running `detect` against them.

**Evidence:** `openspec_graph/detect.py`'s `_threshold()` (before this
change) checked exactly 3 JSON governance-policy candidates, then exactly 1
file (`pyproject.toml`), and nothing else. The downstream consumer,
`scaffold.threshold_locator()`, falls back to the generic, non-actionable
string "the governance policy" when `profile.threshold` is `None` — a
developer whose repo's only coverage config lives in `.coveragerc` or
`setup.cfg` is told to consult a file that doesn't exist in their repo.
Separately, `parse_semantics.THRESHOLD_ALLOWLIST` (rule G003's allowlist for
excusing a spec that legitimately names its config source) also lacked
both filenames, so even after `_threshold()` learns to find the floor, a
spec citing `.coveragerc`/`setup.cfg` by name would still false-positive.

## What Changes

- `detect._threshold()` gains two additional checks, in precedence order
  after the existing `pyproject.toml` check: `.coveragerc` (`[report]`
  section), then `setup.cfg` (`[coverage:report]` section — namespaced
  differently, per coverage.py's own convention, to avoid colliding with
  other tools' sections in that file). Purely additive: behavior is
  unchanged for any repo that already resolves successfully today.
- Uses stdlib `configparser` (both files are INI format) — no new
  dependency.
- `parse_semantics.THRESHOLD_ALLOWLIST` gains both filenames.
- `docs/architecture/c4.md`'s invariants section updated to name all three
  possible coverage-floor locations, not just `pyproject.toml`.

## Non-Goals

- No change to precedence for repos with a config conflict across multiple
  files — `pyproject.toml` keeps winning over `.coveragerc`/`setup.cfg`
  unconditionally, matching today's "first resolvable source wins" design.
  A "most specific file wins" reordering (mirroring coverage.py's own real
  file-precedence) is a legitimate alternative but changes behavior for a
  rare case outside this fix's scope.
- No change to `tools/check_coverage_floor.py` — a separate CI gate script
  reading this repo's own `pyproject.toml`, not part of the `planlint
  detect` code path.

## Affected Capabilities

- `coverage-floor-detection`
