"""Scaffold change packages in whichever dialect the target repo already speaks.

Writes are idempotent and refuse to clobber. Every generated document cites
only make targets the target repo actually has, and refers to its real
threshold locator instead of a literal number.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .detect import StackProfile

CONFIG_NAME = "specgraph.json"

# Preference order for the stage a criterion should name.
_STAGE_PREFS = (
    "test-governance",
    "regression",
    "behaviour",
    "gates",
    "validate",
    "test",
    "ci",
)
_FULL_PREFS = ("ci", "pre-pr", "test", "validate")


@dataclasses.dataclass(frozen=True)
class WritePlan:
    path: Path
    content: str
    exists: bool

    @property
    def action(self) -> str:
        return "skip (exists)" if self.exists else "create"


def pick_stage(profile: StackProfile, prefs: tuple[str, ...] = _STAGE_PREFS) -> str:
    for candidate in prefs:
        if candidate in profile.make_targets:
            return candidate
    return profile.make_targets[0] if profile.make_targets else "test"


def threshold_locator(profile: StackProfile) -> str:
    return profile.threshold.locator if profile.threshold else "the governance policy"


def _proposal(name: str, capability: str) -> str:
    return f"""# Change: {name.replace("-", " ").title()}

## Why

<!-- What is wrong or missing. Attach evidence: a failing test, a governance
     gap, a user report. No evidence, no spec. -->

## What Changes

- <!-- one bullet per externally visible change -->

## Non-Goals

- <!-- name what this change explicitly does not do, so scope cannot drift -->
- No claim of isolation or sandboxing unless a mechanism is cited.

## Affected Capabilities

- `{capability}`
"""


def _tasks(name: str, stage: str, full: str) -> str:
    return f"""# Milestones

## Milestone 1 — <name>

- <!-- ordered work; each step declares what it reads and what it leaves behind -->
- **Gate:** `make {stage}` green; every acceptance criterion for this milestone passes.

## Milestone 2 — Evidence and release

- Wire new gates into the repo's required-target list.
- Confirm coverage floors from the repo threshold source.
- **Gate:** `make {full}` green on the full matrix; zero unapproved test skips.
"""


def _spec_harness(capability: str, change: str, stage: str, full: str, locator: str) -> str:
    title = capability.replace("-", " ").title()
    area = "".join(w[0] for w in capability.split("-"))[:3].upper() or "CAP"
    return f"""# Spec: {title}

> **Change:** `{change}`
> **Version:** 1.0.0-draft
> **Authors:** <role> · <role>
> **Status:** DRAFT

---

## Problem Statement

<!-- What is broken or unverifiable today. Cite the file and symbol that proves
     it. **Evidence:** `path/to/module.py::symbol` does X but not Y. -->

---

## Requirements

- R-{area}-1: The system MUST <observable behavior>, sourced from configuration
  rather than a literal value.
- C-{area}-1: The change MUST NOT weaken any declared invariant.

## Acceptance Criteria

- [ ] **AC-{area}-1:** <observable, executable check>. (R-{area}-1)
  _Verified by:_ `pytest -k test_<selector>` · stage: `make {stage}`

- [ ] **AC-{area}-2 (non-success):** <what this rejects, denies, or fails closed
  on; name the expected failure message>. (C-{area}-1)
  _Verified by:_ `pytest -k test_<negative_selector>` · stage: `make {stage}`

- [ ] **AC-{area}-3:** Coverage meets the floor declared in `{locator}`. No
  literal threshold appears in this document or its tests.
  _Verified by:_ `make {full}`

## Invariants Touched

- <!-- INV-n: how it is preserved, and which AC proves it -->

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused gate | `make {stage}` | AC-{area}-1..2 pass |
| Full pipeline | `make {full}` | all of the above |

## Backward Compatibility

<!-- The deprecation or compatibility path for existing callers. -->

## Open Questions

> [!IMPORTANT]
> **DEC-{area}-001 (BLOCKING):** <question that must be resolved before the
> first milestone gate>.
"""


def _spec_upstream(capability: str, stage: str) -> str:
    title = capability.replace("-", " ").capitalize()
    return f"""# Spec delta — {title}

## ADDED Requirements

### Requirement: <the system> SHALL <normative, observable behavior>

<!-- Prose stating the obligation precisely. Use SHALL or MUST. -->

#### Scenario: the gate enforces the requirement

- **GIVEN** <the starting state>
- **WHEN** `make {stage}` runs <the named check>
- **THEN** <the observable pass condition>

#### Scenario: a future regression is caught before merge

- **GIVEN** a hypothetical edit that violates the requirement
- **WHEN** the suite runs
- **THEN** the check fails and names the offending file
"""


def plan_change(
    profile: StackProfile,
    name: str,
    capability: str,
    dialect: str | None = None,
) -> list[WritePlan]:
    """Build the write plan for a new change package. Pure: touches no disk state."""
    root = profile.openspec_root or (profile.root / "openspec")
    resolved = dialect or profile.dialect
    if resolved in {"unknown", "mixed"}:
        resolved = "harness"

    stage = pick_stage(profile)
    full = pick_stage(profile, _FULL_PREFS)
    base = root / "changes" / name

    files: dict[Path, str] = {
        base / "proposal.md": _proposal(name, capability),
        base / "tasks.md": _tasks(name, stage, full),
    }
    spec_path = base / "specs" / capability / "spec.md"
    if resolved == "upstream":
        files[spec_path] = _spec_upstream(capability, stage)
    else:
        files[spec_path] = _spec_harness(
            capability, name, stage, full, threshold_locator(profile)
        )

    return [WritePlan(path=p, content=c, exists=p.exists()) for p, c in files.items()]


def plan_init(profile: StackProfile) -> list[WritePlan]:
    """Bootstrap `openspec/` and pin the detected conventions into specgraph.json."""
    root = profile.openspec_root or (profile.root / "openspec")
    config = {
        "dialect": profile.dialect if profile.dialect != "unknown" else "harness",
        "threshold_locator": threshold_locator(profile),
        "focused_stage": pick_stage(profile),
        "full_stage": pick_stage(profile, _FULL_PREFS),
        "invariant_source": (
            str(profile.invariant_source.relative_to(profile.root))
            if profile.invariant_source
            else None
        ),
        "languages": list(profile.languages),
    }
    project_md = f"""# Project conventions

Detected by `openspec-graph` — correct anything wrong, this file is authoritative.

- Spec dialect: `{config["dialect"]}`
- Coverage floor source: `{config["threshold_locator"]}`
- Focused gate: `make {config["focused_stage"]}`
- Full gate: `make {config["full_stage"]}`
- Invariant source: `{config["invariant_source"] or "(none found)"}`

## Rules

1. Thresholds are read from the coverage floor source above. Never hard-coded in a spec.
2. Every criterion names a stage that exists in the Makefile.
3. Every spec carries at least one non-success criterion.
4. A `(BLOCKING)` open question keeps the spec at `Status: DRAFT`.
"""
    return [
        WritePlan(
            root / CONFIG_NAME,
            json.dumps(config, indent=2) + "\n",
            (root / CONFIG_NAME).exists(),
        ),
        WritePlan(root / "project.md", project_md, (root / "project.md").exists()),
    ]


def apply(plans: list[WritePlan], force: bool = False) -> list[Path]:
    written: list[Path] = []
    for item in plans:
        if item.exists and not force:
            continue
        item.path.parent.mkdir(parents=True, exist_ok=True)
        item.path.write_text(item.content, encoding="utf-8")
        written.append(item.path)
    return written
