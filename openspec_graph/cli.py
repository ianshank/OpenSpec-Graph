"""`planlint` — the CI gate that fails when a spec cites a gate this repo does
not have.

Pointed at a cloned repository, `planlint` reads the target's real machinery
(make targets, coverage floor, invariant source, spec dialect) and holds every
spec to that, using the target's own vocabulary. It is a linter under
`openspec validate`, not an authoring framework.

Verbs:
  detect    read-only report of the target's stack, gates, threshold, dialect
  init      write openspec/specgraph.json + project.md, a snapshot of detected conventions
  new       scaffold a change package in the target's own dialect
  validate  run the rule engine over every change package
  graph     emit the spec dependency graph as JSON or Mermaid (pure projection of validate)
  rules     print the rule table
  waivers   list every waived rule across the tree, with file, line, reason, change

Exit codes: 0 clean, 1 findings at or above the fail level, 2 usage error.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import sys
from pathlib import Path

from . import detect, dialect_card, ledger, mermaid, rules, scaffold
from . import graph as graph_module
from .log import configure as configure_logging
from .parse import ParsedSpec, parse_spec

SEVERITY_ORDER = {"INFO": 0, "WARN": 1, "ERROR": 2}

logger = logging.getLogger("planlint")


def _version_string() -> str:
    # Resolve the distribution name from the importable package name
    # ("openspec_graph") via packages_distributions(), rather than a second
    # hardcoded copy of pyproject.toml's [project] name ("openspec-graph"
    # -- spelled differently, hyphen vs. underscore, which is exactly why
    # only this mapping, not a literal, can bridge the two correctly).
    # NOT "planlint", which is only the console-script name.
    top_level = (__package__ or __name__).split(".")[0]
    try:
        distributions = importlib.metadata.packages_distributions()[top_level]
        version = importlib.metadata.version(distributions[0])
    except (KeyError, IndexError, importlib.metadata.PackageNotFoundError):
        # Uninstalled checkout (e.g. running from a source clone without
        # `pip install -e .`): fall back to the package's own constant
        # rather than a third hardcoded copy.
        from . import __version__ as version
    return f"%(prog)s {version}"


def _profile(args: argparse.Namespace) -> detect.StackProfile:
    root = Path(args.target).resolve()
    logger.debug("profiling target %s", root)
    if not root.is_dir():
        raise SystemExit(f"target is not a directory: {root}")
    prof = detect.profile(root)
    logger.debug(
        "profile: dialect=%s change_packages=%d openspec=%s "
        "make_targets=%d make_confidence=%s make_unresolved=%d",
        prof.dialect, len(prof.change_dirs), bool(prof.openspec_root),
        len(prof.make_targets), prof.make_target_confidence, prof.make_unresolved_count,
    )
    return prof


def cmd_detect(args: argparse.Namespace) -> int:
    prof = _profile(args)

    if args.diff:
        baseline_path = Path(args.diff)
        try:
            previous = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"cannot read --diff baseline {baseline_path}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(previous, dict):
            print(
                f"cannot read --diff baseline {baseline_path}: expected a JSON object, "
                f"got {type(previous).__name__}",
                file=sys.stderr,
            )
            return 2
        changes = dialect_card.diff_cards(previous, prof.to_card())
        if changes:
            for change in changes:
                print(f"FAIL: {change}")
            return 1
        print("PASS: no drift in detected conventions")
        return 0

    if args.format == "json":
        print(json.dumps(prof.to_card(), indent=2))
        return 0

    if args.json:
        print(json.dumps(prof.as_dict(), indent=2))
        return 0
    thr = prof.threshold
    print(f"target            {prof.root}")
    print(f"languages         {', '.join(prof.languages) or '(none detected)'}")
    print(f"make targets      {len(prof.make_targets)} found")
    print(f"openspec/         {'present' if prof.openspec_root else 'ABSENT — run ``planlint init``'}")
    print(f"spec dialect      {prof.dialect}")
    print(f"change packages   {len(prof.change_dirs)}")
    print(f"coverage floor    {thr.value if thr else '(none)'}  from {thr.locator if thr else '(not found)'}")
    src = prof.invariant_source.name if prof.invariant_source else "(none)"
    print(f"invariants        {len(prof.invariant_ids)} in {src}")
    print(f"focused stage     make {scaffold.pick_stage(prof)}")
    if prof.dialect == "mixed":
        print("\nWARN  repo contains both spec dialects; validate will resolve per file.")
    if prof.make_target_confidence == "low":
        print(
            f"\nINFO  Makefile parsed with low confidence "
            f"({prof.make_unresolved_count} target(s) could not be resolved "
            "structurally); falling back to regex-based detection for those."
        )
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    prof = _profile(args)
    plans = scaffold.plan_init(prof)
    for item in plans:
        print(f"{item.action:15s} {item.path.relative_to(prof.root)}")
    if args.dry_run:
        print("\ndry run — nothing written")
        return 0
    written = scaffold.apply(plans, force=args.force)
    print(f"\nwrote {len(written)} file(s)")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    prof = _profile(args)
    plans = scaffold.plan_change(prof, args.name, args.capability, args.dialect)
    for item in plans:
        print(f"{item.action:15s} {item.path.relative_to(prof.root)}")
    if args.dry_run:
        print("\ndry run — nothing written")
        return 0
    written = scaffold.apply(plans, force=args.force)
    print(f"\nwrote {len(written)} file(s)")
    if written:
        print("Now fill the Problem Statement with evidence, then run ``planlint validate``.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    prof = _profile(args)
    if not prof.openspec_root:
        print("no openspec/ directory; run ``planlint init`` first", file=sys.stderr)
        return 2

    spec_files = detect.find_spec_files(prof.openspec_root)
    if args.change:
        spec_files = detect.filter_by_change(spec_files, args.change)
        if not spec_files:
            print(f"no specs found for change {args.change!r}", file=sys.stderr)
            return 2

    findings: list[rules.Finding] = []
    specs: list[ParsedSpec] = []
    for path in spec_files:
        logger.debug("evaluating %s", path)
        spec = parse_spec(path, args.dialect or prof.dialect)
        specs.append(spec)
        findings.extend(rules.evaluate(spec, prof))

    if args.change:
        # G006/G009 are whole-tree properties (DEC-WL-001/DEC-AD-003);
        # spec_files was just filtered by --change above, so evaluate_tree()
        # over that filtered set would report every invariant/ADR outside
        # the filtered view as falsely orphaned (DEC-WL-003/DEC-AD-004). A
        # --change-scoped run's contract is "does this one package pass"
        # either way, so skip both outright.
        print("INFO  G006 skipped (tree-wide check needs an unscoped run)", file=sys.stderr)
        print("INFO  G009 skipped (tree-wide check needs an unscoped run)", file=sys.stderr)
    else:
        findings.extend(rules.evaluate_tree(specs, prof))

    fail_at = SEVERITY_ORDER[args.fail_on]
    blocking = [f for f in findings if SEVERITY_ORDER[f.severity] >= fail_at]

    if args.json:
        print(
            json.dumps(
                {
                    "target": str(prof.root),
                    "specs_checked": len(spec_files),
                    "findings": [f.as_dict() for f in findings],
                    "blocking": len(blocking),
                },
                indent=2,
            )
        )
        return 1 if blocking else 0

    for finding in sorted(findings, key=lambda f: (str(f.path), f.rule)):
        print(finding.render(prof.root))

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in SEVERITY_ORDER}
    print(
        f"\n{len(spec_files)} spec(s) checked · "
        f"{counts['ERROR']} error · {counts['WARN']} warn · {counts['INFO']} info"
    )
    if blocking:
        print(f"FAIL — {len(blocking)} finding(s) at or above {args.fail_on}")
        return 1
    print("PASS")
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    table = rules.rule_table()
    if args.json:
        print(json.dumps(table, indent=2))
        return 0
    print(f"{'ID':6s} {'SEV':6s} {'DIALECTS':12s} SUMMARY")
    for row in table:
        print(f"{row['id']:6s} {row['severity']:6s} {row['dialects']:12s} {row['summary']}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    # Rendering is a downstream concern; reject it before doing any work so
    # the message is explicit rather than a generic argparse complaint (AC-GR-6).
    # Mermaid is not "rendering" in that sense -- it's text GitHub/GitLab
    # render natively, the same posture as JSON output; planlint still does
    # no image rendering. This AC is unrevised, only added to.
    if args.format == "dot":
        print(
            "error: --format dot is not supported; graph rendering is a "
            "downstream, out-of-scope concern. Use --format json.",
            file=sys.stderr,
        )
        return 2

    prof = _profile(args)
    spec_files = None
    if args.change:
        if not prof.openspec_root:
            print("no openspec/ directory; run ``planlint init`` first", file=sys.stderr)
            return 2
        spec_files = detect.filter_by_change(detect.find_spec_files(prof.openspec_root), args.change)
        if not spec_files:
            print(f"no specs found for change {args.change!r}", file=sys.stderr)
            return 2
        # Unlike `validate --change` (which skips G006/G009 outright,
        # DEC-WL-003/DEC-AD-004), `graph --change` keeps evaluate_tree()
        # running unscoped and folds its results into broken_links
        # (DEC-GV-002) -- so a nonzero broken_links here can reflect an
        # invariant/ADR issue entirely outside the rendered scope. Flagged
        # so that is never a silent surprise.
        print(
            "INFO  G006 included unscoped (tree-wide check; may report an "
            "invariant outside this --change scope)",
            file=sys.stderr,
        )
        print(
            "INFO  G009 included unscoped (tree-wide check; may report an "
            "ADR outside this --change scope)",
            file=sys.stderr,
        )

    try:
        graph = graph_module.build_graph(prof, spec_files=spec_files)
    except graph_module.NoOpenSpecTreeError as exc:
        # Name the missing directory and exit non-zero rather than emitting an
        # empty graph (AC-GR-2).
        print(str(exc), file=sys.stderr)
        return 2

    if args.format == "mermaid":
        print(mermaid.to_mermaid(graph), end="")
    else:
        print(json.dumps(graph, indent=2))
    return 0


def cmd_waivers(args: argparse.Namespace) -> int:
    prof = _profile(args)
    if not prof.openspec_root:
        print("no openspec/ directory; run ``planlint init`` first", file=sys.stderr)
        return 2

    spec_files = detect.find_spec_files(prof.openspec_root)
    specs = [parse_spec(path, args.dialect or prof.dialect) for path in spec_files]
    entries = ledger.build_ledger(specs, prof.root)

    if args.format == "json":
        print(json.dumps([e.as_dict() for e in entries], indent=2))
        return 0

    if not entries:
        print("no waivers found")
        return 0
    print(f"{'RULE':6s} {'LINE':>5s}  {'CHANGE':30s} {'PATH':40s} REASON")
    for e in entries:
        print(f"{e.rule:6s} {e.line:5d}  {(e.change or '-'):30s} {e.path:40s} {e.reason}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planlint", description="The CI gate that fails when a spec cites a gate this repo does not have."
    )
    parser.add_argument("--target", default=".", help="path to the cloned repository")
    # Global debug flag: diagnostics go to stderr only, never stdout, so JSON
    # output stays parseable (AC-EH-5). Overridden by nothing; overrides the
    # SPECGRAPH_LOG_LEVEL env var when set.
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="emit debug diagnostics to stderr (does not affect stdout)",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=_version_string(),
        help="print the installed version and exit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="read-only stack and dialect report")
    p_detect.add_argument(
        "--json", action="store_true",
        help="print the full detected profile as JSON (legacy; unchanged shape)",
    )
    p_detect.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="output format; 'json' emits a stable, schema-versioned dialect "
        "card excluding machine-specific paths (portable; see --diff)",
    )
    p_detect.add_argument(
        "--diff", metavar="PREV_CARD_JSON",
        help="compare against a previous 'detect --format json' output; "
        "exits non-zero and lists changed fields on drift",
    )
    p_detect.set_defaults(func=cmd_detect)

    p_init = sub.add_parser("init", help="write a snapshot of detected conventions into openspec/")
    p_init.add_argument("--dry-run", action="store_true")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_new = sub.add_parser("new", help="scaffold a change package")
    p_new.add_argument("name")
    p_new.add_argument("--capability", required=True)
    p_new.add_argument("--dialect", choices=["harness", "upstream"])
    p_new.add_argument("--dry-run", action="store_true")
    p_new.add_argument("--force", action="store_true")
    p_new.set_defaults(func=cmd_new)

    p_val = sub.add_parser("validate", help="run the rule engine")
    p_val.add_argument("--change", help="limit to one change package")
    p_val.add_argument("--dialect", choices=["harness", "upstream", "auto"])
    p_val.add_argument("--fail-on", choices=["INFO", "WARN", "ERROR"], default="ERROR")
    p_val.add_argument("--json", action="store_true")
    p_val.set_defaults(func=cmd_validate)

    p_rules = sub.add_parser("rules", help="print the rule table")
    p_rules.add_argument("--json", action="store_true")
    p_rules.set_defaults(func=cmd_rules)

    p_graph = sub.add_parser("graph", help="emit the spec dependency graph (JSON or Mermaid)")
    p_graph.add_argument(
        "--format", choices=["json", "mermaid", "dot"], default="json",
        help="output format; 'dot' is rejected (rendering is out of scope)",
    )
    p_graph.add_argument("--change", help="limit rendered nodes/edges to one change package")
    p_graph.set_defaults(func=cmd_graph)

    p_waivers = sub.add_parser("waivers", help="list every waived rule across the tree")
    p_waivers.add_argument("--dialect", choices=["harness", "upstream", "auto"])
    p_waivers.add_argument("--format", choices=["text", "json"], default="text")
    p_waivers.set_defaults(func=cmd_waivers)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=getattr(args, "verbose", False))
    return int(args.func(args))


_DEPRECATION_WARNING = (
    "`specgraph` is deprecated; use `planlint` instead. "
    "The `specgraph` command is a backwards-compatible alias and will be removed."
)


def main_deprecated(argv: list[str] | None = None) -> int:
    """Backwards-compatible entry point for the legacy `specgraph` command.

    Emits a one-line deprecation warning to **stderr** (so stdout stays
    parseable), then delegates to :func:`main` and returns its exit code. The
    warning never changes the exit code — existing CI that runs
    `specgraph validate` keeps failing on real errors, never silently passing.
    """
    print(_DEPRECATION_WARNING, file=sys.stderr)
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
