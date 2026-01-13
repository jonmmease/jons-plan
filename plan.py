#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
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

# Task schema documentation injected into phases with use_tasks=true
TASK_SCHEMA = """
## Task Schema

Create `tasks.json` as a JSON array of task objects:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (kebab-case) |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Array of concrete steps |
| `status` | Yes | Always `"todo"` when creating |
| `subagent` | No | Agent type: `general-purpose` (default), `Explore`, `gemini-reviewer`, `codex-reviewer` |
| `subagent_prompt` | No | Additional context (e.g., `"very thorough analysis"`) |
| `model` | No | `sonnet` (default), `haiku`, `opus` |

### Example
```json
[
  {
    "id": "research-patterns",
    "description": "Research existing patterns in codebase",
    "subagent": "Explore",
    "subagent_prompt": "very thorough analysis",
    "model": "haiku",
    "parents": [],
    "steps": ["Find relevant files", "Document patterns found"],
    "status": "todo"
  },
  {
    "id": "implement-feature",
    "description": "Implement the feature",
    "parents": ["research-patterns"],
    "steps": ["Create module", "Add tests"],
    "status": "todo"
  }
]
```

### Parallelization
Tasks without shared parents can run in parallel, but add parent dependencies when:
- Tasks modify files in the same directory
- Tasks edit the same config files
- Tasks have logical ordering requirements
""".strip()


def get_project_dir() -> Path:
    """Get project directory (git root or cwd).

    Uses git root if in a git repo, otherwise falls back to cwd.
    Never walks up looking for .claude/ to avoid accidentally using ~/.claude/.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass

    # Fallback to cwd if not in a git repo
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


def get_tasks_file(plan_dir: Path) -> Path | None:
    """Get the path to tasks.json for the current phase.

    Returns:
        Path to tasks.json if in a phase, None otherwise
    """
    state_file = plan_dir / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            phase_dir = state.get("current_phase_dir")
            if phase_dir:
                return plan_dir / phase_dir / "tasks.json"
        except (json.JSONDecodeError, OSError):
            pass
    return None


def get_tasks(plan_dir: Path) -> list[dict]:
    """Load tasks from current phase's tasks.json."""
    tasks_file = get_tasks_file(plan_dir)
    if tasks_file and tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        if isinstance(data, list):
            return data
        return data.get("tasks", [])
    return []


def save_tasks(plan_dir: Path, tasks: list[dict]) -> Path | None:
    """Save tasks to current phase's tasks.json.

    Returns the path to the tasks file that was written, or None if no current phase.
    """
    tasks_file = get_tasks_file(plan_dir)
    if not tasks_file:
        return None

    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        if isinstance(data, list):
            tasks_file.write_text(json.dumps(tasks, indent=2) + "\n")
        else:
            data["tasks"] = tasks
            tasks_file.write_text(json.dumps(data, indent=2) + "\n")
    else:
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.write_text(json.dumps(tasks, indent=2) + "\n")
    return tasks_file


def get_task_output_dir(plan_dir: Path, task_id: str) -> Path | None:
    """Get the path to a task's output directory in current phase.

    Returns None if no current phase is set.
    """
    state_file = plan_dir / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            phase_dir = state.get("current_phase_dir")
            if phase_dir:
                return plan_dir / phase_dir / "tasks" / task_id
        except (json.JSONDecodeError, OSError):
            pass
    return None


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


# --- State Management Classes ---


class StateManager:
    """Handles atomic state.json operations for workflow plans."""

    def __init__(self, plan_dir: Path):
        self.plan_dir = plan_dir
        self.state_file = plan_dir / "state.json"

    def load(self) -> dict:
        """Load state, return default if missing or corrupted."""
        if not self.state_file.exists():
            return self._default_state()
        try:
            state = json.loads(self.state_file.read_text())
            return state
        except (json.JSONDecodeError, OSError):
            return self._default_state()

    def save(self, state: dict) -> None:
        """Atomically write state.json using temp-file + rename."""
        temp_file = self.state_file.with_suffix(".json.tmp")
        try:
            content = json.dumps(state, indent=2) + "\n"
            temp_file.write_text(content)
            # Force to disk before rename
            import os

            with open(temp_file, "r") as f:
                os.fsync(f.fileno())
            # Atomic rename (POSIX); on Windows, may need to remove target first
            if sys.platform == "win32" and self.state_file.exists():
                self.state_file.unlink()
            temp_file.rename(self.state_file)
        except Exception:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink()
            raise

    def update_phase(
        self, phase_id: str, phase_dir: str, reason: str = ""
    ) -> dict:
        """Transition to new phase, update history, return updated state."""
        state = self.load()
        entry = state.get("current_phase_entry", 0) + 1

        # Close current phase in history if exists
        if state.get("phase_history"):
            current_entry = state["phase_history"][-1]
            if "exited" not in current_entry:
                current_entry["exited"] = datetime.now().isoformat()
                current_entry["outcome"] = "completed"

        # Update current phase info
        state["current_phase"] = phase_id
        state["current_phase_dir"] = phase_dir
        state["current_phase_entry"] = entry

        # Add new phase entry to history
        new_entry = {
            "entry": entry,
            "phase": phase_id,
            "dir": phase_dir,
            "entered": datetime.now().isoformat(),
        }
        if reason:
            new_entry["reason"] = reason

        # Check if this is a re-entry (phase visited before)
        prev_entries = [
            e for e in state.get("phase_history", []) if e["phase"] == phase_id
        ]
        if prev_entries:
            new_entry["context_from"] = prev_entries[-1]["entry"]

        if "phase_history" not in state:
            state["phase_history"] = []
        state["phase_history"].append(new_entry)

        self.save(state)
        return state

    def record_artifact(self, filename: str, path: str) -> None:
        """Register artifact produced by current phase."""
        state = self.load()
        if state.get("phase_history"):
            current = state["phase_history"][-1]
            if "artifacts" not in current:
                current["artifacts"] = {}
            current["artifacts"][filename] = path
            self.save(state)

    def _default_state(self) -> dict:
        """Create default state structure."""
        return {
            "current_phase": None,
            "current_phase_dir": None,
            "current_phase_entry": 0,
            "started_at": datetime.now().isoformat(),
            "phase_history": [],
        }


