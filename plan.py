#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomli_w"]
# ///
"""
Plan management CLI for long-running agent harness.

Usage: uv run $PLUGIN_ROOT/plan.py <subcommand> [args]
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Plugin root directory (for generating portable paths in prompts)
PLUGIN_ROOT = Path(__file__).parent

# Task schema documentation injected into phases with use_tasks=true
# Keep in sync with schemas/tasks-schema.json
TASK_SCHEMA = """
## Task Schema

Create `tasks.json` as a JSON array of task objects:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (kebab-case) |
| `description` | Yes | What the task accomplishes |
| `status` | Yes | Always `"todo"` when creating |
| `type` | No | Task type: `cache-reference`, `prototype` |
| `steps` | No | Array of concrete steps |
| `parents` | No | Task IDs that must complete first (empty `[]` if none) |
| `context_artifacts` | No | Artifact names to include (e.g., `["request", "design"]`) |
| `subagent` | No | Agent type: `general-purpose` (default), `Explore`, `gemini-reviewer`, `codex-reviewer` |
| `subagent_prompt` | No | Additional context (e.g., `"very thorough analysis"`) |
| `model` | No | `sonnet` (default), `haiku`, `opus` |
| `question` | No | For prototype tasks: the question being answered |
| `hypothesis` | No | For prototype tasks: expected outcome |
| `inject_project_context` | No | Include project CLAUDE.md in task prompt (default: false) |
| `locks` | No | Lock names for exclusive access (files, tools, or resources) |
| `cache_id` | No | Cache entry ID for cache-reference type tasks |

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
    "locks": ["cargo"],
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

Use `locks` to serialize tasks needing exclusive access to the same resource:
- `"cargo"` - Rust builds (cargo build/check/test)
- `"browser"` - Browser automation tools
- `"src/config.rs"` - Specific files edited by multiple tasks
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
    """Append entry to task's progress.txt in current phase directory."""
    task_dir = get_task_output_dir(plan_dir, task_id)
    if not task_dir:
        # Fallback for non-workflow plans (legacy)
        task_dir = plan_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    progress_file = task_dir / "progress.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(progress_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def log_phase_progress(plan_dir: Path, message: str) -> None:
    """Append entry to current phase's progress.txt."""
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_dir = state.get("current_phase_dir")
    if not current_dir:
        return
    phase_dir = plan_dir / current_dir
    phase_dir.mkdir(parents=True, exist_ok=True)
    progress_file = phase_dir / "progress.txt"
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
        old_phase_id = state.get("current_phase")
        if state.get("phase_history"):
            current_entry = state["phase_history"][-1]
            if "exited" not in current_entry:
                current_entry["exited"] = datetime.now().isoformat()
                current_entry["outcome"] = "completed"

        # Reset retry counter for old phase if transitioning to a different phase
        # (successful completion, not a loopback)
        if old_phase_id and old_phase_id != phase_id:
            if "phase_retries" in state and old_phase_id in state["phase_retries"]:
                state["phase_retries"][old_phase_id] = 0

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
            "phase_retries": {},
        }

    def get_phase_retries(self, phase_id: str) -> int:
        """Get the number of re-entries for a phase (not including original)."""
        state = self.load()
        return state.get("phase_retries", {}).get(phase_id, 0)

    def increment_phase_retries(self, phase_id: str) -> int:
        """Increment retry count for a phase. Returns new count."""
        state = self.load()
        if "phase_retries" not in state:
            state["phase_retries"] = {}
        current = state["phase_retries"].get(phase_id, 0)
        state["phase_retries"][phase_id] = current + 1
        self.save(state)
        return current + 1

    def reset_phase_retries(self, phase_id: str) -> None:
        """Reset retry counter for a phase (on successful completion)."""
        state = self.load()
        if "phase_retries" in state and phase_id in state["phase_retries"]:
            state["phase_retries"][phase_id] = 0
            self.save(state)

    def get_pending_approval(self) -> dict | None:
        """Get pending approval info if exists."""
        state = self.load()
        return state.get("pending_approval")

    def set_pending_approval(
        self,
        from_phase: str,
        to_phase: str,
        reason: str,
        from_entry: int,
    ) -> None:
        """Set pending approval for a transition.

        Args:
            from_phase: Source phase ID
            to_phase: Target phase ID
            reason: Why transition is needed
            from_entry: Current phase entry number (for staleness check)
        """
        state = self.load()
        state["pending_approval"] = {
            "from_phase": from_phase,
            "from_entry": from_entry,
            "to_phase": to_phase,
            "reason": reason,
            "proposed_at": datetime.now().isoformat(),
        }
        self.save(state)

    def clear_pending_approval(self) -> None:
        """Clear any pending approval."""
        state = self.load()
        if "pending_approval" in state:
            del state["pending_approval"]
            self.save(state)

    def validate_pending_approval(self) -> tuple[bool, str]:
        """Validate pending approval is not stale.

        Returns:
            (is_valid, error_message) - is_valid is True if approval can proceed
        """
        state = self.load()
        pending = state.get("pending_approval")
        if not pending:
            return False, "No pending approval"

        current_entry = state.get("current_phase_entry", 0)
        pending_entry = pending.get("from_entry", 0)

        if current_entry != pending_entry:
            return False, f"Stale approval: proposed at entry {pending_entry}, now at entry {current_entry}"

        return True, ""

    def record_expansion(self, phase_id: str, generated_phases: list[str]):
        """Record expansion event in state.

        Args:
            phase_id: The phase that triggered expansion
            generated_phases: List of phase IDs that were generated
        """
        state = self.load()
        if "expansions" not in state:
            state["expansions"] = []
        state["expansions"].append({
            "phase": phase_id,
            "generated": generated_phases,
            "timestamp": datetime.now().isoformat()
        })
        self.save(state)

    def get_expansions(self) -> list[dict]:
        """Get all expansion events.

        Returns:
            List of expansion event dicts with phase, generated, timestamp
        """
        return self.load().get("expansions", [])


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
        """Get suggested next phases for a given phase (phase IDs only)."""
        return self.normalize_suggested_next(
            self.get_phase(phase_id).get("suggested_next", []) if self.get_phase(phase_id) else []
        )

    def normalize_suggested_next(self, suggested_next: list) -> list[str]:
        """Extract phase IDs from mixed string/object format.

        Handles both:
        - "phase-id" (string)
        - {"phase": "phase-id", "requires_approval": true} (object)
        """
        result = []
        for item in suggested_next:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                phase_id = item.get("phase", "")
                if phase_id:
                    result.append(phase_id)
        return result

    def get_suggested_next_full(self, phase_id: str) -> list[dict]:
        """Get suggested_next with full metadata for each item.

        Returns list of dicts with 'phase', 'requires_approval', 'approval_prompt'.
        """
        phase = self.get_phase(phase_id)
        if not phase:
            return []
        suggested = phase.get("suggested_next", [])
        result = []
        for item in suggested:
            if isinstance(item, str):
                result.append({"phase": item, "requires_approval": False})
            elif isinstance(item, dict):
                # Ensure required fields are present
                result.append({
                    "phase": item.get("phase", ""),
                    "requires_approval": item.get("requires_approval", False),
                    "approval_prompt": item.get("approval_prompt"),
                })
        return result

    def get_approval_prompt(self, from_phase: str, to_phase: str) -> str | None:
        """Get approval prompt for a transition, if any."""
        for item in self.get_suggested_next_full(from_phase):
            if item.get("phase") == to_phase:
                return item.get("approval_prompt")
        return None

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

    def supports_cache_reference(self, phase_id: str) -> bool:
        """Check if phase supports cache-reference tasks."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("supports_cache_reference", False)
        return False

    def supports_prototypes(self, phase_id: str) -> bool:
        """Check if phase supports prototype tasks."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("supports_prototypes", False)
        return False

    def supports_validation(self, phase_id: str) -> bool:
        """Check if phase supports validation tasks."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("supports_validation", False)
        return False

    def supports_test_definition(self, phase_id: str) -> bool:
        """Check if phase supports test definition tasks."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("supports_test_definition", False)
        return False

    def supports_proposals(self, phase_id: str) -> bool:
        """Check if phase supports CLAUDE.md proposals."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("supports_proposals", False)
        return False

    def get_max_iterations(self, phase_id: str) -> int | None:
        """Get max iterations for a phase (for research loops)."""
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("max_iterations")
        return None

    def get_max_retries(self, phase_id: str) -> int | None:
        """Get max retries for a phase (re-entries, not total).

        Returns None if no limit configured.
        A value of 3 means 4 total entries (1 original + 3 retries).
        """
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("max_retries")
        return None

    def get_required_artifacts(self, phase_id: str) -> list[str]:
        """Get required artifacts for a phase.

        Returns list of artifact names that must be recorded before
        transitioning out of this phase. Empty list if none required.
        """
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("required_artifacts", [])
        return []

    def get_context_artifacts(self, phase_id: str) -> list[str]:
        """Get context artifacts for a phase.

        Returns list of artifact names that should be injected into
        the phase context from upstream phases. Empty list if none needed.
        """
        phase = self.get_phase(phase_id)
        if phase:
            return phase.get("context_artifacts", [])
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

    def transition_requires_approval(self, from_phase: str, to_phase: str) -> bool:
        """Check if transition requires user approval.

        Reads from suggested_next objects with requires_approval field.
        """
        for item in self.get_suggested_next_full(from_phase):
            if item.get("phase") == to_phase:
                return item.get("requires_approval", False)
        return False

    def is_transition_allowed(self, from_phase: str, to_phase: str) -> bool:
        """Check if transition is allowed.

        Allowed if:
        - to_phase in from_phase.suggested_next (string or object)
        - OR from_phase.on_blocked == to_phase
        """
        # Check on_blocked
        on_blocked = self.get_on_blocked(from_phase)
        if on_blocked == to_phase:
            return True
        # Handle "self" as special value
        if on_blocked == "self" and from_phase == to_phase:
            return True

        # Check suggested_next (handles both string and object format)
        suggested = self.get_suggested_next(from_phase)
        if to_phase in suggested:
            return True

        return False

    def validate_phase_references(self) -> list[str]:
        """Validate all phase ID references in workflow config.

        Returns list of errors if any phase IDs in on_blocked or
        suggested_next don't exist.
        """
        errors = []
        if not self.exists():
            return errors

        workflow = self.load()
        phases = workflow.get("phases", [])
        phase_ids = {p.get("id") for p in phases}

        # Check on_blocked references
        for phase in phases:
            pid = phase.get("id")
            on_blocked = phase.get("on_blocked")
            if on_blocked and on_blocked != "self" and on_blocked not in phase_ids:
                errors.append(f"Phase '{pid}' has on_blocked='{on_blocked}' but phase '{on_blocked}' doesn't exist")

            # Check suggested_next references (handles both string and object format)
            for item in phase.get("suggested_next", []):
                if isinstance(item, str):
                    target = item
                elif isinstance(item, dict):
                    target = item.get("phase", "")
                    # Check approval_prompt is present when requires_approval is true
                    if item.get("requires_approval") and not item.get("approval_prompt"):
                        errors.append(f"Phase '{pid}' transition to '{target}' requires approval but has no approval_prompt")
                else:
                    continue

                if target and target not in phase_ids and target not in ("complete", "__expand__"):
                    errors.append(f"Phase '{pid}' has suggested_next '{target}' which doesn't exist")

        return errors

    def is_expandable(self, phase_id: str) -> bool:
        """Check if phase has __expand__ marker in suggested_next."""
        # Use normalized version which extracts phase IDs from objects
        suggested_ids = self.get_suggested_next(phase_id)
        return "__expand__" in suggested_ids

    def get_expand_prompt(self, phase_id: str) -> str | None:
        """Get expansion prompt for expandable phase."""
        phase = self.get_phase(phase_id)
        return phase.get("expand_prompt") if phase else None

    def invalidate_cache(self):
        """Clear cached workflow to force reload."""
        self._workflow = None

    def validate_schema(self) -> list[str]:
        """Validate workflow.toml schema - check for unknown/invalid fields.

        Returns list of error strings for unknown fields.
        """
        errors = []
        if not self.exists():
            return errors

        workflow = self.load()

        # Valid top-level keys
        VALID_TOP_LEVEL = {"workflow", "phases"}
        for key in workflow.keys():
            if key not in VALID_TOP_LEVEL:
                errors.append(f"Unknown top-level key: '{key}' (valid: {VALID_TOP_LEVEL})")

        # Valid [workflow] section keys
        VALID_WORKFLOW_KEYS = {"name", "description"}
        workflow_section = workflow.get("workflow", {})
        if isinstance(workflow_section, dict):
            for key in workflow_section.keys():
                if key not in VALID_WORKFLOW_KEYS:
                    errors.append(f"Unknown [workflow] key: '{key}' (valid: {VALID_WORKFLOW_KEYS})")

        # Valid [[phases]] keys
        VALID_PHASE_KEYS = {
            "id", "prompt", "suggested_next", "terminal", "use_tasks",
            "requires_user_input", "on_blocked", "max_retries", "max_iterations",
            "supports_proposals", "supports_prototypes", "supports_cache_reference",
            "expand_prompt", "required_artifacts", "context_artifacts",
        }
        # Valid keys in suggested_next objects
        VALID_TRANSITION_KEYS = {"phase", "requires_approval", "approval_prompt"}

        phases = workflow.get("phases", [])
        if not isinstance(phases, list):
            errors.append(f"'phases' must be an array, got {type(phases).__name__}")
            return errors

        for i, phase in enumerate(phases):
            if not isinstance(phase, dict):
                errors.append(f"Phase {i} must be a table, got {type(phase).__name__}")
                continue

            phase_id = phase.get("id", f"<index {i}>")
            for key in phase.keys():
                if key not in VALID_PHASE_KEYS:
                    errors.append(f"Phase '{phase_id}' has unknown key: '{key}' (valid: {sorted(VALID_PHASE_KEYS)})")

            # Check required fields
            if "id" not in phase:
                errors.append(f"Phase at index {i} missing required 'id' field")
            if "prompt" not in phase:
                errors.append(f"Phase '{phase_id}' missing required 'prompt' field")

            # Validate suggested_next items
            for item in phase.get("suggested_next", []):
                if isinstance(item, dict):
                    for key in item.keys():
                        if key not in VALID_TRANSITION_KEYS:
                            errors.append(f"Phase '{phase_id}' suggested_next has unknown key: '{key}' (valid: {VALID_TRANSITION_KEYS})")

        return errors

    def validate_expandable(self) -> list[str]:
        """Validate expandable phase configuration.

        Checks:
        - Phases with __expand__ have expand_prompt
        - Phases with expand_prompt have __expand__ in suggested_next
        - __expand__ can only coexist with "complete" in suggested_next

        Returns list of error strings.
        """
        errors = []
        for phase in self.get_all_phases():
            # Use normalized suggested_next to handle both string and object formats
            suggested_ids = self.normalize_suggested_next(phase.get("suggested_next", []))
            has_expand_marker = "__expand__" in suggested_ids
            has_expand_prompt = "expand_prompt" in phase

            if has_expand_marker and not has_expand_prompt:
                errors.append(
                    f"Phase '{phase['id']}' has __expand__ but no expand_prompt"
                )
            if has_expand_prompt and not has_expand_marker:
                errors.append(
                    f"Phase '{phase['id']}' has expand_prompt but no __expand__ in suggested_next"
                )
            # __expand__ can coexist with "complete" only
            if has_expand_marker and len(suggested_ids) > 1:
                other_targets = [
                    t for t in suggested_ids if t not in ("__expand__", "complete")
                ]
                if other_targets:
                    errors.append(
                        f"Phase '{phase['id']}' has __expand__ mixed with non-complete targets: {other_targets}"
                    )

        return errors


def get_assembled_prompts(workflow_mgr: "WorkflowManager", phase_id: str) -> str:
    """Assemble prompts based on workflow phase configuration flags.

    Reads prompt files from the prompts/ directory and concatenates them
    based on which flags are enabled for the phase.

    Args:
        workflow_mgr: WorkflowManager instance
        phase_id: ID of the current phase

    Returns:
        Assembled prompt string with all applicable guidance
    """
    # Get the prompts directory (relative to plan.py location)
    prompts_dir = Path(__file__).parent / "prompts"
    if not prompts_dir.exists():
        return ""

    prompt_parts: list[str] = []

    # Core task execution (required for any task-based phase)
    if workflow_mgr.uses_tasks(phase_id):
        task_exec_file = prompts_dir / "task-execution.md"
        if task_exec_file.exists():
            prompt_parts.append(task_exec_file.read_text())

    # Optional task types
    if workflow_mgr.supports_cache_reference(phase_id):
        cache_ref_file = prompts_dir / "cache-reference.md"
        if cache_ref_file.exists():
            prompt_parts.append(cache_ref_file.read_text())

    if workflow_mgr.supports_prototypes(phase_id):
        prototype_file = prompts_dir / "prototype.md"
        if prototype_file.exists():
            prompt_parts.append(prototype_file.read_text())

    # Research iteration support
    if workflow_mgr.get_max_iterations(phase_id):
        iteration_file = prompts_dir / "iteration-guidance.md"
        if iteration_file.exists():
            prompt_parts.append(iteration_file.read_text())

    # Validation/test phases
    if workflow_mgr.supports_validation(phase_id):
        validation_file = prompts_dir / "validation-tasks.md"
        if validation_file.exists():
            prompt_parts.append(validation_file.read_text())

    if workflow_mgr.supports_test_definition(phase_id):
        test_def_file = prompts_dir / "test-definition.md"
        if test_def_file.exists():
            prompt_parts.append(test_def_file.read_text())

    # CLAUDE.md proposals support
    if workflow_mgr.supports_proposals(phase_id):
        proposals_file = prompts_dir / "claude-md-proposals.md"
        if proposals_file.exists():
            prompt_parts.append(proposals_file.read_text())

    # User review instructions for phases requiring user input
    if workflow_mgr.requires_user_input(phase_id):
        suggested_next = workflow_mgr.get_suggested_next(phase_id)
        if suggested_next:
            # Build numbered options list
            options_lines = []
            for i, opt in enumerate(suggested_next, 1):
                # Handle both string and object formats
                phase_name = opt if isinstance(opt, str) else opt.get("phase", "")
                if phase_name:
                    options_lines.append(f"{i}. **{phase_name}**")

            if options_lines:
                user_review = """# User Review Required

