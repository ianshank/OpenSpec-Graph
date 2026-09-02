# Milestones

## Milestone 0 — Design + adversarial review

- Designed against the real tree rather than against a sketch: every claim in
  the change package was checked against `openspec_graph/` source before
  being written down.
- A first draft was put through a dedicated adversarial review pass before
  any code was written. It found four defects in the draft itself: an ERROR-only
  gate that would have turned `graph-diff` red on a WARN, a false exit-code
  contract, a hand-maintained rule catalog reproducing a drift class this
  repo already guards against, and frontmatter that the existing flat parser
  would have read as a fold marker.
- All four resolved as named decisions, see `DEC-SD-001` through `DEC-SD-009`.

## Milestone 1 — Change package

- This package (`proposal.md`, `tasks.md`, the capability spec) written
  spec-first, before implementation. Every acceptance criterion starts
  unchecked.
- **Gate:** `make validate` is clean against this package, and the spec is
  also clean at the warning level so the graph-diff gate cannot regress.

## Milestone 2 — Exit-code correction

- `_profile()` returns exit 2 for a target path that is not a directory,
  matching the `witness` verb's own boundary validation.
- **Gate:** `make test`

## Milestone 3 — Skill package and manifests

- `skills/planlint-spec-governance/` with SKILL.md, three references, and the
  CI asset; `.claude-plugin/` manifests naming it.
- `tools/render_rule_catalog.py` generates the catalog from the rule
  registry, following the existing package-importing tool pattern.
- **Gate:** `make test`

## Milestone 4 — Contract tests and guard extensions

- `tests/test_skill_contract.py` proves read-only behaviour by full-tree
  hashing, pins the per-verb exit-2 messages, and checks manifest agreement.
- `tests/test_agent_skill_docs.py` extended to cover the new tree.
- `tools/check_docs.py` and `tools/check_no_hardcoded_thresholds.py` widened.
- **Gate:** `make pre-pr`

## Milestone 5 — Packaging and release

- Distribution renamed with a single version source and the metadata a
  package index requires; tag-triggered release workflow using trusted
  publishing, with a clean-environment smoke test of the console script.
- **Gate:** `make pre-pr`

## Milestone 6 — Retrieval scoping and evaluation suite

- `context7.json` scopes agent-facing documentation; `evals/` carries the
  activation and adversarial cases in the plugin-eval layout.
- **Gate:** `make pre-pr`
