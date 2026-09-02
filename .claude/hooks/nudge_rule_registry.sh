#!/bin/bash
# PostToolUse(Edit|Write): nudge after editing a rules module or a
# threshold-bearing config file -- this exact drift class (doc locations
# falling out of sync with rules.RULES; a hard-coded threshold creeping into
# Makefile/CI YAML) has recurred multiple times in this repo's own history
# (see tests/test_rule_registry_docs.py's docstring, tools/check_no_hardcoded_thresholds.py).
# "decision": "block" here is PostToolUse's contract for surfacing `reason`
# to Claude prominently -- it does NOT undo the edit (PostToolUse fires
# after the write already landed, so there is nothing left to prevent). It
# is a strong reminder, not an actual block, despite the JSON key's name.
#
# No jq dependency: not guaranteed to be on PATH (confirmed absent in at
# least one real dev environment this repo is used from). file_path is
# extracted with grep/sed and the response JSON is hand-emitted -- safe here
# since every reason string below is plain text with no embedded double
# quotes or backslashes.
INPUT=$(cat)
FILE=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"(.*)"/\1/')
if [ -z "$FILE" ]; then
  FILE=$(echo "$INPUT" | grep -o '"path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"(.*)"/\1/')
fi
# Normalize separators before matching -- file_path may arrive JSON-escaped
# (a Windows path's "\\" doubled to "\\\\") or already single-backslash;
# collapse both forms to "/" so a forward-slash-only glob still matches.
FILE_NORM=$(printf '%s' "$FILE" | sed 's/\\\\/\//g; s/\\/\//g')

case "$FILE_NORM" in
  */openspec_graph/rules.py|*/openspec_graph/rules_*.py)
    printf '{"decision": "block", "reason": "You just edited a rules module. Before finishing: regenerate tests/baseline_rules.json via `planlint rules --json > tests/baseline_rules.json`, then run `make skill-catalog` to regenerate the distributable skill rule catalog, then run `pytest tests/test_rule_registry_docs.py tests/test_skill_contract.py` and fix every doc location they report out of sync (see the planlint-add-rule skill)."}'
    exit 0
    ;;
  */Makefile|*/.github/workflows/*.yml)
    printf '{"decision": "block", "reason": "You just edited a Makefile or CI workflow file. Run `make thresholds` (or `python tools/check_no_hardcoded_thresholds.py` if make is unavailable) before finishing -- this repo requires every threshold to be read from its real locator, never hard-coded here."}'
    exit 0
    ;;
  */skills/*|*/.claude-plugin/*)
    printf '{"decision": "block", "reason": "You just edited the distributable Agent Skill or its plugin manifests. These are prose and metadata an external agent acts on, so nothing else catches drift in them. Before finishing: run `pytest tests/test_skill_contract.py tests/test_agent_skill_docs.py` -- they pin the read-only claim, the per-verb exit-code messages, the generated rule catalog, and manifest/version agreement."}'
    exit 0
    ;;
  */openspec/changes/*/specs/*/spec.md)
    printf '{"decision": "block", "reason": "You just edited a change-package spec.md -- the exact file planlint dialect-sniffs. Quoting a dialect marker as prose (e.g. a heading name in backticks) can misclassify this spec as the dialect it merely describes, the self-referential trap this repo has hit twice. Before finishing: run `planlint --target . validate --fail-on ERROR` (or `make validate`) and confirm the dialect/finding count is what you expect."}'
    exit 0
    ;;
esac

exit 0
