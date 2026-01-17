#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyside6>=6.6", "graphviz>=0.20", "tomli>=2.0", "markdown>=3.5", "darkdetect>=0.8"]
# ///
"""
JonsPlan Workflow Viewer

A PySide6/QML application for visualizing jons-plan workflows.

Usage:
    uv run viewer.py /path/to/plan
"""

import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import darkdetect
import graphviz
import markdown
import tomli

# Configure logging - set JONS_PLAN_LOG_LEVEL=DEBUG for verbose output
_log_level = os.environ.get("JONS_PLAN_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.WARNING),
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("jons-plan-viewer")
from PySide6.QtCore import (
    Property,
    QFileSystemWatcher,
    QObject,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

# Markdown converter with styling for Qt Rich Text
_md = markdown.Markdown(extensions=["fenced_code", "tables"])


def md_to_html(text: str) -> str:
    """Convert markdown to HTML for Qt Rich Text display."""
    _md.reset()
    html = _md.convert(text)
    # Qt's CSS is very limited - wrap code blocks in a table for borders
    html = re.sub(
        r'<pre><code[^>]*>(.*?)</code></pre>',
        r'<table border="0" cellpadding="8" cellspacing="0" width="100%" style="border: 1px solid #ddd; margin: 8px 0;"><tr><td><pre style="font-family: Menlo, monospace; margin: 0;">\1</pre></td></tr></table>',
        html,
        flags=re.DOTALL
    )
    html = html.replace("<code>", '<code style="font-family: Menlo, monospace;">')
    # Wrap in div (color set by QML Theme.wrapHtml)
    return f"""<div><style>
        ul, ol {{ margin-left: 4px; padding-left: 12px; }}
        li {{ margin-bottom: 2px; }}
    </style>{html}</div>"""


def check_graphviz() -> None:
    """Verify Graphviz system binaries are installed."""
    if not shutil.which("dot"):
        print("Error: Graphviz not found.", file=sys.stderr)
        print("Install with: brew install graphviz", file=sys.stderr)
        sys.exit(1)


def parse_plan_path(path_str: str) -> Path:
    """Parse and validate plan directory path."""
    plan_path = Path(path_str)
    if not plan_path.exists():
        print(f"Error: Plan not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    if not (plan_path / "workflow.toml").exists():
        print(f"Error: Not a valid plan (missing workflow.toml): {plan_path}", file=sys.stderr)
        sys.exit(1)

    return plan_path


def compute_layout(workflow: dict) -> dict:
    """
    Use Graphviz to compute node positions and edge paths.

    Returns:
        dict with 'nodes' and 'edges' lists, plus 'bounds' for the graph.
    """
    g = graphviz.Digraph(format="json")
    g.attr(rankdir="TB", nodesep="0.5", ranksep="0.75")
    g.attr("node", shape="box", width="1.5", height="0.6")

    # Add phase nodes
    phases = workflow.get("phases", [])
    for phase in phases:
        phase_id = phase.get("id", "")
        label = phase_id.replace("-", " ").title()
        g.node(phase_id, label=label)

    # Add transition edges (handle both string and object format)
    for phase in phases:
        phase_id = phase.get("id", "")
        for item in phase.get("suggested_next", []):
            # Extract phase ID from string or object format
            if isinstance(item, str):
                next_id = item
            elif isinstance(item, dict):
                next_id = item.get("phase", "")
            else:
                continue
            # Skip special transitions like __expand__
            if next_id and not next_id.startswith("__"):
                g.edge(phase_id, next_id)

    # Compute layout and parse JSON output
    try:
        json_bytes = g.pipe()
        result = json.loads(json_bytes.decode("utf-8"))
    except Exception as e:
        print(f"Warning: Graphviz layout failed: {e}", file=sys.stderr)
        return {"nodes": [], "edges": [], "bounds": {"minX": 0, "minY": 0, "maxX": 400, "maxY": 300}}

    # Parse bounding box
    bb_str = result.get("bb", "0,0,400,300")
    bb_parts = bb_str.split(",")
    bounds = {
        "minX": float(bb_parts[0]),
        "minY": float(bb_parts[1]),
        "maxX": float(bb_parts[2]),
        "maxY": float(bb_parts[3]),
    }

    # Parse nodes
    nodes = []
    for obj in result.get("objects", []):
        if "name" not in obj or "pos" not in obj:
            continue
        pos_parts = obj["pos"].split(",")
        x = float(pos_parts[0])
        y = float(pos_parts[1])
        # Flip Y-axis (Graphviz Y increases upward, QML Y increases downward)
        y = bounds["maxY"] - y

        nodes.append({
            "id": obj["name"],
            "label": obj.get("label", obj["name"]),
            "x": x,
            "y": y,
            "width": float(obj.get("width", 1.5)) * 72,  # inches to points
            "height": float(obj.get("height", 0.6)) * 72,
        })

    # Parse edges
    edges = []
    for edge in result.get("edges", []):
        pos_str = edge.get("pos", "")
        if not pos_str:
            continue

        spline_data = parse_edge_spline(pos_str, bounds["maxY"])
        curve_points = spline_data.get("curvePoints", [])

        if curve_points:
            # Get source and target node names
            tail_idx = edge.get("tail", 0)
            head_idx = edge.get("head", 0)
            source = result["objects"][tail_idx]["name"] if tail_idx < len(result.get("objects", [])) else ""
            target = result["objects"][head_idx]["name"] if head_idx < len(result.get("objects", [])) else ""

            # Build SVG path string for cubic bezier segments
            # Format: M startX,startY C c1x,c1y c2x,c2y endx,endy C ...
            svg_path = f"M {curve_points[0]['x']},{curve_points[0]['y']}"

            # Graphviz gives us: start, then groups of 3 (c1, c2, end) for cubic bezier
            i = 1
            while i + 2 < len(curve_points):
                c1 = curve_points[i]
                c2 = curve_points[i + 1]
                end = curve_points[i + 2]
                svg_path += f" C {c1['x']},{c1['y']} {c2['x']},{c2['y']} {end['x']},{end['y']}"
                i += 3

            # Handle any remaining points with line segments
            while i < len(curve_points):
                svg_path += f" L {curve_points[i]['x']},{curve_points[i]['y']}"
                i += 1

            edges.append({
                "source": source,
                "target": target,
                "svgPath": svg_path,
                "arrowEnd": spline_data.get("arrowEnd"),
                "prevPoint": spline_data.get("prevPoint"),
            })

    return {"nodes": nodes, "edges": edges, "bounds": bounds}


def parse_edge_spline(pos_str: str, max_y: float) -> dict:
    """
    Parse Graphviz edge spline format.

    Format: "e,endX,endY startX,startY control1X,control1Y control2X,control2Y ..."
    Or: "s,startX,startY endX,endY control1X,control1Y ..."

    Returns dict with:
        - arrowEnd: {x, y} for arrow head position
        - curvePoints: list of {x, y} for the bezier curve
        - prevPoint: {x, y} for second-to-last point (for arrow angle)
    """
    parts = pos_str.split()
    arrow_end = None
    curve_points = []

    for part in parts:
        # Handle endpoint markers
        if part.startswith("e,"):
            coords = part[2:].split(",")
            if len(coords) >= 2:
                arrow_end = {
                    "x": float(coords[0]),
                    "y": max_y - float(coords[1])
                }
        elif part.startswith("s,"):
            # Start marker - just parse as regular point
            coords = part[2:].split(",")
            if len(coords) >= 2:
                curve_points.append({
                    "x": float(coords[0]),
                    "y": max_y - float(coords[1])
                })
        else:
            # Regular control point
            coords = part.split(",")
            if len(coords) >= 2:
                curve_points.append({
                    "x": float(coords[0]),
                    "y": max_y - float(coords[1])
                })

    # If no arrow end specified, use last curve point
    if not arrow_end and curve_points:
        arrow_end = curve_points[-1]

    # Get second-to-last point for arrow direction
    prev_point = curve_points[-2] if len(curve_points) >= 2 else arrow_end

    return {
        "arrowEnd": arrow_end,
        "curvePoints": curve_points,
        "prevPoint": prev_point,
    }


class WorkflowModel(QObject):
    """Bridge between Python workflow data and QML UI."""

    dataChanged = Signal()
    selectedPhaseChanged = Signal()
    selectedPhaseEntryChanged = Signal()
    selectedPhaseArtifactsChanged = Signal()
    selectedPhaseLogsChanged = Signal()
    selectedTaskChanged = Signal()
    selectedTaskPromptChanged = Signal()
    selectedTaskLogsChanged = Signal()
    selectedTaskFindingsChanged = Signal()
    requestTabSwitch = Signal(int)  # Signal to switch tabs (0=Phase, 1=Tasks)
    themeModeChanged = Signal()  # Emitted when theme mode changes
    progressFilterChanged = Signal()  # Emitted when progress filter changes
    fullPhasePromptChanged = Signal()  # Emitted when full prompt is loaded

    def __init__(self, plan_path: Path):
        super().__init__()
        self._plan_path = plan_path
        self._plan_name = plan_path.name
        self._nodes = []
        self._edges = []
        self._phases = {}
        self._phase_history = []
        self._selected_phase = None
        self._selected_phase_entry = None  # Entry number (1, 2, 3, ...)
        self._selected_phase_details = {}
        self._progress_entries = []
        self._progress_filter = ""  # Filter string for progress entries
        self._selected_task = None  # Currently selected task dict
        self._selected_task_id = None  # Task ID string
        self._selected_task_prompt = ""  # Full task prompt from CLI
        self._selected_task_logs = ""  # Task progress.txt content
        self._selected_task_findings = []  # List of {name, content} dicts
        self._task_log_watcher = None  # QFileSystemWatcher for task logs
        self._selected_phase_artifacts = []  # List of {name, content, rawContent, isHtml}
        self._selected_phase_logs = ""  # Phase progress logs
        self._phase_log_watcher = None  # QFileSystemWatcher for phase logs
        self._current_phase = None  # Track current phase for auto-follow
        self._full_phase_prompt = ""  # Full prompt from phase-context CLI

        # Theme mode: "system", "light", "dark"
        self._theme_mode = "system"
        self._system_is_dark = darkdetect.isDark() or False

        # File watcher for live updates
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._setup_watches()

        # Initial load
        self._reload()

    def _setup_watches(self) -> None:
        """Watch key files and directories for changes."""
        watch_files = [
            self._plan_path / "state.json",
            self._plan_path / "workflow.toml",
            self._plan_path / "claude-progress.txt",
        ]
        watch_dirs = []

        # Watch phases directory and subdirectories for new file creation
        phases_dir = self._plan_path / "phases"
        if phases_dir.exists():
            watch_dirs.append(phases_dir)
            # Watch each phase directory
            for phase_subdir in phases_dir.iterdir():
                if phase_subdir.is_dir():
                    watch_dirs.append(phase_subdir)
                    # Watch tasks subdirectory if it exists
                    tasks_subdir = phase_subdir / "tasks"
                    if tasks_subdir.exists():
                        watch_dirs.append(tasks_subdir)
                        for task_dir in tasks_subdir.iterdir():
                            if task_dir.is_dir():
                                watch_dirs.append(task_dir)

            # Watch existing files
            for tasks_file in phases_dir.glob("*/tasks.json"):
                watch_files.append(tasks_file)
            for phase_file in phases_dir.glob("*/*.txt"):
                watch_files.append(phase_file)
            for phase_file in phases_dir.glob("*/*.md"):
                watch_files.append(phase_file)
            for task_file in phases_dir.glob("*/tasks/*/*.txt"):
                watch_files.append(task_file)
            for task_file in phases_dir.glob("*/tasks/*/*.md"):
                watch_files.append(task_file)

        for f in watch_files:
            if f.exists():
                self._watcher.addPath(str(f))
                logger.debug(f"Watching file: {f}")
        for d in watch_dirs:
            if d.exists():
                self._watcher.addPath(str(d))
                logger.debug(f"Watching dir: {d}")
        logger.info(f"Watching {len(self._watcher.files())} files, {len(self._watcher.directories())} directories")

    def _on_file_changed(self, path: str) -> None:
        """Reload when watched files change."""
        logger.info(f"File changed: {path}")
        self._reload()
        # Re-add watch (Qt removes after change notification)
        if Path(path).exists():
            self._watcher.addPath(path)
        # Check for new files that weren't being watched
        self._watch_new_phase_files()

    def _on_directory_changed(self, path: str) -> None:
        """Reload when directory contents change (new files created)."""
        logger.info(f"Directory changed: {path}")
        self._reload()
        # Watch any new files/directories that were created
        self._watch_new_phase_files()
        self._watch_new_directories()

    def _watch_new_directories(self) -> None:
        """Add watches for any new directories."""
        phases_dir = self._plan_path / "phases"
        if phases_dir.exists():
            watched = set(self._watcher.directories())
            # Watch phases dir itself
            if str(phases_dir) not in watched:
                self._watcher.addPath(str(phases_dir))
                logger.debug(f"Added watch for new dir: {phases_dir}")
            # Watch phase subdirectories and their contents
            for phase_subdir in phases_dir.iterdir():
                if phase_subdir.is_dir():
                    if str(phase_subdir) not in watched:
                        self._watcher.addPath(str(phase_subdir))
                        logger.debug(f"Added watch for new dir: {phase_subdir}")
                    # Always check for tasks subdirectory (may be created later)
                    tasks_subdir = phase_subdir / "tasks"
                    if tasks_subdir.exists():
                        if str(tasks_subdir) not in watched:
                            self._watcher.addPath(str(tasks_subdir))
                            logger.debug(f"Added watch for new dir: {tasks_subdir}")
                        # Watch individual task directories
                        for task_dir in tasks_subdir.iterdir():
                            if task_dir.is_dir() and str(task_dir) not in watched:
                                self._watcher.addPath(str(task_dir))
                                logger.debug(f"Added watch for new dir: {task_dir}")

    def _watch_new_phase_files(self) -> None:
        """Add watches for any new phase/task files."""
        phases_dir = self._plan_path / "phases"
        if phases_dir.exists():
            watched = set(self._watcher.files())
            # Patterns to watch for new files
            patterns = [
                "*/tasks.json",      # Phase tasks
                "*/*.txt",           # Phase progress/artifacts
                "*/*.md",            # Phase artifacts
                "*/tasks/*/*.txt",   # Task progress
                "*/tasks/*/*.md",    # Task outputs
            ]
            for pattern in patterns:
                for f in phases_dir.glob(pattern):
                    if str(f) not in watched:
                        self._watcher.addPath(str(f))
                        logger.debug(f"Added watch for new file: {f}")

    def _reload(self) -> None:
        """Reload workflow and state from files."""
        logger.debug("Reloading workflow data...")
        workflow = self._load_workflow()
        state = self._load_state()
        layout = compute_layout(workflow)

        # Track current phase for auto-follow
        old_current = self._current_phase
        new_current = state.get("current_phase")

        self._build_nodes(workflow, state, layout)
        self._edges = layout["edges"]
        self._build_phase_details(workflow, state)
        self._build_phase_history(state)
        self._load_progress()

        # Auto-follow current phase logic:
        # 1. On initial load (nothing selected), select current phase
        # 2. If user was viewing current phase and it changed, follow it
        # 3. Otherwise, keep user's selection
        if self._selected_phase is None and new_current:
            # Initial load - select current phase
            logger.debug(f"Initial load: selecting current phase {new_current}")
            self._current_phase = new_current
            self.selectPhase(new_current)
        elif (
            self._selected_phase == old_current
            and new_current
            and new_current != old_current
        ):
            # User was following current, and it changed
            logger.debug(f"Auto-following current phase: {old_current} -> {new_current}")
            self._current_phase = new_current
            self.selectPhase(new_current)
        else:
            # User has a different selection, keep it
            self._current_phase = new_current
            # Update selected phase details if an entry is selected
            if self._selected_phase_entry:
                logger.debug(f"Updating selected phase entry: {self._selected_phase_entry}")
                self._update_selected_phase_details()

        self.dataChanged.emit()
        logger.debug("Reload complete, dataChanged emitted")

    def _load_workflow(self) -> dict:
        """Load workflow.toml."""
        workflow_path = self._plan_path / "workflow.toml"
        if workflow_path.exists():
            with open(workflow_path, "rb") as f:
                return tomli.load(f)
        return {"phases": []}

    def _load_state(self) -> dict:
        """Load state.json."""
        state_path = self._plan_path / "state.json"
        if state_path.exists():
            with open(state_path) as f:
                return json.load(f)
        return {}

    def _build_nodes(self, workflow: dict, state: dict, layout: dict) -> None:
        """Build node list with layout positions and status."""
        current_phase = state.get("current_phase")
        phase_history = state.get("phase_history", [])
        completed_phases = {entry.get("phase", entry.get("phase_id", "")) for entry in phase_history}

        # Map layout nodes by id
        layout_map = {n["id"]: n for n in layout["nodes"]}

        self._nodes = []
        for phase in workflow.get("phases", []):
            phase_id = phase.get("id", "")
            layout_node = layout_map.get(phase_id, {})

            # Determine status
            if phase_id == current_phase:
                # Terminal phases that are current should show as completed
                status = "completed" if phase.get("terminal") else "current"
            elif phase_id in completed_phases:
                status = "completed"
            elif phase.get("terminal"):
                status = "terminal"
            else:
                status = "pending"

            self._nodes.append({
                "id": phase_id,
                "label": layout_node.get("label", phase_id.replace("-", " ").title()),
                "x": layout_node.get("x", 0),
                "y": layout_node.get("y", 0),
                "width": layout_node.get("width", 108),
                "height": layout_node.get("height", 43),
                "status": status,
            })

    def _build_phase_details(self, workflow: dict, state: dict) -> None:
        """Build detailed info for each phase."""
        phase_history = state.get("phase_history", [])

        # Count entries per phase
        entry_counts = {}
        for entry in phase_history:
            pid = entry.get("phase", entry.get("phase_id", ""))
            entry_counts[pid] = entry_counts.get(pid, 0) + 1

        self._phases = {}
        for phase in workflow.get("phases", []):
            phase_id = phase.get("id", "")
            # Normalize suggested_next to include approval metadata
            suggested_full = []
            for item in phase.get("suggested_next", []):
                if isinstance(item, str):
                    suggested_full.append({"phase": item, "requires_approval": False})
                elif isinstance(item, dict):
                    suggested_full.append({
                        "phase": item.get("phase", ""),
                        "requires_approval": item.get("requires_approval", False),
                        "approval_prompt": item.get("approval_prompt"),
                    })
            self._phases[phase_id] = {
                "id": phase_id,
                "name": phase_id.replace("-", " ").title(),
                "prompt": phase.get("prompt", ""),
                "suggested_next": suggested_full,
                "terminal": phase.get("terminal", False),
                "use_tasks": phase.get("use_tasks", False),
                "entry_count": entry_counts.get(phase_id, 0),
                "tasks": [],
            }

    def _load_progress(self) -> None:
        """Load claude-progress.txt entries."""
        progress_path = self._plan_path / "claude-progress.txt"
        self._progress_entries = []

        if not progress_path.exists():
            return

        # Parse progress lines: [YYYY-MM-DD HH:MM:SS] message
        pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.+)")

        with open(progress_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = pattern.match(line)
                if match:
                    timestamp, message = match.groups()
                    # Categorize message
                    msg_type = "info"
                    if message.startswith("TASK_STATUS:"):
                        msg_type = "task"
                    elif message.startswith("PHASE_ENTERED:"):
                        msg_type = "phase"
                    elif message.startswith("SESSION_"):
                        msg_type = "session"

                    self._progress_entries.append({
                        "timestamp": timestamp,
                        "message": message,
                        "type": msg_type,
                    })

        # Keep most recent entries (last 100)
        self._progress_entries = self._progress_entries[-100:]

    def _build_phase_history(self, state: dict) -> None:
        """Build phase history list for QML."""
        raw_history = state.get("phase_history", [])
        self._phase_history = []

        for entry in raw_history:
            self._phase_history.append({
                "entry": entry.get("entry", 0),
                "phase": entry.get("phase", ""),
                "dir": entry.get("dir", ""),
                "entered": entry.get("entered", ""),
                "exited": entry.get("exited"),
                "reason": entry.get("reason", ""),
                "outcome": entry.get("outcome"),
            })

    def _load_phase_tasks(self, phase_dir: str) -> list:
        """Load tasks for a specific phase directory."""
        if not phase_dir:
            logger.debug("_load_phase_tasks: no phase_dir provided")
            return []
        phase_path = Path(phase_dir)
        if not phase_path.is_absolute():
            phase_path = self._plan_path / phase_path
        tasks_file = phase_path / "tasks.json"
        logger.debug(f"_load_phase_tasks: checking {tasks_file}")
        if tasks_file.exists():
            with open(tasks_file) as f:
                tasks = json.load(f)
                logger.debug(f"_load_phase_tasks: loaded {len(tasks)} tasks")
                return tasks
        logger.debug("_load_phase_tasks: tasks.json not found")
        return []

    def _find_entry_by_number(self, entry_num: int) -> dict | None:
        """Find phase history entry by entry number."""
        for entry in self._phase_history:
            if entry.get("entry") == entry_num:
                return entry
        return None

    def _find_latest_entry_for_phase(self, phase_id: str) -> dict | None:
        """Find the most recent entry for a given phase."""
        latest = None
        for entry in self._phase_history:
            if entry.get("phase") == phase_id:
                if latest is None or entry.get("entry", 0) > latest.get("entry", 0):
                    latest = entry
        return latest

    def _update_selected_phase_details(self) -> None:
        """Update details for the selected phase entry."""
        logger.debug(f"_update_selected_phase_details: entry={self._selected_phase_entry}")
        # Clear full prompt when phase changes (loaded on demand)
        self._full_phase_prompt = ""
        self.fullPhasePromptChanged.emit()

        if not self._selected_phase_entry:
            self._selected_phase_details = {}
            return

        entry = self._find_entry_by_number(self._selected_phase_entry)
        if not entry:
            logger.debug("_update_selected_phase_details: entry not found")
            self._selected_phase_details = {}
            return

        phase_id = entry.get("phase", "")
        phase_dir = entry.get("dir", "")
        logger.debug(f"_update_selected_phase_details: phase={phase_id}, dir={phase_dir}")

        if phase_id in self._phases:
            details = dict(self._phases[phase_id])
            details["entry"] = entry.get("entry")
            details["entryDir"] = phase_dir
            details["entered"] = entry.get("entered", "")
            details["reason"] = entry.get("reason", "")
            details["outcome"] = entry.get("outcome")
            details["tasks"] = self._load_phase_tasks(phase_dir)
            logger.debug(f"_update_selected_phase_details: loaded {len(details['tasks'])} tasks")
            self._selected_phase_details = details
            self._load_phase_artifacts(phase_dir)
            self._load_phase_logs(phase_dir)
            self.selectedPhaseChanged.emit()  # Notify QML of updated details
        else:
            self._selected_phase_details = {}
            self._selected_phase_artifacts = []
            self._selected_phase_logs = ""
            self.selectedPhaseChanged.emit()
            self.selectedPhaseArtifactsChanged.emit()
            self.selectedPhaseLogsChanged.emit()

    def _load_phase_artifacts(self, phase_dir: str) -> None:
        """Load artifacts from phase directory."""
        artifacts = []
        if phase_dir:
            phase_path = Path(phase_dir)
            if not phase_path.is_absolute():
                phase_path = self._plan_path / phase_path
            if phase_path.exists():
                # Look for common artifact files (exclude tasks.json, progress files)
                exclude = {"tasks.json", "progress.txt", "claude-progress.txt"}
                for file_path in phase_path.iterdir():
                    if file_path.is_file() and file_path.name not in exclude:
                        try:
                            raw_content = file_path.read_text(encoding="utf-8")
                            is_md = file_path.suffix.lower() == ".md"
                            artifacts.append({
                                "name": file_path.name,
                                "content": md_to_html(raw_content) if is_md else raw_content,
                                "rawContent": raw_content,
                                "isHtml": is_md,
                            })
                        except Exception:
                            pass
        self._selected_phase_artifacts = artifacts
        self.selectedPhaseArtifactsChanged.emit()

    def _load_phase_logs(self, phase_dir: str) -> None:
        """Load phase progress logs with live watching."""
        # Clean up previous watcher
        if self._phase_log_watcher:
            self._phase_log_watcher.deleteLater()
            self._phase_log_watcher = None

        logs = ""
        if phase_dir:
            phase_path = Path(phase_dir)
            if not phase_path.is_absolute():
                phase_path = self._plan_path / phase_path
            # Try progress.txt in phase dir
            progress_file = phase_path / "progress.txt"
            if progress_file.exists():
                try:
                    logs = progress_file.read_text(encoding="utf-8")
                    # Set up file watcher for live updates
                    self._phase_log_watcher = QFileSystemWatcher()
                    self._phase_log_watcher.addPath(str(progress_file))
                    self._phase_log_watcher.fileChanged.connect(
                        lambda: self._reload_phase_logs(progress_file)
                    )
                except Exception:
                    pass
        self._selected_phase_logs = logs
        self.selectedPhaseLogsChanged.emit()

    def _reload_phase_logs(self, log_file: Path) -> None:
        """Reload phase logs when file changes."""
        try:
            if log_file.exists():
                self._selected_phase_logs = log_file.read_text(encoding="utf-8")
                self.selectedPhaseLogsChanged.emit()
                # Re-add path (Qt removes it after change)
                if self._phase_log_watcher:
                    self._phase_log_watcher.addPath(str(log_file))
        except Exception:
            pass

    # Qt Properties for QML binding

    @Property(str, constant=True)
    def planName(self) -> str:
        return self._plan_name

    @Property(str, constant=True)
    def planPath(self) -> str:
        return str(self._plan_path)

    @Property(str, notify=themeModeChanged)
    def themeMode(self) -> str:
        """Current theme mode: 'system', 'light', or 'dark'."""
        return self._theme_mode

    @Property(bool, notify=themeModeChanged)
    def systemIsDark(self) -> bool:
        """Whether the system is in dark mode."""
        return self._system_is_dark

    @Property(bool, notify=themeModeChanged)
    def isDark(self) -> bool:
        """Computed dark mode state based on theme mode and system setting."""
        if self._theme_mode == "system":
            return self._system_is_dark
        return self._theme_mode == "dark"

    @Slot()
    def cycleTheme(self) -> None:
        """Cycle through theme modes: system -> light -> dark -> system."""
        modes = ["system", "light", "dark"]
        current_index = modes.index(self._theme_mode)
        self._theme_mode = modes[(current_index + 1) % len(modes)]
        self.themeModeChanged.emit()

    @Property("QVariantList", notify=dataChanged)
    def nodes(self) -> list:
        return self._nodes

    @Property("QVariantList", notify=dataChanged)
    def edges(self) -> list:
        return self._edges

    @Property(str, notify=selectedPhaseChanged)
    def selectedPhase(self) -> str:
        return self._selected_phase or ""

    @Property("QVariant", notify=selectedPhaseChanged)
    def selectedPhaseDetails(self) -> dict:
        return self._selected_phase_details

    @Property(str, notify=selectedPhaseChanged)
    def selectedPhasePromptHtml(self) -> str:
        """Phase prompt converted to HTML for rich text display."""
        prompt = self._selected_phase_details.get("prompt", "")
        return md_to_html(prompt) if prompt else ""

    @Property(str, notify=fullPhasePromptChanged)
    def fullPhasePromptHtml(self) -> str:
        """Full assembled prompt converted to HTML for rich text display."""
        return md_to_html(self._full_phase_prompt) if self._full_phase_prompt else ""

    @Slot()
    def loadFullPhasePrompt(self) -> None:
        """Load the full phase prompt from CLI (called on demand from QML)."""
        import subprocess

        if not self._selected_phase_entry:
            self._full_phase_prompt = ""
            self.fullPhasePromptChanged.emit()
            return

        try:
            # Get plugin root from environment or infer from this file's location
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent))
            result = subprocess.run(
                ["uv", "run", f"{plugin_root}/plan.py", "phase-context",
                 "--entry", str(self._selected_phase_entry)],
                capture_output=True,
                text=True,
                cwd=str(self._plan_path.parent.parent.parent),  # Project dir
                timeout=10,
            )
            if result.returncode == 0:
                self._full_phase_prompt = result.stdout
            else:
                self._full_phase_prompt = f"Error loading full prompt: {result.stderr}"
        except Exception as e:
            self._full_phase_prompt = f"Error loading full prompt: {e}"

        self.fullPhasePromptChanged.emit()

    @Property("QVariantList", notify=selectedPhaseArtifactsChanged)
    def selectedPhaseArtifacts(self) -> list:
        return self._selected_phase_artifacts

    @Property(str, notify=selectedPhaseLogsChanged)
    def selectedPhaseLogs(self) -> str:
        return self._selected_phase_logs

    @Property("QVariantList", notify=dataChanged)
    def progressEntries(self) -> list:
        if not self._progress_filter:
            return self._progress_entries
        filter_lower = self._progress_filter.lower()
        return [e for e in self._progress_entries if filter_lower in e.get("message", "").lower()]

    @Property(str, notify=progressFilterChanged)
    def progressFilter(self) -> str:
        return self._progress_filter

    @progressFilter.setter
    def progressFilter(self, value: str) -> None:
        if self._progress_filter != value:
            self._progress_filter = value
            self.progressFilterChanged.emit()
            self.dataChanged.emit()  # Trigger re-filter of progressEntries

    @Property("QVariantList", notify=dataChanged)
    def phaseHistory(self) -> list:
        return self._phase_history

    @Property(int, notify=selectedPhaseEntryChanged)
    def selectedPhaseEntry(self) -> int:
        return self._selected_phase_entry or 0

    @Property("QVariant", notify=selectedTaskChanged)
    def selectedTask(self) -> dict | None:
        return self._selected_task

    @Property(str, notify=selectedTaskChanged)
    def selectedTaskId(self) -> str:
        return self._selected_task_id or ""

    @Property(str, notify=selectedTaskPromptChanged)
    def selectedTaskPrompt(self) -> str:
        return self._selected_task_prompt

    @Property(str, notify=selectedTaskLogsChanged)
    def selectedTaskLogs(self) -> str:
        return self._selected_task_logs

    @Property("QVariantList", notify=selectedTaskFindingsChanged)
    def selectedTaskFindings(self) -> list:
        return self._selected_task_findings

    # Slots for QML actions

    @Slot(str)
    def selectPhase(self, phase_id: str) -> None:
        """Select a phase from the diagram - selects the most recent entry."""
        # Find the most recent entry for this phase
        entry = self._find_latest_entry_for_phase(phase_id)
        if entry:
            entry_num = entry.get("entry", 0)
            if entry_num != self._selected_phase_entry:
                self._selected_phase = phase_id
                self._selected_phase_entry = entry_num
                self._update_selected_phase_details()
                # Clear task selection when phase changes
                self._clear_task_selection()
                self.selectedPhaseChanged.emit()
                self.selectedPhaseEntryChanged.emit()
        elif phase_id != self._selected_phase:
            # Phase exists but hasn't been entered yet - just select the phase
            self._selected_phase = phase_id
            self._selected_phase_entry = None
            self._selected_phase_details = dict(self._phases.get(phase_id, {}))
            # Clear task selection when phase changes
            self._clear_task_selection()
            self.selectedPhaseChanged.emit()
            self.selectedPhaseEntryChanged.emit()

    @Slot(int)
    def selectPhaseEntry(self, entry_num: int) -> None:
        """Select a specific phase entry from the history list."""
        if entry_num != self._selected_phase_entry:
            entry = self._find_entry_by_number(entry_num)
            if entry:
                self._selected_phase_entry = entry_num
                self._selected_phase = entry.get("phase", "")
                self._update_selected_phase_details()
                # Clear task selection when phase changes
                self._clear_task_selection()
                self.selectedPhaseChanged.emit()
                self.selectedPhaseEntryChanged.emit()

    @Slot(str)
    def selectTask(self, task_id: str) -> None:
        """Select a task to show its details."""
        if task_id != self._selected_task_id:
            self._selected_task_id = task_id
            # Find task in current phase's tasks
            tasks = self._selected_phase_details.get("tasks", [])
            self._selected_task = None
            for task in tasks:
                if task.get("id") == task_id:
                    self._selected_task = task
                    break
            self.selectedTaskChanged.emit()

            # Load task data
            if self._selected_task:
                self._load_task_prompt(task_id)
                self._load_task_findings(task_id)
                self._load_task_logs(task_id)
            else:
                self._clear_task_data()

    def _load_task_prompt(self, task_id: str) -> None:
        """Build task prompt from task data as HTML."""
        if not self._selected_task:
            self._selected_task_prompt = ""
            self.selectedTaskPromptChanged.emit()
            return

        task = self._selected_task
        lines = []

        # Description
        if task.get("description"):
            lines.append(f"**{task['description']}**")
            lines.append("")

        # Steps
        if task.get("steps"):
            lines.append("### Steps")
            for step in task["steps"]:
                lines.append(f"- {step}")
            lines.append("")

        # Parents (dependencies)
        if task.get("parents"):
            parents = ", ".join(f"`{p}`" for p in task["parents"])
            lines.append(f"**Dependencies:** {parents}")
            lines.append("")

        # Context artifacts
        if task.get("context_artifacts"):
            artifacts = ", ".join(f"`{a}`" for a in task["context_artifacts"])
            lines.append(f"**Context artifacts:** {artifacts}")
            lines.append("")

        # Subagent info
        if task.get("subagent"):
            lines.append(f"**Subagent:** `{task['subagent']}`")
        if task.get("subagent_prompt"):
            lines.append(f"**Subagent prompt:** {task['subagent_prompt']}")

        md_text = "\n".join(lines)
        self._selected_task_prompt = md_to_html(md_text)
        self.selectedTaskPromptChanged.emit()

    def _get_task_dir(self, task_id: str) -> Path | None:
        """Get task directory from selected phase entry."""
        entry_dir = self._selected_phase_details.get("entryDir", "")
        if entry_dir:
            # entry_dir may be relative to plan path
            entry_path = Path(entry_dir)
            if not entry_path.is_absolute():
                entry_path = self._plan_path / entry_path
            task_dir = entry_path / "tasks" / task_id
            if task_dir.exists():
                return task_dir
        return None

    def _load_task_findings(self, task_id: str) -> None:
        """Load task findings from task directory as HTML."""
        findings = []
        task_dir = self._get_task_dir(task_id)
        if task_dir:
            for file_path in task_dir.iterdir():
                # Skip progress.txt (shown in logs) and directories
                if file_path.is_file() and file_path.name != "progress.txt":
                    try:
                        raw_content = file_path.read_text(encoding="utf-8")
                        is_md = file_path.suffix.lower() == ".md"
                        findings.append({
                            "name": file_path.name,
                            "content": md_to_html(raw_content) if is_md else raw_content,
                            "rawContent": raw_content,
                            "isHtml": is_md,
                        })
                    except Exception:
                        pass
        self._selected_task_findings = findings
        self.selectedTaskFindingsChanged.emit()

    def _load_task_logs(self, task_id: str) -> None:
        """Load task progress.txt and set up file watching."""
        # Stop watching previous task log
        if self._task_log_watcher:
            self._task_log_watcher.deleteLater()
            self._task_log_watcher = None

        self._selected_task_logs = ""
        task_dir = self._get_task_dir(task_id)
        if task_dir:
            log_file = task_dir / "progress.txt"
            if log_file.exists():
                try:
                    self._selected_task_logs = log_file.read_text(encoding="utf-8")
                    # Set up file watcher for live updates
                    self._task_log_watcher = QFileSystemWatcher()
                    self._task_log_watcher.addPath(str(log_file))
                    self._task_log_watcher.fileChanged.connect(
                        lambda: self._on_task_log_changed(log_file)
                    )
                except Exception:
                    pass
        self.selectedTaskLogsChanged.emit()

    def _on_task_log_changed(self, log_file: Path) -> None:
        """Handle task log file changes."""
        try:
            if log_file.exists():
                self._selected_task_logs = log_file.read_text(encoding="utf-8")
                # Re-add watch (Qt removes it after notification)
                if self._task_log_watcher:
                    self._task_log_watcher.addPath(str(log_file))
            else:
                self._selected_task_logs = ""
        except Exception:
            self._selected_task_logs = ""
        self.selectedTaskLogsChanged.emit()

    def _clear_task_data(self) -> None:
        """Clear all task-related data."""
        self._selected_task_prompt = ""
        self._selected_task_logs = ""
        self._selected_task_findings = []
        if self._task_log_watcher:
            self._task_log_watcher.deleteLater()
            self._task_log_watcher = None
        self.selectedTaskPromptChanged.emit()
        self.selectedTaskLogsChanged.emit()
        self.selectedTaskFindingsChanged.emit()

    @Slot()
    def clearTaskSelection(self) -> None:
        """Clear the current task selection."""
        self._clear_task_selection()

    def _clear_task_selection(self) -> None:
        """Internal method to clear task selection."""
        if self._selected_task is not None or self._selected_task_id is not None:
            self._selected_task = None
            self._selected_task_id = None
            self._clear_task_data()
            self.selectedTaskChanged.emit()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)

    @Slot(str, result=bool)
    def navigateToLink(self, url: str) -> bool:
        """
        Navigate to a link from rich text content.
        Handles task findings links like '.../tasks/task-id/findings.md'.
        Returns True if navigation occurred, False if link should open externally.
        """
        # Parse task links - look for /tasks/<task-id>/ pattern anywhere in path
        if "/tasks/" in url:
            # Extract task ID from path like .../tasks/task-id/...
            parts = url.split("/tasks/")
            if len(parts) >= 2:
                # Get the part after /tasks/ and extract task-id
                after_tasks = parts[1]
                task_id = after_tasks.split("/")[0]
                if task_id:
                    # Check if this task exists in current phase
                    tasks = self._selected_phase_details.get("tasks", [])
                    for task in tasks:
                        if task.get("id") == task_id:
                            # Select the task and switch to Tasks tab
                            self.selectTask(task_id)
                            self.requestTabSwitch.emit(1)  # Switch to Tasks tab
                            return True
        return False


def main() -> int:
    """Main entry point."""
    # Check dependencies
    check_graphviz()

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: viewer.py /path/to/plan")
        return 1

    plan_path = parse_plan_path(sys.argv[1])

    # Create Qt application
    app = QGuiApplication(sys.argv)
    app.setApplicationName("JonsPlan Viewer")
    app.setOrganizationName("jons-plan")

    # Create model
    model = WorkflowModel(plan_path)

    # Load QML
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("workflowModel", model)

    qml_path = Path(__file__).parent / "qml" / "main.qml"
    if not qml_path.exists():
        print(f"Error: QML not found: {qml_path}", file=sys.stderr)
        return 1

    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("Error: Failed to load QML", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
