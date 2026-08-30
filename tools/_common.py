"""Small shared helpers for the ``tools/`` gate scripts.

These scripts are intentionally dependency-free (stdlib only) so they run in a
bare CI runner. Anything repeated across them lives here so a fix to repo-root
discovery or text reading is made once.
"""

from __future__ import annotations

from pathlib import Path

# tools/ sits one level below the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """Return the repository root (the parent of the ``tools/`` directory)."""
    return REPO_ROOT


def read_text(path: Path) -> str:
    """Read a file as UTF-8, returning ``\"\"`` if it is missing.

    Centralizes the ``encoding=\"utf-8\"`` convention used by every gate script
    so encoding is never left to the platform default.
    """
    return path.read_text(encoding="utf-8") if path.exists() else ""
