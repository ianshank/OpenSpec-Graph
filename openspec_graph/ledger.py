"""Waiver ledger: aggregate every waived rule across a spec tree (CP-4).

Pure aggregation, no file I/O or subprocess -- mirrors ``dialect_card.py``'s
precedent. Takes already-parsed ``ParsedSpec`` objects (importing the type
is fine; see the import-boundary guard in ``tests/test_decomposition.py``)
and turns their ``waivers`` into a stable-ordered list of ledger rows. The
CLI layer (``cli.cmd_waivers``) owns reading ``openspec/`` and parsing specs.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from .parse import ParsedSpec

__all__ = ["LedgerEntry", "build_ledger", "owning_change"]


@dataclasses.dataclass(frozen=True)
class LedgerEntry:
    rule: str
    path: str
    line: int
    reason: str
    change: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "reason": self.reason,
            "change": self.change,
        }


def owning_change(path: str) -> str | None:
    """The change package a spec path belongs to, or None outside one.

    Per the ``openspec/changes/<name>/specs/<capability>/spec.md``
    convention: the path segment immediately after "changes".
    """
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part == "changes" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def _relative(path: Path, root: Path | None) -> str:
    if root is None:
        return str(path)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_ledger(specs: Sequence[ParsedSpec], root: Path | None = None) -> list[LedgerEntry]:
    """One row per waived rule id.

    A comment naming multiple rules (``<!-- specgraph:allow G003,G004 reason -->``)
    expands to one row per rule, all sharing that comment's reason and line
    (mirroring ``parse_waivers``'s own expansion). Stable order: path, then
    line, then rule id.
    """
    entries: list[LedgerEntry] = []
    for spec in specs:
        rel = _relative(spec.path, root)
        change = owning_change(rel)
        for waiver in spec.waivers:
            entries.append(
                LedgerEntry(rule=waiver.rule, path=rel, line=waiver.line, reason=waiver.reason, change=change)
            )
    entries.sort(key=lambda e: (e.path, e.line, e.rule))
    return entries
