# Change: Fix `init` Snapshot Wording

## Why

`planlint init` writes `openspec/specgraph.json` and `project.md`, but the
generated content and the CLI's own help text describe them as something
that "pins" or is "authoritative" for detected conventions. Confirmed by
grep across `detect.py`/`cli.py`/`scaffold.py`: nothing ever reads either
file back. `detect.profile()` always re-derives every convention fresh
from the filesystem, on every `detect`/`validate` run — which is the
correct, intentional behavior. A hand-editable file whose contents can
silently drift from what a repo actually does is exactly the class of
stale-cached-belief bug this project exists to catch in *target* repos;
having `planlint`'s own output file overclaim the same kind of authority
over its own behavior would be the same bug turned inward.

**Evidence:** `scaffold.py`'s generated `project.md` told every scaffolded
target repo "this file is authoritative," and `scaffold.py`/`cli.py`'s
docstrings and help text both said `init` "pins" conventions — none of
which matches what the code actually does.

## What Changes

Wording only, zero behavior change:

- `openspec_graph/scaffold.py`: `plan_init`'s docstring and the generated
  `project.md` content now describe the file as a snapshot for humans, not
  a live config — explicit that `detect` always re-derives fresh rather
  than reading it back, and that editing it corrects the record but does
  not change enforcement.
- `openspec_graph/cli.py`: the module docstring's verb table and the
  `init` subparser's `--help` text both changed from "pin(s/ning)
  detected conventions" to "write a snapshot of detected conventions."
- `README.md`: the matching inline comment on the `init` usage example.

## Non-Goals

- No change to `specgraph.json`'s JSON schema — it carries no misleading
  prose today (it's pure data), so there's nothing to correct there.
- No read-back/override feature. Considered and explicitly rejected:
  detect always re-deriving from real filesystem state is the safer,
  philosophically-consistent choice, matching how this project already
  treats a target repo's own possibly-stale cached beliefs.
- No change to the "stable contract identifiers" language elsewhere in the
  docs (e.g. the `rename-cli-and-positioning` package's Non-Goals) — that
  is a claim about the *name* `specgraph.json` staying stable across the
  `specgraph`→`planlint` rename, not a claim about persistence/override
  *behavior*. Different claim, already accurate, left alone.

## Affected Capabilities

- `detected-conventions-snapshot`
