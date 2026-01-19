#!/usr/bin/env python3
"""
PreToolUse hook to protect jons-plan metadata files from direct editing.

These files should only be modified via the plan.py CLI to ensure proper
state management, logging, and validation.

Protected files (always blocked):
- state.json      - Workflow state (current phase, history)
- active-plan     - Active plan pointer
- dead-ends.json  - Dead-end tracking

Conditionally blocked:
- workflow.toml   - Blocked during execution (proceed mode), allowed during plan creation

Validated files (allowed if valid):
- tasks.json      - Task definitions (validated against JSON schema)
"""

import json
import os
import sys
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Files that are always blocked (must use CLI)
ALWAYS_BLOCKED = {
    "state.json": "Use 'uv run plan.py enter-phase <phase>' to change phases",
    "active-plan": "Use 'uv run plan.py set-active <plan-name>' to change active plan",
    "dead-ends.json": "Use 'uv run plan.py add-dead-end ...' to record dead ends",
}

# Files blocked only during execution (proceed mode)
BLOCKED_DURING_EXECUTION = {
    "workflow.toml": "workflow.toml should not be modified during task execution",
}


def is_in_jons_plan_dir(file_path: str) -> bool:
    """Check if file is within a .claude/jons-plan/ directory."""
    normalized = os.path.normpath(file_path)
    return "/.claude/jons-plan/" in normalized or "\\.claude\\jons-plan\\" in normalized


def get_jons_plan_root(file_path: str) -> Path | None:
    """Find the .claude/jons-plan directory from a file path within it."""
    path = Path(file_path).resolve()
    # Walk up to find .claude/jons-plan
    for parent in path.parents:
        jons_plan_dir = parent / ".claude" / "jons-plan"
        if jons_plan_dir.is_dir():
            return jons_plan_dir
    return None


def get_session_mode(file_path: str) -> str | None:
    """Get the current session mode from the jons-plan directory."""
    jons_plan_dir = get_jons_plan_root(file_path)
    if not jons_plan_dir:
        return None

    mode_file = jons_plan_dir / "session-mode"
    if mode_file.exists():
        try:
            return mode_file.read_text().strip()
        except OSError:
            return None
    return None


def get_schema_path() -> Path | None:
    """Get path to tasks schema file."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if plugin_root:
        schema_path = Path(plugin_root) / "schemas" / "tasks-schema.json"
        if schema_path.exists():
            return schema_path
    # Fallback: relative to this script
    script_dir = Path(__file__).parent.parent
    schema_path = script_dir / "schemas" / "tasks-schema.json"
    if schema_path.exists():
        return schema_path
    return None


def validate_tasks_json(content: str) -> tuple[bool, list[str]]:
    """Validate tasks.json content against JSON schema. Returns (is_valid, errors)."""
    errors = []

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Must be an array (basic check before schema validation)
    if not isinstance(data, list):
        return False, ["tasks.json must be a JSON array of tasks"]

    # Load and validate against schema
    schema_path = get_schema_path()
    if not schema_path:
        errors.append("Warning: Could not find tasks-schema.json, skipping schema validation")
        return True, errors  # Allow but warn

    if not HAS_JSONSCHEMA:
        errors.append("Warning: jsonschema not installed, skipping schema validation")
        return True, errors  # Allow but warn

    try:
        schema = json.loads(schema_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        errors.append(f"Warning: Could not load schema: {e}")
        return True, errors  # Allow but warn

    # Validate against schema
    validator = jsonschema.Draft7Validator(schema)
    schema_errors = list(validator.iter_errors(data))

    if schema_errors:
        for error in schema_errors[:10]:  # Limit to 10 errors
            # Format the error path nicely
            path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            errors.append(f"[{path}] {error.message}")
        if len(schema_errors) > 10:
            errors.append(f"... and {len(schema_errors) - 10} more errors")
        return False, errors

    # Additional validations not easily expressed in JSON schema

    # Check for duplicate IDs
    all_ids = set()
    duplicate_ids = set()
    for task in data:
        if isinstance(task, dict) and "id" in task:
            tid = task["id"]
            if tid in all_ids:
                duplicate_ids.add(tid)
            all_ids.add(tid)

    if duplicate_ids:
        errors.append(f"Duplicate task IDs: {', '.join(sorted(duplicate_ids))}")

    # Validate parent references
    for task in data:
        if isinstance(task, dict) and "parents" in task:
            task_id = task.get("id", "unknown")
            for parent_id in task.get("parents", []):
                if parent_id not in all_ids:
                    errors.append(f"Task '{task_id}': Parent '{parent_id}' not found in tasks")

    return len(errors) == 0, errors


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

    # Check if it's an always-blocked file
    if filename in ALWAYS_BLOCKED:
        cli_hint = ALWAYS_BLOCKED[filename]
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

    # Check if it's a file blocked only during execution (proceed mode)
    if filename in BLOCKED_DURING_EXECUTION:
        session_mode = get_session_mode(file_path)
        if session_mode == "proceed":
            cli_hint = BLOCKED_DURING_EXECUTION[filename]
            operation = "rewrite" if tool_name == "Write" else "modify"

            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"BLOCKED: Cannot {operation} '{filename}' during task execution.\n\n"
                        f"This file is protected while in proceed mode.\n"
                        f"Hint: {cli_hint}\n\n"
                        f"See CLAUDE.md for workflow management commands."
                    ),
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        # Not in proceed mode - allow the write
        sys.exit(0)

    # Special handling for tasks.json - validate and allow if valid
    if filename == "tasks.json":
        # Only allow Write (full replacement), not Edit (partial modification)
        if tool_name == "Edit":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "BLOCKED: Cannot use Edit tool on tasks.json.\n\n"
                        "To modify task status, use: uv run plan.py set-status <task-id> <status>\n"
                        "To rewrite tasks, use Write tool with the complete file.\n"
                        "To add a single task, use: uv run plan.py add-task <json-file>"
                    ),
                }
            }
            print(json.dumps(output))
            sys.exit(0)

        # For Write, validate the content
        content = tool_input.get("content", "")
        is_valid, errors = validate_tasks_json(content)

        if not is_valid:
            schema_path = get_schema_path()
            schema_hint = f"\n\nSchema: {schema_path}" if schema_path else ""

            error_list = "\n".join(f"  - {e}" for e in errors)

            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"BLOCKED: Invalid tasks.json content.\n\n"
                        f"Validation errors:\n{error_list}\n\n"
                        f"Required fields: id, description, status\n"
                        f"Valid statuses: todo, in-progress, done, blocked{schema_hint}"
                    ),
                }
            }
            print(json.dumps(output))
            sys.exit(0)

        # Valid - allow the write
        sys.exit(0)

    # Allow edits to other files in jons-plan directories
    # (like progress.txt, research.md, findings.md, etc.)
    sys.exit(0)


if __name__ == "__main__":
    main()
