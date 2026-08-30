"""Structured debug logging for the ``specgraph`` CLI.

Logging goes to **stderr only**. CLI machine-readable output (`--json`,
`graph --format json`) goes to stdout and must stay pure/parseable, so no log
records ever reach stdout. The level is controlled by:

  - the global ``--verbose`` / ``-v`` flag (DEBUG), or
  - the ``SPECGRAPH_LOG_LEVEL`` environment variable (DEBUG/INFO/WARNING/ERROR),
    which the flag overrides when set.

Level precedence (highest wins): ``--verbose`` > ``SPECGRAPH_LOG_LEVEL`` > default
WARNING. The default keeps the CLI quiet for normal use; diagnostics surface
only when a contributor asks for them.
"""

from __future__ import annotations

import logging
import os

_ENV_VAR = "SPECGRAPH_LOG_LEVEL"
_DEFAULT_LEVEL = logging.WARNING


def level_from(verbose: bool, env: str | None = None) -> int:
    """Resolve the effective log level. ``verbose`` wins over the env var."""
    if verbose:
        return logging.DEBUG
    env_value = (env if env is not None else os.environ.get(_ENV_VAR, "")).upper()
    # logging.getLevelNamesMapping() is 3.11+; the repo supports 3.10, so use a
    # stdlib mapping that exists on every supported version.
    named = logging.getLevelName(env_value)
    return int(named) if isinstance(named, int) else _DEFAULT_LEVEL


def configure(verbose: bool = False) -> logging.Logger:
    """Configure the ``specgraph`` logger to write to stderr at the resolved level.

    Idempotent: calling repeatedly only adjusts the level, never stacks handlers.
    Returns the package logger so call sites can ``logger.debug(...)``.
    """
    logger = logging.getLogger("specgraph")
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
