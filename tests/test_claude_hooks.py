"""The Claude Code PostToolUse hook is wired, and nudges for what it claims to.

``.claude/hooks/nudge_rule_registry.sh`` is a third gate layer (see
``docs/hooks.md``): it fires inside an agentic session right after a file
write and reminds the agent which check that file class needs. It is a shell
script nothing else executes, so until now it could drift from
``docs/hooks.md``'s bullet list, lose a case, or stop being referenced from
``.claude/settings.json`` with every other gate green -- the same argument
``tests/test_agent_skill_docs.py`` makes for the skill files.

Each case below feeds the script the JSON shape Claude Code sends, for one
representative path per documented class, and asserts a reason comes back
naming the check to run. A path in no class must produce nothing: a hook that
nags on every write gets ignored, then disabled.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "nudge_rule_registry.sh"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
HOOKS_DOC = REPO_ROOT / "docs" / "hooks.md"

# One representative path per documented class -> a token the reason must
# carry (the command or checklist it points the agent at). Keeping the token
# to the *remedy* rather than the full sentence lets the wording evolve
# without turning this into a prose snapshot.
NUDGED: dict[str, str] = {
    "openspec_graph/rules_generic.py": "tests/test_rule_registry_docs.py",
    "Makefile": "make thresholds",
    ".github/workflows/ci.yml": "make thresholds",
    "skills/planlint-spec-governance/SKILL.md": "tests/test_skill_contract.py",
    ".claude-plugin/plugin.json": "tests/test_skill_contract.py",
    "evals/waive-all-g003/prompt.md": "tests/test_agent_artifacts.py",
    "README.md": "tests/test_adopter_urls.py",
    "llms.txt": "tests/test_adopter_urls.py",
    "openspec/changes/add-witness-mode/specs/witness-mode/spec.md": "validate",
    "tests/corpus/targets/bom-rule-first/expected.json": "tests/test_detect_corpus.py",
    "tests/fixtures/phrasing/criteria.jsonl": "make matcher-accuracy",
    "openspec_graph/parse_semantics.py": "make matcher-accuracy",
}

# Paths that must stay quiet. Each is a file class that has its own gate
# already and where a nudge would be noise.
QUIET = (
    "openspec_graph/cli.py",
    "tests/test_graph.py",
    "docs/aqa.md",
    "tools/check_docs.py",
    ".claude/skills/planlint-add-rule/SKILL.md",
)

bash = shutil.which("bash")
needs_bash = pytest.mark.skipif(bash is None, reason="bash not on PATH (capability probe)")


def _run(file_path: str) -> str:
    """Feed the hook one PostToolUse payload and return its stdout."""
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": file_path}})
    result = subprocess.run(
        [bash or "bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
    return result.stdout


def test_settings_wires_the_hook_script() -> None:
    """The script is only a gate if settings.json actually names it."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entry in settings["hooks"]["PostToolUse"]
        for hook in entry["hooks"]
        if hook.get("type") == "command"
    ]
    assert any(cmd.endswith("/.claude/hooks/nudge_rule_registry.sh") for cmd in commands), (
        f"settings.json does not run the nudge hook: {commands}"
    )
    matchers = [entry["matcher"] for entry in settings["hooks"]["PostToolUse"]]
    assert any("Edit" in m and "Write" in m for m in matchers), matchers


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX execute bit")
def test_hook_script_is_executable() -> None:
    assert os.access(HOOK, os.X_OK), f"{HOOK.name} is not executable; Claude Code cannot run it"


@needs_bash
@pytest.mark.parametrize(("path", "remedy"), sorted(NUDGED.items()))
def test_each_documented_file_class_is_nudged(path: str, remedy: str) -> None:
    out = _run(str(REPO_ROOT / path))
    assert out, f"no nudge for {path}"
    reason = json.loads(out)["reason"]
    assert remedy in reason, f"{path}: nudge does not name {remedy!r}:\n{reason}"


@needs_bash
@pytest.mark.parametrize("path", QUIET)
def test_unrelated_paths_are_not_nudged(path: str) -> None:
    assert _run(str(REPO_ROOT / path)) == "", f"{path} should not be nudged"


@needs_bash
def test_windows_style_paths_are_normalised() -> None:
    """A JSON-escaped backslash path must hit the same case as a POSIX one.

    ``json.dumps`` doubles each backslash on the wire, exactly as Claude Code
    does; the script collapses both that form and a bare single backslash.
    """
    windows = "C:\\repo\\openspec_graph\\rules_generic.py"
    out = _run(windows)
    assert out and "tests/test_rule_registry_docs.py" in json.loads(out)["reason"]


@needs_bash
def test_every_emitted_reason_is_valid_json() -> None:
    """The reasons are hand-emitted without jq; one stray quote breaks them all."""
    for path in NUDGED:
        json.loads(_run(str(REPO_ROOT / path)))


def test_docs_list_every_hook_case_the_script_implements() -> None:
    """docs/hooks.md's bullet list and the script's case list must agree.

    Checked by remedy token rather than by parsing bash: every distinct remedy
    the script points at must be mentioned in the doc's hook section.
    """
    doc = HOOKS_DOC.read_text(encoding="utf-8")
    for remedy in sorted(set(NUDGED.values())):
        assert remedy in doc, f"docs/hooks.md does not mention the {remedy!r} nudge"
