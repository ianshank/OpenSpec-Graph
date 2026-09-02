"""Rule-engine types: Finding, Rule, and severity constants.

Sits at the bottom of the rules layer. Imports the parsed-spec and stack-profile
types only for type hints (``Rule.check`` signature); performs no analysis.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable
from pathlib import Path

from .detect import StackProfile, to_posix_relative
from .parse import ParsedSpec

__all__ = [
    "ERROR",
    "FINDINGS_SCHEMA_VERSION",
    "INFO",
    "WARN",
    "Finding",
    "ParsedSpec",
    "Rule",
    "StackProfile",
]

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# Version of the `validate --json` envelope, declared beside the Finding whose
# serialization it describes -- the same pattern as dialect_card.SCHEMA_VERSION
# and witness.WITNESS_SCHEMA_VERSION, so all three machine-readable outputs
# announce their shape the same way. Bump on any breaking change to the
# envelope or to a finding's own keys; additive keys do not bump it.
FINDINGS_SCHEMA_VERSION = 1

# Make targets a spec may cite without them existing yet in the Makefile.
GENERIC_STAGES = {"ci", "test", "validate", "lint", "coverage"}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    path: Path | None = None
    line: int = 0
    subject: str = ""  # entity a tree-scoped finding is about, e.g. an invariant id (G006)

    def as_dict(self, root: Path | None = None) -> dict[str, object]:
        """Serialize for a machine consumer.

        ``root`` renders ``path`` as a POSIX path relative to it, via the same
        ``to_posix_relative`` helper every other serializer in this codebase
        already used -- ``render`` above, ``ledger.build_ledger``,
        ``graph._relative_to``, ``StackProfile.as_dict``. This method was the
        sole holdout, emitting an absolute native-separator path.

        That was a deliberate decision (DEC-PS-002) on the premise that no
        consumer compares the field across two checkouts. The shipped CI
        template refutes it: it uploads ``validate --json`` as a build
        artifact produced on a runner and read elsewhere, where an absolute
        ``/home/runner/work/...`` path resolves to nothing. DEC-FE-001
        supersedes it on that evidence.

        ``root=None`` keeps the pre-existing absolute rendering, so callers
        that have no root to relativize against are unchanged.
        """
        if self.path is None:
            rendered: str | None = None
        elif root is None:
            rendered = str(self.path)
        else:
            # Never dropped and never None when a path exists: a finding
            # outside the target falls back to as_posix() inside the helper.
            rendered = to_posix_relative(self.path, root)
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "path": rendered,
            "line": self.line,
            "subject": self.subject,
        }

    def render(self, root: Path | None = None) -> str:
        where = ""
        if self.path:
            shown = to_posix_relative(self.path, root)
            where = f"{shown}:{self.line}: " if self.line else f"{shown}: "
        return f"{self.severity:5s} {self.rule}  {where}{self.message}"


@dataclasses.dataclass(frozen=True)
class Rule:
    ident: str
    severity: str
    dialects: tuple[str, ...]  # ("*",) for any
    summary: str
    check: Callable[[ParsedSpec, StackProfile], Iterable[str]]

    def applies(self, dialect: str) -> bool:
        return "*" in self.dialects or dialect in self.dialects
