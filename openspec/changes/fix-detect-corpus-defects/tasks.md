# Tasks: fix-detect-corpus-defects

## Milestone 1 — Reproduce the four defects  [DONE]

- Build the four shapes by hand (BOM rule-first, foreign-table `fail_under`,
  `fail_under = 85.5`, a directory named `Makefile`) and confirm each wrong
  card or traceback against `7cb2bd6` before touching code (DEC-TC-007).
- **Gate:** `make test`

## Milestone 2 — Fix detection  [DONE]

- `openspec_graph/machinery.py`: `strip_bom()`; `parse_makefile` applies it
  (R-TC-1, DEC-TC-001).
- `openspec_graph/detect.py`: `read_text_or_none()` for every optional read,
  regular files only, `utf-8-sig` (R-TC-5, R-TC-6, DEC-TC-005);
  `scoped_fail_under()` with string/array tracking and header normalisation
  (R-TC-2, DEC-TC-002); `as_threshold_number()` with a plain-decimal grammar,
  a percentage range and an `int`-preserving return (R-TC-3, R-TC-4,
  DEC-TC-003, DEC-TC-004); `_legacy_make_targets` strips the BOM too.
- `openspec_graph/parse_semantics.py` `HARD_THRESHOLD`/`threshold_values`,
  `openspec_graph/delta.py` `_baseline_threshold`/`_mentions_value`: carry a
  fraction (R-TC-7).
- `openspec_graph/parse.py`, `openspec_graph/cli.py`: `utf-8-sig` reads (R-TC-6).
- **Gate:** `make test`

## Milestone 3 — The labelled corpus  [DONE]

- `tests/corpus/targets/<shape>/{repo/, expected.json}` for the defect
  shapes, the INI conventions, the hostile Makefile, the documented limits
  (include chain, tox-only, Gradle, vitest, inline table, dotted key) and the
  dialect classifications; `tests/corpus/targets/README.md` states every
  expectation in words (R-TC-8, C-TC-2, DEC-TC-006..008).
- `.gitattributes`: the corpus and phrasing fixtures are `-text`.
- `tests/test_detect_corpus.py`: parametrised comparison through
  `diff_cards()`, README referential check, schema-version pin, hostile
  canary, generated directory/FIFO/large-Makefile cases.
- `tests/test_detect_thresholds.py`: the helpers on the inputs the review
  named, the float reaching G003 and `delta`, BOM spec heading, byte
  specimens, hash-seed subprocess determinism.
- **Gate:** `make test`

## Milestone 4 — Record it  [DONE]

- `README.md` ledger items 5–7, `CHANGELOG.md`, `docs/aqa.md` "Detection is
  held to a labelled corpus", `docs/architecture/c4.md` §6,
  `docs/next-steps.md` items 7 and 7a, `.claude/skills/planlint-add-detect-shape/`.
- **Gate:** `make pre-pr`
