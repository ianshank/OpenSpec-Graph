"""Shared test helpers for the planlint test suite.

Only genuinely-duplicated helpers live here. Tailored per-test fixture *variants*
( GOOD_HARNESS, MAKEFILE, etc.) stay inline in the test modules that use them,
because each variant asserts behavior specific to its content.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def supports_symlinks() -> bool:
    """Whether this process can create a filesystem symlink right now.

    Windows requires either Administrator rights or Developer Mode enabled
    (SeCreateSymbolicLinkPrivilege) to create any symlink at all, unlike
    POSIX where an unprivileged user always can -- a capability probe, not a
    bare ``sys.platform`` check, so a Windows box that *does* have one of
    those enabled still runs the tests this guards.
    """
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "target"
        target.write_text("")
        try:
            (Path(td) / "link").symlink_to(target)
        except (OSError, NotImplementedError):
            # OSError: the common case (Windows without the privilege).
            # NotImplementedError: Path.symlink_to()'s own fallback when
            # os.symlink doesn't exist on this platform at all -- letting
            # this one escape would crash the *importing* test module at
            # collection time (see the module-level probes in
            # test_witness.py/test_graft.py), the exact all-or-nothing
            # failure this capability probe exists to avoid.
            return False
        return True


def load_tool(name: str, filename: str) -> ModuleType:
    """Import a ``tools/`` script by path, in-process, under ``name``.

    In-process rather than as a subprocess so coverage sees the module and
    its functions can be called directly. Registered in ``sys.modules`` so a
    script that imports a sibling (``from _common import ...``) resolves it
    the same way twice. Shared by the three test modules that exercise the
    gate scripts; the previous three verbatim copies are exactly what this
    file exists to hold.
    """
    path = Path(__file__).resolve().parent.parent / "tools" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    """Write a spec body into ``openspec/changes/<change>/specs/<capability>/spec.md``."""
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit encoding matches every read/write in openspec_graph itself
    # (parse.py, detect.py, scaffold.py all pass encoding="utf-8") -- without
    # it, Path.write_text's platform-default encoding (e.g. cp1252 on
    # Windows) can't represent arbitrary non-ASCII spec content and raises
    # UnicodeEncodeError before the CLI under test ever runs.
    path.write_text(body, encoding="utf-8")
    return path


def write_speckit_spec(repo: Path, feature: str, body: str) -> Path:
    """Write a spec body into ``specs/<feature>/spec.md`` (SpecKit layout --
    no ``changes/`` nesting, no ``openspec/`` ancestor)."""
    path = repo / "specs" / feature / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the planlint CLI against ``repo`` and return the completed process.

    Injects ``COVERAGE_PROCESS_START`` so this subprocess's coverage is
    tracked, not just the parent test process's -- pytest-cov's own
    auto-installed subprocess hook (a .pth file in site-packages, active
    whenever this env var is set) reads it, no project-specific hook file
    needed. A caller-supplied ``env`` value for the same key always wins,
    never overridden.
    """
    subprocess_env = dict(os.environ if env is None else env)
    subprocess_env.setdefault("COVERAGE_PROCESS_START", str(_PYPROJECT))
    return subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(repo), *args],
        capture_output=True, text=True, check=False, env=subprocess_env,
        # cli.py's main() always forces its own stdout/stderr to UTF-8
        # (Defect D fix), regardless of the child's ambient encoding -- so
        # the parent side must decode as UTF-8 too, not whatever
        # locale.getpreferredencoding() would otherwise pick (e.g. cp1252 on
        # Windows), or non-ASCII content round-trips as mojibake here even
        # though the child emitted it correctly.
        encoding="utf-8",
    )


def normalize_root(text: str, root: Path) -> str:
    """Replace ``root`` with ``<ROOT>`` in CLI output, raw and JSON-escaped.

    ``json.dumps`` escapes each backslash as ``\\\\``, so on Windows the raw
    native path never textually matches inside ``--json`` output -- a bare
    ``text.replace(str(root), ...)`` normalizes POSIX only. And the CLI emits
    ``Path(args.target).resolve()``, whose spelling can differ from the
    ``str(root)`` a test built (8.3 short names, junctions, a symlinked
    ``TemporaryDirectory``) -- so a single fixed spelling can be a silent
    no-op, leaving the absolute path in the hash (this exact failure shipped
    the windows-latest CI leg red). Try every plausible spelling of the same
    directory, in both raw and JSON-escaped form, so the absolute path is
    always erased regardless of how ``resolve()`` rendered it.
    """
    spellings = {str(root), str(root.resolve())}
    for spelling in spellings:
        text = text.replace(spelling, "<ROOT>").replace(spelling.replace("\\", "\\\\"), "<ROOT>")
    return text
