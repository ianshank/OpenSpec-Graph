---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent treated this as ordinary authoring work and did NOT
present it as a linting task.

This is the must-not-activate case. `planlint` evaluates plans; it does not
author them, and there is no spec tree here to evaluate. An agent that runs
`detect` or `validate`, reports an exit code, or explains the skill's refusal
boundary has misrouted: the user asked for a document, not a gate. Declining to
write the document because "planlint does not author specs" is also a failure —
the skill governs how the CLI is invoked, not what the agent is allowed to write
when the CLI is not involved.
