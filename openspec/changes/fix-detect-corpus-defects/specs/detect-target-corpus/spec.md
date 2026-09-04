# Spec: Detection held to a labelled target corpus

> **Change:** `fix-detect-corpus-defects`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

## Problem Statement

`detect` reads a stranger's repository and every rule downstream trusts what
it reports. It had two real repositories and inline fixtures as its evidence.
Twenty labelled synthetic shapes found four defects that reproduce by hand —
a BOM-mangled target name producing a false G004, a `fail_under` attributed
to a TOML table that did not exist, a fractional floor truncated so the
reported gate was looser than the real one, and a traceback with exit 1 when
a config file's name was a directory — and an adversarial review of the fix
found three more of the same class. None of them was visible to any existing
gate. The card needs labelled input, not confidence.

## Requirements

- R-TC-1: `machinery.parse_makefile` MUST treat a leading U+FEFF as absent,
  and `detect._legacy_make_targets` MUST do the same, so neither parser can
  fabricate or drop a first target on a BOM-prefixed Makefile.
- R-TC-2: A `fail_under` key MUST be reported as the coverage floor only when
  it is declared directly under `[tool.coverage.report]`; a line inside a
  multi-line string or array under that table, a key under any other table,
  and an `[[array-of-tables]]` MUST NOT be.
- R-TC-3: A fractional coverage floor MUST be reported with its fraction, and
  an integral floor MUST stay an `int` in the card so saved `detect --diff`
  baselines report no drift.
- R-TC-4: A coverage floor MUST be a plain decimal within the percentage
  range; `float()`'s wider grammar (exponents, underscores, signs, non-ASCII
  digits) and out-of-range values MUST be rejected, and the
  governance-policy path MUST accept numbers only.
- R-TC-5: An optional config file that exists but is not a regular readable
  file (a directory, a FIFO, a dangling symlink) MUST be treated as absent by
  every read in `detect`, never raised and never blocked on.
- R-TC-6: Every read of optional config and of spec text MUST decode with
  `utf-8-sig`, so dialect detection and spec parsing see the same first line.
- R-TC-7: G003's exact-floor suppression and `delta`'s baseline reader MUST
  compare a fractional floor like with like.
- R-TC-8: Each corpus shape MUST carry a hand-written partial expected card
  compared through `dialect_card.diff_cards()`, and each MUST be described in
  the corpus README.
- C-TC-1: `machinery.py` MUST NOT import `subprocess` and `detect.py` MUST
  remain its only importer (DEC-WM-009); the hostile-Makefile shape MUST prove
  by canary that parsing executes nothing.
- C-TC-2: No new TOML locator spelling beyond the plain and quoted table
  header MUST be claimed; unsupported spellings MUST be pinned in the corpus
  as `threshold = null`.

## Decisions

- **DEC-TC-001:** BOM handling lives in the pure parser *and* at the read
  site. `parse_makefile` is public API that takes text from any caller, so its
  own contract is BOM-tolerant; `utf-8-sig` at the read site keeps the codec
  from ever handing a BOM to either parser. One without the other leaves a
  path where the two Makefile parsers disagree, which is the exact divergence
  `fix-makefile-define-block-misparse` closed for `define` blocks.
- **DEC-TC-002:** a line scanner, not `tomllib`. `tomllib` exists only from
  3.11, this package declares zero runtime dependencies so `tomli` is not
  available, and choosing a parser by interpreter version would make the card
  differ across the 3.10–3.13 matrix — breaking the byte-identical contract
  (`AC-DC-1`). The scanner tracks multi-line strings and arrays because
  `[tool.coverage.report]` is exactly where coverage.py's free-text
  `exclude_lines` lists live.
- **DEC-TC-003:** `as_threshold_number` returns `int` for integral input.
  Widening `90` to `90.0` would make every saved `--diff` baseline report
  drift on an unchanged repository; the card's stability is a contract, not
  a formatting choice.
- **DEC-TC-004:** a plain-decimal grammar and a percentage range, not
  `float()`. `float("1e3")`, `float("1_000")`, `float("-5")` and full-width
  digits all succeed, none is a coverage floor coverage.py would accept, and
  any of them would become a number W002 compares witness coverage against.
- **DEC-TC-005:** an unreadable optional file is absent, not exit 2. The
  plan proposed exit 2; `_invariants` and `_adrs` already treated their
  candidates as absent on `OSError`, and consistency won. `is_file()` is
  checked before opening because a FIFO passes `exists()` and blocks on
  `open()` with no exception to catch.
- **DEC-TC-006:** partial expected cards through `diff_cards()`. The function
  already ignores fields absent from the baseline, so a shape asserts only
  its own dimension and an additive schema change does not churn every
  fixture; `schema_version` is injected by the test and pinned once.