This phase requires your approval before proceeding.

## Options
Present these numbered options to the user:
"""
                user_review += "\n".join(options_lines)
                user_review += """

After presenting options, show: `Use /jons-plan:proceed <number> [optional feedback]` to select.

Examples:
- `/jons-plan:proceed 1` - Select first option
- `/jons-plan:proceed 2 <feedback>` - Select second option with guidance

**Stop and await user input.**"""
                prompt_parts.append(user_review)

    return "\n\n".join(prompt_parts)


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


# --- Research Cache ---


@dataclass
class CacheEntry:
    """A cached research entry."""

    id: int
    query: str
    query_normalized: str
    findings: str
    created_at: int
    expires_at: int
    source_type: str
    source_url: str | None
    plan_id: str | None
    supersedes_id: int | None
    is_expired: bool
    score: float | None = None  # BM25 score (only when from search)


@dataclass
class CacheStats:
    """Research cache statistics."""

    total_entries: int
    active_entries: int
    expired_entries: int
    total_size_kb: float
    oldest_entry: int | None
    newest_entry: int | None
    entries_by_source: dict[str, int]


class ResearchCache:
    """SQLite FTS5-based research cache for storing and searching research results."""

    BUSY_TIMEOUT_MS = 5000  # 5 second timeout for locked database
    MAX_FINDINGS_SIZE = 1_000_000  # 1MB max
    WARN_FINDINGS_SIZE = 100_000  # 100KB warning threshold
    GC_THRESHOLD = 100  # Run auto-GC when this many expired entries exist
    DEFAULT_TTL_DAYS = 30

    # Schema for external-content FTS5 with triggers
    SCHEMA = """
    -- Main storage table (single source of truth)
    CREATE TABLE IF NOT EXISTS research_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        query_normalized TEXT NOT NULL,
        findings TEXT NOT NULL,
        created_at INTEGER NOT NULL DEFAULT (unixepoch()),
        expires_at INTEGER NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'web_search',
        source_url TEXT,
        plan_id TEXT,
        supersedes_id INTEGER REFERENCES research_entries(id)
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_expires ON research_entries(expires_at);
    CREATE INDEX IF NOT EXISTS idx_query_norm ON research_entries(query_normalized);
    CREATE INDEX IF NOT EXISTS idx_source_type ON research_entries(source_type);
    CREATE INDEX IF NOT EXISTS idx_plan_id ON research_entries(plan_id);

    -- FTS5 table for full-text search (external content mode)
    CREATE VIRTUAL TABLE IF NOT EXISTS research_fts USING fts5(
        query,
        findings,
        content='research_entries',
        content_rowid='id',
        tokenize='porter unicode61'
    );

    -- Triggers to keep FTS in sync with main table
    CREATE TRIGGER IF NOT EXISTS research_ai AFTER INSERT ON research_entries BEGIN
        INSERT INTO research_fts(rowid, query, findings)
        VALUES (new.id, new.query, new.findings);
    END;

    CREATE TRIGGER IF NOT EXISTS research_ad AFTER DELETE ON research_entries BEGIN
        INSERT INTO research_fts(research_fts, rowid, query, findings)
        VALUES ('delete', old.id, old.query, old.findings);
    END;

    CREATE TRIGGER IF NOT EXISTS research_au AFTER UPDATE ON research_entries BEGIN
        INSERT INTO research_fts(research_fts, rowid, query, findings)
        VALUES ('delete', old.id, old.query, old.findings);
        INSERT INTO research_fts(rowid, query, findings)
        VALUES (new.id, new.query, new.findings);
    END;
    """

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.cache_dir = project_dir / ".claude" / "jons-plan" / "research-cache"
        self.db_path = self.cache_dir / "cache.db"
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database and schema if needed."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            # Set BM25 weights (query 10x, findings 1x)
            # Note: This may fail if already set, which is fine
            try:
                conn.execute(
                    "INSERT INTO research_fts(research_fts, rank) "
                    "VALUES('rank', 'bm25(10.0, 1.0)')"
                )
            except sqlite3.OperationalError:
                pass  # Already configured

    def _connect(self) -> sqlite3.Connection:
        """Create connection with appropriate settings."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"PRAGMA busy_timeout = {self.BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA auto_vacuum = incremental")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize query for duplicate detection: lowercase, trim, collapse whitespace."""
        return " ".join(query.lower().split())

    def add(
        self,
        query: str,
        findings: str,
        ttl_days: int | None = None,
        source_type: str = "web_search",
        source_url: str | None = None,
        plan_id: str | None = None,
        replace: bool = False,
    ) -> int:
        """
        Add research to cache. Returns entry id.

        Args:
            query: The research query/question
            findings: The research findings/answer
            ttl_days: Days until expiration (default 30)
            source_type: Type of source (web_search, documentation, etc.)
            source_url: URL of the source if applicable
            plan_id: ID of the plan that created this entry
            replace: If True, delete existing entry with same normalized query

        Returns:
            The ID of the new entry

        Raises:
            ValueError: If findings exceed MAX_FINDINGS_SIZE
        """
        if ttl_days is None:
            ttl_days = self.DEFAULT_TTL_DAYS

        # Size check
        if len(findings) > self.MAX_FINDINGS_SIZE:
            raise ValueError(
                f"Findings too large ({len(findings)} bytes). "
                f"Maximum is {self.MAX_FINDINGS_SIZE} bytes."
            )
        if len(findings) > self.WARN_FINDINGS_SIZE:
            print(
                f"Warning: Large findings ({len(findings)} bytes). "
                f"Consider summarizing.",
                file=sys.stderr,
            )

        query_normalized = self.normalize_query(query)
        expires_at = int(datetime.now().timestamp()) + (ttl_days * 86400)

        with self._connect() as conn:
            # Check for existing entry with same normalized query
            existing = conn.execute(
                "SELECT id FROM research_entries WHERE query_normalized = ?",
                (query_normalized,),
            ).fetchone()

            supersedes_id = None
            if existing:
                if replace:
                    # Delete existing entry
                    conn.execute(
                        "DELETE FROM research_entries WHERE id = ?", (existing["id"],)
                    )
                else:
                    # Track supersession
                    supersedes_id = existing["id"]

            # Insert new entry
            cursor = conn.execute(
                """
                INSERT INTO research_entries
                (query, query_normalized, findings, expires_at, source_type,
                 source_url, plan_id, supersedes_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    query_normalized,
                    findings,
                    expires_at,
                    source_type,
                    source_url,
                    plan_id,
                    supersedes_id,
                ),
            )
            entry_id = cursor.lastrowid
            conn.commit()

            # Opportunistic GC
            self._maybe_gc(conn)

            return entry_id

    def search(
        self, query: str, limit: int = 5, include_expired: bool = False
    ) -> list[CacheEntry]:
        """
        Search cache using FTS5. Returns ranked results.

        Note: Lower BM25 scores indicate higher relevance.
        Results are sorted by score ascending (most relevant first).

        Args:
            query: Search query
            limit: Maximum number of results
            include_expired: If True, include expired entries

        Returns:
            List of CacheEntry objects sorted by relevance
        """
        now = int(datetime.now().timestamp())

        with self._connect() as conn:
            # Build query with optional expiry filter
            sql = """
                SELECT
                    e.id, e.query, e.query_normalized, e.findings,
                    e.created_at, e.expires_at, e.source_type,
                    e.source_url, e.plan_id, e.supersedes_id,
                    bm25(research_fts) as score
                FROM research_fts f
                JOIN research_entries e ON f.rowid = e.id
                WHERE research_fts MATCH ?
            """
            params: list = [query]

            if not include_expired:
                sql += " AND e.expires_at > ?"
                params.append(now)

            # Only return latest version of each normalized query
            sql += """
                AND e.id = (
                    SELECT MAX(e2.id) FROM research_entries e2
                    WHERE e2.query_normalized = e.query_normalized
                )
            """

            sql += " ORDER BY score ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            # Opportunistic GC (less frequent for searches)
            self._maybe_gc(conn)

            return [
                CacheEntry(
                    id=row["id"],
                    query=row["query"],
                    query_normalized=row["query_normalized"],
                    findings=row["findings"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    source_type=row["source_type"],
                    source_url=row["source_url"],
                    plan_id=row["plan_id"],
                    supersedes_id=row["supersedes_id"],
                    is_expired=row["expires_at"] <= now,
                    score=row["score"],
                )
                for row in rows
            ]

    def get(self, entry_id: int, allow_expired: bool = False) -> CacheEntry | None:
        """
        Get specific cache entry by ID.

        Args:
            entry_id: The entry ID
            allow_expired: If True, return even if expired

        Returns:
            CacheEntry if found (and not expired unless allow_expired), None otherwise
        """
        now = int(datetime.now().timestamp())

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, query, query_normalized, findings, created_at,
                       expires_at, source_type, source_url, plan_id, supersedes_id
                FROM research_entries WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()

            if not row:
                return None

            is_expired = row["expires_at"] <= now
            if is_expired and not allow_expired:
                return None

            return CacheEntry(
                id=row["id"],
                query=row["query"],
                query_normalized=row["query_normalized"],
                findings=row["findings"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                source_type=row["source_type"],
                source_url=row["source_url"],
                plan_id=row["plan_id"],
                supersedes_id=row["supersedes_id"],
                is_expired=is_expired,
            )

    def clear(
        self,
        entry_id: int | None = None,
        query: str | None = None,
        all_entries: bool = False,
    ) -> int:
        """
        Clear entries. Returns count deleted.

        Args:
            entry_id: Delete specific entry by ID
            query: Delete entries matching exact normalized query
            all_entries: Delete all entries (requires explicit flag)

        Returns:
            Number of entries deleted

        Raises:
            ValueError: If no targeting argument provided
        """
        if not any([entry_id, query, all_entries]):
            raise ValueError(
                "Must specify --id, --query, or --all to clear entries"
            )

        with self._connect() as conn:
            if all_entries:
                cursor = conn.execute("DELETE FROM research_entries")
            elif entry_id:
                cursor = conn.execute(
                    "DELETE FROM research_entries WHERE id = ?", (entry_id,)
                )
            elif query:
                query_normalized = self.normalize_query(query)
                cursor = conn.execute(
                    "DELETE FROM research_entries WHERE query_normalized = ?",
                    (query_normalized,),
                )
            else:
                return 0

            count = cursor.rowcount
            conn.commit()
            return count

    def gc(self) -> int:
        """Delete expired entries. Returns count deleted."""
        now = int(datetime.now().timestamp())
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM research_entries WHERE expires_at <= ?", (now,)
            )
            count = cursor.rowcount
            conn.commit()
            # Reclaim space
            conn.execute("PRAGMA incremental_vacuum")
            return count

    def _maybe_gc(self, conn: sqlite3.Connection) -> None:
        """Run GC if expired count exceeds threshold."""
        result = conn.execute(
            "SELECT COUNT(*) as cnt FROM research_entries WHERE expires_at <= unixepoch()"
        ).fetchone()
        if result and result["cnt"] > self.GC_THRESHOLD:
            conn.execute(
                "DELETE FROM research_entries WHERE expires_at <= unixepoch()"
            )
            conn.commit()

    def stats(self) -> CacheStats:
        """Return cache statistics."""
        now = int(datetime.now().timestamp())

        with self._connect() as conn:
            # Total entries
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM research_entries"
            ).fetchone()["cnt"]

            # Active vs expired
            active = conn.execute(
                "SELECT COUNT(*) as cnt FROM research_entries WHERE expires_at > ?",
                (now,),
            ).fetchone()["cnt"]

            # Oldest and newest
            times = conn.execute(
                "SELECT MIN(created_at) as oldest, MAX(created_at) as newest "
                "FROM research_entries"
            ).fetchone()

            # Entries by source type
            by_source = {}
            for row in conn.execute(
                "SELECT source_type, COUNT(*) as cnt FROM research_entries "
                "GROUP BY source_type"
            ):
                by_source[row["source_type"]] = row["cnt"]

            # Database size
            size_kb = 0.0
            if self.db_path.exists():
                size_kb = self.db_path.stat().st_size / 1024

            return CacheStats(
                total_entries=total,
                active_entries=active,
                expired_entries=total - active,
                total_size_kb=size_kb,
                oldest_entry=times["oldest"],
                newest_entry=times["newest"],
                entries_by_source=by_source,
            )


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

    # Clear pending approval from old plan if switching
    old_plan_dir = get_active_plan_dir(project_dir)
    if old_plan_dir and old_plan_dir != plan_dir:
        state_mgr = StateManager(old_plan_dir)
        state_mgr.clear_pending_approval()

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

    # Clear pending approval before deactivating
    plan_dir = get_active_plan_dir(project_dir)
    if plan_dir:
        state_mgr = StateManager(plan_dir)
        state_mgr.clear_pending_approval()

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


def has_lock_conflict(task: dict, all_tasks: list) -> bool:
    """Check if task's locks conflict with any in-progress tasks.

    Returns True if the task requires exclusive access to a lock
    that is currently held by an in-progress task.
    """
    task_locks = set(task.get("locks", []))
    if not task_locks:
        return False  # No locks = no conflict possible

    for other in all_tasks:
        if other["id"] == task["id"]:
            continue
        if other.get("status") == "in-progress":
            other_locks = set(other.get("locks", []))
            if task_locks & other_locks:  # Set intersection
                return True
    return False


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
            if not has_lock_conflict(task, tasks):
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
    tasks_file = save_tasks(plan_dir, tasks)
    if tasks_file:
        print(f"Updated: {tasks_file}")
    else:
        print("Warning: No current phase - could not determine tasks.json location", file=sys.stderr)
        return 1
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


def cmd_phase_log(args: argparse.Namespace) -> int:
    """Append message to current phase's progress.txt."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_dir = state.get("current_phase_dir")
    if not current_dir:
        print("No current phase", file=sys.stderr)
        return 1

    phase_dir = plan_dir / current_dir
    phase_dir.mkdir(parents=True, exist_ok=True)
    progress_file = phase_dir / "progress.txt"
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
    tasks_file = save_tasks(plan_dir, tasks)

    if not tasks_file:
        print("No current phase - cannot determine tasks.json location", file=sys.stderr)
        return 1

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

    # 1b. For prototype tasks, include question and hypothesis
    if task.get("type") == "prototype":
        question = task.get("question")
        hypothesis = task.get("hypothesis")
        if question:
            prompt_parts.append(f"\n**Question:** {question}")
        if hypothesis:
            prompt_parts.append(f"\n**Hypothesis:** {hypothesis}")

    # 1c. Plugin prompt file - inject specialized instructions from prompts/ directory
    prompt_file = task.get("prompt_file")
    if prompt_file:
        # Plugin root is where this script lives
        plugin_root = Path(__file__).parent
        prompt_path = plugin_root / "prompts" / f"{prompt_file}.md"
        if prompt_path.exists():
            prompt_content = prompt_path.read_text().strip()
            if prompt_content:
                prompt_parts.append(f"\n\n## Instructions\n\n{prompt_content}")
        else:
            # Warn but don't fail - the prompt file might be optional
            print(f"Warning: prompt_file '{prompt_file}' not found at {prompt_path}", file=sys.stderr)

    # 2. Steps list
    steps = task.get("steps", [])
    if steps:
        prompt_parts.append("\nSteps:")
        for step in steps:
            prompt_parts.append(f"- {step}")

    # 2b. Project context (CLAUDE.md) - opt-in via task field
    if task.get("inject_project_context", False):
        claude_md_paths = [
            project_dir / ".claude" / "CLAUDE.md",
            project_dir / "CLAUDE.md",
        ]
        for claude_path in claude_md_paths:
            if claude_path.exists():
                content = claude_path.read_text().strip()
                if content:
                    # Size guard: truncate if over 500 lines
                    lines = content.split('\n')
                    if len(lines) > 500:
                        content = '\n'.join(lines[:500])
                        content += f"\n\n[... truncated, {len(lines) - 500} lines omitted]"
                    prompt_parts.append(f"\n\n## Project Context (from {claude_path.name})")
                    prompt_parts.append(content)
                break

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

    # 6. Progress logging (required for resumption)
    prompt_parts.append("\n\n## Progress Logging (Required)")
    prompt_parts.append("Log key actions as you work to enable resumption and provide visibility:")
    prompt_parts.append("```bash")
    prompt_parts.append(f"uv run {PLUGIN_ROOT}/plan.py task-log {args.task_id} \"<message>\"")
    prompt_parts.append("```")
    prompt_parts.append("")
    prompt_parts.append("**What to log:**")
    prompt_parts.append("- File modifications: `\"Edited path/to/file.py: Brief description of change\"`")
    prompt_parts.append("- Key decisions: `\"Chose approach X because Y\"`")
    prompt_parts.append("- Blockers: `\"BLOCKED: Description of issue\"`")
    prompt_parts.append("- Completion: `\"Complete: Summary of what was accomplished\"`")
    prompt_parts.append("")
    prompt_parts.append("Log after each file edit, decision, or significant step.")

    # 7. Task output directory (for artifacts)
    output_dir = get_task_output_dir(plan_dir, args.task_id)
    if output_dir:
        prompt_parts.append("\n\n## Task Output Directory")
        prompt_parts.append(f"For findings, research results, or artifacts for downstream tasks:")
        prompt_parts.append(f"- Output path: `{output_dir}/`")
        prompt_parts.append(f"- Create files as needed (e.g., findings.md, analysis.md)")

    # 8. CLAUDE.md proposals (if phase supports it)
    workflow_mgr = WorkflowManager(plan_dir)
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase_id = state.get("current_phase")
    if current_phase_id and workflow_mgr.supports_proposals(current_phase_id):
        prompts_dir = Path(__file__).parent / "prompts"
        proposals_file = prompts_dir / "claude-md-proposals.md"
        if proposals_file.exists():
            prompt_parts.append("\n\n" + proposals_file.read_text().strip())

    # 9. CLI reference for task completion
    prompt_parts.append("\n\n## When Done")
    prompt_parts.append(f"Mark this task complete: `uv run {PLUGIN_ROOT}/plan.py set-status {args.task_id} done`")

    # Output the complete prompt
    print("\n".join(prompt_parts))
    return 0


def cmd_help(args: argparse.Namespace) -> int:
    """Print concise CLI reference."""
    # Get the actual plugin root path
    plugin_root = Path(__file__).parent
    cli_path = plugin_root / "plan.py"

    print(f"""## CLI Commands

**CLI:** `uv run {cli_path} <command>`
**Overview:** `status` - all plans, active plan stats, tasks
**Switch plan:** `set-active <plan>`
**Task status:** `set-status <task-id> in-progress|done`
**Next tasks:** `next-tasks` - available tasks to start
**Progress:** `log <message>` | `recent-progress`

Full docs: {plugin_root}/CLAUDE.md""")
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

    # Get old mode for logging
    old_mode = mode_file.read_text().strip() if mode_file.exists() else "(none)"

    mode_file.parent.mkdir(parents=True, exist_ok=True)
    mode_file.write_text(args.mode)

    # Log mode change to plan progress
    plan_dir = get_active_plan_dir(project_dir)
    if plan_dir:
        log_progress(plan_dir, f"MODE_CHANGE: {old_mode} -> {args.mode} (command: set-mode {args.mode})")

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

    # Get old mode for logging
    old_mode = mode_file.read_text().strip() if mode_file.exists() else "(none)"

    if mode_file.exists():
        mode_file.unlink()

    # Log mode change to plan progress
    plan_dir = get_active_plan_dir(project_dir)
    if plan_dir:
        log_progress(plan_dir, f"MODE_CHANGE: {old_mode} -> (cleared) (command: clear-mode)")

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

    # Check required_artifacts for the current phase (if any) before allowing transition
    current_phase = state.get("current_phase")
    if current_phase:
        required_artifacts = workflow_mgr.get_required_artifacts(current_phase)
        if required_artifacts:
            # Get artifacts recorded for the current phase entry
            current_entry = None
            for entry in reversed(state.get("phase_history", [])):
                if entry.get("entry") == state.get("current_phase_entry"):
                    current_entry = entry
                    break

            recorded = set((current_entry or {}).get("artifacts", {}).keys())
            missing = [a for a in required_artifacts if a not in recorded]

            if missing:
                print(
                    f"Error: Cannot leave phase '{current_phase}' - missing required artifacts:",
                    file=sys.stderr,
                )
                for artifact in missing:
                    print(f"  - {artifact}", file=sys.stderr)
                print("", file=sys.stderr)
                print("Record each artifact before transitioning:", file=sys.stderr)
                print("  uv run plan.py record-artifact <name> <filename>", file=sys.stderr)
                print("", file=sys.stderr)
                print("Example:", file=sys.stderr)
                print(f"  uv run plan.py record-artifact {missing[0]} {missing[0]}.md", file=sys.stderr)
                return 1

    # Count existing entries for this phase (for re-entry detection)
    prev_entries = [
        e for e in state.get("phase_history", []) if e["phase"] == args.phase_id
    ]
    is_reentry = len(prev_entries) > 0

    # Check max_iterations limit (legacy research phase looping)
    max_iterations = workflow_mgr.get_max_iterations(args.phase_id)
    if max_iterations and len(prev_entries) >= max_iterations:
        print(
            f"Error: Phase '{args.phase_id}' has reached max iterations ({max_iterations})",
            file=sys.stderr,
        )
        print("Proceeding to next phase is required.", file=sys.stderr)
        return 1

    # Check max_retries limit for phase loopbacks
    if is_reentry:
        # REQUIRE --reason-file for re-entries to ensure detailed context
        if not args.reason_file:
            print(
                f"Error: Re-entering phase '{args.phase_id}' requires --reason-file",
                file=sys.stderr,
            )
            print("", file=sys.stderr)
            print("When looping back to a phase, you must provide detailed context", file=sys.stderr)
            print("explaining why the previous attempt didn't succeed and what", file=sys.stderr)
            print("should be done differently this time.", file=sys.stderr)
            print("", file=sys.stderr)
            print("Create a markdown file with:", file=sys.stderr)
            print("  ## Why Previous Attempt Failed", file=sys.stderr)
            print("  ## What Was Learned", file=sys.stderr)
            print("  ## What Should Be Done Differently", file=sys.stderr)
            print("  ## Specific Issues to Address", file=sys.stderr)
            print("", file=sys.stderr)
            print("Then call: enter-phase {phase} --reason-file <path>".format(phase=args.phase_id), file=sys.stderr)
            return 1

        reason_file_path = Path(args.reason_file)
        if not reason_file_path.exists():
            print(f"Error: Reason file not found: {args.reason_file}", file=sys.stderr)
            return 1

        reentry_reason_content = reason_file_path.read_text().strip()
        if len(reentry_reason_content) < 100:
            print(
                f"Error: Reason file too short ({len(reentry_reason_content)} chars)",
                file=sys.stderr,
            )
            print("Re-entry context must be detailed (at least 100 characters).", file=sys.stderr)
            return 1

        max_retries = workflow_mgr.get_max_retries(args.phase_id)
        current_retries = state_mgr.get_phase_retries(args.phase_id)
        if max_retries is not None and current_retries >= max_retries:
            print(
                f"Max retries ({max_retries}) exceeded for phase '{args.phase_id}'",
                file=sys.stderr,
            )
            print("User intervention required.", file=sys.stderr)
            return 10  # Exit code for max retries exceeded

        # Increment retry counter for this re-entry
        state_mgr.increment_phase_retries(args.phase_id)
    else:
        reentry_reason_content = None

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

## Artifacts from Previous Attempt
"""
        prev_artifacts = last_entry.get("artifacts", {})
        if prev_artifacts:
            for name, path in prev_artifacts.items():
                reentry_content += f"- {name}: {path}\n"
        else:
            reentry_content += "(none)\n"

        # Add the detailed re-entry context from the reason file
        reentry_content += f"""
## Re-entry Analysis

{reentry_reason_content}
"""

        reentry_file = phase_dir / "reentry-context.md"
        reentry_file.write_text(reentry_content)

    # Update state
    relative_phase_dir = f"phases/{phase_dir_name}"
    state_mgr.update_phase(args.phase_id, relative_phase_dir, args.reason or "")

    # Log to progress (both plan-level and phase-level)
    plan_name = get_active_plan(project_dir)
    log_progress(plan_dir, f"PHASE_ENTERED: {args.phase_id} -> {relative_phase_dir}")

    # Log to phase progress
    entry_msg = f"PHASE_STARTED: {args.phase_id}"
    if args.reason:
        entry_msg += f" - {args.reason}"
    log_phase_progress(plan_dir, entry_msg)

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

    suggested_full = workflow_mgr.get_suggested_next_full(current_phase)
    if suggested_full:
        for item in suggested_full:
            phase_id = item.get("phase")
            phase = workflow_mgr.get_phase(phase_id)
            markers = []
            if phase and phase.get("terminal"):
                markers.append("terminal")
            if phase and phase.get("requires_user_input"):
                markers.append("requires user input")
            if item.get("requires_approval"):
                markers.append("requires approval")
            marker_str = f" ({', '.join(markers)})" if markers else ""
            print(f"{phase_id}{marker_str}")
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
    reason_str = f"User selected option {number}"
    if guidance:
        reason_str += f": {guidance}"

    # Simulate args for enter-phase
    class EnterPhaseArgs:
        phase_id = target_phase
        reason = reason_str

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


def cmd_prior_phase_outputs(args: argparse.Namespace) -> int:
    """List task output directories from prior entries of the same phase type."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    # Determine which phase type to look for
    phase_type = args.phase_type if args.phase_type else current_phase
    if not phase_type:
        print("No current phase and no --phase-type specified", file=sys.stderr)
        return 1

    # Find all prior entries of this phase type
    history = state.get("phase_history", [])
    current_entry = state.get("current_phase_entry", 0)

    prior_entries = []
    for entry in history:
        if entry.get("phase") == phase_type and entry.get("entry") != current_entry:
            entry_num = entry.get("entry")
            entry_dir = entry.get("dir")
            if entry_dir:
                tasks_dir = plan_dir / entry_dir / "tasks"
                task_outputs = []
                if tasks_dir.exists():
                    for task_dir in sorted(tasks_dir.iterdir()):
                        if task_dir.is_dir():
                            files = [f.name for f in task_dir.iterdir() if f.is_file()]
                            if files:
                                task_outputs.append({
                                    "task": task_dir.name,
                                    "files": sorted(files)
                                })
                prior_entries.append({
                    "entry": entry_num,
                    "dir": entry_dir,
                    "task_outputs": task_outputs
                })

    if args.json:
        result = {
            "phase_type": phase_type,
            "prior_entries": prior_entries
        }
        print(json.dumps(result, indent=2))
    else:
        if not prior_entries:
            print(f"No prior {phase_type} phase outputs")
        else:
            print(f"Prior {phase_type} phase outputs:")
            for entry in prior_entries:
                print(f"  Entry {entry['entry']} ({entry['dir']}/tasks/):")
                if entry["task_outputs"]:
                    for to in entry["task_outputs"]:
                        files_str = ", ".join(to["files"])
                        print(f"    - {to['task']}/: {files_str}")
                else:
                    print("    (no task outputs)")

    return 0


def cmd_loop_phase(args: argparse.Namespace) -> int:
    """Re-enter current phase (self-loop).

    Exit codes:
        0: Success, phase re-entered
        1: In-progress tasks exist
        2: No active plan/phase
        10: Max retries exceeded
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 2

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")
    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 2

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 2

    # Check no in-progress tasks (require all done or blocked)
    tasks = get_tasks(plan_dir)
    in_progress = [t for t in tasks if t.get("status") == "in-progress"]
    if in_progress:
        print("Cannot loop: in-progress tasks exist", file=sys.stderr)
        for t in in_progress:
            print(f"  - {t['id']}", file=sys.stderr)
        return 1

    # Check max_retries not exceeded
    max_retries = workflow_mgr.get_max_retries(current_phase)
    current_retries = state_mgr.get_phase_retries(current_phase)
    if max_retries is not None and current_retries >= max_retries:
        # Set mode to awaiting-feedback
        state["session_mode"] = "awaiting-feedback"
        state_mgr.save(state)
        print(f"Max retries ({max_retries}) exceeded for {current_phase}. User intervention required.", file=sys.stderr)
        if args.json:
            result = {
                "error": "max_retries_exceeded",
                "phase": current_phase,
                "retries": current_retries,
                "max_retries": max_retries
            }
            print(json.dumps(result))
        return 10

    # Call enter-phase with same phase ID
    reason = args.reason or f"Self-loop: retry attempt {current_retries + 1}"

    class EnterPhaseArgs:
        phase_id = current_phase
        reason = reason

    enter_args = EnterPhaseArgs()
    enter_args.reason = reason

    result = cmd_enter_phase(enter_args)

    if result == 0 and args.json:
        new_state = state_mgr.load()
        output = {
            "success": True,
            "phase": current_phase,
            "new_dir": new_state.get("current_phase_dir"),
            "retry_count": new_state.get("phase_retries", {}).get(current_phase, 0)
        }
        print(json.dumps(output))

    return result


def cmd_loop_to_phase(args: argparse.Namespace) -> int:
    """Transition to a different phase (cross-phase loopback).

    Exit codes:
        0: Success, transitioned
        2: No active plan/phase
        10: Target phase max retries exceeded
        11: Approval required (pending_approval set)
        12: Invalid transition (not allowed)
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 2

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")
    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 2

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml in plan", file=sys.stderr)
        return 2

    target_phase = args.phase_id

    # Check target phase exists
    if not workflow_mgr.get_phase(target_phase):
        print(f"Phase not found: {target_phase}", file=sys.stderr)
        return 12

    # Validate transition is allowed
    if not workflow_mgr.is_transition_allowed(current_phase, target_phase):
        print(f"Transition not allowed: {current_phase} -> {target_phase}", file=sys.stderr)
        if args.json:
            result = {
                "error": "invalid_transition",
                "from": current_phase,
                "to": target_phase
            }
            print(json.dumps(result))
        return 12

    # Check target phase's max_retries
    # We need to check if target has been entered before (would be a re-entry)
    prev_entries = [
        e for e in state.get("phase_history", []) if e["phase"] == target_phase
    ]
    if prev_entries:
        max_retries = workflow_mgr.get_max_retries(target_phase)
        current_retries = state_mgr.get_phase_retries(target_phase)
        if max_retries is not None and current_retries >= max_retries:
            state["session_mode"] = "awaiting-feedback"
            state_mgr.save(state)
            print(f"Max retries ({max_retries}) exceeded for target phase '{target_phase}'.", file=sys.stderr)
            if args.json:
                result = {
                    "error": "max_retries_exceeded",
                    "phase": target_phase,
                    "retries": current_retries,
                    "max_retries": max_retries
                }
                print(json.dumps(result))
            return 10

    # Check if transition requires approval
    if workflow_mgr.transition_requires_approval(current_phase, target_phase):
        # Get approval prompt from suggested_next object
        approval_prompt = workflow_mgr.get_approval_prompt(current_phase, target_phase) or f"Transition to {target_phase}?"

        # Set pending approval
        current_entry = state.get("current_phase_entry", 0)
        reason = args.reason or f"Loopback: {current_phase} -> {target_phase}"
        state_mgr.set_pending_approval(current_phase, target_phase, reason, current_entry)

        # Set mode to awaiting-feedback
        state = state_mgr.load()
        state["session_mode"] = "awaiting-feedback"
        state_mgr.save(state)

        log_progress(plan_dir, f"TRANSITION_PROPOSED: {current_phase} -> {target_phase}")

        print(f"Transition proposed: {current_phase} -> {target_phase}")
        print(f"Reason: {reason}")
        print()
        print(f"Approval prompt: {approval_prompt}")
        print()
        print("Use /jons-plan:proceed with user decision:")
        print("- To approve: Agent will call `uv run plan.py approve-transition`")
        print("- To reject: Agent will call `uv run plan.py reject-transition`")

        if args.json:
            result = {
                "approval_required": True,
                "from": current_phase,
                "to": target_phase,
                "reason": reason,
                "approval_prompt": approval_prompt
            }
            print(json.dumps(result))

        return 11

    # Transition directly
    reason = args.reason or f"Loopback: {current_phase} -> {target_phase}"

    class EnterPhaseArgs:
        phase_id = target_phase

    enter_args = EnterPhaseArgs()
    enter_args.reason = reason

    result = cmd_enter_phase(enter_args)

    if result == 0:
        log_progress(plan_dir, f"LOOPBACK: {current_phase} -> {target_phase}")
        if args.json:
            new_state = state_mgr.load()
            output = {
                "success": True,
                "from": current_phase,
                "to": target_phase,
                "new_dir": new_state.get("current_phase_dir")
            }
            print(json.dumps(output))

    return result


def cmd_propose_transition(args: argparse.Namespace) -> int:
    """Request user approval for a transition.

    Exit codes:
        0: Proposal set
        1: Existing pending approval (must reject first)
        2: No active plan/phase
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 2

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")
    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 2

    # Check no existing pending approval
    pending = state_mgr.get_pending_approval()
    if pending:
        print(f"Existing pending approval: {pending['from_phase']} -> {pending['to_phase']}", file=sys.stderr)
        print("Call reject-transition to cancel first.", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    target_phase = args.phase_id

    # Check target phase exists
    if workflow_mgr.exists() and not workflow_mgr.get_phase(target_phase):
        print(f"Phase not found: {target_phase}", file=sys.stderr)
        return 1

    # Set pending approval
    current_entry = state.get("current_phase_entry", 0)
    reason = args.reason or f"Transition requested: {current_phase} -> {target_phase}"
    state_mgr.set_pending_approval(current_phase, target_phase, reason, current_entry)

    # Set mode to awaiting-feedback
    state = state_mgr.load()
    state["session_mode"] = "awaiting-feedback"
    state_mgr.save(state)

    log_progress(plan_dir, f"TRANSITION_PROPOSED: {current_phase} -> {target_phase}")

    # Get approval prompt if available
    approval_prompt = f"Transition to {target_phase}?"
    if workflow_mgr.exists():
        transition = workflow_mgr.get_transition(current_phase, target_phase)
        if transition and transition.get("approval_prompt"):
            approval_prompt = transition["approval_prompt"]

    print(f"Transition proposed: {current_phase} -> {target_phase}")
    print(f"Reason: {reason}")
    print()
    print("Use /jons-plan:proceed with user decision:")
    print("- To approve: Agent will call `uv run plan.py approve-transition`")
    print("- To reject: Agent will call `uv run plan.py reject-transition`")

    if args.json:
        result = {
            "success": True,
            "from": current_phase,
            "to": target_phase,
            "reason": reason,
            "approval_prompt": approval_prompt
        }
        print(json.dumps(result))

    return 0


def cmd_approve_transition(args: argparse.Namespace) -> int:
    """Execute a pending approved transition.

    Exit codes:
        0: Transitioned successfully
        2: No active plan/phase
        13: No pending approval
        14: Stale pending approval
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 2

    state_mgr = StateManager(plan_dir)

    # Check pending approval exists
    pending = state_mgr.get_pending_approval()
    if not pending:
        print("No pending approval", file=sys.stderr)
        return 13

    # Validate staleness
    is_valid, error_msg = state_mgr.validate_pending_approval()
    if not is_valid:
        print(f"Cannot approve: {error_msg}", file=sys.stderr)
        if args.json:
            result = {
                "error": "stale_approval",
                "message": error_msg
            }
            print(json.dumps(result))
        return 14

    target_phase = pending["to_phase"]
    from_phase = pending["from_phase"]
    reason = pending.get("reason", f"Approved transition: {from_phase} -> {target_phase}")

    # Execute transition via enter-phase
    class EnterPhaseArgs:
        phase_id = target_phase

    enter_args = EnterPhaseArgs()
    enter_args.reason = reason

    result = cmd_enter_phase(enter_args)

    # Only clear pending after successful transition
    if result == 0:
        state_mgr.clear_pending_approval()
        # Clear session mode
        state = state_mgr.load()
        if state.get("session_mode") == "awaiting-feedback":
            del state["session_mode"]
            state_mgr.save(state)
        log_progress(plan_dir, f"TRANSITION_APPROVED: {from_phase} -> {target_phase}")

        if args.json:
            new_state = state_mgr.load()
            output = {
                "success": True,
                "from": from_phase,
                "to": target_phase,
                "new_dir": new_state.get("current_phase_dir")
            }
            print(json.dumps(output))

    return result


def cmd_reject_transition(args: argparse.Namespace) -> int:
    """Cancel a pending transition.

    Exit codes:
        0: Rejected
        13: No pending approval
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 2

    state_mgr = StateManager(plan_dir)

    # Check pending approval exists
    pending = state_mgr.get_pending_approval()
    if not pending:
        print("No pending approval", file=sys.stderr)
        return 13

    from_phase = pending["from_phase"]
    to_phase = pending["to_phase"]

    # Clear pending approval
    state_mgr.clear_pending_approval()

    # Clear session mode
    state = state_mgr.load()
    if state.get("session_mode") == "awaiting-feedback":
        del state["session_mode"]
        state_mgr.save(state)

    log_progress(plan_dir, f"TRANSITION_REJECTED: {from_phase} -> {to_phase}")

    print(f"Transition rejected: {from_phase} -> {to_phase}")
    print("Agent continues in current phase.")

    if args.json:
        output = {
            "success": True,
            "rejected_from": from_phase,
            "rejected_to": to_phase,
            "current_phase": state.get("current_phase")
        }
        print(json.dumps(output))

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
    if current_phase_dir and not args.path.startswith(current_phase_dir):
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

    # If --entry specified, look up that specific entry from history
    if args.entry:
        history = state.get("phase_history", [])
        entry = None
        for h in history:
            if h.get("entry") == args.entry:
                entry = h
                break
        if not entry:
            print(f"Phase entry #{args.entry} not found", file=sys.stderr)
            return 1
        current_phase = entry.get("phase")
        current_phase_dir = entry.get("dir")
    else:
        current_phase = state.get("current_phase")
        current_phase_dir = state.get("current_phase_dir")

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
        assembled_prompts = get_assembled_prompts(workflow_mgr, current_phase)
        required_artifacts = workflow_mgr.get_required_artifacts(current_phase)
        phase_context_artifacts = workflow_mgr.get_context_artifacts(current_phase)

        # Resolve context artifacts content
        context_artifacts_content = {}
        if phase_context_artifacts:
            all_artifacts = resolver.resolve_all(exclude_current=True)
            for artifact_name in phase_context_artifacts:
                if artifact_name in all_artifacts:
                    artifact_path = all_artifacts[artifact_name]
                    if artifact_path.exists():
                        context_artifacts_content[artifact_name] = {
                            "path": str(artifact_path),
                            "content": artifact_path.read_text().strip(),
                        }

        output = {
            "phase_id": current_phase,
            "phase_dir": str(plan_dir / current_phase_dir) if current_phase_dir else None,
            "prompt": phase.get("prompt", ""),
            "terminal": phase.get("terminal", False),
            "requires_user_input": phase.get("requires_user_input", False),
            "use_tasks": use_tasks,
            "task_schema": TASK_SCHEMA if use_tasks else None,
            "assembled_prompts": assembled_prompts if assembled_prompts else None,
            "suggested_next": phase.get("suggested_next", []),
            "required_artifacts": required_artifacts if required_artifacts else None,
            "context_artifacts": context_artifacts_content if context_artifacts_content else None,
            "input_artifacts": {
                "found": [str(p) for p in found],
                "missing": missing,
            },
            "reentry_context": reentry_context,
            "request": request_content,
            "user_guidance": state.get("user_guidance", ""),
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

        # Context artifacts (injected from upstream phases)
        phase_context_artifacts = workflow_mgr.get_context_artifacts(current_phase)
        if phase_context_artifacts:
            all_artifacts = resolver.resolve_all(exclude_current=True)
            injected_any = False
            for artifact_name in phase_context_artifacts:
                if artifact_name in all_artifacts:
                    artifact_path = all_artifacts[artifact_name]
                    if artifact_path.exists():
                        content = artifact_path.read_text().strip()
                        if content:
                            if not injected_any:
                                print("## Context Artifacts (from upstream phases)")
                                print()
                                injected_any = True
                            print(f"### {artifact_name}")
                            print(f"_Source: {artifact_path.relative_to(plan_dir)}_")
                            print()
                            print(content)
                            print()
                else:
                    print(f"**Warning:** Context artifact '{artifact_name}' not found in phase history", file=sys.stderr)

        # Task schema (injected for phases with use_tasks=true)
        if workflow_mgr.uses_tasks(current_phase):
            print(TASK_SCHEMA)
            print()

        # Assembled prompts based on workflow flags
        assembled_prompts = get_assembled_prompts(workflow_mgr, current_phase)
        if assembled_prompts:
            print(assembled_prompts)
            print()

        # Re-entry context
        if reentry_context:
            print("## Re-entry Context")
            print(reentry_context)
            print()

        # User guidance (if set)
        guidance = state.get("user_guidance", "")
        if guidance:
            print("## User Guidance")
            print(f"_Provided when entering this phase:_")
            print(guidance)
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

        # Required artifacts (must be recorded before transitioning)
        required_artifacts = workflow_mgr.get_required_artifacts(current_phase)
        if required_artifacts:
            print("## Required Artifacts")
            print()
            print("**IMPORTANT:** Before transitioning to the next phase, you MUST record these artifacts:")
            print()
            for artifact in required_artifacts:
                print(f"```bash")
                print(f"uv run plan.py record-artifact {artifact} {artifact}.md")
                print(f"```")
            print()
            print("The transition will fail if any required artifacts are missing.")
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
        next_labels = []
        for item in suggested:
            if isinstance(item, str):
                next_labels.append(item)
            elif isinstance(item, dict):
                next_labels.append(item.get("phase", ""))
        print(f"Next: {', '.join(next_labels)}")

    # Show user guidance (truncated for summary)
    guidance = state.get("user_guidance", "")
    if guidance:
        display = guidance[:200] + "..." if len(guidance) > 200 else guidance
        print(f"User Guidance: {display}")

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


def cmd_check_tasks_required(args: argparse.Namespace) -> int:
    """Check if current phase requires tasks but none exist.

    Exit codes:
        0 - Phase doesn't require tasks OR tasks exist
        1 - Phase requires tasks (use_tasks=true) but no tasks.json
    """
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        return 0  # No plan, nothing to check

    workflow_mgr = WorkflowManager(plan_dir)
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        return 0

    # Check if phase has use_tasks=true
    if not workflow_mgr.uses_tasks(current_phase):
        return 0  # Phase doesn't require tasks

    # Check if tasks.json exists and has tasks
    tasks = get_tasks(plan_dir)
    if tasks:
        return 0  # Tasks exist

    # Phase requires tasks but none exist
    print(f"Phase '{current_phase}' has use_tasks=true but no tasks.json")
    return 1


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
            if not has_lock_conflict(task, tasks):
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


def _normalize_suggested_next(suggested_next: list) -> list[str]:
    """Extract phase IDs from mixed string/object format for diagram rendering."""
    result = []
    for item in suggested_next:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            phase_id = item.get("phase", "")
            if phase_id:
                result.append(phase_id)
    return result


def _render_vertical_diagram(phases: list[dict], phase_map: dict, current_phase: str | None) -> None:
    """Render workflow as vertical Unicode box diagram."""
    # Build transition graph (normalize to handle object format)
    transitions: dict[str, list[str]] = {}
    on_blocked_transitions: dict[str, str] = {}
    for phase in phases:
        pid = phase["id"]
        transitions[pid] = _normalize_suggested_next(phase.get("suggested_next", []))
        if phase.get("on_blocked"):
            on_blocked_transitions[pid] = phase["on_blocked"]

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
        on_blocked = on_blocked_transitions.get(pid)

        # Collect all transitions to show
        all_transitions: list[tuple[str, str]] = []  # (target, label)
        for np in next_phases:
            all_transitions.append((np, ""))

        # Add on_blocked if it's not already in suggested_next and not "self"
        if on_blocked and on_blocked != "self" and on_blocked not in next_phases:
            all_transitions.append((on_blocked, "[blocked]"))
        elif on_blocked == "self":
            all_transitions.append((pid, "[blocked→self]"))

        # ANSI color codes
        RED = "\033[31m"  # Dark red for blocked transitions
        RESET = "\033[0m"

        if all_transitions and not is_terminal:
            if len(all_transitions) == 1 and not all_transitions[0][1]:
                print(f"     │")
                print(f"     ↓")
            else:
                # Multiple transitions (branching) or labeled transitions
                print(f"     │")
                for j, (target, label) in enumerate(all_transitions):
                    prefix = "├" if j < len(all_transitions) - 1 else "└"
                    if label:  # Blocked transition - render in red
                        print(f"     {RED}{prefix}──→ {target} {label}{RESET}")
                    else:
                        print(f"     {prefix}──→ {target}")
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


# --- Research Cache Commands ---


def cmd_cache_add(args: argparse.Namespace) -> int:
    """Add an entry to the research cache."""
    project_dir = get_project_dir()

    # Get findings from various sources
    if args.findings_file:
        if args.findings_file == "-":
            findings = sys.stdin.read()
        else:
            findings_path = Path(args.findings_file)
            if not findings_path.exists():
                print(f"Findings file not found: {args.findings_file}", file=sys.stderr)
                return 1
            findings = findings_path.read_text()
    elif args.findings:
        findings = args.findings
    else:
        print("Must specify --findings, --findings-file, or --findings -", file=sys.stderr)
        return 1

    try:
        cache = ResearchCache(project_dir)
        entry_id = cache.add(
            query=args.query,
            findings=findings,
            ttl_days=args.ttl_days,
            source_type=args.source_type,
            source_url=args.source_url,
            plan_id=args.plan_id,
            replace=args.replace,
        )
        print(f"Added cache entry: {entry_id}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_cache_search(args: argparse.Namespace) -> int:
    """Search the research cache."""
    project_dir = get_project_dir()

    cache = ResearchCache(project_dir)
    results = cache.search(
        query=args.query,
        limit=args.limit,
        include_expired=args.include_expired,
    )

    if not results:
        if args.json:
            print("[]")
        else:
            print("No results found")
        return 0

    if args.json:
        output = [
            {
                "id": r.id,
                "query": r.query,
                "findings": r.findings,
                "score": r.score,
                "source_type": r.source_type,
                "source_url": r.source_url,
                "is_expired": r.is_expired,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            expired_marker = " [EXPIRED]" if r.is_expired else ""
            print(f"\n## Entry {r.id} (score: {r.score:.2f}){expired_marker}")
            print(f"Query: {r.query}")
            print(f"Source: {r.source_type}")
            if r.source_url:
                print(f"URL: {r.source_url}")
            print(f"Findings preview: {r.findings[:200]}...")

    return 0


def cmd_cache_get(args: argparse.Namespace) -> int:
    """Get a specific cache entry by ID."""
    project_dir = get_project_dir()

    cache = ResearchCache(project_dir)
    entry = cache.get(entry_id=args.id, allow_expired=args.allow_expired)

    if not entry:
        print(f"Entry {args.id} not found (or expired)", file=sys.stderr)
        return 1

    if args.json:
        output = {
            "id": entry.id,
            "query": entry.query,
            "findings": entry.findings,
            "source_type": entry.source_type,
            "source_url": entry.source_url,
            "is_expired": entry.is_expired,
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
            "plan_id": entry.plan_id,
            "supersedes_id": entry.supersedes_id,
        }
        print(json.dumps(output, indent=2))
    else:
        expired_marker = " [EXPIRED]" if entry.is_expired else ""
        print(f"## Entry {entry.id}{expired_marker}")
        print(f"Query: {entry.query}")
        print(f"Source: {entry.source_type}")
        if entry.source_url:
            print(f"URL: {entry.source_url}")
        if entry.plan_id:
            print(f"Plan: {entry.plan_id}")
        if entry.supersedes_id:
            print(f"Supersedes: {entry.supersedes_id}")
        print(f"\n### Findings\n{entry.findings}")

    return 0


def cmd_cache_clear(args: argparse.Namespace) -> int:
    """Clear cache entries."""
    project_dir = get_project_dir()

    try:
        cache = ResearchCache(project_dir)
        count = cache.clear(
            entry_id=args.id,
            query=args.query,
            all_entries=args.all,
        )
        print(f"Cleared {count} entries")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_cache_gc(args: argparse.Namespace) -> int:
    """Run garbage collection on expired cache entries."""
    project_dir = get_project_dir()

    cache = ResearchCache(project_dir)
    count = cache.gc()
    print(f"Removed {count} expired entries")
    return 0


def cmd_cache_stats(args: argparse.Namespace) -> int:
    """Show cache statistics."""
    project_dir = get_project_dir()

    cache = ResearchCache(project_dir)
    stats = cache.stats()

    if args.json:
        output = {
            "total_entries": stats.total_entries,
            "active_entries": stats.active_entries,
            "expired_entries": stats.expired_entries,
            "total_size_kb": round(stats.total_size_kb, 2),
            "oldest_entry": stats.oldest_entry,
            "newest_entry": stats.newest_entry,
            "entries_by_source": stats.entries_by_source,
        }
        print(json.dumps(output, indent=2))
    else:
        print("## Research Cache Stats")
        print(f"  Total entries: {stats.total_entries}")
        print(f"  Active entries: {stats.active_entries}")
        print(f"  Expired entries: {stats.expired_entries}")
        print(f"  Database size: {stats.total_size_kb:.1f} KB")

        if stats.entries_by_source:
            print("\n  By source type:")
            for source, count in stats.entries_by_source.items():
                print(f"    {source}: {count}")

        if stats.oldest_entry:
            oldest = datetime.fromtimestamp(stats.oldest_entry).strftime("%Y-%m-%d")
            newest = datetime.fromtimestamp(stats.newest_entry).strftime("%Y-%m-%d")
            print(f"\n  Date range: {oldest} to {newest}")

    return 0


def cmd_cache_suggest(args: argparse.Namespace) -> int:
    """Suggest cache reference tasks for a task description.

    Searches the cache for matches and returns JSON with suggestions
    for creating cache-reference tasks.
    """
    project_dir = get_project_dir()
    cache = ResearchCache(project_dir)

    # Search with top-3 results
    hits = cache.search(args.description, limit=3, include_expired=False)

    # Filter by relevance threshold (lower BM25 score = more relevant)
    # Note: BM25 scores are typically small negative numbers for good matches
    # A threshold of 0.0 means "any match is relevant" (using <= to include -0.00)
    RELEVANCE_THRESHOLD = 0.0
    relevant_hits = [h for h in hits if h.score is not None and h.score <= RELEVANCE_THRESHOLD]

    # Build suggestions
    suggestions = []
    for hit in relevant_hits:
        ref_task = {
            "id": f"ref-{hit.id}",
            "type": "cache-reference",
            "cache_id": hit.id,
            "description": f"Cached: {hit.query[:50]}{'...' if len(hit.query) > 50 else ''}",
            "parents": [],
            "steps": [],
            "status": "todo",
        }
        suggestions.append({
            "cache_id": hit.id,
            "query": hit.query,
            "score": round(hit.score, 2) if hit.score else None,
            "ref_task": ref_task,
        })

    output = {
        "has_hits": len(suggestions) > 0,
        "threshold": RELEVANCE_THRESHOLD,
        "suggestions": suggestions,
    }

    print(json.dumps(output, indent=2))
    return 0


# --- Proposal Commands ---


def slugify(text: str) -> str:
    """Convert text to slug format for IDs."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]  # Limit length


def parse_proposals_md(content: str) -> list[dict]:
    """Parse proposals.md markdown format into structured proposals.

    Expected format:
    ## Proposal: <title>

    **Target File**: `path/to/file`

    **Content**:
    <content lines>

    **Rationale**:
    <rationale lines>
    """
    import re
    proposals = []

    # Split by ## Proposal: headers
    sections = re.split(r'^## Proposal:\s*', content, flags=re.MULTILINE)

    for section in sections[1:]:  # Skip content before first proposal
        lines = section.strip().split('\n')
        if not lines:
            continue

        title = lines[0].strip()
        section_text = '\n'.join(lines[1:])

        # Extract Target File
        target_match = re.search(r'\*\*Target File\*\*:\s*`([^`]+)`', section_text)
        target_file = target_match.group(1) if target_match else ""

        # Extract Content (between **Content**: and **Rationale**:)
        content_match = re.search(
            r'\*\*Content\*\*:\s*\n(.*?)(?=\*\*Rationale\*\*:|\Z)',
            section_text,
            re.DOTALL
        )
        proposal_content = content_match.group(1).strip() if content_match else ""

        # Extract Rationale
        rationale_match = re.search(
            r'\*\*Rationale\*\*:\s*\n(.*?)(?=---|\Z)',
            section_text,
            re.DOTALL
        )
        rationale = rationale_match.group(1).strip() if rationale_match else ""

        if title and target_file:
            proposals.append({
                "title": title,
                "target_file": target_file,
                "content": proposal_content,
                "rationale": rationale,
            })

    return proposals


def cmd_collect_proposals(args: argparse.Namespace) -> int:
    """Collect all proposals from task directories into a manifest."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    manifest_file = plan_dir / "proposals-manifest.json"

    # Load existing manifest to preserve status
    existing = {}
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text())
            existing = {p["id"]: p for p in data.get("proposals", [])}
        except (json.JSONDecodeError, KeyError):
            pass

    # Collect proposals from all task directories
    proposals = []
    phases_dir = plan_dir / "phases"

    if phases_dir.exists():
        for phase_dir in sorted(phases_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            tasks_dir = phase_dir / "tasks"
            if not tasks_dir.exists():
                continue

            for task_dir in sorted(tasks_dir.iterdir()):
                if not task_dir.is_dir():
                    continue
                proposals_file = task_dir / "proposals.md"
                if not proposals_file.exists():
                    continue

                # Parse proposals from this task
                parsed = parse_proposals_md(proposals_file.read_text())
                for p in parsed:
                    # Generate ID as task:title-slug
                    proposal_id = f"{task_dir.name}:{slugify(p['title'])}"

                    proposal = {
                        "id": proposal_id,
                        "source_task": task_dir.name,
                        "source_phase": str(phase_dir.relative_to(plan_dir)),
                        "target_file": p["target_file"],
                        "title": p["title"],
                        "content": p["content"],
                        "rationale": p["rationale"],
                        "status": "pending",
                    }

                    # Preserve status from existing manifest
                    if proposal_id in existing:
                        proposal["status"] = existing[proposal_id].get("status", "pending")

                    proposals.append(proposal)

    # Write manifest
    manifest = {"proposals": proposals}
    manifest_file.write_text(json.dumps(manifest, indent=2))

    new_count = sum(1 for p in proposals if p["id"] not in existing)
    print(f"Collected {len(proposals)} proposals ({new_count} new)")
    return 0


def cmd_list_proposals(args: argparse.Namespace) -> int:
    """List proposals with status."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    manifest_file = plan_dir / "proposals-manifest.json"
    if not manifest_file.exists():
        print("No proposals collected yet. Run collect-proposals first.")
        return 0

    try:
        manifest = json.loads(manifest_file.read_text())
    except json.JSONDecodeError:
        print("Error: Invalid manifest file", file=sys.stderr)
        return 1

    proposals = manifest.get("proposals", [])
    if not proposals:
        print("No proposals")
        return 0

    # Filter by status if specified
    status_filter = getattr(args, 'status', None)
    if status_filter:
        proposals = [p for p in proposals if p.get("status") == status_filter]

    # Group by status
    by_status = {"pending": [], "accepted": [], "rejected": []}
    for p in proposals:
        status = p.get("status", "pending")
        if status in by_status:
            by_status[status].append(p)
        else:
            by_status["pending"].append(p)

    total = len(proposals)
    pending = len(by_status["pending"])

    print(f"Proposals ({total} total, {pending} pending):")

    for status in ["pending", "accepted", "rejected"]:
        if by_status[status]:
            print(f"\n  {status}:")
            for p in by_status[status]:
                print(f"    {p['id']}: [{p['target_file']}] {p['title']} (from {p['source_task']})")

    return 0


def cmd_update_proposal_status(args: argparse.Namespace) -> int:
    """Update proposal status in manifest."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    manifest_file = plan_dir / "proposals-manifest.json"
    if not manifest_file.exists():
        print("No proposals manifest. Run collect-proposals first.", file=sys.stderr)
        return 1

    try:
        manifest = json.loads(manifest_file.read_text())
    except json.JSONDecodeError:
        print("Error: Invalid manifest file", file=sys.stderr)
        return 1

    # Find and update the proposal
    found = False
    for p in manifest.get("proposals", []):
        if p["id"] == args.proposal_id:
            p["status"] = args.status
            found = True
            break

    if not found:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1

    manifest_file.write_text(json.dumps(manifest, indent=2))
    print(f"Updated: {args.proposal_id} -> {args.status}")
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
        print(f"  Use: uv run {PLUGIN_ROOT}/plan.py set-active <plan-name>")

    return 0


# =============================================================================
# Workflow Expansion Commands
# =============================================================================


def cmd_build_expand_prompt(args: argparse.Namespace) -> int:
    """Build full expand prompt with reference workflow templates."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")

    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 1

    # Get workflow-specific expand_prompt
    phase_expand_prompt = workflow_mgr.get_expand_prompt(current_phase)
    if not phase_expand_prompt:
        print(f"Phase '{current_phase}' has no expand_prompt", file=sys.stderr)
        return 1

    # Load reference workflows
    workflows_dir = Path.home() / ".claude-plugins" / "jons-plan" / "workflows"
    reference_workflows = []
    for template in ["implementation.toml", "design.toml", "deep-implementation.toml"]:
        path = workflows_dir / template
        if path.exists():
            reference_workflows.append((template, path.read_text()))

    # Assemble the full prompt
    prompt = """# Workflow Expansion

Generate the remaining workflow phases based on your research findings.

## Philosophy: Plan the Visible Horizon

You're not planning everything - you're planning what you can clearly see from research.

**Key principles:**

1. **Validation phases are checkpoints** - not just "does it work" but "should we continue or re-plan?"

2. **Break complex work into chunks** - even coupled components benefit from validation points between them. This catches issues early and creates natural decision points.

3. **Include loopback transitions** - validation phases should be able to return to research if things aren't working. Don't plan a path that assumes everything succeeds.

4. **It's OK to not see everything** - plan confidently to the next validation checkpoint. The checkpoint is where you reassess.

5. **Nested expansion** - generated phases can themselves be expandable. Use this when:
   - A component needs its own research before planning
   - Later phases depend on decisions made during earlier phases
   - Phased delivery where later phases aren't scoped yet

## When to Ask for User Input

Use your judgment based on research findings:

**Generate directly if:**
- Research clearly identified components and their relationships
- There's an obvious workflow structure
- You're confident in the approach

**Use AskUserQuestion first if:**
- Multiple valid approaches exist
- Research revealed optional concerns
- Scope is ambiguous
- Trade-offs the user should decide

## Reference: Existing Workflow Templates

Study these patterns before generating:

"""
    for name, content in reference_workflows:
        prompt += f"### {name}\n```toml\n{content}\n```\n\n"

    prompt += """**Note on `[[transitions]]` in templates:** These are DEPRECATED. The new format puts loopback transitions directly in `suggested_next` as objects. See Output Format below.

## Phase Configuration Reference

| Flag | Purpose |
|------|---------|
| `use_tasks` | Phase uses tasks.json for work breakdown |
| `on_blocked = "self"` | Retry phase on blocked tasks |
| `max_retries` | Limit retries before escalating |
| `supports_proposals` | Enable CLAUDE.md improvement proposals |
| `supports_prototypes` | Enable prototype tasks |
| `terminal = true` | Final phase, workflow ends here |

## Your Expansion Instructions

"""
    prompt += phase_expand_prompt
    prompt += """

## Output Format

Return JSON with this structure:
```json
{
  "phases": [
    {
      "id": "phase-id",
      "prompt": "Phase instructions...",
      "use_tasks": true,
      "suggested_next": ["next-phase-id"]
    }
  ]
}
```

**IMPORTANT: Every phase MUST have `suggested_next`**

- Each phase's `suggested_next` points to the next phase in sequence
- The LAST phase must have `suggested_next: ["complete"]` or `["__expand__"]`

Example chain: `impl-a` → `impl-b` → `validate` → `complete`
```json
{
  "phases": [
    {"id": "impl-a", "prompt": "...", "suggested_next": ["impl-b"]},
    {"id": "impl-b", "prompt": "...", "suggested_next": ["validate"]},
    {"id": "validate", "prompt": "...", "suggested_next": ["complete"]}
  ]
}
```

**Loopback transitions (optional)**

For backward jumps (e.g., validate fails → return to research), use object format in `suggested_next`:

```json
{
  "phases": [
    {"id": "impl", "prompt": "...", "suggested_next": ["validate"]},
    {"id": "validate", "prompt": "...", "suggested_next": [
      "complete",
      {"phase": "research", "requires_approval": true, "approval_prompt": "Return to research?"}
    ]}
  ]
}
```

The object format fields:
- `phase` (required): target phase ID
- `requires_approval` (required for loopbacks): set to `true`
- `approval_prompt` (required if requires_approval): prompt shown to user
"""

    print(prompt)
    return 0


def validate_generated_phases(generated: dict) -> list[str]:
    """Validate generated phases JSON structure and content."""
    errors = []

    if not isinstance(generated, dict):
        errors.append("Input must be a JSON object")
        return errors

    phases = generated.get("phases", [])
    if not phases:
        errors.append("No phases defined")
        return errors

    if not isinstance(phases, list):
        errors.append("phases must be an array")
        return errors

    phase_ids = {p.get("id") for p in phases if p.get("id")}

    def normalize_suggested(suggested_next: list) -> list[str]:
        """Extract phase IDs from mixed string/object format."""
        result = []
        for item in suggested_next:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                phase_id = item.get("phase", "")
                if phase_id:
                    result.append(phase_id)
        return result

    # Check each phase
    for i, phase in enumerate(phases):
        if not phase.get("id"):
            errors.append(f"Phase {i} missing id")
            continue

        pid = phase["id"]
        if not phase.get("prompt"):
            errors.append(f"Phase '{pid}' missing prompt")

        # Every phase must have suggested_next
        if not phase.get("suggested_next"):
            errors.append(f"Phase '{pid}' missing suggested_next (every phase needs it)")

        # Check suggested_next targets exist (handles both string and object format)
        suggested_ids = normalize_suggested(phase.get("suggested_next", []))
        for item in phase.get("suggested_next", []):
            if isinstance(item, str):
                target = item
            elif isinstance(item, dict):
                target = item.get("phase", "")
                # Check approval config
                if item.get("requires_approval") and not item.get("approval_prompt"):
                    errors.append(f"Phase '{pid}' transition to '{target}' requires approval but has no approval_prompt")
            else:
                continue

            if target and target not in ("complete", "__expand__") and target not in phase_ids:
                errors.append(f"Phase '{pid}' has suggested_next '{target}' which doesn't exist")

        # Check expandable config (using normalized IDs)
        has_expand = "__expand__" in suggested_ids
        has_expand_prompt = "expand_prompt" in phase
        if has_expand and not has_expand_prompt:
            errors.append(f"Phase '{pid}' has __expand__ but no expand_prompt")
        if has_expand_prompt and not has_expand:
            errors.append(f"Phase '{pid}' has expand_prompt but no __expand__ in suggested_next")

    # Check phase count
    if len(phases) > 10:
        errors.append(f"Too many phases ({len(phases)}), maximum is 10")

    # Check last phase points to terminal
    if phases:
        last_phase = phases[-1]
        suggested_ids = normalize_suggested(last_phase.get("suggested_next", []))
        if "complete" not in suggested_ids and "__expand__" not in suggested_ids:
            errors.append(f"Last phase '{last_phase.get('id')}' must end with 'complete' or '__expand__'")

    return errors


def cmd_expand_phase(args: argparse.Namespace) -> int:
    """Expand current expandable phase with generated phases."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase = state.get("current_phase")
    current_phase_dir = state.get("current_phase_dir")

    if not current_phase:
        print("No current phase", file=sys.stderr)
        return 1

    # Check if expandable
    if not workflow_mgr.is_expandable(current_phase):
        print(f"Phase '{current_phase}' is not expandable (no __expand__ in suggested_next)", file=sys.stderr)
        return 1

    # Read generated phases from stdin
    try:
        generated = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        return 1

    # Validate generated phases
    errors = validate_generated_phases(generated)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("## Dry Run - Would generate these phases:")
        print(json.dumps(generated, indent=2))
        return 0

    # Backup current workflow
    workflow_file = plan_dir / "workflow.toml"
    phase_dir = plan_dir / current_phase_dir if current_phase_dir else plan_dir
    backup_file = phase_dir / "workflow-backup.toml"

    import shutil
    shutil.copy(workflow_file, backup_file)

    # Load and modify workflow
    import tomllib
    with open(workflow_file, "rb") as f:
        workflow = tomllib.load(f)

    # Remove __expand__ from current phase, point to first generated
    first_generated_id = generated["phases"][0]["id"]
    for phase in workflow["phases"]:
        if phase["id"] == current_phase:
            # Keep 'complete' if it was there, remove __expand__
            old_suggested = phase.get("suggested_next", [])
            new_suggested = [first_generated_id]
            if "complete" in old_suggested:
                # complete was an option, now expansion happened so we continue
                pass
            phase["suggested_next"] = new_suggested
            # Remove expand_prompt since it's no longer expandable
            if "expand_prompt" in phase:
                del phase["expand_prompt"]
            break

    # Append generated phases
    workflow["phases"].extend(generated["phases"])

    # Append generated transitions (if any)
    if "transitions" in generated:
        if "transitions" not in workflow:
            workflow["transitions"] = []
        workflow["transitions"].extend(generated["transitions"])

    # Write atomically using tomli_w
    try:
        import tomli_w
    except ImportError:
        print("Error: tomli_w not installed. Install with: pip install tomli_w", file=sys.stderr)
        return 1

    temp_file = workflow_file.with_suffix(".tmp")
    with open(temp_file, "wb") as f:
        tomli_w.dump(workflow, f)
    temp_file.rename(workflow_file)

    # Invalidate cache
    workflow_mgr.invalidate_cache()

    # Record expansion
    state_mgr.record_expansion(
        current_phase,
        [p["id"] for p in generated["phases"]]
    )

    print(f"Expanded workflow with {len(generated['phases'])} phases")
    print(f"Backup saved to: {backup_file}")
    log_progress(plan_dir, f"EXPANDED: {current_phase} -> {[p['id'] for p in generated['phases']]}")
    return 0


def cmd_rollback_expansion(args: argparse.Namespace) -> int:
    """Rollback to pre-expansion workflow from backup."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    state_mgr = StateManager(plan_dir)
    state = state_mgr.load()
    current_phase_dir = state.get("current_phase_dir")

    if not current_phase_dir:
        print("No current phase directory", file=sys.stderr)
        return 1

    phase_dir = plan_dir / current_phase_dir
    backup_file = phase_dir / "workflow-backup.toml"

    if not backup_file.exists():
        # Try to find backup in any phase directory
        phases_dir = plan_dir / "phases"
        if phases_dir.exists():
            for pdir in sorted(phases_dir.iterdir(), reverse=True):
                candidate = pdir / "workflow-backup.toml"
                if candidate.exists():
                    backup_file = candidate
                    break

    if not backup_file.exists():
        print("No workflow backup found", file=sys.stderr)
        return 1

    workflow_file = plan_dir / "workflow.toml"
    import shutil
    shutil.copy(backup_file, workflow_file)

    # Invalidate cache
    workflow_mgr = WorkflowManager(plan_dir)
    workflow_mgr.invalidate_cache()

    print(f"Restored workflow from: {backup_file}")
    log_progress(plan_dir, f"ROLLBACK: restored workflow from {backup_file.name}")
    return 0


def cmd_validate_workflow(args: argparse.Namespace) -> int:
    """Validate workflow including expandable phase rules."""
    project_dir = get_project_dir()
    plan_dir = get_active_plan_dir(project_dir)
    if not plan_dir:
        print("No active plan", file=sys.stderr)
        return 1

    workflow_mgr = WorkflowManager(plan_dir)
    if not workflow_mgr.exists():
        print("No workflow.toml found", file=sys.stderr)
        return 1

    errors = []

    # Run schema validation first (catches unknown fields)
    errors.extend(workflow_mgr.validate_schema())

    # Run phase reference validation
    errors.extend(workflow_mgr.validate_phase_references())

    # Run expandable validation
    errors.extend(workflow_mgr.validate_expandable())

    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("Workflow validation passed")
    return 0


# ============================================================================
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

    # phase-log
    p_phase_log = subparsers.add_parser("phase-log", help="Append message to phase progress")
    p_phase_log.add_argument("message", help="Message to log")

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
    p_enter_phase.add_argument("--reason", default="", help="Reason for entering phase (for first entry)")
    p_enter_phase.add_argument("--reason-file", help="Path to markdown file with detailed re-entry context (REQUIRED for re-entries)")

    subparsers.add_parser("suggested-next", help="List possible phase transitions")

    p_enter_by_num = subparsers.add_parser("enter-phase-by-number", help="Enter phase by number from suggested_next")
    p_enter_by_num.add_argument("number", type=int, help="Option number (1-indexed)")
    p_enter_by_num.add_argument("guidance", nargs="?", default="", help="Optional guidance text")

    subparsers.add_parser("phase-history", help="Show all phase entries")

    p_prior_outputs = subparsers.add_parser("prior-phase-outputs", help="List outputs from prior same-type phases")
    p_prior_outputs.add_argument("--phase-type", help="Phase type to look for (default: current phase)")
    p_prior_outputs.add_argument("--json", action="store_true", help="Output as JSON")

    # Phase loopback commands
    p_loop_phase = subparsers.add_parser("loop-phase", help="Re-enter current phase (self-loop)")
    p_loop_phase.add_argument("--reason", help="Reason for looping")
    p_loop_phase.add_argument("--json", action="store_true", help="Output as JSON")

    p_loop_to = subparsers.add_parser("loop-to-phase", help="Transition to a different phase (cross-phase loopback)")
    p_loop_to.add_argument("phase_id", help="Target phase ID")
    p_loop_to.add_argument("--reason", help="Reason for looping")
    p_loop_to.add_argument("--json", action="store_true", help="Output as JSON")

    p_propose = subparsers.add_parser("propose-transition", help="Request user approval for a transition")
    p_propose.add_argument("phase_id", help="Target phase ID")
    p_propose.add_argument("--reason", help="Reason for transition")
    p_propose.add_argument("--json", action="store_true", help="Output as JSON")

    p_approve = subparsers.add_parser("approve-transition", help="Execute a pending approved transition")
    p_approve.add_argument("--json", action="store_true", help="Output as JSON")

    p_reject = subparsers.add_parser("reject-transition", help="Cancel a pending transition")
    p_reject.add_argument("--json", action="store_true", help="Output as JSON")

    # Artifact commands
    p_record_art = subparsers.add_parser("record-artifact", help="Record artifact produced by current phase")
    p_record_art.add_argument("filename", help="Logical name for artifact")
    p_record_art.add_argument("path", help="Relative path to artifact file")

    p_input_art = subparsers.add_parser("input-artifacts", help="List all artifacts from prior phases")
    p_input_art.add_argument("--json", action="store_true", help="Output as JSON")

    # Phase display commands
    p_phase_ctx = subparsers.add_parser("phase-context", help="Display full phase context")
    p_phase_ctx.add_argument("--json", action="store_true", help="Output as JSON")
    p_phase_ctx.add_argument("--entry", type=int, help="Show context for specific phase entry number")

    subparsers.add_parser("phase-summary", help="Display compact phase summary")

    # Phase task commands
    subparsers.add_parser("phase-tasks-file", help="Print current phase's tasks.json path")

    subparsers.add_parser("phase-tasks", help="List tasks in current phase")

    subparsers.add_parser("phase-next-tasks", help="List available tasks in current phase")

    subparsers.add_parser("check-tasks-required", help="Check if phase requires tasks but none exist (exit 1 if missing)")

    # Workflow diagram
    p_diagram = subparsers.add_parser("workflow-diagram", help="Display ASCII diagram of workflow")
    p_diagram.add_argument("--flow", choices=["east", "south"], default="south", help="Direction (default: south)")

    # --- Research Cache Commands ---

    # cache-add
    p_cache_add = subparsers.add_parser("cache-add", help="Add entry to research cache")
    p_cache_add.add_argument("--query", "-q", required=True, help="The research query/question")
    p_cache_add.add_argument("--findings", "-f", help="The research findings (direct text)")
    p_cache_add.add_argument("--findings-file", help="Path to file with findings, or '-' for stdin")
    p_cache_add.add_argument("--ttl-days", type=int, default=30, help="Days until expiration (default: 30)")
    p_cache_add.add_argument("--source-type", default="web_search", help="Source type (default: web_search)")
    p_cache_add.add_argument("--source-url", help="URL of the source")
    p_cache_add.add_argument("--plan-id", help="ID of the plan creating this entry")
    p_cache_add.add_argument("--replace", action="store_true", help="Replace existing entry with same query")

    # cache-search
    p_cache_search = subparsers.add_parser("cache-search", help="Search research cache")
    p_cache_search.add_argument("query", help="Search query")
    p_cache_search.add_argument("--limit", "-n", type=int, default=5, help="Max results (default: 5)")
    p_cache_search.add_argument("--include-expired", action="store_true", help="Include expired entries")
    p_cache_search.add_argument("--json", action="store_true", help="Output as JSON")

    # cache-get
    p_cache_get = subparsers.add_parser("cache-get", help="Get cache entry by ID")
    p_cache_get.add_argument("id", type=int, help="Entry ID")
    p_cache_get.add_argument("--allow-expired", action="store_true", help="Return even if expired")
    p_cache_get.add_argument("--json", action="store_true", help="Output as JSON")

    # cache-clear
    p_cache_clear = subparsers.add_parser("cache-clear", help="Clear cache entries")
    p_cache_clear.add_argument("--id", type=int, help="Delete specific entry by ID")
    p_cache_clear.add_argument("--query", help="Delete entries matching normalized query")
    p_cache_clear.add_argument("--all", action="store_true", help="Delete all entries")

    # cache-gc
    subparsers.add_parser("cache-gc", help="Remove expired cache entries")

    # cache-stats
    p_cache_stats = subparsers.add_parser("cache-stats", help="Show cache statistics")
    p_cache_stats.add_argument("--json", action="store_true", help="Output as JSON")

    # cache-suggest
    p_cache_suggest = subparsers.add_parser("cache-suggest", help="Suggest cache references for a task")
    p_cache_suggest.add_argument("--description", "-d", required=True, help="Task description to search for")

    # Proposal commands
    subparsers.add_parser("collect-proposals", help="Collect proposals from task directories")

    p_list_proposals = subparsers.add_parser("list-proposals", help="List proposals with status")
    p_list_proposals.add_argument("--status", choices=["pending", "accepted", "rejected"], help="Filter by status")

    p_update_proposal = subparsers.add_parser("update-proposal-status", help="Update proposal status")
    p_update_proposal.add_argument("proposal_id", help="Proposal ID")
    p_update_proposal.add_argument("status", choices=["pending", "accepted", "rejected"], help="New status")

    # Workflow expansion commands
    subparsers.add_parser("build-expand-prompt", help="Build full expand prompt with reference workflows")

    p_expand = subparsers.add_parser("expand-phase", help="Expand current phase with generated phases")
    p_expand.add_argument("--dry-run", action="store_true", help="Preview without writing")

    subparsers.add_parser("rollback-expansion", help="Rollback to pre-expansion workflow")

    subparsers.add_parser("validate-workflow", help="Validate workflow including expandable rules")

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
        "phase-log": cmd_phase_log,
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
        "prior-phase-outputs": cmd_prior_phase_outputs,
        "loop-phase": cmd_loop_phase,
        "loop-to-phase": cmd_loop_to_phase,
        "propose-transition": cmd_propose_transition,
        "approve-transition": cmd_approve_transition,
        "reject-transition": cmd_reject_transition,
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
        "check-tasks-required": cmd_check_tasks_required,
        # Workflow diagram
        "workflow-diagram": cmd_workflow_diagram,
        # Research cache commands
        "cache-add": cmd_cache_add,
        "cache-search": cmd_cache_search,
        "cache-get": cmd_cache_get,
        "cache-clear": cmd_cache_clear,
        "cache-gc": cmd_cache_gc,
        "cache-stats": cmd_cache_stats,
        "cache-suggest": cmd_cache_suggest,
        # Proposal commands
        "collect-proposals": cmd_collect_proposals,
        "list-proposals": cmd_list_proposals,
        "update-proposal-status": cmd_update_proposal_status,
        # Workflow expansion commands
        "build-expand-prompt": cmd_build_expand_prompt,
        "expand-phase": cmd_expand_phase,
        "rollback-expansion": cmd_rollback_expansion,
        "validate-workflow": cmd_validate_workflow,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
