"""Secret-scanning gate (AC-EH-3).

Prefers **gitleaks** when installed (the real, config-driven scanner used in CI).
Falls back to a deterministic Python high-entropy pattern scan over
git-tracked files so ``make security`` is a real gate even on a machine without
the gitleaks binary. Either way: a committed secret fails non-zero.

The gitleaks config lives in ``.gitleaks.toml``; the fallback honours the same
allowlist (paths under ``tests/`` fixtures) so a fake key used by a test does not
trip the gate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import repo_root

REPO_ROOT = repo_root()
GITLEAKS_CONFIG = REPO_ROOT / ".gitleaks.toml"

# High-entropy token patterns for the fallback scanner. Intentionally narrow:
# we want a real committed key (AKIA..., github_pat_..., sk-..., ghp_...) to
# trip, not a version string or a hash in a lockfile.
_FALLBACK_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),              # AWS access key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),   # GitHub token
    re.compile(r"github_pat_[A-Za-z0-9_]{82,}"),  # GitHub fine-grained PAT
    re.compile(r"sk-[A-Za-z0-9]{20,}"),          # OpenAI-style secret
    re.compile(r"xox[bpras]-[A-Za-z0-9-]+"),     # Slack token
]

# Paths the fallback scanner skips: vendored, generated, or test fixtures that
# legitimately contain fake secrets.
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".ruff_cache", ".mypy_cache", "node_modules"}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]


def _is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    # Test sources are scanned on purpose: a real secret committed in a test
    # must fail the gate. Only vendored/generated dirs are skipped.
    return any(part in _SKIP_DIRS for part in rel.parts)


def fallback_scan() -> list[str]:
    findings: list[str] = []
    for path in _tracked_files():
        if not path.is_file() or _is_allowlisted(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in _FALLBACK_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0)[:12] + "..."
                findings.append(f"{path.relative_to(REPO_ROOT)}: potential secret ({snippet})")
    return findings


def run_gitleaks() -> tuple[int, str]:
    binary = shutil.which("gitleaks")
    if binary is None:
        return -1, "gitleaks not installed"
    result = subprocess.run(
        [binary, "detect", "--source", str(REPO_ROOT), "--config", str(GITLEAKS_CONFIG), "--no-banner"],
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout + result.stderr


def main(argv: list[str]) -> int:
    code, output = run_gitleaks()
    if code == 0:
        print("PASS: gitleaks found no secrets")
        return 0
    if code == -1:
        # gitleaks absent locally — use the deterministic fallback so the gate
        # still runs. CI uses real gitleaks; this is the local safety net.
        findings = fallback_scan()
        if findings:
            for message in findings:
                print(f"FAIL: {message}")
            return 1
        print("PASS: no secrets found (gitleaks absent, fallback scan clean)")
        return 0
    # gitleaks ran and found something.
    print("FAIL: gitleaks detected secrets")
    print(output)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
