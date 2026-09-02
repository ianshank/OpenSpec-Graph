"""Generate ``.claude-plugin/`` manifests from the package's own facts.

Both manifests restate things that already exist elsewhere: the plugin's
version is the package version, and its name and description belong to the
skill's own frontmatter. Hand-maintaining those meant three literals to bump
on every release, with nothing but a reviewer's memory keeping them in step --
the same drift shape ``tools/render_rule_catalog.py`` exists to remove for the
rule table, and the same one ``tests/test_rule_registry_docs.py`` was added
for after it recurred three times.

So the manifests are generated: ``openspec_graph.__version__`` and
``skills/<name>/SKILL.md`` are the only sources, and a release bumps one
literal (the package version) rather than four.

Imports ``openspec_graph`` for the same documented reason
``tools/render_mermaid.py`` and ``tools/render_rule_catalog.py`` do.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import logger, read_text, repo_root, write_or_check

from openspec_graph import __version__

SKILL_NAME = "planlint-spec-governance"
MARKETPLACE_NAME = "planlint"
OWNER = "ianshank"
HOMEPAGE = f"https://github.com/{OWNER}/{MARKETPLACE_NAME}"
MAKE_TARGET = "make skill-manifests"

PLUGIN_DIR = repo_root() / ".claude-plugin"
PLUGIN_PATH = PLUGIN_DIR / "plugin.json"
MARKETPLACE_PATH = PLUGIN_DIR / "marketplace.json"
SKILL_MD = repo_root() / "skills" / SKILL_NAME / "SKILL.md"


def skill_description(text: str) -> str:
    """Pull ``description`` out of a SKILL.md's flat frontmatter.

    Deliberately the same flat, single-line-scalar assumption
    ``tests/test_agent_skill_docs.py`` documents and enforces: a folded scalar
    would silently yield the fold marker as the value, and a manifest whose
    description reads ``>-`` is worse than a build failure. Raises rather than
    defaulting, so a malformed SKILL.md stops the generator instead of
    publishing a manifest describing nothing.
    """
    if not text.startswith("---\n"):
        raise ValueError(f"{SKILL_MD} has no frontmatter block")
    block = text[4:text.index("\n---\n", 4)]
    for line in block.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "description":
            description = value.strip()
            if not description or description in (">-", "|", ">"):
                raise ValueError(
                    f"{SKILL_MD}: description must be a non-empty single-line scalar, "
                    f"got {description!r}"
                )
            return description
    raise ValueError(f"{SKILL_MD}: frontmatter has no description")


def _dump(payload: dict[str, object]) -> str:
    """Serialize with a trailing newline so the file is POSIX-clean."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_plugin(description: str) -> str:
    return _dump({
        "name": SKILL_NAME,
        "version": __version__,
        "description": description,
        "author": {"name": OWNER},
        "homepage": HOMEPAGE,
        "license": "Apache-2.0",
        "keywords": ["specs", "governance", "lint", "openspec", "speckit"],
    })


def render_marketplace(description: str) -> str:
    return _dump({
        "name": MARKETPLACE_NAME,
        "owner": {"name": OWNER, "url": f"https://github.com/{OWNER}"},
        "metadata": {
            "description": "Deterministic spec and plan governance for coding agents.",
            "version": __version__,
        },
        "plugins": [
            {
                "name": SKILL_NAME,
                # The repo root is the plugin root, so skills/ ships with it.
                "source": "./",
                "description": description,
                "version": __version__,
                "category": "workflow",
            }
        ],
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the plugin manifests.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="regenerate both manifests")
    group.add_argument(
        "--check", action="store_true", help="exit 1 if either manifest is stale"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="log what was compared, to stderr (also via PLANLINT_LOG_LEVEL=DEBUG)",
    )
    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
        logger.setLevel(logging.DEBUG)

    text = read_text(SKILL_MD)
    if not text:
        print(f"ERROR {SKILL_MD} is missing or empty", file=sys.stderr)
        return 2
    try:
        description = skill_description(text)
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    logger.debug("manifests: version=%s description=%d chars", __version__, len(description))
    # Both are regenerated even when the first is stale, so --write is not
    # order-dependent and --check reports every stale file in one run rather
    # than one per invocation.
    codes = [
        write_or_check(PLUGIN_PATH, render_plugin(description),
                       write=args.write, label=MAKE_TARGET),
        write_or_check(MARKETPLACE_PATH, render_marketplace(description),
                       write=args.write, label=MAKE_TARGET),
    ]
    return max(codes)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
