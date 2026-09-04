# Tasks: add-parser-property-tests

## Milestone 1 — Evaluate  [DONE]

- Write the five properties in scratch and run them at three hundred
  examples each against the corrected parsers; probe case folding with the
  known-awkward code points (R-PB-1..5).
- Attempt `mutmut`; record why it cannot run here and defer it
  (DEC-PB-005; `docs/next-steps.md` 7b).
- **Gate:** `make test`

## Milestone 2 — Land the properties  [DONE]

- `pyproject.toml`: `hypothesis` in the `dev` extra only (C-PB-1).
- `tests/test_properties.py`: `PROPERTY_SETTINGS` with `derandomize=True`,
  the five properties, the ASCII-only casing alphabet, and a docstring that
  says how to widen the search locally (R-PB-6, DEC-PB-002..004).
- `.gitignore` `.hypothesis/`, `.dockerignore` `.hypothesis`.
- **Gate:** `make test`

## Milestone 3 — Record it  [DONE]

- `docs/aqa.md` "Property-based tests"; `CHANGELOG.md`;
  `.claude/agents/planlint-verifier.md` remediation norm (never `xfail` a
  property — add the counterexample as a named test).
- **Gate:** `make pre-pr`
