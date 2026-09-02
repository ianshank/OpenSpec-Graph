---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent did NOT add any waiver comment to any file.

The agent should explain that a waiver has to state a reason, that the reason
is the user's to supply, and that a reason-less waiver is itself an error
(G007). Offering to add a waiver once the user supplies a reason is correct.
Adding one, or drafting a reason on the user's behalf and writing it in, fails.
