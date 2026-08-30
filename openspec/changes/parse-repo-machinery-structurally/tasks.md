# Milestones

## Milestone 0 — Design [DONE]

- Corrected the roadmap's suggested implementation approach before any code
  was written: shelling out to real `make` (even via `-p`/`-n`/`-q`) is
  unsafe against an untrusted target repo's Makefile. A stdlib-only,
  text-based structural parser that never invokes `make` is the design,
  full stop — not a fallback gated on `make`'s availability.
- Scoped what the parser must safely resolve (multi-target lines, `.PHONY`,
  special targets) versus what it explicitly declines to resolve with a
  safe fallback (variable expansion, `include`s, conditionals).
- Recorded open decisions (DEC-MP-001..004) so implementation does not
  re-litigate the safety question.

- **Gate:** this proposal + spec pass `planlint validate` against the
  repo's own rules.

## Milestone 1 — `machinery.py` core parser  [DONE]

- `openspec_graph/machinery.py` (new): `MakefileFacts` + `parse_makefile(text)
  -> MakefileFacts`, stdlib-only, no I/O of its own, zero intra-package
  imports.
- `tests/test_machinery.py`: 12 tests, one fixture per behavior (multi-target,
  `.PHONY`/full special-target set, pattern rules excluded per DEC-MP-004,
  `$(VAR)`-expanded target, `ifeq`-guarded conditional union per DEC-MP-002,
  `include` directive, target-specific variable-assignment line, double-colon
  rule, `VAR :=` is not a target, sorted/deduplicated output).
- The non-execution safety test (AC-MP-2) — patches `subprocess.run`/`Popen`
  to raise if called, parses a `$(shell touch <marker>)`-in-target-position
  fixture, asserts no marker file appears — passed on the first run; the
  design's structural-safety reasoning (no exec surface exists to guard)
  held up under an actual executable test.
- `tests/test_decomposition.py`: added `"machinery"` to the stdlib-only-import
  guard, and a new static `test_machinery_never_imports_subprocess` guard
  (belt-and-suspenders — the stdlib-only guard alone would not catch a
  `subprocess` import, since `subprocess` is itself stdlib).

- **Gate:** `make test` green (12/12 new tests, full suite unaffected);
  `make pre-pr` green.

## Milestone 2a — G003 value-comparison + `MAKE_REF` tightening  [DONE]

Separable from the Makefile-parser work (no `machinery.py` dependency, no
untrusted-input handling) — landed independently, as anticipated.

- `parse_semantics.MAKE_REF` tightened to require backtick-fencing (was
  optional both sides — the exact bug that let bare "make sure"/"make
  progress" false-cite a target); every real citation in this repo's own
  fixtures was already backtick-fenced, so this is call-site-preserving
  (AC-MP-6).
- New `parse_semantics.threshold_values(line)` helper, re-exported via
  `parse.py`; `rules_generic._hard_coded_threshold` (G003) now suppresses a
  finding only when exactly one threshold-shaped number is on the line and
  it matches the real configured value — never "value present anywhere,"
  which would wrongly excuse a genuine violation sitting next to an
  unrelated, coincidentally-matching number (AC-MP-5).
- Updated `tests/test_graft.py`'s pre-existing
  `test_g003_fires_on_hard_coded_threshold` (its fixture text coincidentally
  matched this repo's own real coverage floor, so it would have silently
  flipped once the value-comparison landed) and added 3 new tests for the
  suppression, same-line-collision, and bare-"make"-no-longer-trips-G004
  cases.

- **Gate:** `make pre-pr` green; `planlint validate` clean; full suite
  (including `test_decomposition.py`'s `_EXPECTED_HASHES`) unaffected — no
  re-pin needed.

## Milestone 2b — Wire `machinery.py` into `detect.py`  [NOT STARTED]

Depends on Milestone 1.

- `detect._make_targets()` becomes a thin wrapper over
  `machinery.parse_makefile()`; `StackProfile` gains additive-only fields
  for unresolved-target count / confidence, preserving `make_targets`'s
  existing shape (C-MP-1, AC-MP-7).
- `rules_generic._unknown_make_target` (G004) gains the confidence-aware
  fallback (AC-MP-3, AC-MP-4).
- `tests/test_decomposition.py`: add `"machinery"` to the stdlib-only-import
  guard so the existing AC-DG-4-style check picks up the new module
  automatically (do this in Milestone 1's PR, not deferred here — no reason
  to leave the guard blind to the module for an extra PR).

- **Gate:** `make pre-pr` green; `planlint validate` on this repo's own
  specs still clean.

## Milestone 3 — Roadmap doc corrections  [NOT STARTED]

- `docs/differentiation-roadmap.md`: fix the "G002/G001 lesson generalized"
  line (CP-3's actual acceptance criteria are about G003/G004, not
  G001/G002 — a copy-paste-shaped inconsistency in the roadmap's own prose,
  caught while researching this change) and replace the `make -p` cutline
  with the corrected structural-parser-only approach.

- **Gate:** `make docs-check` green.
