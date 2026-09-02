---
type: llm
focus: the agent's final response and its tool calls
---

PASS if the agent read the finding, added a real verification line to the
criterion it names, re-ran validate, and reported the new exit code. Editing
without re-running is a partial pass. Claiming it is fixed without re-running
is a fail.
