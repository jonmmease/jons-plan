---
description: Open the workflow viewer for the active jons-plan
allowed-tools: Bash(uv run:*)
---

# Open Viewer

Launch the workflow viewer for the active plan.

## Workflow

1. **Check for active plan**:
   ```bash
   PLAN_DIR="$(uv run ~/.claude-plugins/jons-plan/plan.py active-plan-dir 2>/dev/null)"
   ```

   If empty or command fails, tell user: "No active plan. Use `/jons-plan:new [topic]` to create one, or `/jons-plan:switch [name]` to select an existing plan."

2. **Launch viewer**:
   ```bash
   nohup uv run ~/.claude-plugins/jons-plan/viewer.py "$PLAN_DIR" &>/dev/null &
   ```

3. **Confirm**: Tell user "Viewer launched for plan: [plan-name]"
