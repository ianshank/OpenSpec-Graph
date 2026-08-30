# Milestones

## Milestone 0 — Design + adversarial review  [DONE]

- First pass designed the waiver-ledger/G006/G007 mechanism.
- Second, independent adversarial-review pass found two real, concrete bugs
  in that design before any code was written (DEC-WL-003, DEC-WL-004),
  both resolved in this package's spec.md before implementation began.

## Milestone 1 — Waiver data model (reason + line) + G007  [DONE]

- `openspec_graph/parse_semantics.py`: new `Waiver` dataclass,
  `parse_waivers()`; `suppressions()` refactored to derive from it
  (unchanged signature/behavior).
- `openspec_graph/parse_model.py`: additive `waivers: tuple[Waiver, ...] = ()`
  field on `ParsedSpec`.
- `openspec_graph/parse.py`: `parse_spec()` computes `parse_waivers()` once,
  derives both `suppressed` and `waivers`; re-exports `Waiver`/`parse_waivers`.
- `openspec_graph/rules_generic.py`: new `_unjustified_waiver` check,
  registered as `Rule("G007", ERROR, ("*",), ...)`.
- `openspec_graph/rules.py`: `_NON_WAIVABLE = frozenset({"G007"})` exemption
  in `evaluate()` (DEC-WL-005).
- `tests/test_graft.py`: fixed the one existing test a reason-less waiver
  fixture broke (`test_cli_validate_passes_when_the_only_error_is_waived`);
  9 new tests (fires/doesn't fire, exact two-Finding-set interaction,
  both dialects, self-exemption, multi-rule expansion,
  `suppressions()` regression lock).
- `tests/baseline_rules.json` + `tests/test_decomposition.py::_EXPECTED_HASHES["rules"]`
  regenerated (17 rules; `validate`/`graph` hashes unaffected — confirmed the
  canonical fixture has no waiver comments).
- Docs: README rule table +G007; `docs/next-steps.md`/`docs/agents-skills-harness.md`
  "16 rules" → "17 rules"; CHANGELOG bullet.
- **Gate:** `make pre-pr` green; `planlint validate` clean (15 specs, 0 findings).

## Milestone 2 — G006 orphan invariant  [PENDING]

- `openspec_graph/rules_generic.py`: `orphan_invariant_ids()` (real cross-tree
  logic) + `_orphan_invariant_registry_stub` (inert, for `planlint rules`
  discoverability), registered as `Rule("G006", WARN, ("*",), ...)` before G007.
- `openspec_graph/rule_types.py`: additive `Finding.subject: str = ""` field.
- `openspec_graph/rules.py`: new `evaluate_tree()` sibling to `evaluate()`,
  sets `path=profile.invariant_source` (DEC-WL-004).
- `openspec_graph/cli.py` (`cmd_validate`): skip G006 with an INFO note when
  `--change` is set (DEC-WL-003); call `evaluate_tree()` otherwise.
- `openspec_graph/graph.py`: `build_graph()` accumulates parsed specs, calls
  a new `_add_tree_finding_edges` helper that explicitly creates the
  `invariant:{id}` node before appending the edge, preserving AC-GR-4.
- New tests in `tests/test_graft.py` (fires/doesn't fire/waived/skipped
  under `--change`) and `tests/test_graph.py` (AC-GR-4 holds, node created).
- Golden fixtures regenerated again (18 rules).
- Docs: README +G006 row; rule-count strings → "18 rules"; CHANGELOG bullet.
- **Gate:** `make pre-pr` green; `planlint validate` clean.

## Milestone 3 — `ledger.py` + `waivers` CLI verb (AC-WL-1)  [PENDING]

- `openspec_graph/ledger.py` (new): `LedgerEntry`, `owning_change()`,
  `build_ledger()` — pure aggregation, no file I/O, mirrors `dialect_card.py`'s
  precedent.
- `openspec_graph/cli.py`: new `cmd_waivers` + `p_waivers` subparser
  (`--dialect`, `--format {text,json}`).
- `tests/test_cli_surface.py`: `ALLOWED_VERBS` gains `"waivers"`.
- `tests/test_ledger.py` (new, pure unit tests) + CLI-level tests in
  `tests/test_graft.py`.
- Docs: README CLI verb list + usage example; CHANGELOG bullet; mark every
  AC in this package's own spec.md `[x]`.
- **Gate:** `make pre-pr` green; manual dogfood spot-check:
  `planlint --target . waivers --format json` (expected `[]`).
