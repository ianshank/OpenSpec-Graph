"""SARIF 2.1.0 projection of a validate run (CP-6).

A pure projection, like ``mermaid.py``: it is handed the findings
``cmd_validate`` already computed and reshapes them. It never evaluates a rule,
which is what makes "the same findings as ``--json``, no divergence" true by
construction rather than by a second implementation somebody has to keep in
step.

The point of the format is placement, not content. Findings reach an adopter
today as text in a CI log that nobody opens; SARIF puts the same findings
inline on the diff, in the pull request their team already reviews.

Stdlib-only, no I/O, and **zero intra-package imports** -- the same posture
``mermaid.py`` holds, and for the same reason: a projection that reaches back
into the package is one refactor away from depending on evaluation order. It
is handed the finding dicts ``cmd_validate`` has already serialized, which is
also what makes "the same findings as ``--json``" literally true: both
renderings read the same list of dicts, not two traversals that have to be
kept in step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

__all__ = ["SARIF_SCHEMA_URI", "SARIF_VERSION", "to_sarif"]

SARIF_VERSION = "2.1.0"
# schemastore's copy, which is what CodeQL itself emits. The oasis-tcs URL
# that reads like the canonical one is dead: that repository moved off
# `master` and reorganised its schema directory, so a validator following it
# gets a 404 rather than a schema.
SARIF_SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"

# The base id every artifact location is expressed against. GitHub resolves
# it to the repository root, which is what makes a repository-relative uri
# land on the right file in the diff.
SRCROOT = "%SRCROOT%"

# planlint severities to SARIF levels. Total over SEVERITY_ORDER's vocabulary;
# `_level` fails upward rather than silently downgrading anything missing.
_LEVELS = {"ERROR": "error", "WARN": "warning", "INFO": "note"}


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


def _location(finding: Mapping[str, object]) -> list[dict[str, object]]:
    """The finding's location, or an empty list when it has no path.

    An empty ``locations`` array is valid SARIF and is honest: it says no
    location was computed. The alternatives are both worse — dropping the
    finding loses a real result to make a schema happy, and inventing a
    synthetic uri asserts a file the finding is not about. GitHub will not
    render a locationless alert, which is a real cost, but a silently missing
    finding is a worse one.

    The path arrives already repository-relative and POSIX-rendered, because
    the caller serialized it that way for the JSON envelope. Relativizing it
    here would be a second implementation of the same rule.
    """
    path = finding.get("path")
    if not path:
        return []

    physical: dict[str, object] = {
        "artifactLocation": {"uri": str(path), "uriBaseId": SRCROOT}
    }
    # Only a real line gets a region. SARIF's startLine minimum is 1, so a 0
    # cannot be represented, and clamping it to 1 would put an annotation on
    # the first line of a real file pointing at content the finding is not
    # about -- a wrong location a reviewer cannot tell is wrong. This is the
    # common path, not an edge case: no rule currently sets a line at all.
    line = finding.get("line")
    if isinstance(line, int) and line >= 1:
        physical["region"] = {"startLine": line}
    return [{"physicalLocation": physical}]


def to_sarif(
    findings: Sequence[Mapping[str, object]],
    rule_table: Sequence[Mapping[str, object]],
    *,
    tool_version: str = "",
    information_uri: str = "https://github.com/ianshank/planlint",
) -> dict[str, object]:
    """Build a SARIF log from findings the caller has already serialized.

    ``findings`` are ``Finding.as_dict(root)`` outputs -- the same list the
    ``--json`` envelope carries, in the same order. Taking dicts rather than
    ``Finding`` objects is what keeps this module free of intra-package
    imports, and it makes the no-divergence property structural: there is one
    list, rendered twice, not two traversals to keep in step.

    Order is preserved rather than re-imposed, so the text, JSON and SARIF
    renderings of one run agree.

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
                "defaultConfiguration": {"level": _level(str(entry.get("severity", "ERROR")))},
                # rule_table() renders dialects as a comma-joined string
                # ("*", "harness,upstream"). Split rather than list() -- the
                # latter would explode the string into single characters.
                "properties": {"dialects": _dialects(entry.get("dialects"))},
            }
        )

    results: list[dict[str, object]] = []
    for finding in findings:
        rule_id = str(finding.get("rule", ""))
        result: dict[str, object] = {
            "ruleId": rule_id,
            "level": _level(str(finding.get("severity", ""))),
            "message": {"text": str(finding.get("message", ""))},
            "locations": _location(finding),
        }
        # ruleIndex is optional, and omitted rather than guessed when the
        # rule is not in the registry -- an index pointing at the wrong rule
        # is worse than none, and a caller can always resolve by ruleId.
        if rule_id in index_of:
            result["ruleIndex"] = index_of[rule_id]
        if finding.get("subject"):
            result["properties"] = {"subject": finding["subject"]}
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
                # Declared so a strict validator can resolve %SRCROOT%; GitHub
                # tolerates its absence, other consumers warn.
                "originalUriBaseIds": {SRCROOT.strip("%"): {"uri": "file:///"}},
                "results": results,
            }
        ],
    }
