#!/usr/bin/env python3
"""
PreToolUse hook to protect jons-plan metadata files from direct editing.

These files should only be modified via the plan.py CLI to ensure proper
state management, logging, and validation.

Protected files (always blocked):
- state.json      - Workflow state (current phase, history)
- workflow.toml   - Phase definitions
- active-plan     - Active plan pointer
- dead-ends.json  - Dead-end tracking

Validated files (allowed if valid):
- tasks.json      - Task definitions (validated against schema)
"""

import json
import os
import re
import sys
from pathlib import Path


# Files that are always blocked (must use CLI)
ALWAYS_BLOCKED = {
    "state.json": "Use 'uv run plan.py enter-phase <phase>' to change phases",
    "workflow.toml": "workflow.toml should not be modified during execution",
    "active-plan": "Use 'uv run plan.py set-active <plan-name>' to change active plan",
    "dead-ends.json": "Use 'uv run plan.py add-dead-end ...' to record dead ends",
}

# Valid task statuses
VALID_STATUSES = {"todo", "in-progress", "done", "blocked"}

# Valid task types
VALID_TASK_TYPES = {"cache-reference", "prototype"}

# Valid models
VALID_MODELS = {"sonnet", "haiku", "opus"}

# Task ID pattern (lowercase alphanumeric with hyphens)
TASK_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")


def is_in_jons_plan_dir(file_path: str) -> bool:
    """Check if file is within a .claude/jons-plan/ directory."""
    normalized = os.path.normpath(file_path)
    return "/.claude/jons-plan/" in normalized or "\\.claude\\jons-plan\\" in normalized


def validate_task(task: dict, index: int, all_ids: set) -> list[str]:
    """Validate a single task and return list of errors."""
    errors = []
    prefix = f"Task {index}"

    if not isinstance(task, dict):
        return [f"{prefix}: Must be an object"]

    task_id = task.get("id")
    if task_id:
        prefix = f"Task '{task_id}'"

    # Required fields
    if "id" not in task:
        errors.append(f"{prefix}: Missing required field 'id'")
    elif not isinstance(task["id"], str):
        errors.append(f"{prefix}: 'id' must be a string")
    elif not TASK_ID_PATTERN.match(task["id"]):
        errors.append(f"{prefix}: 'id' must be lowercase alphanumeric with hyphens (got '{task['id']}')")

    if "description" not in task:
        errors.append(f"{prefix}: Missing required field 'description'")
    elif not isinstance(task["description"], str) or not task["description"].strip():
        errors.append(f"{prefix}: 'description' must be a non-empty string")

    if "status" not in task:
        errors.append(f"{prefix}: Missing required field 'status'")
    elif task["status"] not in VALID_STATUSES:
        errors.append(f"{prefix}: Invalid status '{task['status']}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

    # Optional fields with type checking
    if "type" in task and task["type"] not in VALID_TASK_TYPES:
        errors.append(f"{prefix}: Invalid type '{task['type']}'. Must be one of: {', '.join(sorted(VALID_TASK_TYPES))}")

    if "steps" in task:
        if not isinstance(task["steps"], list):
            errors.append(f"{prefix}: 'steps' must be an array")
        elif not all(isinstance(s, str) for s in task["steps"]):
            errors.append(f"{prefix}: All items in 'steps' must be strings")

    if "parents" in task:
        if not isinstance(task["parents"], list):
            errors.append(f"{prefix}: 'parents' must be an array")
        elif not all(isinstance(p, str) for p in task["parents"]):
            errors.append(f"{prefix}: All items in 'parents' must be strings")

    if "context_artifacts" in task:
        if not isinstance(task["context_artifacts"], list):
            errors.append(f"{prefix}: 'context_artifacts' must be an array")
        elif not all(isinstance(a, str) for a in task["context_artifacts"]):
            errors.append(f"{prefix}: All items in 'context_artifacts' must be strings")

    if "subagent" in task and not isinstance(task["subagent"], str):
        errors.append(f"{prefix}: 'subagent' must be a string")

    if "subagent_prompt" in task and not isinstance(task["subagent_prompt"], str):
        errors.append(f"{prefix}: 'subagent_prompt' must be a string")

    if "model" in task and task["model"] not in VALID_MODELS:
        errors.append(f"{prefix}: Invalid model '{task['model']}'. Must be one of: {', '.join(sorted(VALID_MODELS))}")

    if "question" in task and not isinstance(task["question"], str):
        errors.append(f"{prefix}: 'question' must be a string")

    if "hypothesis" in task and not isinstance(task["hypothesis"], str):
        errors.append(f"{prefix}: 'hypothesis' must be a string")

    if "inject_project_context" in task and not isinstance(task["inject_project_context"], bool):
        errors.append(f"{prefix}: 'inject_project_context' must be a boolean")

    # Check for unknown fields
    known_fields = {
        "id", "description", "status", "type", "steps", "parents",
        "context_artifacts", "subagent", "subagent_prompt", "model",
        "question", "hypothesis", "inject_project_context"
    }
    unknown = set(task.keys()) - known_fields
    if unknown:
        errors.append(f"{prefix}: Unknown fields: {', '.join(sorted(unknown))}")

    return errors


def validate_tasks_json(content: str) -> tuple[bool, list[str]]:
    """Validate tasks.json content. Returns (is_valid, errors)."""
    errors = []

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Must be an array
    if not isinstance(data, list):
        return False, ["tasks.json must be a JSON array of tasks"]

    # Collect all task IDs for duplicate checking
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

    # Validate each task
    for i, task in enumerate(data):
        task_errors = validate_task(task, i, all_ids)
        errors.extend(task_errors)

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
                        "To add tasks, use Write to replace the entire file with valid JSON.\n"
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
            # Get path to schema for reference
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
            schema_hint = ""
            if plugin_root:
                schema_path = os.path.join(plugin_root, "schemas", "tasks-schema.json")
                if os.path.exists(schema_path):
                    schema_hint = f"\n\nSee schema at: {schema_path}"

            error_list = "\n".join(f"  - {e}" for e in errors[:10])  # Limit to 10 errors
            if len(errors) > 10:
                error_list += f"\n  ... and {len(errors) - 10} more errors"

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
