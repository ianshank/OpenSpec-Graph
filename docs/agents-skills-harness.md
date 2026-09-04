# Agents, Skills, and the Harness Model

This document is about `planlint`'s own product architecture — what the tool
*is*. It is unrelated to `.claude/agents/` and `.claude/skills/` (Claude Code
dev-tooling used to *develop* planlint itself — spec-drafter, spec-adversary,
planlint-verifier, and the `planlint-add-rule` / `planlint-add-eval-case` /
`planlint-add-detect-shape` / `planlint-add-phrasing-case` skills; see docs/hooks.md's
"Claude Code hooks" section): same word, three different meanings — one about
the shipped CLI's rules, one about this repo's own contributor workflow, and
one about the distributable Agent Skill under `skills/` (see "A third
meaning", below).

`planlint` is deliberately **not** an autonomous agent. There is no LLM in the
loop, no tool selection, no planning step. What it provides is a deterministic
**governance harness** with a set of mechanical **skills** (rules) that turn
spec conventions into CI gates. This document defines those terms in-repo so
they are not confused with autonomous-agent abstractions.

## Definitions

- **Harness** — `cli.py` + the `tools/` gate scripts. It pins the working
  directory, reads config, runs the rules, and returns a pass/fail exit code.
  The harness *contains* work; it does not *decide* what to do.
- **Skill** — a single `Rule` in `rules.py`: a pure, deterministic function
  `(ParsedSpec, StackProfile) -> Iterable[str]`. Each skill encodes one spec
  convention (e.g. G002: every spec names a non-success outcome). Skills are
  registered, not invoked dynamically; there is no routing. Two skills
  (G006, G009) are whole-tree properties no per-spec function can express —
  their `Rule.check` is an inert registry stub (so they still list in
  `planlint rules`) and their real logic lives in `rules.evaluate_tree()`
  instead, called once per run over every parsed spec (see below).
- **Agent** — *not present in this repo.* (The Agent Skill under `skills/`
  is a document written *for* someone else's agent; it is not an agent this
  repo contains or runs.) An agent (in the broader Mango
  sense) would propose work; here, the harness only *evaluates* proposed work
  (specs) and reports. Cognitive/proposal logic is out of scope and stays
  outside `planlint` by design (INV-16 analogue: the harness disposes, it does
  not propose).

## A third meaning: the distributable Agent Skill

Since the `add-agent-skill-distribution` change there is a third thing in this
repo called a "skill", and it is neither of the two above:
`skills/planlint-spec-governance/` is an **Agent Skill** in the open
SKILL.md format — a document a coding agent installs so it knows how to *run*
this CLI. It is product, shipped to other people's repositories, unlike
`.claude/skills/` (contributor tooling for developing planlint itself).

The three senses, disambiguated once:

| Term | What it is | Where |
|---|---|---|
| Skill (this document) | One `Rule` — a pure, deterministic check | `openspec_graph/rules*.py` |
| Skill (contributor tooling) | A checklist Claude Code follows when working on this repo | `.claude/skills/` |
| Agent Skill (product) | A document telling any agent how to invoke the CLI | `skills/` |
| Agent entry point | A pointer an agent loads unprompted, on arriving in this repo | `AGENTS.md` |

The fourth is the newest and the thinnest on purpose. `AGENTS.md` exists
because agents read a file by that name at the repository root whether or not
anyone tells them to, so the question is not whether it is consulted but
whether it says the right thing. It names the gate command and defers to
`skills/planlint-spec-governance/SKILL.md` for everything else; it deliberately
does not restate the verb surface, the exit codes, or the refusal boundary,
because a second copy of those is a second thing to keep true.

One non-obvious consequence of the name: `AGENTS.md` is also the last entry in
`detect.INVARIANT_SOURCES`, so for a target repository with no dedicated
contract file it is where planlint looks for `INV-n` declarations. Writing an
invariant id into *this* repository's `AGENTS.md` would therefore make
planlint's own self-validation adopt it as the invariant source. A test forbids
that (`test_agents_md_declares_no_invariant_ids`).

The product skill deliberately contains no rule logic. It names verbs, exit
codes, and a boundary; its rule catalog is generated from the registry by
`make skill-catalog` rather than written by hand, so the deterministic harness
stays the only place a rule is defined.

## Why not autonomous agents

The whole point of a governance CLI is **reproducibility**: the same spec tree
must produce the same findings, every time, on every machine. That is
incompatible with non-deterministic planning. The 26 rules are the "skills" —
fixed, auditable, and byte-stable in their output (AC-EH-4). Waivers are
explicit inline comments (`<!-- specgraph:allow G003 reason -->`) that downgrade
a finding to INFO but keep it visible — a suppression is never silent.

## How the pieces compose

```text
  spec.md  ──parse──▶  ParsedSpec  ──rules.evaluate──▶  Finding[]
                            │                              │
                            └──rules.evaluate_tree─────────┤   (G006/G009 only;
                               (once, over every spec)      │    whole-tree)
                                                             │
                                          graph.build_graph (pure projection)
                                                          │
                                              nodes / edges / broken_links
```

`detect` tells the harness *what* the target repo does (Makefile targets,
coverage locator, dialect); `parse` turns prose into structured data; the
**skills** (rules) evaluate it; the **harness** (CLI + tools) reports and
gates. Adding a skill is a one-function, one-test change (see
`docs/hooks.md`).

Makefile target detection is itself a small illustration of "disposes, does
not propose": `machinery.py` structurally *reads* a target repo's Makefile
text and reports what it found — it never executes anything, not even the
target repo's own `make`, at any confidence level. Where structural
parsing can't confidently resolve a target, it says so (a low-confidence
signal) and falls back to the pre-existing detection, rather than guessing
or acting on the target repo's behalf.

## Determinism contract

The skills are deterministic by construction: rules iterate in a fixed tuple
order, findings are appended in that order, and JSON output preserves it.
`tests/test_enterprise.py` asserts byte-identical re-evaluation so a future
refactor that introduces unordered iteration fails the gate. This is the
enterprise-grade guarantee: a spec review is an auditable artifact, not an
opinion.
