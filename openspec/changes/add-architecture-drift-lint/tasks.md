# Milestones

## Milestone 0 — Design + adversarial review [DONE]

- Designed via a fresh Explore (2 parallel agents) + Plan pass, specifically
  because the original sketch's motivating problem (`c4.md` doc drift) had
  gone stale — already fixed twice on this branch — and needed re-grounding
  in current evidence rather than being carried over unexamined.
- Found the live recurrence of the same drift class (`rules.py:6`'s own
  module docstring) that now motivates this change instead, and one proposed
  module-split heuristic with no real precedent in this codebase (rejected;
  see `DEC-AD-008`).
- Cut the original four-artifact-kind sketch (ADR + OpenAPI + event schema +
  a C4 rule pair) down to ADR-only this round, with a lightweight doc-drift
  test replacing the C4 rule pair entirely — both resolved as named
  decisions in the spec, not silently dropped.

## Milestone 1 — Data model + discovery

- New `openspec_graph/parse_semantics.py::ADR_REF` regex, `ParsedSpec.adr_refs`
  field (additive/defaulted, `DEC-AD-001`), wired in `parse.py::parse_spec()`.
- New `openspec_graph/detect.py::_adrs()` + `ADR_SOURCES`, supporting both a
  directory-of-files and single-index-file discovery shape (`DEC-AD-002`).
  `StackProfile` gains `adr_source`/`adr_ids` + `adr_source_name` property.
- `dialect_card._COMPARABLE_FIELDS` gains the two new fields, so
  `detect --diff` doesn't go blind to them.
- **Gate:** `make pre-pr` green; new tests for extraction, both discovery
  shapes, empty-repo fallback, the zero-padding-mismatch regression, and a
  dialect-card diff round-trip.

## Milestone 2 — G008/G009 + `evaluate_tree()` + `--change` wiring

- `rules_generic.py`: `_unknown_adr` (G008), `orphan_adr_ids` +
  `_orphan_adr_registry_stub` (G009), both added to `GENERIC_RULES`. Module
  docstring fixed to `G001-G009`.
- `rules.py::evaluate_tree()` gains a parallel G009 block, identical shape to
  the existing G006 block (`DEC-AD-003`). Module docstring's stale
  `G001-G005` claim fixed — the live drift this change's Problem Statement
  is grounded in.
- `cli.py`: `cmd_validate`/`cmd_graph`'s `--change` blocks each gain one
  additive G009 `INFO` line, alongside the existing G006 ones (`DEC-AD-004`).
- **Gate:** `make pre-pr` green; tests mirroring G005/G006's existing shapes
  1:1. `tests/baseline_rules.json` regenerated (20 rules);
  `test_decomposition.py::_EXPECTED_HASHES["rules"]` regenerated.

## Milestone 3 — Graph representation

- `graph.py`: new `_add_adr_edges()` (mirrors `_add_invariant_edges()`);
  `_add_tree_finding_edges()` becomes rule-aware via a 2-entry
  `{rule: node_kind}` dispatch table instead of a hardcoded type
  (`DEC-AD-005`) — existing G006 tests must keep passing unmodified, proving
  the refactor is behavior-preserving. New `adr_source` key on
  `build_graph()`'s return dict. Module docstring's node/edge-type list
  updated.
- `mermaid.py`: no production changes — one new regression test proves an
  `adr:*` orphan node renders with the same styling as any other orphan type
  through the existing generic logic.
- **Gate:** `make pre-pr` green; `_EXPECTED_HASHES["graph"]` regenerated (a
  new `adr_source: null` key changes the hash on the canonical fixture —
  expected, not a regression).

## Milestone 4 — Doc-drift guard + fix the live drift + doc sync

- New `tests/test_rule_registry_docs.py`: computes ground truth once from
  `rules.RULES`, checks it against README's rules table, `c4.md`'s count and
  per-family range comments, `docs/agents-skills-harness.md`,
  `docs/next-steps.md` (×2), and `rules.py`'s own module docstring.
  `CHANGELOG.md` deliberately excluded (`DEC-AD-006`).
- Same commit: fixes the `rules.py:6` live drift and syncs every doc's
  count/ranges so the new guard lands green, not red.
- **Gate:** `make pre-pr` green; the new test file passes against the
  now-corrected docs.

## Milestone 5 — Change package + roadmap section + full verification

- This change package (`proposal.md`, `tasks.md`, this `spec.md`) with all
  15 ACs flipped to `[x]` as each is actually implemented and verified — not
  written retroactively as already-true.
- `docs/differentiation-roadmap.md` gains a proper `add-architecture-drift-lint`
  section (mirroring how CP-GV got its own late addition), replacing the
  current bare blockquote mention.
- **Gate:** full `make pre-pr`; dogfood spot-check
  (`planlint --target . validate`/`graph --format json` against this repo's
  own tree — expected clean/inert, since this repo has no `docs/adr/` of its
  own; that silence is a correct proof point, not a gap). Pushed as a new PR.
