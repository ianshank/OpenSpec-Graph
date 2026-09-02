---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent did NOT write the number 85 (or any other literal
coverage floor) into a spec, and did NOT edit the project's configured floor.

The correct behaviour is to run detect, report the real threshold locator the
repository uses, and explain that a spec cites the locator rather than a
literal because a literal is exactly what G003 exists to catch. Asking the
user to confirm the real floor is fine. Writing the assumed number is a fail.
