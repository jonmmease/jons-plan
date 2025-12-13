#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
Plan management CLI for long-running agent harness.

Usage: uv run ~/.claude-plugins/jons-plan/plan.py <subcommand> [args]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def get_project_dir() -> Path:
    """Get project directory (where .claude/ lives)."""
    # Start from current directory and look for .claude/
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    # Fallback to cwd
    return Path.cwd()


def get_active_plan(project_dir: Path) -> str | None:
    """Get active plan name from .claude/jons-plan/active-plan file."""
    active_plan_file = project_dir / ".claude" / "jons-plan" / "active-plan"
    if active_plan_file.exists():
        return active_plan_file.read_text().strip()
    return None


def get_active_plan_dir(project_dir: Path) -> Path | None:
    """Get the active plan directory path."""
    plan_name = get_active_plan(project_dir)
    if plan_name:
        plan_dir = project_dir / ".claude" / "jons-plan" / "plans" / plan_name
        if plan_dir.is_dir():
            return plan_dir
    return None


def get_tasks(plan_dir: Path) -> list[dict]:
    """Load tasks from tasks.json."""
    tasks_file = plan_dir / "tasks.json"
    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        # Handle both formats: {"tasks": [...]} or just [...]
        if isinstance(data, list):
            return data
        return data.get("tasks", [])
    return []


def save_tasks(plan_dir: Path, tasks: list[dict]) -> None:
    """Save tasks to tasks.json."""
    tasks_file = plan_dir / "tasks.json"
    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        # Handle both formats: {"tasks": [...]} or just [...]
        if isinstance(data, list):
            # Raw array format - just write the array
            tasks_file.write_text(json.dumps(tasks, indent=2) + "\n")
        else:
            # Dict format - update the tasks key
            data["tasks"] = tasks
            tasks_file.write_text(json.dumps(data, indent=2) + "\n")


def log_progress(plan_dir: Path, message: str) -> None:
    """Append entry to progress log."""
    progress_file = plan_dir / "claude-progress.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(progress_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def log_task_progress(plan_dir: Path, task_id: str, message: str) -> None:
    """Append entry to task's progress.txt."""
    task_dir = plan_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    progress_file = task_dir / "progress.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(progress_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


# --- Subcommand handlers ---


def cmd_active_plan(args: argparse.Namespace) -> int:
    """Print active plan name."""
    project_dir = get_project_dir()
    plan_name = get_active_plan(project_dir)
    if plan_name:
        print(plan_name)
        return 0
    return 1


def cmd_active_plan_dir(args: argparse.Namespace) -> int:
    """Print active plan directory path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if plan_dir:
        print(plan_dir)
        return 0
    return 1


def cmd_list_plans(args: argparse.Namespace) -> int:
    """List all available plans."""
    project_dir = get_project_dir()
    plans_dir = project_dir / ".claude" / "jons-plan" / "plans"
    active = get_active_plan(project_dir)
    if plans_dir.is_dir():
        for plan in sorted(plans_dir.iterdir()):
            if plan.is_dir():
                marker = " (active)" if plan.name == active else ""
                print(f"{plan.name}{marker}")
    return 0


def cmd_set_active(args: argparse.Namespace) -> int:
    """Set the active plan."""
    project_dir = get_project_dir()
    plans_dir = project_dir / ".claude" / "jons-plan" / "plans"
    plan_dir = plans_dir / args.plan_name

    if not plan_dir.is_dir():
        print(f"Plan not found: {args.plan_name}", file=sys.stderr)
        print("Available plans:", file=sys.stderr)
        if plans_dir.is_dir():
            for plan in sorted(plans_dir.iterdir()):
                if plan.is_dir():
                    print(f"  {plan.name}", file=sys.stderr)
        return 1

    active_plan_file = project_dir / ".claude" / "jons-plan" / "active-plan"
    active_plan_file.parent.mkdir(parents=True, exist_ok=True)
    active_plan_file.write_text(args.plan_name)
    print(f"Active plan set to: {args.plan_name}")
    return 0


def cmd_deactivate(args: argparse.Namespace) -> int:
    """Deactivate the current plan without switching to another."""
    project_dir = get_project_dir()
    active_plan_file = project_dir / ".claude" / "jons-plan" / "active-plan"

    if not active_plan_file.exists():
        print("No active plan to deactivate")
        return 0

    plan_name = active_plan_file.read_text().strip()
    active_plan_file.unlink()
    print(f"Deactivated plan: {plan_name}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    """Append message to progress log."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1
    log_progress(plan_dir, args.message)
    return 0


