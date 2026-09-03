"""Decomposition guard tests (change package: decompose-god-files).

These lock the public contract BEFORE the production modules are split, so a
refactor that drifts the public import surface or the CLI/graph/rules JSON
output fails `make test`. Path-normalized so they are reproducible across temp
dirs.
"""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.support import normalize_root

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG = REPO_ROOT / "openspec_graph"
FX = REPO_ROOT / "tests" / "fixtures"

# Modules created by this change package. Each must stay stdlib-only (R-DG-3) and
# obey the import boundary: no importing cli or graph (R-DG-5).
_NEW_MODULES = [
    "scaffold_templates",
    "parse_semantics",
    "parse_model",
    "parse_harness",
    "parse_upstream",
    "rule_types",
    "rules_generic",
    "rules_harness",
    "rules_upstream",
    "parse_speckit",
    "rules_speckit",
    "machinery",
    "dialect_card",
    "ledger",
    "delta",
    "sarif",
    "mermaid",
    "witness",
    "rules_witness",
]

# Modules that must NOT import cli or graph (the orchestration/output layers).
# cli.py and __init__.py are the expected hubs and are exempt.
_BOUNDARY_EXEMPT = {"cli", "__init__"}

# Path-normalized SHA-256 of validate --json / graph --format json / rules --json
# for the canonical fixture repo (tests/fixtures/). Captured before the split;
# any drift after decomposition fails AC-DG-2.
#
# The "rules" hash has been re-pinned three times: once by
# `fix-u003-mandatory-given` (reworded U003's summary -- GIVEN became
# optional), once by `add-witness-mode` (W001/W002 added to RULES, listed by
# `rules --json` for discoverability even though neither is evaluated
# without --require-witness), and once by `add-speckit-dialect` (S001-S004
# added to RULES). "validate" and "graph" stayed byte-identical across all
# three changes -- the canonical fixture (tests/fixtures/) has no `specs/`
# directory, so the speckit dialect never fires against it either.

# Any version string the findings envelope reports, normalized out of the
# golden hash (see _run_cli). Matches whatever a dev checkout, an editable
# install or a built wheel resolves to, so the fixture is not pinned to the
# environment the hash was captured in.
_TOOL_VERSION = re.compile(r'"tool_version": "[^"]*"')

_EXPECTED_HASHES = {
    # Re-pinned once more by `add-findings-json-envelope`, which added the
    # schema_version/tool_version envelope keys and made findings[].path
    # root-relative POSIX. tool_version is normalized before hashing, so this
    # is the last re-pin a release can cause.
    "validate": "0f3c1d7716421ca7e9436120a1f4c225cf2d91ba07f6d919d4181be305a147d4",
    "graph": "23eea4b474ff9d6d5c4f89dbb86acaac53562544a551d79bceb5c984d2015482",
    "rules": "5dc8af2ecae022e50a145d42d5a13a2f055ec78b7df3962da593180574dcd20b",
}


def _build_repo(root: Path) -> None:
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"))
    (root / "pyproject.toml").write_text((FX / "pyproject.toml").read_text(encoding="utf-8"))
    for change, cap, fname in [
        ("c1", "cap", "good_harness.md"),
        ("c2", "cap2", "good_upstream.md"),
    ]:
        sp = root / "openspec" / "changes" / change / "specs" / cap / "spec.md"
        sp.parent.mkdir(parents=True)
        sp.write_text((FX / fname).read_text(encoding="utf-8"))


def _run_cli(root: Path, *args: str) -> str:
    r = subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(root), *args],
        # Decode as UTF-8 explicitly: cli.main() forces its own stdout to UTF-8
        # (Defect D fix), so the platform default is wrong on any host whose
        # codepage isn't UTF-8 -- notably the GitHub windows-latest runner
        # (cp1252), where the absolute `target` path's escaped backslashes
        # decode-then-reencode to different bytes and only the `validate` hash
        # (the one verb carrying that path) drifts off golden. run_cli() in
        # tests/support.py already pins UTF-8 for the same reason.
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert r.returncode == 0, f"{' '.join(args)} failed: {r.stderr}"
    # Raw + JSON-escaped path normalization lives in the shared helper -- a
    # bare native-path replace is POSIX-only, because json.dumps doubles
    # every backslash (tests/support.py's normalize_root docstring).
    out = normalize_root(r.stdout, root)
    # Normalize the envelope's tool_version the same way, and for the same
    # reason: it is machine/build state, not spec content. Without this every
    # release would re-pin _EXPECTED_HASHES["validate"] on a version bump that
    # changed no output shape at all -- the hash would stop meaning "the
    # findings projection is stable" and start meaning "nobody bumped the
    # version" (AC-FE-7).
    return _TOOL_VERSION.sub('"tool_version": "<VERSION>"', out)


