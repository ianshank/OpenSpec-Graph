"""Dialect card: a stable, portable snapshot of ``detect``'s conventions (CP-2).

The card is ``StackProfile.to_card()``'s output shape -- everything from
``as_dict()`` that stays valid across different clones/machines/CI runners
(no absolute paths), plus a schema version. This module owns the schema
version and the diff algorithm; ``detect.py`` owns populating an instance
from a live ``StackProfile``. Pure, stdlib-only, zero intra-package import,
mirroring ``machinery.py``'s precedent -- and ``tools/diff_spec_graph.py``'s
``diff(base, head) -> list[str]`` shape, for the same reason: a diff is
either empty (clean) or a list of human-readable descriptions, never a
structured type a caller has to know how to unpack.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# Every field a card carries besides "schema_version" itself, which is
# always compared first and reported distinctly (see diff_cards).
_COMPARABLE_FIELDS = (
    "dialect",
    "languages",
    "make_targets",
    "make_target_confidence",
    "make_unresolved_count",
    "has_openspec_root",
    "change_dirs",
    "threshold",
    "invariant_source",
    "invariant_ids",
    "has_project_md",
    "adr_source",
    "adr_ids",
)

__all__ = ["SCHEMA_VERSION", "diff_cards"]


def diff_cards(previous: dict[str, object], current: dict[str, object]) -> list[str]:
    """Return human-readable descriptions of every changed field; empty if none."""
    changes: list[str] = []
    if previous.get("schema_version") != current.get("schema_version"):
        changes.append(
            f"schema_version changed: {previous.get('schema_version')!r} -> "
            f"{current.get('schema_version')!r}"
        )
    for field in _COMPARABLE_FIELDS:
        old, new = previous.get(field), current.get(field)
        if old != new:
            changes.append(f"{field} changed: {old!r} -> {new!r}")
    return changes
