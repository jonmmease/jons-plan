#!/usr/bin/env python3
"""
PreToolUse hook to protect jons-plan metadata files from direct editing.

These files should only be modified via the plan.py CLI to ensure proper
state management, logging, and validation.

Protected files:
- state.json      - Workflow state (current phase, history)
- tasks.json      - Task definitions and statuses
- workflow.toml   - Phase definitions
- active-plan     - Active plan pointer
- dead-ends.json  - Dead-end tracking

When Claude attempts to directly edit these files, the hook blocks the
operation and provides guidance on which CLI command to use instead.
"""

import json
import os
import sys


# Protected filenames in .claude/jons-plan/ directories
PROTECTED_FILES = {
    "state.json": "Use 'uv run plan.py enter-phase <phase>' to change phases",
    "tasks.json": "Use 'uv run plan.py add-bulk-tasks' to create/add tasks, 'set-status <task-id> <status>' to update",
    "workflow.toml": "workflow.toml should not be modified during execution",
    "active-plan": "Use 'uv run plan.py set-active <plan-name>' to change active plan",
    "dead-ends.json": "Use 'uv run plan.py add-dead-end ...' to record dead ends",
}


def is_in_jons_plan_dir(file_path: str) -> bool:
    """Check if file is within a .claude/jons-plan/ directory."""
    # Normalize path for comparison
    normalized = os.path.normpath(file_path)
    return "/.claude/jons-plan/" in normalized or "\\.claude\\jons-plan\\" in normalized


def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Invalid input - allow the operation (don't block on hook errors)
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only check Write and Edit tools
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    # Get file path from tool input
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check if this is a jons-plan managed file
    if not is_in_jons_plan_dir(file_path):
        sys.exit(0)

    # Get filename
    filename = os.path.basename(file_path)

    # Check if it's a protected file
    if filename in PROTECTED_FILES:
        cli_hint = PROTECTED_FILES[filename]
        operation = "rewrite" if tool_name == "Write" else "modify"

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"BLOCKED: Cannot {operation} '{filename}' directly using the {tool_name} tool.\n\n"
                    f"This file is managed by jons-plan and must be modified via CLI commands.\n"
                    f"Hint: {cli_hint}\n\n"
                    f"See CLAUDE.md for valid task statuses and CLI commands."
                ),
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # Allow edits to other files in jons-plan directories
    # (like progress.txt, research.md, findings.md, etc.)
    sys.exit(0)


if __name__ == "__main__":
    main()
