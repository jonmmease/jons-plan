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
        return data.get("tasks", [])
    return []


def save_tasks(plan_dir: Path, tasks: list[dict]) -> None:
    """Save tasks to tasks.json."""
    tasks_file = plan_dir / "tasks.json"
    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        data["tasks"] = tasks
        tasks_file.write_text(json.dumps(data, indent=2) + "\n")


def log_progress(plan_dir: Path, message: str) -> None:
    """Append entry to progress log."""
    progress_file = plan_dir / "claude-progress.txt"
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
    if plans_dir.is_dir():
        for plan in sorted(plans_dir.iterdir()):
            if plan.is_dir():
                print(plan.name)
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
    found = False
    for task in tasks:
        if task["id"] == args.task_id:
            task["status"] = args.status
            found = True
            break

    if not found:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    save_tasks(plan_dir, tasks)
    log_progress(plan_dir, f"TASK_STATUS: {args.task_id} -> {args.status}")
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

    args = parser.parse_args()

    commands = {
        "active-plan": cmd_active_plan,
        "active-plan-dir": cmd_active_plan_dir,
        "list-plans": cmd_list_plans,
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
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
