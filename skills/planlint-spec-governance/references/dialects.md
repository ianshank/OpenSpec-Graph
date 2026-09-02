# Dialects

A dialect is the house style a repository writes its specs in. `planlint`
detects it from the content of the spec files themselves and applies the rule
families that fit. `planlint detect` reports which one it found.

| Dialect | Where specs live | Shape |
|---|---|---|
| `harness` | `openspec/changes/<name>/specs/<capability>/spec.md` | Requirement and criterion identifiers, a verification line per criterion, a validation matrix |
| `upstream` | the same tree | Delta headers, requirements each carrying a scenario written as stimulus and outcome |
| `speckit` | `specs/<feature>/spec.md` at the repository root | Numbered functional requirements and success criteria, acceptance scenarios inside prioritized user stories |

A repository may carry an OpenSpec tree, a SpecKit tree, both, or neither.
Detection is content-gated: a bare `specs/` directory proves nothing on its
own, because that name is also used by unrelated conventions, so the
fingerprint requires a real spec file inside it.

## Which rules apply

Rule identifiers carry their family in the letter. Generic rules apply to
every dialect. The harness, upstream, and speckit families apply only to their
own. The witness family applies to every dialect but is evaluated only when
`--require-witness` is passed. `references/rule-catalog.md` lists each rule
with the dialects it applies to.

## Scaffolding

`planlint new` accepts only the harness and upstream dialects. This is a
deliberate boundary, not an oversight: a repository using SpecKit conventions
can be validated, graphed, and audited for waivers, but its packages are
authored with its own tooling. If asked to scaffold a SpecKit package, say
that `new` does not produce that shape rather than generating a package in the
wrong one.

## Selecting a dialect explicitly

`validate` and `waivers` accept a dialect flag, including an automatic mode.
Detection is the default and is usually right. Pass an explicit dialect only
when a repository carries more than one tree and you need to scope a run to
one of them.
