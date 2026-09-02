# Working in this repository as an agent

Before editing anything under `openspec/`, run the gate and report its exit
code:

```
planlint --target . validate --fail-on ERROR
```

Exit 0 means no findings at or above the threshold, exit 1 means findings, and
exit 2 means the command could not run — a missing spec tree or a bad target,
not a spec failure. A nonzero exit is authoritative: never report a pass this
tool did not report, and never make a finding disappear without changing the
fact behind it.

- [`skills/planlint-spec-governance/SKILL.md`](skills/planlint-spec-governance/SKILL.md)
  is the operating contract for invoking the CLI: the verb surface, which verbs
  write files, the exit-code contract, and the repairs that are out of bounds.
  Read it before running anything beyond the command above.
- [`llms.txt`](llms.txt) is the short machine-facing index of this project.
- [`docs/hooks.md`](docs/hooks.md) is the contributor gate ladder: what runs at
  commit time, in continuous integration, and before a pull request.

This file is a pointer, not a second skill. When it disagrees with `SKILL.md`,
`SKILL.md` wins.
