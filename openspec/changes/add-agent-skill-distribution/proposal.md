# Change: Publish planlint as a distributable Agent Skill (CP-SD)

## Why

`planlint` is a deterministic governance CLI, but the agents that most need
it — coding agents drafting and repairing implementation plans — have no
packaged way to invoke it. Today an agent pointed at this repo has to infer
the verb surface, the exit-code contract, and the read-only boundary from
prose scattered across `README.md` and `docs/`. Inference is exactly the
failure mode this project exists to eliminate.

**Evidence:** a repo-wide search for `skills/`, `.claude-plugin`, `evals/`,
and `context7.json` finds zero footprint outside `.claude/skills/planlint-add-rule/`,
which is this repo's own contributor tooling and is explicitly disambiguated
from the shipped product in `docs/agents-skills-harness.md`. Nothing today
tells a downstream agent that `detect`, `validate`, `graph`, `rules`, and
`waivers` are read-only while `init`, `new`, and `witness` write files.

A first draft of this change was put through adversarial review before any
code was written, and that review found four defects in the draft itself,
each of which would have shipped a false claim or a red CI run:

- The draft's own gate was `validate --fail-on ERROR`, but `graph.py`
  counts every non-witness finding — WARN included — toward `broken_links`,
  and `tools/diff_spec_graph.py` fails the PR when that count rises. A
  package clean at ERROR but carrying one WARN would have turned CI red.
- The draft asserted an exit-code contract in which exit 1 always means
  findings. `_profile()` raises `SystemExit` with a message string when the
  target is not a directory, which exits 1 for every verb except `witness`.
  The documented contract was false as written.
- The draft planned a hand-written rule catalog inside the skill. This repo
  already added `tests/test_rule_registry_docs.py` because that exact drift
  class recurred three times. A hand-maintained catalog would have been a
  fifth unguarded copy.
- The draft's SKILL.md frontmatter used a folded scalar and a nested map,
  which `tests/test_agent_skill_docs.py`'s deliberately flat parser reads as
  a literal `>-` value plus garbage keys, so its own length assertions would
  have passed vacuously.

All four are resolved below as named decisions rather than silently dropped.

## What Changes

- **New `skills/planlint-spec-governance/`**: a SKILL.md stating the verb
  surface, the three-way exit-code contract, the read-only boundary, and the
  repair rules an agent must not cross, plus three references and one CI
  asset. The body delegates every judgement to the CLI's exit code and never
  restates rule logic in prose.
- **New `tools/render_rule_catalog.py`**: generates the skill's rule catalog
  from `rules.RULES`, following `tools/render_mermaid.py`'s existing
  package-importing tool pattern. Staleness fails `make test`.
- **New `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`**:
  make the repo installable as a single plugin whose source is the repo root.
- **`_profile()` exit code corrected**: a target path that is not a directory
  now exits 2, matching the `witness` verb's own boundary-validation
  behaviour and making the documented contract true.
- **`tests/test_agent_skill_docs.py` extended**: covers `skills/**`, parses
  one level of nested frontmatter, and resolves skill-relative references
  from the document's own directory.
- **New `tests/test_skill_contract.py`**: proves the read-only verbs leave a
  target tree byte-identical, pins the per-verb exit-2 messages the skill
  quotes, and checks manifest agreement.
- **`templates/spec-gate.yml` triggers on SpecKit trees too**, closing a gap
  where a repo using the SpecKit dialect never ran the gate at all.
- **Packaging**: the distribution is renamed to `planlint` with a single
  version source, gains the metadata PyPI requires, and gets a tag-triggered
  release workflow using trusted publishing.
- **New `context7.json` and `evals/`**: retrieval scoping for agent-facing
  docs, and an adversarial eval suite in the plugin-eval layout.

## Non-Goals

- **No reimplementation of rule logic in skill prose.** The skill runs the
  CLI and reports its exit code. Any catalog it carries is generated.
- **No copy of the skill under `.claude/skills/`.** That directory is this
  repo's own contributor tooling; a repo-root skill is not auto-loaded by
  design, and the skill's audience is downstream repositories.
- **No wrapper script around the CLI.** A wrapper adds a second exit-code
  surface, assumes an interpreter on PATH, and reopens the Windows path
  handling closed by the stdout-encoding change.
- **No new runtime dependency.** `dependencies` stays empty; the frontmatter
  and manifest checks are stdlib parsing, matching the existing doc guard.
- **No new CLI verb, and no authoring surface.** The closed verb set is
  unchanged; the skill may repair an existing spec but never writes a waiver,
  a witness, or a spec from nothing.
- **No agent-authored waivers.** A waiver states a claim that must justify
  itself; the reason is the user's to supply.
- **No tool wrapper published to a third-party model hub in this change.** A
  subprocess wrapper carries its own release cadence and would ship untested.

## Affected Capabilities

- `agent-skill-distribution`
