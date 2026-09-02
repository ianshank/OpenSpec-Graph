"""SARIF 2.1.0 projection of a validate run (CP-6).

A pure projection, like ``mermaid.py``: it is handed the findings
``cmd_validate`` already computed and reshapes them. It never evaluates a rule,
which is what makes "the same findings as ``--json``, no divergence" true by
construction rather than by a second implementation somebody has to keep in
step.

The point of the format is placement, not content. Findings reach an adopter
today as text in a CI log that nobody opens; SARIF puts the same findings
inline on the diff, in the pull request their team already reviews.

Stdlib-only, no I/O, no intra-package import beyond the types it reshapes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from . import detect
from .rule_types import ERROR, INFO, WARN, Finding

__all__ = ["SARIF_SCHEMA_URI", "SARIF_VERSION", "to_sarif"]

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)

# The base id every artifact location is expressed against. GitHub resolves
# it to the repository root, which is what makes a repository-relative uri
# land on the right file in the diff.
SRCROOT = "%SRCROOT%"

# planlint severities to SARIF levels. Total over SEVERITY_ORDER's vocabulary;
# `_level` fails upward rather than silently downgrading anything missing.
_LEVELS = {ERROR: "error", WARN: "warning", INFO: "note"}


def _level(severity: str) -> str:
    """The SARIF level for a planlint severity.

    An unrecognised severity maps to "error", never to "none" or "note". A
    severity this module has not been taught about is a bug in the caller, and
    the safe failure is the loud one: under-reporting would hide a finding in
    the one surface an adopter actually reads.
    """
    return _LEVELS.get(severity, "error")


def _dialects(value: object) -> list[str]:
    """The dialect list for a rule-table row.

    ``rule_table()`` renders the tuple as a comma-joined string for its text
    and JSON output; SARIF properties are better served by the list, and
    rebuilding it here beats widening the rule table (which a golden hash
    pins) for one consumer.
    """
    if isinstance(value, str):
        return [part for part in value.split(",") if part]
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value]
    return []


def _location(finding: Finding, root: Path | None) -> list[dict[str, object]]:
    """The finding's location, or an empty list when it has no path.

    An empty ``locations`` array is valid SARIF and is honest: it says no
    location was computed. The alternatives are both worse — dropping the
    finding loses a real result to make a schema happy, and inventing a
    synthetic uri asserts a file the finding is not about.
    """
    if finding.path is None:
        return []

    physical: dict[str, object] = {
        "artifactLocation": {
            "uri": detect.to_posix_relative(finding.path, root),
            "uriBaseId": SRCROOT,
        }
    }
    # Only a real line gets a region. SARIF's startLine minimum is 1, so a 0
    # cannot be represented, and clamping it to 1 would put an annotation on
    # the first line of a real file pointing at content the finding is not
    # about -- a wrong location a reviewer cannot tell is wrong. This is the
    # common path, not an edge case: no rule currently sets a line at all.
    if finding.line >= 1:
        physical["region"] = {"startLine": finding.line}
    return [{"physicalLocation": physical}]


def to_sarif(
    findings: Sequence[Finding],
    rule_table: Sequence[Mapping[str, object]],
    *,
    root: Path | None = None,
    tool_version: str = "",
    information_uri: str = "https://github.com/ianshank/planlint",
) -> dict[str, object]:
    """Build a SARIF log from findings already computed by the rule engine.

    ``findings`` must arrive in the order the caller wants them reported; this
    function preserves it rather than imposing a second ordering, so the text,
    JSON and SARIF renderings of one run agree.

    ``rule_table`` is the whole registry, not only the rules that fired.
    GitHub attaches alert metadata by ``ruleId`` against the driver's rule
    set, so a rule firing for the first time in a later run would otherwise
    arrive with no name or description. It also keeps the driver block a
    function of the build rather than of the target repository, which is what
    makes the output byte-stable for an unchanged build.
    """
    rules: list[dict[str, object]] = []
    index_of: dict[str, int] = {}
    for entry in rule_table:
        ident = str(entry.get("id") or entry.get("ident") or "")
        if not ident:
            continue
        index_of[ident] = len(rules)
        rules.append(
            {
                "id": ident,
                "name": ident,
                "shortDescription": {"text": str(entry.get("summary", ""))},
                "defaultConfiguration": {"level": _level(str(entry.get("severity", ERROR)))},
                # rule_table() renders dialects as a comma-joined string
                # ("*", "harness,upstream"). Split rather than list() -- the
                # latter would explode the string into single characters.
                "properties": {"dialects": _dialects(entry.get("dialects"))},
            }
        )

    results: list[dict[str, object]] = []
    for finding in findings:
        result: dict[str, object] = {
            "ruleId": finding.rule,
            "level": _level(finding.severity),
            "message": {"text": finding.message},
            "locations": _location(finding, root),
        }
        # ruleIndex is optional, and omitted rather than guessed when the
        # rule is not in the registry -- an index pointing at the wrong rule
        # is worse than none, and a caller can always resolve by ruleId.
        if finding.rule in index_of:
            result["ruleIndex"] = index_of[finding.rule]
        if finding.subject:
            result["properties"] = {"subject": finding.subject}
        results.append(result)

    driver: dict[str, object] = {
        "name": "planlint",
        "informationUri": information_uri,
        "rules": rules,
    }
    if tool_version:
        driver["version"] = tool_version

    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": driver},
                "results": results,
            }
        ],
    }
