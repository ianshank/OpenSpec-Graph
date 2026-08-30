"""Diff two spec dependency graphs. Fails if a PR regresses the graph (AC-CH-5,
AC-CH-6).

Exit non-zero if, comparing base -> head:

- ``broken_links`` increased, OR
- a new orphan requirement appears in head that was not in base.

Fixing an existing orphan or reducing broken_links is allowed (the gate only
fails on regressions, never on improvements).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def orphan_ids(graph: dict) -> set[str]:
    return {n["id"] for n in graph["nodes"] if n.get("orphan")}


def diff(base: dict, head: dict) -> list[str]:
    """Return a list of human-readable regressions; empty if the graph improved or held."""
    regressions: list[str] = []
    if head["broken_links"] > base["broken_links"]:
        regressions.append(
            f"broken_links increased: {base['broken_links']} -> {head['broken_links']}"
        )
    new_orphans = orphan_ids(head) - orphan_ids(base)
    if new_orphans:
        regressions.append(f"new orphan requirements: {sorted(new_orphans)}")
    return regressions


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: diff_spec_graph.py <base.json> <head.json>", file=sys.stderr)
        return 2
    base_path, head_path = Path(argv[1]), Path(argv[2])
    base = json.loads(base_path.read_text(encoding="utf-8"))
    head = json.loads(head_path.read_text(encoding="utf-8"))

    regressions = diff(base, head)
    if regressions:
        for message in regressions:
            print(f"FAIL: {message}")
        return 1

    print(
        f"PASS: broken_links {base['broken_links']} -> {head['broken_links']}, "
        f"no new orphan requirements"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
