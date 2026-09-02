# Exit codes, per verb

`planlint` returns one of three codes. Read it before reading anything the
command printed.

| Code | Meaning |
|---|---|
| 0 | The command ran and reported nothing at or above the threshold. |
| 1 | The command ran and reported findings at or above `--fail-on`. |
| 2 | The command could not run: a precondition or usage error. |

Exit 1 means findings, and only findings. Exit 2 means the run never got far
enough to have an opinion. Treating a 2 as a spec failure produces a false
report; treating it as a pass produces a worse one.

## Exit 2, by verb

**`validate` and `waivers`, no spec tree.** Both print exactly:

```
no openspec/ directory and no SpecKit specs/ tree; run ``planlint init`` first
```

**`graph`, no spec tree.** A longer message naming both absolute paths it
looked for:

```
no openspec/ directory found at <root>/openspec and no SpecKit specs/ tree found at <root>/specs; run `planlint init` first
```

**`validate --change` or `graph --change`, unknown package.** The value did
not match a change-package directory:

```
no specs found for change 'name'
```

On a SpecKit target the message says so explicitly, because `--change` scopes
OpenSpec change packages and does not apply to a SpecKit `specs/` tree. Re-run
without the flag rather than hunting for a package that was never there:

```
no specs found for change 'name': --change scopes OpenSpec change packages (openspec/changes/<name>/) and this target is a SpecKit specs/ tree; re-run without --change to validate every feature
```

**`validate`, `waivers`, or `graph`, unreadable spec.** A spec path exists but
its bytes cannot be read -- a permission-denied file, a broken mount, a
directory where a file belongs:

```
ERROR cannot read spec <path>: <reason>
```

The path is repository-relative, so the line is identical on two machines that
cloned the same repository to different directories. This is a precondition
failure, not a finding: the run aborts rather than reporting on the specs it
could read, because a spec skipped silently would pass a gate that never saw
it. Do not retry with a narrower `--change` to route around it; fix the file.

**Any verb, bad target.** The `--target` path does not exist or is not a
directory:

```
ERROR target is not a directory: <path>
```

**`graph --format dot`.** Rendering is deliberately out of scope; the message
names the supported format.

**`witness`.** Every boundary check on its own flags exits 2: a target that is
not a directory, a stage name that is not a make-target identifier, a commit
sha that is not exactly forty hexadecimal characters, a coverage value that is
not a finite number between zero and one hundred, and an unwritable witness
store.

**`init` and `new`, unwritable target.** A read-only checkout, a full disk, or
a permission-denied path exits 2 with `ERROR cannot write to <target>`. This is
a precondition failure, not a spec failure -- the same distinction the bad
`--target` case draws, and the reason it is not exit 1.

## The one exit-1 case that is not a finding

`detect --diff <baseline>` exits 1 when the detected conventions have drifted
from the saved baseline. That is the command working as designed: the drift is
the report. A malformed or unreadable baseline file exits 2 instead.

## What to do

- **0**: report the pass.
- **1**: list the findings verbatim, then either repair the spec or hand the
  list back. Never restate a 1 as a pass.
- **2**: report that the command could not run, and why. For a missing spec
  tree, the honest summary is that the tool does not apply to this repository
  yet. Offer `planlint init --dry-run`; run `init` only when asked.
