# Change: Fix four detection defects found by a labelled target corpus (CP-TC)

## Why

`detect` is the load-bearing primitive: G003's threshold locator, G004's
make-target existence, G005's invariant source and H001's runnable stage are
each only as correct as the dialect card underneath them. Until this change it
had been validated against two real repositories plus a handful of inline
fixtures. A probe over twenty synthetic target repositories, built in one
sitting with `printf` and a hand-written expectation per shape, found five
wrong detections and two crashes.

**Evidence:** `docs/eval-corpus-plan.md` appendix A records the probe table.
Four of its findings reproduce by hand against `7cb2bd6`: a UTF-8 BOM
Makefile yields the target list `["build", "﻿all"]` (`machinery.py`'s
`_RULE_LINE` accepts U+FEFF because `str.strip()` does not remove a Cf format
character) and `validate` then emits a **false G004** for `` `make all` ``;
`detect.py`'s whole-file `_FAIL_UNDER` regex matched `fail_under` under any
TOML table and reported it as `[tool.coverage.report].fail_under`; a
fractional floor `85.5` was reported as `85`; and a directory named
`Makefile` or `pyproject.toml` raised `IsADirectoryError` from
`detect.profile()` with exit 1, the code reserved for "findings were
reported". An adversarial review of the fix then found three more of the
same class: a `fail_under` line inside a multi-line TOML string or array under
the right table was read as the floor, `float()`'s grammar let `"1e3"`,
`"-5"` and non-ASCII digits become floors, and a FIFO named `Makefile`
blocked `detect` forever.

## What Changes

- `openspec_graph/machinery.py`: `strip_bom()`, applied in `parse_makefile`,
  and applied symmetrically in `detect._legacy_make_targets` so the two
  parsers cannot diverge on a BOM the way they once did on `define` blocks.
- `openspec_graph/detect.py`: `read_text_or_none()` (regular files only,
  `utf-8-sig`, treats an unreadable optional file as absent) is the one read
  path for the Makefile, `pyproject.toml`, `governance-policy.json`, the
  invariant and ADR sources and dialect detection; `scoped_fail_under()` is a
  table-aware, string- and array-aware TOML line scanner with normalised
  headers; `as_threshold_number()` accepts plain decimals in the percentage
  range only and returns `int` for integral values so existing cards do not
  churn; `_read_ini_fail_under` decodes `utf-8-sig` and accepts a fraction.
- `openspec_graph/parse_semantics.py` `HARD_THRESHOLD`/`threshold_values()`
  and `openspec_graph/delta.py` `_baseline_threshold()` carry a fraction, so
  a spec citing an exact fractional floor is not a G003 and `delta` does not
  skip threshold deltas for a fractional baseline.
- `openspec_graph/parse.py` and `openspec_graph/cli.py` read specs and
  `--diff`/`--baseline` cards with `utf-8-sig`.
- New `tests/corpus/targets/`: labelled synthetic target repositories, each
  with a partial expected card, plus a README stating every expectation in
  words; `.gitattributes` marks the corpus `-text`.
- New `tests/test_detect_corpus.py` and `tests/test_detect_thresholds.py`.

## Non-Goals

- No new threshold locator (tox.ini, Gradle JaCoCo, vitest) and no following
  of Makefile `include`s. Those shapes are in the corpus as pinned limits so
  that supporting one is a decision, not a drift.
- No `tomllib`. It is 3.11+ and this package has no runtime dependencies, so
  a version-dependent parser would make detection differ across the CI
  matrix. The inline-table and top-level dotted-key spellings of the floor
  stay unread and are pinned as limits (`docs/next-steps.md` 7a).
- No exit 2 for a directory where a config file belongs. The code already
  treated an unreadable invariant or ADR source as absent, and consistency
  with that convention won; with no targets G004 returns early, so absence
  is also the safe reading.
- No CI job for `detect --diff`. The parametrised corpus test is the
  detection-drift gate, on every `make test`.

## Affected Capabilities

detect-target-corpus
