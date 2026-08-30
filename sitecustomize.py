"""Enable coverage measurement inside CLI subprocesses spawned by tests.

Python's site machinery auto-imports this module on interpreter startup
whenever the current working directory is on ``sys.path`` -- true for
``python -m openspec_graph.cli ...``, which is exactly how
``tests/support.py``'s ``run_cli()`` launches the CLI as a real subprocess
to test its process-level behavior. Without this hook, pytest-cov is
structurally blind to every line reachable only through those subprocess
invocations, no matter how thoroughly they are tested.

A no-op whenever ``COVERAGE_PROCESS_START`` is unset, so a normal
``python -m openspec_graph.cli`` invocation outside the test suite is
unaffected. See https://coverage.readthedocs.io/en/latest/subprocess.html.
"""

from __future__ import annotations

import coverage

coverage.process_startup()
