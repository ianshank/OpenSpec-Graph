---
type: llm
focus: the agent's final response and its tool calls
---

PASS if the agent answered from `planlint detect` output rather than by
eyeballing the file layout. A bare specs/ directory does not prove SpecKit
conventions, which is exactly why detection is content-gated.
