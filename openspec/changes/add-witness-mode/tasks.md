# Milestones

## Milestone 0 — Design + two adversarial review rounds [DONE]

- Designed via a fresh 3-agent Explore pass + 1 Plan agent pass against the
  committed roadmap sketch (`docs/differentiation-roadmap.md`'s `CP-7`
  section), specifically because that sketch's own CLI syntax, touch map, and
  "signed" claim didn't survive contact with the real codebase.
- A first draft was itself put through a dedicated adversarial peer review
  (2 independent reviewers) before any code was written — found a real
  HIGH-severity bug introduced during that first draft (a short-sha
  comparison that would silently defeat freshness checking for abbreviated
  commit shas), plus a wider set of gaps: a pre-existing `verified_by`
  waiver-comment leak with asymmetric, dialect-dependent exposure; no stated
  CI-topology/cross-job usage story; a non-atomic witness write; a
  clock-skew-sensitive tie-break; an unbounded "guess the real citation"
  risk for multi-stage GWT scenarios; and a cherry-picked justification for
  a new rule module that didn't actually engage the prior decision
  (`DEC-AD-008`) it needed to.
- All findings resolved as named decisions below, not silently dropped —
  see `DEC-WM-001` through `DEC-WM-020`.

## Milestone 1 — Change package [DONE]

- This change package (`proposal.md`, `tasks.md`, this `spec.md`) written
  spec-first, before implementation. Every AC starts unchecked.
- **Gate:** `planlint validate` against this package's own draft spec is
  clean (self-dogfooding the same discipline this project applies to every
  target repo).

## Milestone 2 — Prerequisite: fix the `verified_by` waiver-comment leak [DONE]

- `parse_harness.py`/`parse_upstream.py`: `Criterion.verified_by` built from
  waiver-comment-stripped text, matching the spec-wide `make_refs`/
  `invariant_refs`/`adr_refs` fields' existing discipline.
- Landed and tested *before* any witness-consuming rule exists, so W001/W002
  are never developed against a codebase with this gap open.
- **Gate:** `make pre-pr` green; new regression tests for both dialects.

## Milestone 3 — Data model [DONE]

- New `openspec_graph/witness.py`: `Witness` schema, atomic `write_witness()`
  (temp file + `os.rename()`), `load_witnesses()` (schema-version +
  finiteness checks, fail-closed on any malformed/hash-mismatched file),
  `matching_witnesses()`.
- `detect.py`: `_current_sha()` (the sole new subprocess call site, lazy —
  only when at least one witness exists), `StackProfile.witnesses`/
  `current_sha` fields (additive, tail-appended). `.gitignore` gains
  `.planlint/`.
- **Gate:** `make pre-pr` green; `tests/test_witness.py` (new), detect-level
  tests, `test_decomposition.py::_NEW_MODULES += "witness"`, a new static
  guard proving `detect.py` is the only module importing `subprocess`.

## Milestone 4 — Rules + CLI wiring [DONE]

- New `openspec_graph/rules_witness.py`: `W001`/`W002`, staged diagnostic
  messages, an explicit `profile.threshold is None` guard on W002.
- `rules.py`: `WITNESS_RULES`/`NON_WITNESS_RULES`, `evaluate(rule_set=...)`.
- `cli.py`: `cmd_witness` (full boundary validation — full-length sha,
  finite coverage, valid stage identifier, a clean exit-2 message on an
  unwritable `.planlint/`), new `witness` subparser, `--require-witness` on
  `validate`.
- `graph.py`: one-line change at its single `rules.evaluate()` call site.
- **Gate:** `make pre-pr` green; `tests/test_cli_surface.py::ALLOWED_VERBS`
  and `test_decomposition.py::_NEW_MODULES` updated; `tests/baseline_rules.json`
  and `test_decomposition.py::_EXPECTED_HASHES["rules"]` regenerated; `"validate"`/
  `"graph"` hashes confirmed unchanged (empirically, not assumed) against the
  canonical fixture, which never passes `--require-witness`.

## Milestone 5 — Doc-drift guard + doc sync [DONE]

- `tests/test_rule_registry_docs.py`: `_FAMILIES` gains `("W", "rules_witness")`;
  README-table regex widened to also match `W\d{3}`.
- README, `c4.md`, `next-steps.md`, `agents-skills-harness.md`,
  `differentiation-roadmap.md`: rule count 20 → 22 everywhere; `rules.py`
  module docstring updated.
- **Gate:** `make pre-pr` green; the doc-drift guard passes against the
  now-corrected docs.

## Milestone 6 — Roadmap section + close out package + full verification [DONE]

- `docs/differentiation-roadmap.md`'s `CP-7` sketch replaced with an
  "implemented" writeup (mirroring how CP-AD got its own late addition
  there).
- This change package's ACs flipped to `[x]` as each is actually
  implemented and verified — not written retroactively as already-true.
- `CHANGELOG.md` entry.
- **Gate:** full `make pre-pr`; dogfood spot-check —
  `planlint --target . validate --require-witness` against this repo's own
  tree **fails closed** as expected (this repo has no
  `.planlint/witnesses/` of its own; 160 `W001` findings, exit 1 — a
  correct proof point for `AC-WM-9`, not a gap). This branch's own
  designated PR (#13, CP-AD) merged mid-implementation; the 6 CP-WM
  commits were rebuilt on fresh `main` per the branch's merged-PR recovery
  protocol (cherry-picked cleanly, zero conflicts) and pushed as
  [PR #14](https://github.com/ianshank/planlint/pull/14).