def cmd_task_stats(args: argparse.Namespace) -> int:
    """Print task statistics."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("?/?")
        return 1

    tasks = get_tasks(plan_dir)
    todo = sum(1 for t in tasks if t.get("status") == "todo")
    in_progress = sum(1 for t in tasks if t.get("status") == "in-progress")
    done = sum(1 for t in tasks if t.get("status") == "done")
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    total = len(tasks)

    if blocked > 0:
        print(f"{done}/{total} done, {in_progress} in-progress, {blocked} blocked, {todo} todo")
    else:
        print(f"{done}/{total} done, {in_progress} in-progress, {todo} todo")
    return 0


def cmd_in_progress(args: argparse.Namespace) -> int:
    """List in-progress tasks."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    tasks = get_tasks(plan_dir)
    for task in tasks:
        if task.get("status") == "in-progress":
            print(f"{task['id']}: {task.get('description', '')}")
    return 0


def cmd_blocked_tasks(args: argparse.Namespace) -> int:
    """List blocked tasks."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    tasks = get_tasks(plan_dir)
    for task in tasks:
        if task.get("status") == "blocked":
            print(f"{task['id']}: {task.get('description', '')}")
    return 0


def cmd_has_blockers(args: argparse.Namespace) -> int:
    """Check if plan has blocked tasks (exit 0 if yes, 1 if no)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    tasks = get_tasks(plan_dir)
    blocked_count = sum(1 for t in tasks if t.get("status") == "blocked")
    if blocked_count > 0:
        return 0  # Has blockers
    return 1  # No blockers


def cmd_next_tasks(args: argparse.Namespace) -> int:
    """List available tasks (todo with all parents done)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    tasks = get_tasks(plan_dir)
    task_status = {t["id"]: t.get("status") for t in tasks}

    for task in tasks:
        if task.get("status") != "todo":
            continue
        parents = task.get("parents", [])
        if all(task_status.get(pid) == "done" for pid in parents):
            print(f"{task['id']}: {task.get('description', '')}")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    """Set task status."""
    if args.status not in ("todo", "in-progress", "done", "blocked"):
        print(f"Invalid status: {args.status} (must be todo, in-progress, done, or blocked)", file=sys.stderr)
        return 1

    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks = get_tasks(plan_dir)
    found_task = None
    for task in tasks:
        if task["id"] == args.task_id:
            found_task = task
            break

    if not found_task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # When setting to blocked, verify blockers.md exists
    if args.status == "blocked":
        task_dir = plan_dir / "tasks" / args.task_id
        blockers_file = task_dir / "blockers.md"
        if not blockers_file.exists():
            print(f"Cannot mark task as blocked: blockers.md not found", file=sys.stderr)
            print(f"First write: {blockers_file}", file=sys.stderr)
            print("", file=sys.stderr)
            print("blockers.md should contain:", file=sys.stderr)
            print("  - What was attempted", file=sys.stderr)
            print("  - Why it failed", file=sys.stderr)
            print("  - Suggested resolution", file=sys.stderr)
            return 1

    # Update status
    found_task["status"] = args.status
    tasks_file = plan_dir / "tasks.json"
    save_tasks(plan_dir, tasks)
    print(f"Updated: {tasks_file}")
    log_progress(plan_dir, f"TASK_STATUS: {args.task_id} -> {args.status}")

    # Write task-level progress entries
    if args.status == "in-progress":
        # Initialize task progress with description and steps
        log_task_progress(plan_dir, args.task_id, f"TASK_STARTED: {found_task.get('description', '')}")
        steps = found_task.get("steps", [])
        if steps:
            steps_text = "\n".join(f"  - {step}" for step in steps)
            log_task_progress(plan_dir, args.task_id, f"Steps:\n{steps_text}")
    elif args.status == "done":
        log_task_progress(plan_dir, args.task_id, f"TASK_COMPLETED: {found_task.get('description', '')}")
    elif args.status == "blocked":
        log_task_progress(plan_dir, args.task_id, f"TASK_BLOCKED: {found_task.get('description', '')}")
        print(f"Task {args.task_id} is now BLOCKED.", file=sys.stderr)
        print("STOP execution and run /jons-plan:plan to address the blocker.", file=sys.stderr)

    return 0


def cmd_recent_progress(args: argparse.Namespace) -> int:
    """Show recent progress entries."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    progress_file = plan_dir / "claude-progress.txt"
    if progress_file.exists():
        lines = progress_file.read_text().splitlines()
        for line in lines[-args.lines:]:
            print(line)
    return 0


