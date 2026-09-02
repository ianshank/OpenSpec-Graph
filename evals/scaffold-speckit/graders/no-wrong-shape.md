---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent explained that `planlint new` scaffolds only the
harness and upstream dialects, and did NOT generate a package in the wrong
shape or pass a speckit value to --dialect.

Offering to validate the repo's existing SpecKit specs instead is the right
follow-up.
