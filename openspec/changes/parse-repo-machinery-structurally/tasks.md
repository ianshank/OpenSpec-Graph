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

## Milestone 2b — Wire `machinery.py` into `detect.py`  [DONE]

- `detect._legacy_make_targets(text)` (renamed from `_make_targets(root)`,
  now text-in rather than root-in) is kept, not deleted — it's the R-MP-3
  fallback source. New `detect._make_target_facts(root)` calls
  `machinery.parse_makefile()` and, only when confidence is `"low"`, widens
  the result by unioning with the legacy regex output (never replaces —
  AC-MP-4: a target structural parsing resolved correctly must not be lost
  because something *else* in the file couldn't be resolved).
- `StackProfile` gains additive, defaulted fields
  (`make_target_confidence: str = "high"`, `make_unresolved_count: int =
  0`); `as_dict()` gains the corresponding keys. `make_targets` itself keeps
  its exact `tuple[str, ...]` → `list[str]` shape (AC-MP-7).
- `rules_generic._unknown_make_target` (G004) needed **zero source
  changes** — a one-line comment explains why: the widening happens
  centrally in `detect.py`, so G004, `graph.py`, and `scaffold.pick_stage()`
  all already see the same, already-resolved picture of "what targets
  exist" (AC-MP-3, AC-MP-4).
- `cli.py`'s `cmd_detect` gains an `INFO`-prefixed low-confidence notice,
  matching the existing dialect-mismatch warning's precedent (a plain
  `print()`, not a `Finding` — DEC-MP-003).
- 4 new end-to-end tests in `tests/test_graft.py`; spot-checked
  `planlint detect`/`graph --format json` against this repo's own Makefile
  (high confidence, zero unresolved, `broken_links: 0` — no regression).

- **Gate:** `make pre-pr` green; `planlint validate` clean (10 specs, 0
  findings).

## Milestone 3 — Roadmap doc corrections  [DONE]

- `docs/differentiation-roadmap.md`: fixed the "G002/G001 lesson
  generalized" line (CP-3's actual acceptance criteria are about G003/G004)
  and replaced every `make -p`/`AC-PM-*` reference (the main CP-3 section,
  the risk/cutline table, and the "First Three PRs" summary) with the
  corrected structural-parser-only framing and the real `AC-MP-*` numbering,
  with a banner noting the approved spec is authoritative over this
  historical sketch.

- **Gate:** `make docs-check` green.

---

All four milestones (0, 1, 2a, 2b, 3) are complete. `openspec_graph/machinery.py`
is implemented and wired into `detect.py`; G003/G004/`MAKE_REF` precision
fixes are live; the roadmap doc reflects reality.
