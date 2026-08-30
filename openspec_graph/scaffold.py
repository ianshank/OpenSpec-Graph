"""Scaffold change packages in whichever dialect the target repo already speaks.

Writes are idempotent and refuse to clobber. Every generated document cites
only make targets the target repo actually has, and refers to its real
threshold locator instead of a literal number.

Document wording lives in :mod:`scaffold_templates`; this module owns the write
plan (what to write where, idempotent application) and stage/threshold policy.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .detect import StackProfile
from .scaffold_templates import (
    proposal as _proposal,
)
from .scaffold_templates import (
    spec_harness as _spec_harness,
)
from .scaffold_templates import (
    spec_upstream as _spec_upstream,
)
from .scaffold_templates import (
    tasks as _tasks,
)

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
    """Bootstrap `openspec/` and write a snapshot of detected conventions
    into specgraph.json/project.md.

    A snapshot, not a config: nothing reads either file back. `detect`
    always re-derives these conventions fresh from the filesystem on every
    run, by design -- a hand-editable file that can silently drift from
    reality is exactly the class of stale-cached-belief bug this project
    exists to catch in *target* repos, so it doesn't reintroduce the same
    problem in its own.
    """
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

Detected by `openspec-graph` at `init` time — a snapshot for humans, not a
live config. `planlint` always re-derives these conventions fresh from the
repo on every `detect`/`validate` run rather than reading this file back,
so edit it freely to correct a misdetection, but note that doing so does
not change enforcement.

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
