# Agents, Skills, and the Harness Model

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
  registered, not invoked dynamically; there is no routing.
- **Agent** — *not present in this repo.* An agent (in the broader Mango
  sense) would propose work; here, the harness only *evaluates* proposed work
  (specs) and reports. Cognitive/proposal logic is out of scope and stays
  outside `planlint` by design (INV-16 analogue: the harness disposes, it does
  not propose).

## Why not autonomous agents

The whole point of a governance CLI is **reproducibility**: the same spec tree
must produce the same findings, every time, on every machine. That is
incompatible with non-deterministic planning. The 16 rules are the "skills" —
fixed, auditable, and byte-stable in their output (AC-EH-4). Waivers are
explicit inline comments (`<!-- specgraph:allow G003 reason -->`) that downgrade
a finding to INFO but keep it visible — a suppression is never silent.

## How the pieces compose

```text
  spec.md  ──parse──▶  ParsedSpec  ──rules.evaluate──▶  Finding[]
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

## Determinism contract

The skills are deterministic by construction: rules iterate in a fixed tuple
order, findings are appended in that order, and JSON output preserves it.
`tests/test_enterprise.py` asserts byte-identical re-evaluation so a future
refactor that introduces unordered iteration fails the gate. This is the
enterprise-grade guarantee: a spec review is an auditable artifact, not an
opinion.