def _outputs(root: Path) -> dict[str, str]:
    return {
        "validate": _run_cli(root, "validate", "--json"),
        "graph": _run_cli(root, "graph", "--format", "json"),
        "rules": _run_cli(root, "rules", "--json"),
    }


def _imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a .py file (absolute imports only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            # relative imports are intra-package; not a stdlib concern
            roots.add(node.module.split(".")[0])
    return roots


def _imported_components(path: Path) -> set[str]:
    """Every module-name component imported by a .py file.

    Catches relative imports too, so the boundary test detects
    ``from .graph import build_graph`` and ``from . import graph, cli``, not
    just absolute ``import openspec_graph.graph``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    comps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                comps.update(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                comps.update(node.module.split("."))
            elif node.level and node.level > 0:
                # `from . import a, b` — names are submodule imports
                for alias in node.names:
                    comps.add(alias.name.split(".")[0])
    return comps


# --- AC-DG-1: public import surface unchanged -------------------------------


def test_public_import_compatibility() -> None:
    # Every symbol tests and call sites import must remain importable from the
    # same paths after the facade split.
    # SpecReadError is exported from the package root alongside
    # NoOpenSpecTreeError, not only from .parse: both are exceptions a caller
    # embedding this package must be able to catch, and an asymmetric export
    # would mean the newer one is catchable only by reaching into a submodule.
    from openspec_graph import SpecReadError as _RootSpecReadError  # noqa: F401
    from openspec_graph import build_graph  # noqa: F401
    from openspec_graph.parse import (  # noqa: F401
        _MAKE_REF,
        Criterion,
        ParsedSpec,
        Requirement,
        SpecReadError,
        parse_spec,
    )
    from openspec_graph.rules import (  # noqa: F401
        Finding,
        Rule,
        evaluate,
        rule_table,
    )


# --- AC-DG-2: byte-identical CLI/graph/rules JSON output --------------------


def test_output_byte_identical() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _build_repo(root)
        outs = _outputs(root)
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in outs.items()}
    if hashes != _EXPECTED_HASHES:
        # Self-diagnosing failure: the hashes alone cannot say *what* drifted,
        # and an environment-specific divergence (this test runs on both the
        # Ubuntu matrix and the Windows leg) is undiagnosable from hex. Dump
        # the normalized output's shape for each drifting verb so the CI log
        # names the exact field, not just the mismatch.
        for verb in sorted(_EXPECTED_HASHES):
            if hashes[verb] == _EXPECTED_HASHES[verb]:
                continue
            lines = outs[verb].splitlines()
            print(f"--- {verb}: {len(lines)} lines, first/last + any path-bearing ---")
            pathy = [ln for ln in lines if "<ROOT>" in ln or "\\\\" in ln][:5]
            for ln in lines[:3] + pathy + lines[-3:]:
                print(f"    {ln}")
    assert hashes == _EXPECTED_HASHES, (
        "CLI/graph/rules JSON drifted after decomposition.\n"
        f"expected: {_EXPECTED_HASHES}\n"
        f"actual:   {hashes}\n"
        "(normalized per-verb output dumped above)"
    )


# --- AC-DG-3 (non-success): rules --json ordering must be stable ------------


def test_rules_json_ordering_stable() -> None:
    # Re-evaluating the same fixture repo twice must yield byte-identical
    # rules --json (stable ordering). A moved rule that changes ordering fails.
    with TemporaryDirectory() as td:
        root = Path(td)
        _build_repo(root)
        first = _run_cli(root, "rules", "--json")
        second = _run_cli(root, "rules", "--json")
    assert first == second, "rules --json must be byte-identical across runs"
    # And it must match the canonical hash.
    assert hashlib.sha256(first.encode()).hexdigest() == _EXPECTED_HASHES["rules"]


# --- AC-DG-4: new modules import only stdlib (no third-party deps) ----------


def test_new_modules_stdlib_only() -> None:
    stdlib = set(sys.stdlib_module_names)
    for name in _NEW_MODULES:
        roots = _imported_roots(PKG / f"{name}.py")
        third_party = roots - stdlib
        assert not third_party, (
            f"{name}.py imports non-stdlib modules: {sorted(third_party)} (R-DG-3)"
        )


def test_machinery_never_imports_subprocess() -> None:
    """DEC-MP-001 is non-negotiable: machinery.py must never shell out to
    inspect an untrusted Makefile. A static guard alongside the runtime
    monkeypatch test in test_machinery.py -- stdlib-only (AC-DG-4) alone
    would not catch this, since subprocess IS stdlib."""
    forbidden = _imported_roots(PKG / "machinery.py") & {"subprocess", "os"}
    assert not forbidden, f"machinery.py must never import {forbidden} (DEC-MP-001)"


def test_only_detect_imports_subprocess() -> None:
    """DEC-WM-008/009: detect._current_sha() (`git rev-parse HEAD`, read-only
    plumbing -- a different risk class from machinery.py's own, stronger,
    non-negotiable ban on ever invoking `make`) is the ONE new `subprocess`
    call site in `openspec_graph/`. No other module may import it without
    the same kind of explicit safety argument detect.py's own docstring
    makes. Globs dynamically (mirrors test_import_boundary_discipline), so
    a future new module is automatically covered, not just today's set."""
    offenders: dict[str, set[str]] = {}
    for path in PKG.glob("*.py"):
        if path.stem == "detect":
            continue
        forbidden = _imported_roots(path) & {"subprocess"}
        if forbidden:
            offenders[path.stem] = forbidden
    assert not offenders, f"only detect.py may import subprocess (DEC-WM-009): {offenders}"


# --- AC-DG-5: shared helper is not duplicated inline ------------------------


def test_helpers_not_duplicated_inline() -> None:
    # write_spec (imported as-is or aliased _write_spec) must come from
    # tests.support, never be redeclared -- a redeclaration silently drifts
    # from the shared version's own fixes (e.g. tests/test_graft.py's own
    # copy was missing support.py's encoding="utf-8", added specifically to
    # write non-ASCII spec content safely on Windows). Scans every test
    # module, not a fixed short list, so a future new test file is covered
    # automatically rather than needing to be added here by hand.
    offenders: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        redeclared = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name in {"write_spec", "_write_spec"}
        ]
        if redeclared:
            offenders[path.name] = redeclared
    assert not offenders, (
        f"redeclares write_spec inline instead of importing tests.support's (R-DG-4): {offenders}"
    )


# --- AC-DG-8 (non-success): detect.py and cli.py stay unsplit --------------


def test_detect_and_cli_remain_unsplit() -> None:
    # R-DG-6: detect.py and cli.py are out of scope. No new detect_*/cli_* module
    # may appear; a split that fragments either fails.
    forbidden = {p.name for p in PKG.glob("detect_*.py")} | {
        p.name for p in PKG.glob("cli_*.py")
    }
    assert not forbidden, (
        f"detect.py / cli.py were split into {sorted(forbidden)}; they are out of "
        "scope for this change (R-DG-6)"
    )


# --- AC-DG-6 (non-success): parser/rule modules must not import cli or graph


def test_import_boundary_discipline() -> None:
    # No module except cli.py and __init__.py may import cli or graph — including
    # via relative imports (from .graph import ... / from . import graph).
    offenders: dict[str, set[str]] = {}
    for path in PKG.glob("*.py"):
        stem = path.stem
        if stem in _BOUNDARY_EXEMPT:
            continue
        comps = _imported_components(path)
        bad = comps & {"cli", "graph"}
        if bad:
            offenders[stem] = bad
    assert not offenders, (
        f"modules import cli/graph (forbidden below the hub layer): {offenders} (R-DG-5)"
    )