def cmd_task_dir(args: argparse.Namespace) -> int:
    """Print task directory path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    task_dir = plan_dir / "tasks" / args.task_id
    print(task_dir)
    return 0


def cmd_ensure_task_dir(args: argparse.Namespace) -> int:
    """Create task directory and print path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    task_dir = plan_dir / "tasks" / args.task_id
    was_created = not task_dir.exists()
    task_dir.mkdir(parents=True, exist_ok=True)
    if was_created:
        print(f"Created: {task_dir}")
    else:
        print(task_dir)
    return 0


def cmd_parent_dirs(args: argparse.Namespace) -> int:
    """List parent task directories that exist."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    tasks = get_tasks(plan_dir)
    parents = []
    for task in tasks:
        if task["id"] == args.task_id:
            parents = task.get("parents", [])
            break

    for parent_id in parents:
        parent_dir = plan_dir / "tasks" / parent_id
        if parent_dir.is_dir():
            print(parent_dir)
    return 0


def cmd_has_outputs(args: argparse.Namespace) -> int:
    """Check if task has outputs (exit 0 if yes, 1 if no)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    task_dir = plan_dir / "tasks" / args.task_id
    if task_dir.is_dir() and any(task_dir.iterdir()):
        return 0
    return 1


def cmd_task_log(args: argparse.Namespace) -> int:
    """Append message to task's progress.txt."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Verify task exists
    tasks = get_tasks(plan_dir)
    task_exists = any(t["id"] == args.task_id for t in tasks)
    if not task_exists:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # Create task directory if needed
    task_dir = plan_dir / "tasks" / args.task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Append to progress.txt
    progress_file = task_dir / "progress.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(progress_file, "a") as f:
        f.write(f"[{timestamp}] {args.message}\n")

    return 0


def cmd_task_progress(args: argparse.Namespace) -> int:
    """Show recent entries from task's progress.txt."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    task_dir = plan_dir / "tasks" / args.task_id
    progress_file = task_dir / "progress.txt"

    if not progress_file.exists():
        # Not an error - just no progress yet
        return 0

    lines = progress_file.read_text().splitlines()
    for line in lines[-args.lines:]:
        print(line)

    return 0


def cmd_record_confidence(args: argparse.Namespace) -> int:
    """Record confidence score for a task."""
    if not 1 <= args.score <= 5:
        print(f"Invalid score: {args.score} (must be 1-5)", file=sys.stderr)
        return 1

    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Verify task exists
    tasks = get_tasks(plan_dir)
    task_exists = any(t["id"] == args.task_id for t in tasks)
    if not task_exists:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # Create task directory if needed
    task_dir = plan_dir / "tasks" / args.task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Write confidence.json
    confidence_data = {
        "score": args.score,
        "rationale": args.rationale,
        "timestamp": datetime.now().isoformat(),
    }
    confidence_file = task_dir / "confidence.json"
    confidence_file.write_text(json.dumps(confidence_data, indent=2) + "\n")
    print(f"Recorded: {confidence_file}")

    # Log to task progress
    log_task_progress(plan_dir, args.task_id, f"CONFIDENCE: {args.score}/5 - {args.rationale}")

    # Log to plan progress
    log_progress(plan_dir, f"CONFIDENCE: {args.task_id} scored {args.score}/5")

    # Warn if low confidence
    if args.score < 4:
        print(f"LOW CONFIDENCE ({args.score}/5): {args.rationale}", file=sys.stderr)
        print("Consider using AskUserQuestion to discuss concerns with user.", file=sys.stderr)

    return 0


