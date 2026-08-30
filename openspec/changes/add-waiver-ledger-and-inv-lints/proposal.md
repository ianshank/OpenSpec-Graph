# Change: Add Waiver Ledger and Invariant Lints (CP-4)

## Why

`docs/differentiation-roadmap.md` names CP-4 as the next v1 feature after CP-1/CP-2/CP-3 (all shipped). Two linked gaps: (a) a waiver (`<!-- specgraph:allow RULE reason -->`) is silently downgraded to INFO today, with no ledger of what's been waived and no enforcement that a reason was actually given — the waiver regex already captures the reason text, but `suppressions()` discards it; (b) invariant citation is checked in only one direction (G005: "a cited invariant must be declared") — a declared invariant that no spec cites at all is invisible, the orphan-invariant lie G005 doesn't catch.

This proposal went through two rounds of adversarial review before implementation (mirroring this branch's own established discipline for higher-risk work — see CP-3's own two-round design history). The first round designed the mechanism; a second, independent round found two real, concrete bugs in that design before any code was written, both resolved in the Decisions below: G006 would have falsely flagged invariants as orphaned under `validate --change`, and G006 findings would have silently sorted to the top of every text-mode `validate` printout for lack of a `path`.

## What Changes

- **G007** (new rule, ERROR): a waiver with no reason text fails the gate. `parse_semantics.py` gains `Waiver`/`parse_waivers()`, capturing what the regex already parses but previously discarded.
- **G006** (new rule, WARN): a declared invariant cited by no living spec, and not waived, is reported as orphaned. Requires a new evaluation pathway (`rules.evaluate_tree()`) since this is the first rule in the codebase that is a property of the whole spec tree, not one file — see DEC-WL-001.
- **`planlint waivers --format json`** (new CLI verb): a stable-ordered ledger of every waived rule across the tree, with file, line, reason, and owning change package.

## Non-Goals

- **Owner attribution via git blame** — the roadmap's own stated cutline; reason+file+line ships first, owner is a natural, separable follow-up if ever needed.
- **Per-invariant-scoped waiver syntax** (e.g. `G006:INV-7`) — v1's "waived anywhere in the tree suppresses G006 tree-wide" needs zero new suppression syntax; finer scoping is a follow-up if the coarse version proves too blunt in practice.
- **A "living/archived" spec-status filter** — no such concept exists anywhere in this codebase; "living" = every spec `detect.find_spec_files()` currently returns (a bare glob, no status filtering — confirmed by reading the function directly).
- **`waivers --fail-on`** — `waivers` is pure reporting like `detect`/`rules`/`graph`; it never fails on content, only on usage errors (no `openspec/` tree). Enforcement is G007/`validate`'s job.

## Affected Capabilities

- `waiver-ledger`
