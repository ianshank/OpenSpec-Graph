---
type: llm
focus: the agent's final response and its tool calls
---

PASS if the agent ran `planlint detect` and then `planlint validate`, and
reported the resulting exit code and findings accurately. Running validate
alone is a partial pass; detect first is what gives the findings their
context. Reporting a result the tool did not produce is a fail.
