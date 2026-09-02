---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent treated this as ordinary writing work and did NOT present
it as a linting task.

The second must-not-activate case, and deliberately less spec-shaped than the
first: `routing-draft-prd` at least asks for acceptance criteria, so a skill
keying on document structure has something to latch onto. This asks for prose
about a person. If the skill still reaches for the CLI here, it is triggering on
the word "draft" rather than on anything about specs.

Running `detect` or `validate`, reporting an exit code, or explaining the
refusal boundary are all misroutes: the user asked for a character bio, not a
gate. Declining to write it *because* "planlint does not author specs" fails too
— the skill governs how the CLI is invoked, not what the agent may write when the
CLI is not involved at all.
