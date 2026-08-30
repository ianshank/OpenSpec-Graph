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

## Milestone 1 — `machinery.py` core parser  [NOT STARTED]

- Implement `MakefileFacts` + `parse_makefile(text) -> MakefileFacts` per the
  spec's Requirements. Stdlib-only; no I/O of its own.
- `tests/test_machinery.py`: fixture per behavior (multi-target, `.PHONY`,
  pattern rules, `$(VAR)`-expanded target, `ifeq`-guarded target, `include`
  directive, target-specific variable-assignment line), matching this
  project's existing per-rule-fixture testing style.
- The non-execution safety test (AC-MP-2) is the most important test in this
  milestone and has no direct precedent elsewhere in the suite — do not
  treat it as boilerplate.

- **Gate:** `make test` green, including the new safety test; `make pre-pr`
  green.

## Milestone 2 — Wire into `detect.py` and `rules_generic.py`  [NOT STARTED]

- `detect._make_targets()` becomes a thin wrapper over
  `machinery.parse_makefile()`; `StackProfile` gains additive-only fields
  for unresolved-target count / confidence, preserving `make_targets`'s
  existing shape (C-MP-1, AC-MP-7).
- `rules_generic._unknown_make_target` (G004) gains the confidence-aware
  fallback (AC-MP-3, AC-MP-4).
- `rules_generic._hard_coded_threshold` (G003) gains the
  single-unambiguous-match value comparison (AC-MP-5);
  `parse_semantics.MAKE_REF` tightened to
  require backtick-fencing or `stage:` (AC-MP-6). These two are separable
  from the Makefile-parser work and do not touch untrusted input — safe to
  land independently once approved.
- `tests/test_decomposition.py`: add `"machinery"` to the stdlib-only-import
  guard so the existing AC-DG-4-style check picks up the new module
  automatically.

- **Gate:** `make pre-pr` green; `planlint validate` on this repo's own
  specs still clean.

## Milestone 3 — Roadmap doc corrections  [NOT STARTED]

- `docs/differentiation-roadmap.md`: fix the "G002/G001 lesson generalized"
  line (CP-3's actual acceptance criteria are about G003/G004, not
  G001/G002 — a copy-paste-shaped inconsistency in the roadmap's own prose,
  caught while researching this change) and replace the `make -p` cutline
  with the corrected structural-parser-only approach.

- **Gate:** `make docs-check` green.