class DeadEndRegistry:
    """Manages dead-ends.json for tracking failed approaches."""

    # Discovery types for categorizing why an approach failed
    DISCOVERY_TYPES = {
        "WRONG_ASSUMPTION",
        "MISSING_PREREQUISITE",
        "DEPENDENCY_CONFLICT",
        "ARCHITECTURAL_MISMATCH",
        "SCOPE_EXCEEDED",
        "EXTERNAL_BLOCKER",
    }

    def __init__(self, plan_dir: Path):
        self.plan_dir = plan_dir
        self.dead_ends_file = plan_dir / "dead-ends.json"

    def load(self) -> list[dict]:
        """Load dead ends, return empty list if missing or corrupted."""
        if not self.dead_ends_file.exists():
            return []
        try:
            return json.loads(self.dead_ends_file.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, dead_ends: list[dict]) -> None:
        """Atomically write dead-ends.json."""
        temp_file = self.dead_ends_file.with_suffix(".json.tmp")
        try:
            content = json.dumps(dead_ends, indent=2) + "\n"
            temp_file.write_text(content)
            import os

            with open(temp_file, "r") as f:
                os.fsync(f.fileno())
            if sys.platform == "win32" and self.dead_ends_file.exists():
                self.dead_ends_file.unlink()
            temp_file.rename(self.dead_ends_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def add(
        self,
        task_id: str,
        what_failed: str,
        why_failed: str,
        discovery_type: str,
        phase: str | None = None,
    ) -> str:
        """Add new dead end, return generated ID."""
        dead_ends = self.load()

        # Generate timestamp-based ID (guaranteed unique)
        import time

        dead_end_id = f"de-{int(time.time() * 1000)}"

        dead_ends.append(
            {
                "id": dead_end_id,
                "phase": phase,
                "task_id": task_id,
                "what_failed": what_failed,
                "why_failed": why_failed,
                "discovery_type": discovery_type,
                "timestamp": datetime.now().isoformat(),
            }
        )

        self.save(dead_ends)
        return dead_end_id

    def clear(self, dead_end_id: str) -> bool:
        """Remove a dead end by ID. Returns True if found and removed."""
        dead_ends = self.load()
        original_len = len(dead_ends)
        dead_ends = [de for de in dead_ends if de.get("id") != dead_end_id]
        if len(dead_ends) < original_len:
            self.save(dead_ends)
            return True
        return False

    def format_for_prompt(self, recent: int = 0) -> str:
        """Format dead ends for agent context injection.

        Args:
            recent: If > 0, only include the N most recent dead ends.
        """
        dead_ends = self.load()
        if recent > 0:
            dead_ends = dead_ends[-recent:]

        if not dead_ends:
            return ""

        lines = ["## Failed Approaches (Do Not Repeat)", ""]
        for de in dead_ends:
            task_id = de.get("task_id", "unknown")
            what = de.get("what_failed", "")
            why = de.get("why_failed", "")
            lines.append(f"- [{task_id}] {what} → {why}")

        return "\n".join(lines)


class WorkflowManager:
    """Handles workflow.toml queries for workflow plans."""

    def __init__(self, plan_dir: Path):
        self.plan_dir = plan_dir
        self.workflow_file = plan_dir / "workflow.toml"
        self._workflow: dict | None = None

    def exists(self) -> bool:
        """Check if workflow.toml exists."""
        return self.workflow_file.exists()

    def load(self) -> dict:
        """Load workflow.toml with lazy loading and caching."""
        if self._workflow is None:
            import tomllib

            with open(self.workflow_file, "rb") as f:
                self._workflow = tomllib.load(f)
        return self._workflow

    def get_phase(self, phase_id: str) -> dict | None:
        """Find phase by ID."""
        if not self.exists():
            return None
        workflow = self.load()
        for phase in workflow.get("phases", []):
            if phase.get("id") == phase_id:
                return phase
        return None

    def get_all_phases(self) -> list[dict]:
        """Get all phases in the workflow."""
        if not self.exists():
            return []
        workflow = self.load()
        return workflow.get("phases", [])

    def get_suggested_next(self, phase_id: str) -> list[str]:
        """Get suggested next phases for a given phase."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("suggested_next", [])
        return []

    def is_terminal(self, phase_id: str) -> bool:
        """Check if phase is a terminal state."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("terminal", False)
        return False

    def requires_user_input(self, phase_id: str) -> bool:
        """Check if phase requires user input before proceeding."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("requires_user_input", False)
        return False

    def uses_tasks(self, phase_id: str) -> bool:
        """Check if phase creates/uses tasks (triggers task schema injection)."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("use_tasks", False)
        return False

    def get_on_blocked(self, phase_id: str) -> str | None:
        """Get suggested phase to transition to when blocked."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("on_blocked")
        return None

    def get_phase_prompt(self, phase_id: str) -> str | None:
        """Get the prompt for a phase."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("prompt")
        return None

    def get_user_review_artifacts(self, phase_id: str) -> list[str]:
        """Get artifacts to present to user for review."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("user_review_artifacts", [])
        return []

    def get_workflow_name(self) -> str:
        """Get the workflow name."""
        if not self.exists():
            return ""
        workflow = self.load()
        return workflow.get("workflow", {}).get("name", "")

    def get_workflow_description(self) -> str:
        """Get the workflow description."""
        if not self.exists():
            return ""
        workflow = self.load()
        return workflow.get("workflow", {}).get("description", "")


class ArtifactResolver:
    """Resolves artifact paths from phase history."""

    def __init__(self, plan_dir: Path):
        self.plan_dir = plan_dir
        self.state_mgr = StateManager(plan_dir)

    def resolve_all(self, exclude_current: bool = True) -> dict[str, Path]:
        """Get all artifacts from prior phases.

        Returns: {filename: Path, ...}
        Later entries override earlier ones (last write wins).

        Args:
            exclude_current: If True, excludes artifacts from the current phase entry
        """
        state = self.state_mgr.load()
        artifacts: dict[str, Path] = {}
        current_entry = state.get("current_phase_entry", 0)

        for entry in state.get("phase_history", []):
            # Skip current phase entry if requested
            if exclude_current and entry.get("entry") == current_entry:
                continue

            # Accumulate artifacts (later entries override)
            if "artifacts" in entry:
                for filename, rel_path in entry["artifacts"].items():
                    artifacts[filename] = self.plan_dir / rel_path

        return artifacts

    def verify_all(self, exclude_current: bool = True) -> tuple[list[Path], list[str]]:
        """Verify all artifacts exist on disk.

        Returns: (found_paths, missing_paths_as_strings)
        """
        artifacts = self.resolve_all(exclude_current)
        found: list[Path] = []
        missing: list[str] = []

        for filename, path in artifacts.items():
            if path.exists():
                found.append(path)
            else:
                missing.append(str(path))

        return found, missing

    # Legacy method for backward compatibility
    def resolve_inputs(self, phase_id: str) -> dict[str, Path]:
        """Deprecated: Use resolve_all() instead."""
        return self.resolve_all(exclude_current=True)

    def verify_inputs(self, phase_id: str) -> tuple[list[Path], list[str]]:
        """Deprecated: Use verify_all() instead."""
        return self.verify_all(exclude_current=True)

    def get_all_artifacts_for_phase(self, phase_id: str) -> dict[str, Path]:
        """Get all artifacts produced by a specific phase (latest entry).

        Returns: {filename: Path, ...}
        """
        state = self.state_mgr.load()
        latest_entry = self._find_latest_entry(state, phase_id)
        if latest_entry and "artifacts" in latest_entry:
            return {
                filename: self.plan_dir / rel_path
                for filename, rel_path in latest_entry["artifacts"].items()
            }
        return {}


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
        task_dir = get_task_output_dir(plan_dir, args.task_id)
        if not task_dir:
            print("No current phase", file=sys.stderr)
            return 1
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
    """Print task directory path (phase-aware for workflow plans)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if task_dir:
        print(task_dir)
        return 0
    print("No current phase", file=sys.stderr)
    return 1


def cmd_ensure_task_dir(args: argparse.Namespace) -> int:
    """Create task directory and print path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if not task_dir:
        print("No current phase", file=sys.stderr)
        return 1
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
        parent_dir = get_task_output_dir(plan_dir, parent_id)
        if parent_dir and parent_dir.is_dir():
            print(parent_dir)
    return 0


def cmd_has_outputs(args: argparse.Namespace) -> int:
    """Check if task has outputs (exit 0 if yes, 1 if no)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 1

    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if task_dir and task_dir.is_dir() and any(task_dir.iterdir()):
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
    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if not task_dir:
        print("No current phase", file=sys.stderr)
        return 1
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

    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if not task_dir:
        print("No current phase", file=sys.stderr)
        return 1
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
    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if not task_dir:
        print("No current phase", file=sys.stderr)
        return 1
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

    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if not task_dir:
        print("No current phase", file=sys.stderr)
        return 1
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

    # Get tasks directory from current phase
    state_file = plan_dir / "state.json"
    if not state_file.exists():
        return 0  # No phase, no tasks
    try:
        state = json.loads(state_file.read_text())
        phase_dir = state.get("current_phase_dir")
        if not phase_dir:
            return 0  # No current phase
        tasks_dir = plan_dir / phase_dir / "tasks"
    except (json.JSONDecodeError, OSError):
        return 0

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

    # 3. Context artifacts (from phase history)
    context_artifacts = task.get("context_artifacts", [])
    if context_artifacts:
        resolver = ArtifactResolver(plan_dir)
        all_artifacts = resolver.resolve_all(exclude_current=False)

        artifact_contents = []
        for artifact_name in context_artifacts:
            if artifact_name in all_artifacts:
                artifact_path = all_artifacts[artifact_name]
                if artifact_path.exists():
                    content = artifact_path.read_text().strip()
                    if content:
                        artifact_contents.append((artifact_name, artifact_path, content))

        if artifact_contents:
            prompt_parts.append("\n\n## Context Artifacts")
            for name, path, content in artifact_contents:
                prompt_parts.append(f"\n### {name}")
                prompt_parts.append(f"_Source: {path.relative_to(plan_dir)}_")
                prompt_parts.append(content)

    # 4. Parent task outputs
    parents = task.get("parents", [])
    parent_outputs = []
    for parent_id in parents:
        parent_dir = get_task_output_dir(plan_dir, parent_id)
        if parent_dir and parent_dir.is_dir():
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

    # 5. Prior progress (for resumption)
    task_dir = get_task_output_dir(plan_dir, args.task_id)
    if task_dir:
        progress_file = task_dir / "progress.txt"
        if progress_file.exists():
            progress_content = progress_file.read_text().strip()
            if progress_content:
                prompt_parts.append("\n\n## Prior Progress (Resuming)")
                prompt_parts.append(progress_content)
                prompt_parts.append("\nContinue from where the previous work left off.")

    # 6. Task output directory (for research/exploration tasks that produce artifacts)
    output_dir = get_task_output_dir(plan_dir, args.task_id)
    if output_dir:
        prompt_parts.append("\n\n## Task Output Directory")
        prompt_parts.append(f"If this task produces findings, research results, or artifacts for downstream tasks:")
        prompt_parts.append(f"- Output path: `{output_dir}/`")
        prompt_parts.append(f"- You have FULL write access - create files as needed (e.g., findings.md, analysis.md)")
        prompt_parts.append(f"- The directory will be created automatically when you write to it")

    # 7. CLI reference for task completion
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

VALID_MODES = ("new", "plan", "proceed", "awaiting-feedback")


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


def cmd_get_user_guidance(args: argparse.Namespace) -> int:
    """Get user guidance from state.json (set by enter-phase-by-number)."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    guidance = state.get("user_guidance", "")
    if guidance:
        print(guidance)
    return 0


def cmd_clear_user_guidance(args: argparse.Namespace) -> int:
    """Clear user guidance from state.json after it's been processed."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    if "user_guidance" in state:
        del state["user_guidance"]
        state_mgr.save(state)
        print("Cleared user guidance")
    return 0


# --- Workflow Commands ---


def cmd_add_dead_end(args: argparse.Namespace) -> int:
    """Record a failed approach."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    # Validate discovery type
    if args.type not in DeadEndRegistry.DISCOVERY_TYPES:
        print(f"Invalid discovery type: {args.type}", file=sys.stderr)
        print(f"Valid types: {', '.join(sorted(DeadEndRegistry.DISCOVERY_TYPES))}", file=sys.stderr)
        return 2

    registry = DeadEndRegistry(plan_dir)

    # Get current phase if workflow exists
    phase = None
    workflow_mgr = WorkflowManager(plan_dir)
    if workflow_mgr.exists():
        state_mgr = StateManager(plan_dir)
        state = state_mgr.load()
        phase = state.get("current_phase")

    dead_end_id = registry.add(
        task_id=args.task_id,
        what_failed=args.what_failed,
        why_failed=args.why_failed,
        discovery_type=args.type,
        phase=phase,
    )
    print(f"Recorded: {dead_end_id}")
    return 0


def cmd_get_dead_ends(args: argparse.Namespace) -> int:
    """Get dead ends formatted for prompt injection or as JSON."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    registry = DeadEndRegistry(plan_dir)
    dead_ends = registry.load()

    # Apply recent filter
    if args.recent > 0:
        dead_ends = dead_ends[-args.recent:]

    if args.json:
        print(json.dumps(dead_ends, indent=2))
    else:
        output = registry.format_for_prompt(recent=args.recent)
        if output:
            print(output)
    return 0


def cmd_clear_dead_end(args: argparse.Namespace) -> int:
    """Remove a dead end by ID."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    registry = DeadEndRegistry(plan_dir)
    if registry.clear(args.dead_end_id):
        print(f"Cleared: {args.dead_end_id}")
        return 0
    else:
        print(f"Dead end not found: {args.dead_end_id}", file=sys.stderr)
        return 1


def cmd_current_phase(args: argparse.Namespace) -> int:
    """Print current phase ID from state.json."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")
    if current_phase:
        print(current_phase)
        return 0
    else:
        print("No current phase", file=sys.stderr)
        return 1


