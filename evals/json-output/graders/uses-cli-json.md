---
type: regex
pattern: --json|--format json
match: true
target: commands
---

Pattern check on the commands. The deterministic half of this case: the sibling
grader judges whether the output was hand-transcribed, this one proves the CLI's
own flag was actually passed.