- **DEC-TC-007:** expectations are written before running the detector.
  A card copied from the detector's output asserts that the code equals
  itself. The corpus README states each expectation in words, and a test
  checks every shape is described.
- **DEC-TC-008:** unsupported TOML spellings are pinned as `null`, not
  omitted. A shape that pins a limit turns "we do not read inline tables"
  from tribal knowledge into a decision a future change must consciously
  reverse.

## Acceptance Criteria

- [x] **AC-TC-1:** a BOM-prefixed Makefile whose first line is a rule yields
  `all, build, test`; one whose first line is `.PHONY:` yields `build, test`
  with no BOM-prefixed special target. (R-TC-1)
  _Verified by:_ `pytest -k test_detected_card_matches_the_labelled_expectation` · stage: `make test`

- [x] **AC-TC-2:** both Makefile parsers agree on a BOM-prefixed file, and
  `strip_bom` is idempotent and leaves a mid-text U+FEFF alone. (R-TC-1)
  _Verified by:_ `pytest -k test_both_makefile_parsers_agree_on_a_bom_prefixed_file` · stage: `make test`

- [x] **AC-TC-3 (non-success):** `fail_under` under `[tool.some_other_tool]`,
  inside a multi-line string, inside a multi-line array, under
  `[[tool.coverage.report]]`, or written as a quoted string yields no floor;
  a quoted or spaced header spelling of the right table yields one. (R-TC-2, C-TC-2)
  _Verified by:_ `pytest -k test_scoped_fail_under_ignores_lines_inside_multiline_strings` · stage: `make test`

- [x] **AC-TC-4:** a floor of `85.5` is reported as `85.5` from `pyproject.toml`,
  `.coveragerc` and `governance-policy.json`, and a floor of `90` stays an
  `int`. (R-TC-3)
  _Verified by:_ `pytest -k test_as_threshold_number_accepts_plain_decimals_in_range` · stage: `make test`

- [x] **AC-TC-5 (non-success):** `"1e2"`, `"1_000"`, `"-5"`, non-ASCII
  digits, booleans, non-finite floats and out-of-range values are rejected,
  and a quoted number in `governance-policy.json` is a misconfiguration, not
  a floor. (R-TC-4)
  _Verified by:_ `pytest -k test_as_threshold_number_rejects_what_is_not_a_percentage` · stage: `make test`

- [x] **AC-TC-6 (non-success):** a directory named `Makefile` or
  `pyproject.toml` produces a profile with no targets and no floor, with no
  traceback; a FIFO in either place returns rather than blocking. (R-TC-5)
  _Verified by:_ `pytest -k test_a_directory_where_a_config_file_belongs_does_not_crash` · stage: `make test`

- [x] **AC-TC-7:** a BOM-prefixed `.coveragerc`, `governance-policy.json` and
  spec file are read correctly; the spec keeps every criterion under a
  BOM-prefixed first-line heading. (R-TC-6)
  _Verified by:_ `pytest -k test_a_bom_prefixed_spec_keeps_its_first_line_criterion` · stage: `make test`

- [x] **AC-TC-8 (non-success):** a criterion citing the exact fractional floor
  draws no G003, and `delta` reads a fractional baseline floor while
  rejecting a boolean. (R-TC-7)
  _Verified by:_ `pytest -k test_g003_does_not_flag_a_criterion_that_cites_the_exact_fractional_floor` · stage: `make test`

- [x] **AC-TC-9 (non-success):** parsing the hostile Makefile shape — with
  `$(shell rm -rf …)`, a bare `$(shell touch …)`, `$(eval $(shell …))`,
  `.SHELLFLAGS` and `.ONESHELL` — leaves the canary directory intact and
  creates none of its side-effect files, while still reporting its targets.
  (C-TC-1)
  _Verified by:_ `pytest -k test_parsing_a_hostile_makefile_executes_nothing` · stage: `make test`

- [x] **AC-TC-10:** every corpus shape is described in the corpus README, the
  corpus is non-empty, and the byte specimens (BOM, CRLF) survive checkout.
  (R-TC-8)
  _Verified by:_ `pytest -k test_every_shape_is_documented` · stage: `make test`

- [x] **AC-TC-11:** the card for every shape is byte-identical across two
  interpreters started with different hash seeds. (R-TC-8)
  _Verified by:_ `pytest -k test_detection_is_byte_stable_across_hash_seeds` · stage: `make test`

- [x] **AC-TC-12:** `detect.py` is still the only module importing
  `subprocess` and `machinery.py` imports neither `subprocess` nor `os`.
  (C-TC-1)
  _Verified by:_ `pytest -k test_only_detect_imports_subprocess` · stage: `make test`

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-TC-1..12 |
| Self-check | `make validate` | this repo's own change packages validate clean with the corrected detector |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, thresholds |