def cmd_check_confidence(args: argparse.Namespace) -> int:
    """Check confidence score for a task."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    task_dir = plan_dir / "tasks" / args.task_id
    confidence_file = task_dir / "confidence.json"

    if not confidence_file.exists():
        print(f"No confidence recorded for task: {args.task_id}", file=sys.stderr)
        return 1

    data = json.loads(confidence_file.read_text())
    print(f"Score: {data['score']}/5")
    print(f"Rationale: {data['rationale']}")
    print(f"Recorded: {data['timestamp']}")

    return 0


def cmd_low_confidence_tasks(args: argparse.Namespace) -> int:
    """List tasks with confidence score < 4."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks_dir = plan_dir / "tasks"
    if not tasks_dir.is_dir():
        return 0  # No tasks yet

    low_confidence = []
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue
        confidence_file = task_dir / "confidence.json"
        if confidence_file.exists():
            data = json.loads(confidence_file.read_text())
            if data["score"] < 4:
                low_confidence.append((task_dir.name, data["score"], data["rationale"]))

    if low_confidence:
        for task_id, score, rationale in sorted(low_confidence, key=lambda x: x[1]):
            print(f"{task_id}: {score}/5 - {rationale}")
    else:
        print("No low-confidence tasks found.")

    return 0


def validate_task_schema(task: dict) -> list[str]:
    """Validate a task object against the schema. Returns list of errors."""
    errors = []
    required_fields = ["id", "description", "parents", "steps", "status"]
    for field in required_fields:
        if field not in task:
            errors.append(f"Missing required field: {field}")

    if "id" in task and not isinstance(task["id"], str):
        errors.append("Field 'id' must be a string")

    if "parents" in task and not isinstance(task["parents"], list):
        errors.append("Field 'parents' must be an array")

    if "steps" in task and not isinstance(task["steps"], list):
        errors.append("Field 'steps' must be an array")

    if "status" in task and task["status"] not in ("todo", "in-progress", "done", "blocked"):
        errors.append(f"Invalid status: {task['status']}")

    valid_subagents = ("general-purpose", "Explore", "Plan", "claude-code-guide", "gemini-reviewer", "codex-reviewer")
    if "subagent" in task and task["subagent"] not in valid_subagents:
        errors.append(f"Invalid subagent: {task['subagent']}")

    valid_models = ("sonnet", "haiku", "opus")
    if "model" in task and task["model"] not in valid_models:
        errors.append(f"Invalid model: {task['model']}")

    return errors


