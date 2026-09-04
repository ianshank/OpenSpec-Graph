# Change: Property-based tests over the parsers that read untrusted text (CP-PB)

## Why

Coverage floors prove a line executes; a fixture proves a parser handles the
input somebody thought of. Neither says what a parser does on input nobody
wrote down, and the parsers here read text out of a repository planlint does
not own. The BOM defect closed by `fix-detect-corpus-defects` is the
demonstration: seven hundred example tests executed `parse_makefile` and not
one of them fed it a byte-order mark.

**Evidence:** `docs/eval-corpus-plan.md` appendix C records the evaluation.
Five Hypothesis properties, each run over three hundred generated examples,
all pass in under three seconds against the corrected parsers; a targeted
case-folding probe (dotless ı, the Kelvin sign, long s, full-width and
ligature forms) found no hole because `re.IGNORECASE` already folds them.
Mutation testing was evaluated in the same session and is deliberately not
adopted here (see Non-Goals).

## What Changes

- `pyproject.toml`: `hypothesis` joins the `dev` extra. `[project]
  dependencies` stays empty; a property test is contributor and CI tooling,
  never something an adopter installing the CLI carries.
- New `tests/test_properties.py`: five properties, `derandomize=True`,
  stating invariants the code already claims — `parse_makefile` is
  deterministic with sorted, unique targets; `parse_makefile` never raises on
  arbitrary text including BOM, NUL, CRLF and the line separators
  `splitlines()` honours; `strip_define_blocks` is idempotent; the upstream
  parser's requirement count is independent of heading depth;
  `Criterion.is_negative` is invariant under printable-ASCII casing and
  surrounding whitespace.
- `.gitignore`: `.hypothesis/`. `.dockerignore`: `.hypothesis`.
- `docs/aqa.md` "Property-based tests"; `docs/next-steps.md` item 7b records
  the mutation-testing decision.

## Non-Goals

- No mutation testing. `mutmut` was tried and the run was cancelled before it
  produced a single kill/survive count; what the attempt established is that
  it cannot run against this repository without deselecting two of the
  repository's own self-checks (`test_new_modules_stdlib_only` rejects its
  injected trampoline import; `test_typecheck_passes_on_clean_repo` fails
  under the mutants tree). Adopting it is its own change package with a real
  measurement, and any score floor it introduces goes in `pyproject.toml`.
- No randomised exploration in CI. A gate that fails one run in fifty gets
  overridden and then deleted; `derandomize=True` fixes the example stream
  per interpreter, and `--hypothesis-seed=random` is the documented local way
  to widen the search. A counterexample found that way becomes a named
  regression test, the way the four documented linter faults did.
- No Unicode casing promise. A few letters case-map to more than one code
  point under Python's own rules (U+0130 lowercases to two); that is not a
  matcher property, so the casing invariant is stated over printable ASCII.

## Affected Capabilities

parser-property-tests
