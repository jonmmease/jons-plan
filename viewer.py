#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyside6>=6.6", "graphviz>=0.20", "tomli>=2.0"]
# ///
"""
JonsPlan Workflow Viewer

A PySide6/QML application for visualizing jons-plan workflows.
Launched via jons-plan:// URL scheme.

Usage:
    uv run viewer.py jons-plan:///path/to/plan
    uv run viewer.py /path/to/plan
"""

import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import graphviz
import tomli
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


def check_graphviz() -> None:
    """Verify Graphviz system binaries are installed."""
    if not shutil.which("dot"):
        print("Error: Graphviz not found.", file=sys.stderr)
        print("Install with: brew install graphviz", file=sys.stderr)
        sys.exit(1)


def parse_url(url_str: str) -> Path:
    """Parse jons-plan:// URL or direct path to plan directory."""
    if url_str.startswith("jons-plan://"):
        parsed = urlparse(url_str)
        path_str = unquote(parsed.path)
    else:
        path_str = url_str

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

    # Add transition edges
    for phase in phases:
        phase_id = phase.get("id", "")
        for next_id in phase.get("suggested_next", []):
            # Skip special transitions like __expand__
            if not next_id.startswith("__"):
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

    def __init__(self, plan_path: Path):
        super().__init__()
        self._plan_path = plan_path
        self._plan_name = plan_path.name
        self._nodes = []
        self._edges = []
        self._phases = {}
        self._selected_phase = None
        self._selected_phase_details = {}
        self._progress_entries = []

        # File watcher for live updates
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._setup_watches()

        # Initial load
        self._reload()

    def _setup_watches(self) -> None:
        """Watch key files for changes."""
        watch_files = [
            self._plan_path / "state.json",
            self._plan_path / "workflow.toml",
            self._plan_path / "claude-progress.txt",
        ]
        for f in watch_files:
            if f.exists():
                self._watcher.addPath(str(f))

    def _on_file_changed(self, path: str) -> None:
        """Reload when watched files change."""
        self._reload()
        # Re-add watch (Qt removes after change notification)
        if Path(path).exists():
            self._watcher.addPath(path)

    def _reload(self) -> None:
        """Reload workflow and state from files."""
        workflow = self._load_workflow()
        state = self._load_state()
        layout = compute_layout(workflow)

        self._build_nodes(workflow, state, layout)
        self._edges = layout["edges"]
        self._build_phase_details(workflow, state)
        self._load_progress()

        # Update selected phase details if a phase is selected
        if self._selected_phase:
            self._update_selected_phase_details()

        self.dataChanged.emit()

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
                status = "current"
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
            self._phases[phase_id] = {
                "id": phase_id,
                "name": phase_id.replace("-", " ").title(),
                "prompt": phase.get("prompt", ""),
                "suggested_next": phase.get("suggested_next", []),
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

    def _load_phase_tasks(self, phase_id: str) -> list:
        """Load tasks for a specific phase."""
        # Find the phase directory
        phases_dir = self._plan_path / "phases"
        if not phases_dir.exists():
            return []

        # Find phase directory (format: NN-{phase_id})
        for phase_dir in phases_dir.iterdir():
            if phase_dir.is_dir() and phase_dir.name.endswith(f"-{phase_id}"):
                tasks_file = phase_dir / "tasks.json"
                if tasks_file.exists():
                    with open(tasks_file) as f:
                        return json.load(f)
        return []

    def _update_selected_phase_details(self) -> None:
        """Update details for the selected phase."""
        if self._selected_phase and self._selected_phase in self._phases:
            details = dict(self._phases[self._selected_phase])
            details["tasks"] = self._load_phase_tasks(self._selected_phase)
            self._selected_phase_details = details
        else:
            self._selected_phase_details = {}

    # Qt Properties for QML binding

    @Property(str, constant=True)
    def planName(self) -> str:
        return self._plan_name

    @Property(str, constant=True)
    def planPath(self) -> str:
        return str(self._plan_path)

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

    @Property("QVariantList", notify=dataChanged)
    def progressEntries(self) -> list:
        return self._progress_entries

    # Slots for QML actions

    @Slot(str)
    def selectPhase(self, phase_id: str) -> None:
        """Select a phase to show its details."""
        if phase_id != self._selected_phase:
            self._selected_phase = phase_id
            self._update_selected_phase_details()
            self.selectedPhaseChanged.emit()


def main() -> int:
    """Main entry point."""
    # Check dependencies
    check_graphviz()

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: viewer.py jons-plan:///path/to/plan")
        print("       viewer.py /path/to/plan")
        return 1

    plan_path = parse_url(sys.argv[1])

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