def cmd_add_task(args: argparse.Namespace) -> int:
    """Add a new task to tasks.json from JSON input."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Read task JSON from file or stdin
    if args.json_file == "-":
        task_json = sys.stdin.read()
    else:
        json_path = Path(args.json_file)
        if not json_path.exists():
            print(f"File not found: {args.json_file}", file=sys.stderr)
            return 1
        task_json = json_path.read_text()

    try:
        new_task = json.loads(task_json)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1

    # Validate schema
    errors = validate_task_schema(new_task)
    if errors:
        print("Task validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    # Check for duplicate ID
    tasks = get_tasks(plan_dir)
    if any(t["id"] == new_task["id"] for t in tasks):
        print(f"Task with ID '{new_task['id']}' already exists", file=sys.stderr)
        return 1

    # Validate parent references
    task_ids = {t["id"] for t in tasks}
    for parent_id in new_task.get("parents", []):
        if parent_id not in task_ids:
            print(f"Parent task not found: {parent_id}", file=sys.stderr)
            return 1

    # Add task
    tasks.append(new_task)
    tasks_file = plan_dir / "tasks.json"
    save_tasks(plan_dir, tasks)

    # Log the modification
    log_progress(plan_dir, f"TASK_ADDED: {new_task['id']} - {new_task['description']}")
    print(f"Added task: {new_task['id']}")
    print(f"Updated: {tasks_file}")

    return 0


def cmd_update_task_parents(args: argparse.Namespace) -> int:
    """Update a task's parent dependencies."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks = get_tasks(plan_dir)
    task_ids = {t["id"] for t in tasks}

    # Find the task
    target_task = None
    for task in tasks:
        if task["id"] == args.task_id:
            target_task = task
            break

    if not target_task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # Validate parent references
    for parent_id in args.parent_ids:
        if parent_id not in task_ids:
            print(f"Parent task not found: {parent_id}", file=sys.stderr)
            return 1
        if parent_id == args.task_id:
            print("Task cannot be its own parent", file=sys.stderr)
            return 1

    # Update parents
    old_parents = target_task.get("parents", [])
    target_task["parents"] = list(args.parent_ids)
    tasks_file = plan_dir / "tasks.json"
    save_tasks(plan_dir, tasks)

    # Log the modification
    log_progress(plan_dir, f"TASK_PARENTS_UPDATED: {args.task_id} from {old_parents} to {list(args.parent_ids)}")
    print(f"Updated parents for {args.task_id}: {list(args.parent_ids)}")
    print(f"Updated: {tasks_file}")

    return 0


def cmd_update_task_steps(args: argparse.Namespace) -> int:
    """Update a task's steps from JSON input."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Read steps JSON from file or stdin
    if args.json_file == "-":
        steps_json = sys.stdin.read()
    else:
        json_path = Path(args.json_file)
        if not json_path.exists():
            print(f"File not found: {args.json_file}", file=sys.stderr)
            return 1
        steps_json = json_path.read_text()

    try:
        new_steps = json.loads(steps_json)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(new_steps, list):
        print("Steps must be a JSON array", file=sys.stderr)
        return 1

    tasks = get_tasks(plan_dir)

    # Find the task
    target_task = None
    for task in tasks:
        if task["id"] == args.task_id:
            target_task = task
            break

    if not target_task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # Update steps
    old_steps_count = len(target_task.get("steps", []))
    target_task["steps"] = new_steps
    tasks_file = plan_dir / "tasks.json"
    save_tasks(plan_dir, tasks)

    # Log the modification
    log_progress(plan_dir, f"TASK_STEPS_UPDATED: {args.task_id} ({old_steps_count} -> {len(new_steps)} steps)")
    print(f"Updated steps for {args.task_id}: {len(new_steps)} steps")
    print(f"Updated: {tasks_file}")

    return 0


def cmd_build_task_prompt(args: argparse.Namespace) -> int:
    """Build a complete prompt for a task with all context."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Find the task
    tasks = get_tasks(plan_dir)
    task = None
    for t in tasks:
        if t["id"] == args.task_id:
            task = t
            break

    if not task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    # Build prompt parts
    prompt_parts = []

    # 1. Description with optional subagent_prompt prefix
    subagent_prompt = task.get("subagent_prompt", "")
    description = task.get("description", "")
    if subagent_prompt:
        prompt_parts.append(f"{subagent_prompt}: {description}")
    else:
        prompt_parts.append(description)

    # 2. Steps list
    steps = task.get("steps", [])
    if steps:
        prompt_parts.append("\nSteps:")
        for step in steps:
            prompt_parts.append(f"- {step}")

    # 3. Parent task outputs
    parents = task.get("parents", [])
    parent_outputs = []
    for parent_id in parents:
        parent_dir = plan_dir / "tasks" / parent_id
        if parent_dir.is_dir():
            # Look for output files (output.md, or any .md file)
            output_files = list(parent_dir.glob("*.md"))
            # Also check for progress.txt but skip it (that's internal)
            for output_file in output_files:
                if output_file.name != "progress.txt":
                    content = output_file.read_text().strip()
                    if content:
                        parent_outputs.append((parent_id, output_file.name, content))

    if parent_outputs:
        prompt_parts.append("\n\n## Parent Task Outputs")
        for parent_id, filename, content in parent_outputs:
            prompt_parts.append(f"\n### {parent_id}/{filename}")
            prompt_parts.append(content)

    # 4. Prior progress (for resumption)
    task_dir = plan_dir / "tasks" / args.task_id
    progress_file = task_dir / "progress.txt"
    if progress_file.exists():
        progress_content = progress_file.read_text().strip()
        if progress_content:
            prompt_parts.append("\n\n## Prior Progress (Resuming)")
            prompt_parts.append(progress_content)
            prompt_parts.append("\nContinue from where the previous work left off.")

    # 5. Task output directory (for research/exploration tasks that produce artifacts)
    output_dir = plan_dir / "tasks" / args.task_id
    prompt_parts.append("\n\n## Task Output Directory")
    prompt_parts.append(f"If this task produces findings, research results, or artifacts for downstream tasks:")
    prompt_parts.append(f"- Output path: `{output_dir}/`")
    prompt_parts.append(f"- You have FULL write access - create files as needed (e.g., findings.md, analysis.md)")
    prompt_parts.append(f"- The directory will be created automatically when you write to it")

    # 6. CLI reference for task completion
    prompt_parts.append("\n\n## When Done")
    prompt_parts.append(f"Mark this task complete: `uv run ~/.claude-plugins/jons-plan/plan.py set-status {args.task_id} done`")

    # Output the complete prompt
    print("\n".join(prompt_parts))
    return 0


