# Change: Fix Unreadable Spec Exit Code

## Why

A spec path that exists but whose bytes cannot be read crashes every verb
that parses specs. `parse.parse_spec` reads with a bare
`path.read_text(encoding="utf-8", errors="replace")` and no guard, and three
callers invoke it unguarded: `cli.cmd_validate`, `cli.cmd_waivers`, and
`graph.build_graph` (whose `for path in all_spec_files:` loop parses the
whole tree before rendering anything). The `OSError` escapes as a traceback
and the process exits **1** — the code
`skills/planlint-spec-governance/references/exit-codes.md` reserves, in its
own words, for "findings at or above `--fail-on`", stating flatly that "exit
1 means findings, and only findings." A broken mount, a permission-denied
checkout, or a path of the wrong file type is a precondition failure: exit 2,
"the command could not run."

**Evidence:** reproduced directly — a *directory* named `spec.md` at
`openspec/changes/<name>/specs/<cap>/spec.md` (a shape `detect.find_spec_files`'
`changes/*/specs/*/spec.md` glob happily yields, since glob matches names, not
readability) produces an `IsADirectoryError` traceback and exit 1 from
`validate`, `validate --json`, `waivers`, and `graph --format json` alike.
`detect.py` already handles this exact class correctly at every one of its own
reads — `_threshold` (`except (json.JSONDecodeError, OSError)`), `_invariants`
(`except OSError` with a `logger.debug("invariants: %s exists but is
unreadable: %s", ...)`), `_adrs` (both the directory and single-file
branches), `detect_dialect`, and `find_speckit_spec_files` — and two tests
already pin that behaviour
(`tests/test_detect_speckit.py::test_detect_dialect_skips_an_unreadable_spec_path_not_crashes`,
`::test_find_speckit_spec_files_skips_an_unreadable_candidate_not_crashes`,
the second of which builds its fixture as a directory named `spec.md` for
precisely this reason). The parse layer is the one read path that was never
given the same treatment, so the defect is reachable only through the verbs a
CI job actually runs. This is the same defect class as `DEC-SD-001` (the
`init`/`new` unwritable-target fix, which moved an escaping `OSError` off exit
1 onto exit 2), one verb further in: that change fixed the *write* boundary
and left the *read* boundary untouched.

A second, smaller defect sits on the same code path. On a SpecKit-only target,
`validate --change <name>` filters through `detect.filter_by_change`, finds
nothing (there are no `changes/` directories at all), and exits 2 with `no
specs found for change 'name'` — which reads as "your package is missing"
when the true answer is "`--change` selects an OpenSpec change package and has
no SpecKit equivalent today" (`DEC-SK-006` already records that
`cmd_graph --change` stays OpenSpec-only deliberately; the message never said
so).

## What Changes

- `openspec_graph/parse.py`: new `SpecReadError` exception carrying `path`
  and `reason`; `parse_spec` translates `OSError` into it at the single place
  spec bytes are read, chaining the original (`raise ... from exc`), and
  records a `logger.debug` line first. Its own `str()` is deliberately terse
  (`"{path}: {reason}"`, the absolute path) so it is *not* a second copy of
  the operator-facing wording, which lives once in `cli._UNREADABLE_SPEC`.
  New module logger (`logging.getLogger("planlint.parse")`), matching
  `detect.py`'s no-handler-attached convention. `SpecReadError` joins
  `__all__`.
- `openspec_graph/cli.py`: `_UNREADABLE_SPEC = "ERROR cannot read spec
  {path}: {reason}"` as a single named constant beside `_NOT_A_DIRECTORY`;
  one shared `_report_unreadable(exc, root)` helper that logs the abort,
  renders the path root-relative via `detect.to_posix_relative`, and returns
  2. `cmd_validate`, `cmd_waivers`, and `cmd_graph` each catch
  `SpecReadError` and return through it — `cmd_graph` alongside its existing
  `NoOpenSpecTreeError` handler.
- `openspec_graph/cli.py`: `_NO_SPECS_FOR_CHANGE` and
  `_CHANGE_IS_OPENSPEC_ONLY` constants, rendered by one shared
  `_report_no_specs_for_change(prof, change)` helper that both `cmd_validate`
  and `cmd_graph` return through. The helper — not the call sites — owns the
  choice between the two templates (`prof.speckit_root and not
  prof.openspec_root`) and the exit code, so an OpenSpec target's existing
  message is byte-identical on both verbs and the gating condition exists
  once.
- `openspec_graph/graph.py`: `build_graph`'s docstring records that it
  propagates `SpecReadError` rather than catching it — the CLI owns exit
  codes, and `graph.py` must not import `cli` (pinned by
  `tests/test_decomposition.py::test_import_boundary_discipline`). No
  behavioural change to the module itself.
- `openspec_graph/__init__.py`: re-export `SpecReadError` beside
  `NoOpenSpecTreeError`, so a library consumer can catch it by the same
  import path the package's other typed error uses.
- `skills/planlint-spec-governance/references/exit-codes.md`: a new "Exit 2,
  by verb" entry for an unreadable spec, quoting the message verbatim, plus
  the SpecKit `--change` wording — `tests/test_skill_contract.py` reads this
  document and pins the strings.
- `tests/test_spec_read_errors.py`: one new module holding the whole
  contract — per-verb exit code and no-traceback coverage (parametrized over
  the six parsing verbs), the message content, the fail-closed and
  still-exits-1/0 non-success pairs, the parse-level translation and
  chaining, and both `--change` messages. Kept together rather than split
  across the four existing modules because the defect was in the *shared*
  parse layer: a reader checking whether every verb is covered should not
  have to visit four files to find out. `tests/test_decomposition.py`'s
  `test_public_import_compatibility` is extended with `SpecReadError` so the
  new public symbol is pinned like the rest.
- `CHANGELOG.md`: one entry under the unreleased heading.

## Non-Goals

- No dangling-symlink diagnostic. A broken link that reaches the read is
  already covered by this guard and renders its own `ENOENT` reason verbatim;
  telling a broken link apart from a wrong-type path, and de-duplicating one
  spec reachable through two paths, belongs to the separate symlink-dedup
  change, which owns the discovery layer this one deliberately does not
  touch.
- No change to what exit 1 means, and no re-classification of any existing
  finding. A spec that parses and fails rules keeps exiting 1; this change
  only removes a case that was never a finding from that bucket.
- No change to `detect.py`'s own reads, which deliberately skip an unreadable
  candidate and continue. Those are *optional* inputs (a maybe-present
  `CONTRACT.md`, one ADR file among many, a dialect vote); a discovered spec
  is a *mandatory* one, so the two must not share a policy.
- No `--feature` flag or SpecKit equivalent of `--change` (`DEC-SK-007`
  stands). The wording change only makes the existing limitation legible.
- No new rule. Nothing here is a spec-quality finding, so nothing enters the
  `RULES` registry or the README rules table.

## Affected Capabilities

- `spec-read-errors`
