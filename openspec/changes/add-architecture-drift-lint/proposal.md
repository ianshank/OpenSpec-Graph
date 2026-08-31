# Change: Add Architecture Drift Lint (CP-AD)

## Why

`planlint` already catches one class of citation drift — a spec that cites an
`INV-n` not declared anywhere (G005), or a declared invariant no living spec
cites (G006). Nothing today extends that same discipline to architecture
decision records (ADRs). A spec that says "see ADR-7" when no such decision
exists, or a repo's `docs/adr/` that has quietly outgrown what any spec still
references, goes unchecked.

**Evidence:** a repo-wide grep for `ADR`/`operationId`/`event.?schema` finds
zero existing citation convention anywhere in this codebase — this is
genuinely new territory, with G005/G006 as the only proven template to mirror.

This proposal's original motivation (`docs/architecture/c4.md` stating a stale
rule count/range) has itself already been fixed, twice, by prior commits on
this branch. A fresh investigation before this design began found the
*identical* drift class alive elsewhere instead: `openspec_graph/rules.py`'s
own module docstring still says "universal rules G001-G005" (really
G001-G009 after this change) — the third independent recurrence of this exact
defect shape in this codebase's history. That recurrence is the real evidence
motivating both this change's ADR-citation rules and its own doc-drift guard
(below) — not the original, now-resolved c4.md claim.

This proposal went through an adversarial review round before implementation
(mirroring this project's established discipline for higher-risk or
open-ended work). The review found the original four-artifact-kind sketch
(ADR + OpenAPI + event schema + a C4 doc-freshness rule pair) overscoped for
one round, and one proposed module-split heuristic unsupported by any real
precedent in this codebase. Both are resolved in What Changes / Non-Goals
below, and in the Decisions section of this capability's spec.

## What Changes

- **New rules `G008`/`G009`** (both WARN): `G008` — a spec cites an ADR id
  not declared in the detected ADR source. `G009` — a declared ADR cited by
  no living spec anywhere, and not waived. Mirrors G005/G006 exactly.
- **ADR discovery** in `detect.py`: a new `_adrs(root)` function, trying a
  fixed, most-specific-first list of candidate paths (`docs/adr`,
  `docs/architecture/decisions`, `docs/decisions`, `adr`, `docs/ADR.md`).
  Unlike the single-file `_invariants()` template, this supports *either* a
  directory of per-decision files or a single index file, matching real-world
  ADR practice. Ids are extracted by scanning each candidate's own text, never
  parsed from filenames (a zero-padded filename and a spec's bare citation
  would otherwise silently mismatch).
- **New `ParsedSpec.adr_refs`** field and `ADR_REF` regex (`parse_semantics.py`),
  populated in `parse_spec()` exactly like `invariant_refs`/`INV_REF`.
- **`graph.py` gains its first new node type since the original five: `adr`**
  — reusing the existing `declares` edge type. An orphaned ADR gets graph
  representation the same way an orphaned invariant already does.
- **A new doc-drift guard**: `tests/test_rule_registry_docs.py` asserts every
  prose claim about the rule count/family ranges (README's table, `c4.md`,
  `docs/agents-skills-harness.md`, `docs/next-steps.md`, and `rules.py`'s own
  module docstring) against `rules.RULES` itself — the real source of truth —
  rather than a hand-maintained number. Closes the live `rules.py:6` drift
  found during this design as part of the same commit.

## Non-Goals

- **No OpenAPI operationId or event-schema id citation-checking, and no rule
  idents reserved for either.** Both need their own "Track 2" external-repo
  validation of their discovery-source convention before any candidate-path
  list is locked in — the same treatment this project already gave the
  Makefile-target and invariant-source heuristics — and OpenAPI documents are
  overwhelmingly YAML in real repos, which this zero-dependency project has
  no parser for. Each becomes its own future, separately-reviewed change.
- **No C4 (or any other architecture-doc) freshness rule pair.** The original
  sketch's heaviest piece — a new rule module, two new rules, new
  `StackProfile` fields, an explicit AC-GR-4-exclusion decision — is no
  longer justified: its only concrete motivation is fixed, and the live
  instance of that drift class is fully addressed by the doc-drift guard
  above. Building a rule-pair subsystem to catch what one test already
  catches would be the exact over-engineering a related, already-shipped
  change (`fix-adopter-artifact-drift`) explicitly declined to do.
- **No new CLI verb.** Folds entirely into the existing `validate`/`graph`
  rule pipeline; the closed verb set (`tests/test_cli_surface.py::ALLOWED_VERBS`)
  is unrevised.
- **No new `openspec_graph/*.py` rule module.** G008/G009 stay in
  `rules_generic.py` — see this capability's spec for why the "new
  StackProfile fields imply a new module" heuristic doesn't actually apply.
- **No `evaluate_tree()` generalization.** A second parallel block, mirroring
  G006's existing shape, not a registry — two instances doesn't justify one,
  and this project has separately decided against a dynamic rule-dispatch
  mechanism for a related reason (`DEC-PR-002`).
- **No new `tools/` script or Makefile target for the doc-drift guard** — a
  single pytest test is the cheaper form `fix-adopter-artifact-drift`'s own
  Non-Goals already pre-authorized once recurrence was demonstrated.

## Affected Capabilities

- `architecture-drift-lint`
