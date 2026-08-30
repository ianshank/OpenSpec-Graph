"""Structured debug logging for the ``planlint`` CLI.

Logging goes to **stderr only**. CLI machine-readable output (`--json`,
`graph --format json`) goes to stdout and must stay pure/parseable, so no log
records ever reach stdout. The level is controlled by:

  - the global ``--verbose`` / ``-v`` flag (DEBUG), or
  - the ``PLANLINT_LOG_LEVEL`` environment variable (DEBUG/INFO/WARNING/ERROR),
    which the flag overrides when set. The legacy ``SPECGRAPH_LOG_LEVEL`` is
    still accepted for backwards compatibility.

Level precedence (highest wins): ``--verbose`` > ``PLANLINT_LOG_LEVEL`` >
``SPECGRAPH_LOG_LEVEL`` (legacy) > default WARNING. The default keeps the CLI
quiet for normal use; diagnostics surface only when a contributor asks for them.
"""

from __future__ import annotations

import logging
import os

# Preferred env var (new name); the legacy name is kept as a fallback so
# existing CI/setups that set SPECGRAPH_LOG_LEVEL keep working.
_ENV_VARS = ("PLANLINT_LOG_LEVEL", "SPECGRAPH_LOG_LEVEL")
_DEFAULT_LEVEL = logging.WARNING


def level_from(verbose: bool, env: str | None = None) -> int:
    """Resolve the effective log level. ``verbose`` wins over the env var."""
    if verbose:
        return logging.DEBUG
    raw = env if env is not None else ""
    if not raw:
        # First set env var wins; preferred name takes precedence over legacy.
        for name in _ENV_VARS:
            raw = os.environ.get(name, "")
            if raw:
                break
    env_value = raw.upper()
    # logging.getLevelNamesMapping() is 3.11+; the repo supports 3.10, so use a
    # stdlib mapping that exists on every supported version.
    named = logging.getLevelName(env_value)
    return int(named) if isinstance(named, int) else _DEFAULT_LEVEL


def configure(verbose: bool = False) -> logging.Logger:
    """Configure the ``planlint`` logger to write to stderr at the resolved level.

    Idempotent: calling repeatedly only adjusts the level, never stacks handlers.
    Returns the package logger so call sites can ``logger.debug(...)``.
    """
    logger = logging.getLogger("planlint")
    level = level_from(verbose)
    logger.setLevel(level)

    # Replace any existing handler so re-config (e.g. in tests) does not double-log.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler()  # defaults to sys.stderr
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False  # stderr only; never bubble to the root logger/stdout
    return logger
