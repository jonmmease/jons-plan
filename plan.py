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
    total = len(tasks)

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
    if args.status not in ("todo", "in-progress", "done"):
        print(f"Invalid status: {args.status} (must be todo, in-progress, or done)", file=sys.stderr)
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
            task["status"] = args.status
            found_task = task
            break

    if not found_task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    save_tasks(plan_dir, tasks)
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
    task_dir.mkdir(parents=True, exist_ok=True)
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

VALID_MODES = ("new", "new-design", "plan", "proceed")


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
            total = len(tasks)

            print(f"\n## Active: {active}")
            print(f"  Progress: {done}/{total} done, {in_progress_count} in-progress, {todo} todo")

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

    # log
    p_log = subparsers.add_parser("log", help="Append message to progress log")
    p_log.add_argument("message", help="Message to log")

    # task-stats
    subparsers.add_parser("task-stats", help="Print task statistics")

    # in-progress
    subparsers.add_parser("in-progress", help="List in-progress tasks")

    # next-tasks
    subparsers.add_parser("next-tasks", help="List available tasks")

    # set-status
    p_status = subparsers.add_parser("set-status", help="Set task status")
    p_status.add_argument("task_id", help="Task ID")
    p_status.add_argument("status", choices=["todo", "in-progress", "done"], help="New status")

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
        "log": cmd_log,
        "task-stats": cmd_task_stats,
        "in-progress": cmd_in_progress,
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
        "status": cmd_status,
        "help": cmd_help,
        "set-mode": cmd_set_mode,
        "get-mode": cmd_get_mode,
        "clear-mode": cmd_clear_mode,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