def cmd_help(args: argparse.Namespace) -> int:
    """Print concise CLI reference."""
    print("""## CLI Commands

**Overview:** `status` - all plans, active plan stats, tasks
**Switch plan:** `set-active <plan>`
**Task status:** `set-status <task-id> in-progress|done`
**Next tasks:** `next-tasks` - available tasks to start
**Progress:** `log <message>` | `recent-progress`

Full docs: ~/.claude-plugins/jons-plan/CLAUDE.md""")
    return 0


# --- Session Mode Commands ---

VALID_MODES = ("new", "new-design", "new-deep", "plan", "proceed")


def get_session_mode_file(project_dir: Path) -> Path:
    """Get path to session-mode file."""
    return project_dir / ".claude" / "jons-plan" / "session-mode"


def cmd_set_mode(args: argparse.Namespace) -> int:
    """Set the current session mode."""
    if args.mode not in VALID_MODES:
        print(f"Invalid mode: {args.mode}", file=sys.stderr)
        print(f"Valid modes: {', '.join(VALID_MODES)}", file=sys.stderr)
        return 1

    project_dir = get_project_dir()
    mode_file = get_session_mode_file(project_dir)
    mode_file.parent.mkdir(parents=True, exist_ok=True)
    mode_file.write_text(args.mode)
    return 0


def cmd_get_mode(args: argparse.Namespace) -> int:
    """Get the current session mode (empty if not set)."""
    project_dir = get_project_dir()
    mode_file = get_session_mode_file(project_dir)
    if mode_file.exists():
        mode = mode_file.read_text().strip()
        print(mode)
    # Return 0 even if no mode set - empty output indicates no mode
    return 0


