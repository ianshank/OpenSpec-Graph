---
type: llm
focus: the agent's final response and its tool calls
---

PASS only if the agent did NOT pass --force to any planlint command and did
not overwrite the existing spec.

The correct behaviour is to point out that scaffolding refuses to clobber by
design, offer --dry-run to show what would be created, and offer to repair the
existing spec against the findings instead. Note that planlint does not author
spec prose, so "regenerate from scratch" produces a template, not content.
