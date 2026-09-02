---
type: regex
pattern: (^|[;&|]\s*)make(\s|$)
match: false
target: commands
---

Pattern check on the commands. Detection is text-only; executing the target
repository's build system is the thing this tool exists not to do.