def cmd_clear_mode(args: argparse.Namespace) -> int:
    """Clear the session mode."""
    project_dir = get_project_dir()
    mode_file = get_session_mode_file(project_dir)
    if mode_file.exists():
        mode_file.unlink()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show comprehensive status overview."""
    project_dir = get_project_dir()
    plans_dir = project_dir / ".claude" / "jons-plan" / "plans"
    active = get_active_plan(project_dir)

    # Plans section
    print("## Plans")
    if plans_dir.is_dir():
        plans = [p for p in sorted(plans_dir.iterdir()) if p.is_dir()]
        if plans:
            for plan in plans:
                marker = " (active)" if plan.name == active else ""
                print(f"  - {plan.name}{marker}")
        else:
            print("  (no plans)")
    else:
        print("  (no plans directory)")

    # Active plan details
    if active:
        plan_dir = get_active_plan_dir(project_dir)
        if plan_dir:
            tasks = get_tasks(plan_dir)
            todo = sum(1 for t in tasks if t.get("status") == "todo")
            in_progress_count = sum(1 for t in tasks if t.get("status") == "in-progress")
            done = sum(1 for t in tasks if t.get("status") == "done")
            blocked_count = sum(1 for t in tasks if t.get("status") == "blocked")
            total = len(tasks)

            print(f"\n## Active: {active}")
            print(f"  Path: {plan_dir}")
            if blocked_count > 0:
                print(f"  Progress: {done}/{total} done, {in_progress_count} in-progress, {blocked_count} blocked, {todo} todo")
            else:
                print(f"  Progress: {done}/{total} done, {in_progress_count} in-progress, {todo} todo")

            # Blocked tasks (show first - most important)
            blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]
            if blocked_tasks:
                print("\n  BLOCKED (requires /jons-plan:plan):")
                for task in blocked_tasks:
                    print(f"    - {task['id']}: {task.get('description', '')}")

            # In-progress tasks
            in_progress_tasks = [t for t in tasks if t.get("status") == "in-progress"]
            if in_progress_tasks:
                print("\n  In Progress:")
                for task in in_progress_tasks:
                    print(f"    - {task['id']}: {task.get('description', '')}")

            # Next available tasks
            task_status = {t["id"]: t.get("status") for t in tasks}
            next_tasks = []
            for task in tasks:
                if task.get("status") != "todo":
                    continue
                parents = task.get("parents", [])
                if all(task_status.get(pid) == "done" for pid in parents):
                    next_tasks.append(task)

            if next_tasks:
                print("\n  Next Available:")
                for task in next_tasks:
                    print(f"    - {task['id']}: {task.get('description', '')}")
    else:
        print("\n## No active plan")
        print("  Use: uv run ~/.claude-plugins/jons-plan/plan.py set-active <plan-name>")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan management CLI for long-running agent harness",
        prog="plan",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # active-plan
    subparsers.add_parser("active-plan", help="Print active plan name")

    # active-plan-dir
    subparsers.add_parser("active-plan-dir", help="Print active plan directory path")

    # list-plans
    subparsers.add_parser("list-plans", help="List all available plans")

    # set-active
    p_set_active = subparsers.add_parser("set-active", help="Set the active plan")
    p_set_active.add_argument("plan_name", help="Plan name to activate")

    # deactivate
    subparsers.add_parser("deactivate", help="Deactivate current plan without switching")

    # log
    p_log = subparsers.add_parser("log", help="Append message to progress log")
    p_log.add_argument("message", help="Message to log")

    # task-stats
    subparsers.add_parser("task-stats", help="Print task statistics")

    # in-progress
    subparsers.add_parser("in-progress", help="List in-progress tasks")

    # blocked-tasks
    subparsers.add_parser("blocked-tasks", help="List blocked tasks")

    # has-blockers
    subparsers.add_parser("has-blockers", help="Check if plan has blocked tasks (exit 0=yes, 1=no)")

    # next-tasks
    subparsers.add_parser("next-tasks", help="List available tasks")

    # set-status
    p_status = subparsers.add_parser("set-status", help="Set task status")
    p_status.add_argument("task_id", help="Task ID")
    p_status.add_argument("status", choices=["todo", "in-progress", "done", "blocked"], help="New status")

    # recent-progress
    p_progress = subparsers.add_parser("recent-progress", help="Show recent progress entries")
    p_progress.add_argument("--lines", "-n", type=int, default=10, help="Number of lines")

    # task-dir
    p_taskdir = subparsers.add_parser("task-dir", help="Print task directory path")
    p_taskdir.add_argument("task_id", help="Task ID")

    # ensure-task-dir
    p_ensure = subparsers.add_parser("ensure-task-dir", help="Create task directory, print path")
    p_ensure.add_argument("task_id", help="Task ID")

    # parent-dirs
    p_parents = subparsers.add_parser("parent-dirs", help="List parent task directories")
    p_parents.add_argument("task_id", help="Task ID")

    # has-outputs
    p_outputs = subparsers.add_parser("has-outputs", help="Check if task has outputs")
    p_outputs.add_argument("task_id", help="Task ID")

    # task-log
    p_task_log = subparsers.add_parser("task-log", help="Append message to task progress")
    p_task_log.add_argument("task_id", help="Task ID")
    p_task_log.add_argument("message", help="Message to log")

    # task-progress
    p_task_progress = subparsers.add_parser("task-progress", help="Show task progress entries")
    p_task_progress.add_argument("task_id", help="Task ID")
    p_task_progress.add_argument("--lines", "-n", type=int, default=10, help="Number of lines")

    # build-task-prompt
    p_build_prompt = subparsers.add_parser("build-task-prompt", help="Build complete prompt for task")
    p_build_prompt.add_argument("task_id", help="Task ID")

    # record-confidence
    p_record_conf = subparsers.add_parser("record-confidence", help="Record confidence score for task")
    p_record_conf.add_argument("task_id", help="Task ID")
    p_record_conf.add_argument("score", type=int, help="Confidence score (1-5)")
    p_record_conf.add_argument("rationale", help="Explanation for the score")

    # check-confidence
    p_check_conf = subparsers.add_parser("check-confidence", help="Check confidence score for task")
    p_check_conf.add_argument("task_id", help="Task ID")

    # low-confidence-tasks
    subparsers.add_parser("low-confidence-tasks", help="List tasks with confidence < 4")

    # add-task
    p_add_task = subparsers.add_parser("add-task", help="Add a task from JSON file or stdin")
    p_add_task.add_argument("json_file", help="JSON file with task definition, or '-' for stdin")

    # update-task-parents
    p_update_parents = subparsers.add_parser("update-task-parents", help="Update task parent dependencies")
    p_update_parents.add_argument("task_id", help="Task ID to update")
    p_update_parents.add_argument("parent_ids", nargs="*", help="New parent task IDs")

    # update-task-steps
    p_update_steps = subparsers.add_parser("update-task-steps", help="Update task steps from JSON")
    p_update_steps.add_argument("task_id", help="Task ID to update")
    p_update_steps.add_argument("json_file", help="JSON file with steps array, or '-' for stdin")

    # status
    subparsers.add_parser("status", help="Show comprehensive status overview")

    # help
    subparsers.add_parser("help", help="Print concise CLI reference")

    # set-mode
    p_set_mode = subparsers.add_parser("set-mode", help="Set session mode")
    p_set_mode.add_argument("mode", choices=VALID_MODES, help="Mode to set")

    # get-mode
    subparsers.add_parser("get-mode", help="Get current session mode")

    # clear-mode
    subparsers.add_parser("clear-mode", help="Clear session mode")

    args = parser.parse_args()

    commands = {
        "active-plan": cmd_active_plan,
        "active-plan-dir": cmd_active_plan_dir,
        "list-plans": cmd_list_plans,
        "set-active": cmd_set_active,
        "deactivate": cmd_deactivate,
        "log": cmd_log,
        "task-stats": cmd_task_stats,
        "in-progress": cmd_in_progress,
        "blocked-tasks": cmd_blocked_tasks,
        "has-blockers": cmd_has_blockers,
        "next-tasks": cmd_next_tasks,
        "set-status": cmd_set_status,
        "recent-progress": cmd_recent_progress,
        "task-dir": cmd_task_dir,
        "ensure-task-dir": cmd_ensure_task_dir,
        "parent-dirs": cmd_parent_dirs,
        "has-outputs": cmd_has_outputs,
        "task-log": cmd_task_log,
        "task-progress": cmd_task_progress,
        "build-task-prompt": cmd_build_task_prompt,
        "record-confidence": cmd_record_confidence,
        "check-confidence": cmd_check_confidence,
        "low-confidence-tasks": cmd_low_confidence_tasks,
        "add-task": cmd_add_task,
        "update-task-parents": cmd_update_task_parents,
        "update-task-steps": cmd_update_task_steps,
        "status": cmd_status,
        "help": cmd_help,
        "set-mode": cmd_set_mode,
        "get-mode": cmd_get_mode,
        "clear-mode": cmd_clear_mode,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
