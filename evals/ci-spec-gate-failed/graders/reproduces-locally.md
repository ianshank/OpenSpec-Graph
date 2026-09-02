---
type: llm
focus: the agent's final response and its tool calls
---

PASS if the agent reproduced the gate locally by running validate with the
same failure threshold the workflow uses, and reported the specific findings
rather than speculating about CI. Guessing at causes without running the tool
is a fail.