def cmd_current_phase_dir(args: argparse.Namespace) -> int:
    """Print current phase directory path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase_dir = state.get("current_phase_dir")
    if current_phase_dir:
        full_path = plan_dir / current_phase_dir
        print(full_path)
        return 0
    else:
        print("No current phase", file=sys.stderr)
        return 1


def cmd_enter_phase(args: argparse.Namespace) -> int:
    """Enter a new phase, creating numbered directory."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    phase = workflow_mgr.get_phase(args.phase_id)
    if not phase:
        print(f"Phase not found: {args.phase_id}", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()

    # Count existing entries for this phase (for re-entry detection)
    prev_entries = [
        e for e in state.get("phase_history", []) if e["phase"] == args.phase_id
    ]
    is_reentry = len(prev_entries) > 0

    # Determine next entry number (global across all phases)
    next_entry = state.get("current_phase_entry", 0) + 1

    # Create numbered directory: phases/NN-{phase-id}/
    phases_dir = plan_dir / "phases"
    phases_dir.mkdir(exist_ok=True)
    phase_dir_name = f"{next_entry:02d}-{args.phase_id}"
    phase_dir = phases_dir / phase_dir_name
    phase_dir.mkdir(exist_ok=True)

    # Generate reentry-context.md if this is a re-entry
    if is_reentry:
        last_entry = prev_entries[-1]
        reentry_content = f"""# Re-entry Context

## Previous Attempt
- Entry: {last_entry['entry']}
- Directory: {last_entry.get('dir', 'N/A')}
- Entered: {last_entry.get('entered', 'N/A')}
- Exited: {last_entry.get('exited', 'N/A')}
- Outcome: {last_entry.get('outcome', 'N/A')}

## Reason for Re-entry
{args.reason or 'Not specified'}

## Artifacts from Previous Attempt
"""
        prev_artifacts = last_entry.get("artifacts", {})
        if prev_artifacts:
            for name, path in prev_artifacts.items():
                reentry_content += f"- {name}: {path}\n"
        else:
            reentry_content += "(none)\n"

        reentry_file = phase_dir / "reentry-context.md"
        reentry_file.write_text(reentry_content)

    # Update state
    relative_phase_dir = f"phases/{phase_dir_name}"
    state_mgr.update_phase(args.phase_id, relative_phase_dir, args.reason or "")

    # Log to progress
    plan_name = get_active_plan(project_dir)
    log_progress(plan_dir, f"PHASE_ENTERED: {args.phase_id} -> {relative_phase_dir}")

    print(f"Entered: {phase_dir}")
    if is_reentry:
        print(f"Re-entry detected, context from entry {prev_entries[-1]['entry']}")
    return 0


def cmd_suggested_next(args: argparse.Namespace) -> int:
    """List possible phase transitions from current phase."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        # No current phase - suggest the first phase in the workflow
        all_phases = workflow_mgr.get_all_phases()
        if all_phases:
            first_phase = all_phases[0]
            terminal = " (terminal)" if first_phase.get("terminal") else ""
            user_input = " (requires user input)" if first_phase.get("requires_user_input") else ""
            print(f"{first_phase['id']}{terminal}{user_input}")
        else:
            print("(no phases found)")
        return 0

    suggested = workflow_mgr.get_suggested_next(current_phase)
    if suggested:
        for phase_id in suggested:
            phase = workflow_mgr.get_phase(phase_id)
            if phase:
                terminal = " (terminal)" if phase.get("terminal") else ""
                user_input = " (requires user input)" if phase.get("requires_user_input") else ""
                print(f"{phase_id}{terminal}{user_input}")
    else:
        # Check if current phase is terminal
        if workflow_mgr.is_terminal(current_phase):
            print("(current phase is terminal)")
        else:
            print("(no suggested transitions)")

    return 0


def cmd_enter_phase_by_number(args: argparse.Namespace) -> int:
    """Enter a phase by its number in the suggested_next list."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 1

    suggested = workflow_mgr.get_suggested_next(current_phase)
    if not suggested:
        if workflow_mgr.is_terminal(current_phase):
            print("Current phase is terminal, no transitions available", file=sys.stderr)
        else:
            print("No suggested transitions from current phase", file=sys.stderr)
        return 1

    number = args.number
    if number < 1 or number > len(suggested):
        print(f"Invalid option: {number}. Valid range: 1-{len(suggested)}", file=sys.stderr)
        print("Options:", file=sys.stderr)
        for i, phase_id in enumerate(suggested, 1):
            print(f"  {i}. {phase_id}", file=sys.stderr)
        return 1

    target_phase = suggested[number - 1]

    # Store guidance in state if provided
    guidance = args.guidance.strip() if args.guidance else ""
    if guidance:
        state["user_guidance"] = guidance
        state_mgr.save(state)
        log_progress(plan_dir, f"USER_GUIDANCE: {guidance}")

    # Build reason string
    reason = f"User selected option {number}"
    if guidance:
        reason += f": {guidance}"

    # Simulate args for enter-phase
    class EnterPhaseArgs:
        phase_id = target_phase
        reason = reason

    return cmd_enter_phase(EnterPhaseArgs())


def cmd_phase_history(args: argparse.Namespace) -> int:
    """Show all phase entries in chronological order."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    history = state.get("phase_history", [])

    if not history:
        print("No phase history")
        return 0

    current_entry = state.get("current_phase_entry", 0)

    for entry in history:
        entry_num = entry.get("entry", 0)
        phase_id = entry.get("phase", "?")
        entered = entry.get("entered", "?")[:19]  # Trim to datetime
        exited = entry.get("exited", "")[:19] if entry.get("exited") else ""
        outcome = entry.get("outcome", "")

        current_marker = " *" if entry_num == current_entry else ""
        reentry_marker = f" (from {entry.get('context_from')})" if entry.get("context_from") else ""

        if exited:
            print(f"{entry_num:2d}. {phase_id}: {entered} -> {exited} [{outcome}]{reentry_marker}")
        else:
            print(f"{entry_num:2d}. {phase_id}: {entered} (active){current_marker}{reentry_marker}")

    return 0


def cmd_record_artifact(args: argparse.Namespace) -> int:
    """Record an artifact produced by the current phase."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()

    if not state.get("current_phase"):
        print("No current phase", file=sys.stderr)
        return 1

    # Build path relative to plan directory
    current_phase_dir = state.get("current_phase_dir")
    if current_phase_dir:
        rel_path = f"{current_phase_dir}/{args.path}"
    else:
        rel_path = args.path

    # Record artifact with full relative path
    state_mgr.record_artifact(args.filename, rel_path)
    print(f"Recorded: {args.filename} -> {rel_path}")
    return 0


def cmd_input_artifacts(args: argparse.Namespace) -> int:
    """List all artifacts from prior phases."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    resolver = ArtifactResolver(plan_dir)
    found, missing = resolver.verify_all(exclude_current=True)

    if args.json:
        output = {
            "found": [str(p) for p in found],
            "missing": missing,
        }
        print(json.dumps(output, indent=2))
    else:
        if found:
            print("## Available Artifacts from Prior Phases")
            for path in found:
                print(f"  - {path}")
        if missing:
            print("\n## Missing Artifacts (recorded but not found)", file=sys.stderr)
            for path in missing:
                print(f"  - {path}", file=sys.stderr)
        if not found and not missing:
            print("No artifacts from prior phases")

    return 1 if missing else 0


def cmd_phase_context(args: argparse.Namespace) -> int:
    """Display full phase context for agent injection."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 1

    phase = workflow_mgr.get_phase(current_phase)
    if not phase:
        print(f"Phase not found in workflow: {current_phase}", file=sys.stderr)
        return 1

    resolver = ArtifactResolver(plan_dir)
    found, missing = resolver.verify_inputs(current_phase)

    # Get re-entry context if applicable
    current_phase_dir = state.get("current_phase_dir")
    reentry_context = None
    if current_phase_dir:
        reentry_file = plan_dir / current_phase_dir / "reentry-context.md"
        if reentry_file.exists():
            reentry_context = reentry_file.read_text()

    # Get request.md contents
    request_content = None
    request_file = plan_dir / "request.md"
    if request_file.exists():
        request_content = request_file.read_text()

    if args.json:
        use_tasks = workflow_mgr.uses_tasks(current_phase)
        output = {
            "phase_id": current_phase,
            "phase_dir": str(plan_dir / current_phase_dir) if current_phase_dir else None,
            "prompt": phase.get("prompt", ""),
            "terminal": phase.get("terminal", False),
            "requires_user_input": phase.get("requires_user_input", False),
            "use_tasks": use_tasks,
            "task_schema": TASK_SCHEMA if use_tasks else None,
            "suggested_next": phase.get("suggested_next", []),
            "input_artifacts": {
                "found": [str(p) for p in found],
                "missing": missing,
            },
            "reentry_context": reentry_context,
            "request": request_content,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"# Phase: {current_phase}")
        if current_phase_dir:
            print(f"Directory: {plan_dir / current_phase_dir}")
        print()

        # Request context
        if request_content:
            print("## Request")
            print(request_content)
            print()

        # Phase prompt
        prompt = phase.get("prompt", "")
        if prompt:
            print("## Phase Prompt")
            print(prompt)
            print()

        # Task schema (injected for phases with use_tasks=true)
        if workflow_mgr.uses_tasks(current_phase):
            print(TASK_SCHEMA)
            print()

        # Re-entry context
        if reentry_context:
            print("## Re-entry Context")
            print(reentry_context)
            print()

        # Input artifacts
        if found or missing:
            print("## Input Artifacts")
            if found:
                print("Found:")
                for path in found:
                    print(f"  - {path}")
            if missing:
                print("Missing:", file=sys.stderr)
                for path in missing:
                    print(f"  - {path}", file=sys.stderr)
            print()

        # Next phases
        suggested = phase.get("suggested_next", [])
        if suggested:
            print("## Suggested Next Phases")
            for phase_id in suggested:
                next_phase = workflow_mgr.get_phase(phase_id)
                if next_phase:
                    markers = []
                    if next_phase.get("terminal"):
                        markers.append("terminal")
                    if next_phase.get("requires_user_input"):
                        markers.append("requires user input")
                    marker_str = f" ({', '.join(markers)})" if markers else ""
                    print(f"  - {phase_id}{marker_str}")

    return 0


def cmd_phase_summary(args: argparse.Namespace) -> int:
    """Display compact phase summary for hooks."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 1

    phase = workflow_mgr.get_phase(current_phase)
    if not phase:
        print(f"Phase not found: {current_phase}", file=sys.stderr)
        return 1

    current_phase_dir = state.get("current_phase_dir")
    entry_num = state.get("current_phase_entry", 0)

    # Count phase history
    history = state.get("phase_history", [])
    total_entries = len(history)
    reentries = sum(1 for e in history if e.get("context_from"))

    # Check for re-entry
    prev_entries = [e for e in history if e.get("phase") == current_phase and e.get("entry") != entry_num]
    is_reentry = len(prev_entries) > 0

    # Build summary
    markers = []
    if phase.get("terminal"):
        markers.append("terminal")
    if phase.get("requires_user_input"):
        markers.append("user-input")
    if is_reentry:
        markers.append(f"re-entry from #{prev_entries[-1]['entry']}")

    marker_str = f" [{', '.join(markers)}]" if markers else ""
    print(f"Phase: {current_phase} (entry #{entry_num}){marker_str}")
    if current_phase_dir:
        print(f"Dir: {plan_dir / current_phase_dir}")

    # Show suggested next
    suggested = phase.get("suggested_next", [])
    if suggested:
        print(f"Next: {', '.join(suggested)}")

    return 0


def cmd_phase_tasks_file(args: argparse.Namespace) -> int:
    """Print current phase's tasks.json path."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks_file = get_tasks_file(plan_dir)
    if tasks_file:
        print(tasks_file)
        return 0
    print("No current phase", file=sys.stderr)
    return 1


def cmd_phase_tasks(args: argparse.Namespace) -> int:
    """List tasks in current phase."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks = get_tasks(plan_dir)
    if not tasks:
        print("No tasks in current phase")
        return 0

    for task in tasks:
        status = task.get("status", "todo")
        status_marker = {"todo": " ", "in-progress": "*", "done": "+", "blocked": "!"}
        marker = status_marker.get(status, " ")
        print(f"[{marker}] {task['id']}: {task.get('description', '')}")

    return 0


def cmd_phase_next_tasks(args: argparse.Namespace) -> int:
    """List available tasks in current phase."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    tasks = get_tasks(plan_dir)
    if not tasks:
        print("No tasks in current phase")
        return 0

    task_status = {t["id"]: t.get("status") for t in tasks}
    next_tasks = []
    for task in tasks:
        if task.get("status") != "todo":
            continue
        parents = task.get("parents", [])
        if all(task_status.get(pid) == "done" for pid in parents):
            next_tasks.append(task)

    if next_tasks:
        for task in next_tasks:
            print(f"{task['id']}: {task.get('description', '')}")
    else:
        # Check if all tasks are done
        all_done = all(t.get("status") == "done" for t in tasks)
        if all_done:
            print("All phase tasks complete")
        else:
            print("No tasks available (check blocked tasks)")

    return 0


def cmd_workflow_diagram(args: argparse.Namespace) -> int:
    """Display ASCII diagram of workflow phases and transitions."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    wm = WorkflowManager(plan_dir)
    if not wm.exists():
        print("No workflow.toml in this plan", file=sys.stderr)
        return 1

    try:
        workflow = wm.load()
        phases = workflow.get("phases", [])
    except Exception as e:
        print(f"Failed to load workflow: {e}", file=sys.stderr)
        return 1

    if not phases:
        print("No phases in workflow")
        return 0

    # Get current phase from state
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    # Build phase map for quick lookups
    phase_map = {p["id"]: p for p in phases}

    # Determine flow direction
    flow = getattr(args, "flow", "south")

    if flow == "east":
        # Horizontal flow: phase1 -> phase2 -> phase3
        _render_horizontal_diagram(phases, phase_map, current_phase)
    else:
        # Vertical flow (default): stack phases vertically
        _render_vertical_diagram(phases, phase_map, current_phase)

    return 0


def _render_vertical_diagram(phases: list[dict], phase_map: dict, current_phase: str | None) -> None:
    """Render workflow as vertical Unicode box diagram."""
    # Build transition graph
    transitions: dict[str, list[str]] = {}
    for phase in phases:
        pid = phase["id"]
        transitions[pid] = phase.get("suggested_next", [])

    # Print each phase with unicode boxes
    for i, phase in enumerate(phases):
        pid = phase["id"]
        is_current = pid == current_phase
        is_terminal = phase.get("terminal", False)
        requires_input = phase.get("requires_user_input", False)

        # Build annotations
        annotations = []
        if is_current:
            annotations.append("← current")
        if is_terminal:
            annotations.append("[terminal]")
        if requires_input:
            annotations.append("[user-input]")

        # Calculate box width
        ann_str = " ".join(annotations)
        content = pid
        box_width = max(len(content) + 2, 10)

        # Draw unicode box
        top = "┌" + "─" * box_width + "┐"
        mid = "│ " + content.center(box_width - 2) + " │"
        bot = "└" + "─" * box_width + "┘"

        print(f"  {top}")
        print(f"  {mid} {ann_str}")
        print(f"  {bot}")

        # Show transitions (arrows)
        next_phases = transitions.get(pid, [])
        if next_phases and not is_terminal:
            if len(next_phases) == 1:
                print(f"     │")
                print(f"     ↓")
            else:
                # Multiple transitions (branching)
                print(f"     │")
                for j, np in enumerate(next_phases):
                    prefix = "├" if j < len(next_phases) - 1 else "└"
                    print(f"     {prefix}──→ {np}")
        elif not is_terminal and i < len(phases) - 1:
            print(f"     │")
            print(f"     ↓")


def _render_horizontal_diagram(phases: list[dict], phase_map: dict, current_phase: str | None) -> None:
    """Render workflow as horizontal Unicode box diagram."""
    # Build boxes and arrows
    boxes = []
    for phase in phases:
        pid = phase["id"]
        is_current = pid == current_phase
        is_terminal = phase.get("terminal", False)
        requires_input = phase.get("requires_user_input", False)

        # Build markers
        markers = []
        if is_current:
            markers.append("*")
        if is_terminal:
            markers.append("!")
        if requires_input:
            markers.append("?")

        suffix = "".join(markers)
        boxes.append((pid, suffix))

    # Build three-line output (top, middle, bottom)
    top_line = ""
    mid_line = ""
    bot_line = ""

    for i, (pid, suffix) in enumerate(boxes):
        width = len(pid) + 2
        top_line += "┌" + "─" * width + "┐"
        mid_line += "│ " + pid + " │" + suffix
        bot_line += "└" + "─" * width + "┘"

        if i < len(boxes) - 1:
            top_line += "   "
            mid_line += " → "
            bot_line += "   "

    print(f"  {top_line}")
    print(f"  {mid_line}")
    print(f"  {bot_line}")

    # Legend
    print("\n  Legend: * = current, ! = terminal, ? = user-input")


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

    # User guidance commands
    subparsers.add_parser("get-user-guidance", help="Get user guidance from state.json")
    subparsers.add_parser("clear-user-guidance", help="Clear user guidance after processing")

    # --- Workflow Commands ---

    # Dead-end commands
    p_add_de = subparsers.add_parser("add-dead-end", help="Record a failed approach")
    p_add_de.add_argument("--task-id", required=True, help="Task ID where failure occurred")
    p_add_de.add_argument("--what-failed", required=True, help="What was attempted")
    p_add_de.add_argument("--why-failed", required=True, help="Why it failed")
    p_add_de.add_argument("--type", required=True, help="Discovery type (WRONG_ASSUMPTION, MISSING_PREREQUISITE, DEPENDENCY_CONFLICT, ARCHITECTURAL_MISMATCH, SCOPE_EXCEEDED, EXTERNAL_BLOCKER)")

    p_get_de = subparsers.add_parser("get-dead-ends", help="Get dead ends for prompt injection")
    p_get_de.add_argument("--json", action="store_true", help="Output as JSON")
    p_get_de.add_argument("--recent", type=int, default=0, help="Only show N most recent")

    p_clear_de = subparsers.add_parser("clear-dead-end", help="Remove a dead end")
    p_clear_de.add_argument("dead_end_id", help="Dead end ID to remove")

    # Phase navigation commands
    subparsers.add_parser("current-phase", help="Print current phase ID")

    subparsers.add_parser("current-phase-dir", help="Print current phase directory path")

    p_enter_phase = subparsers.add_parser("enter-phase", help="Enter a new phase")
    p_enter_phase.add_argument("phase_id", help="Phase ID to enter")
    p_enter_phase.add_argument("--reason", default="", help="Reason for entering/re-entering phase")

    subparsers.add_parser("suggested-next", help="List possible phase transitions")

    p_enter_by_num = subparsers.add_parser("enter-phase-by-number", help="Enter phase by number from suggested_next")
    p_enter_by_num.add_argument("number", type=int, help="Option number (1-indexed)")
    p_enter_by_num.add_argument("guidance", nargs="?", default="", help="Optional guidance text")

    subparsers.add_parser("phase-history", help="Show all phase entries")

    # Artifact commands
    p_record_art = subparsers.add_parser("record-artifact", help="Record artifact produced by current phase")
    p_record_art.add_argument("filename", help="Logical name for artifact")
    p_record_art.add_argument("path", help="Relative path to artifact file")

    p_input_art = subparsers.add_parser("input-artifacts", help="List all artifacts from prior phases")
    p_input_art.add_argument("--json", action="store_true", help="Output as JSON")

    # Phase display commands
    p_phase_ctx = subparsers.add_parser("phase-context", help="Display full phase context")
    p_phase_ctx.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers.add_parser("phase-summary", help="Display compact phase summary")

    # Phase task commands
    subparsers.add_parser("phase-tasks-file", help="Print current phase's tasks.json path")

    subparsers.add_parser("phase-tasks", help="List tasks in current phase")

    subparsers.add_parser("phase-next-tasks", help="List available tasks in current phase")

    # Workflow diagram
    p_diagram = subparsers.add_parser("workflow-diagram", help="Display ASCII diagram of workflow")
    p_diagram.add_argument("--flow", choices=["east", "south"], default="south", help="Direction (default: south)")

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
        "get-user-guidance": cmd_get_user_guidance,
        "clear-user-guidance": cmd_clear_user_guidance,
        # Workflow commands
        "add-dead-end": cmd_add_dead_end,
        "get-dead-ends": cmd_get_dead_ends,
        "clear-dead-end": cmd_clear_dead_end,
        # Phase navigation commands
        "current-phase": cmd_current_phase,
        "current-phase-dir": cmd_current_phase_dir,
        "enter-phase": cmd_enter_phase,
        "suggested-next": cmd_suggested_next,
        "enter-phase-by-number": cmd_enter_phase_by_number,
        "phase-history": cmd_phase_history,
        # Artifact commands
        "record-artifact": cmd_record_artifact,
        "input-artifacts": cmd_input_artifacts,
        # Phase display commands
        "phase-context": cmd_phase_context,
        "phase-summary": cmd_phase_summary,
        # Phase task commands
        "phase-tasks-file": cmd_phase_tasks_file,
        "phase-tasks": cmd_phase_tasks,
        "phase-next-tasks": cmd_phase_next_tasks,
        # Workflow diagram
        "workflow-diagram": cmd_workflow_diagram,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
