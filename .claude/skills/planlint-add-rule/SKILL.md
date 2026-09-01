---
name: planlint-add-rule
description: Add a new lint rule to planlint (G/H/U/W family) and update every location that must stay in sync with it. Use when adding, renaming, or removing a Rule in openspec_graph/rules_*.py.
---

# Adding a rule to planlint

This repo's own `tests/test_rule_registry_docs.py` exists because this exact drift class recurred three separate times before the guard was added (`README.md`'s table, then `docs/architecture/c4.md` twice, then `rules.py`'s own module docstring). `docs/hooks.md`'s "Adding a custom rule" section does not enumerate all the locations that guard checks, so follow this checklist rather than that doc alone.

## Steps

1. **Determine the shape.** Per-spec rule (most common — a `Rule.check(spec, profile) -> Iterable[str]` function) or whole-tree rule (rare — G006/G009 are the only two today; a whole-tree rule's real logic lives in `rules.evaluate_tree()`, not `Rule.check`, since `Rule.check` has no way to see the full spec tree). Confirm which by reading `openspec_graph/rules.py`'s `evaluate()`/`evaluate_tree()` and an existing rule of the shape you need in `rules_generic.py`/`rules_harness.py`/`rules_upstream.py`/`rules_witness.py`.
2. **Add the `Rule(...)`** to the correct family tuple (`GENERIC_RULES`/`HARNESS_RULES`/`UPSTREAM_RULES`/`WITNESS_RULES`), or the inert-stub + `evaluate_tree()` block pattern for a whole-tree rule. Pick the next free ID in that family's letter+number scheme (`G0xx`/`H0xx`/`U0xx`/`W0xx`).
3. **Regenerate the baseline**: `planlint rules --json > tests/baseline_rules.json`.
4. **Add a deterministic test** for the new rule — a fixture that violates it and an assertion the rule fires on exactly that violation (this repo's own stated test philosophy: "a linter that never fails is a decoration," from `tests/test_graft.py`'s module docstring).
5. **Run `pytest tests/test_rule_registry_docs.py` and fix every failure it reports** — do not guess which docs need touching; let the test tell you. It checks: `README.md`'s rules table, `docs/architecture/c4.md`'s rule count *and* per-family range comments, `docs/agents-skills-harness.md`, `docs/next-steps.md`, `docs/differentiation-roadmap.md`, and `rules.py`'s own module docstring.
6. **Run `make pre-pr`** (or the equivalent direct commands if `make` isn't on `PATH` — the `planlint-verifier` subagent knows the fallback) before considering the rule done.

Do not skip step 5 by hand-editing only the docs you remember — the whole point of this checklist is that the real list is longer than intuition suggests.
