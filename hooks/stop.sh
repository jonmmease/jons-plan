#!/bin/bash
# Stop hook: Auto-continue in proceed mode, otherwise provide session summary
# Blocks stop if in proceed mode with available tasks

set -e

# Helper to run plan CLI from plugin location
plan() {
    uv run ~/.claude-plugins/jons-plan/plan.py "$@"
}

# Read hook input from stdin
INPUT=$(cat)

# Parse stop_hook_active from input JSON (prevents infinite loops)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# Find project root (where .claude/ lives)
PROJECT_DIR="$(pwd)"
while [[ "$PROJECT_DIR" != "/" ]]; do
    if [[ -d "${PROJECT_DIR}/.claude" ]]; then
        break
    fi
    PROJECT_DIR="$(dirname "$PROJECT_DIR")"
done

# Get active plan
ACTIVE_PLAN=$(plan active-plan 2>/dev/null || echo "")
ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")

# Skip if no active plan
if [[ -z "$ACTIVE_PLAN_DIR" ]]; then
    exit 0
fi

# Check session mode
SESSION_MODE_FILE="${PROJECT_DIR}/.claude/jons-plan/session-mode"
SESSION_MODE=""
if [[ -f "$SESSION_MODE_FILE" ]]; then
    SESSION_MODE=$(cat "$SESSION_MODE_FILE")
fi

# Auto-continue logic: Block stop if in proceed mode with available tasks
if [[ "$SESSION_MODE" == "proceed" ]] && [[ "$STOP_HOOK_ACTIVE" != "true" ]]; then
    # Check for blocked tasks first
    if plan has-blockers 2>/dev/null; then
        # Don't auto-continue if there are blocked tasks
        :
    else
        # Check for available tasks
        NEXT_TASKS=$(plan next-tasks 2>/dev/null || echo "")
        if [[ -n "$NEXT_TASKS" ]]; then
            # There are available tasks - block the stop
            TASK_COUNT=$(echo "$NEXT_TASKS" | wc -l | tr -d ' ')
            echo '{"decision": "block", "reason": "Session mode is proceed and there are '"$TASK_COUNT"' available tasks. Continue working on the next task. Run: uv run ~/.claude-plugins/jons-plan/plan.py next-tasks"}'
            exit 2
        fi
    fi
fi

# If we get here, allow the stop - log it
plan log "SESSION_STOP" 2>/dev/null || true

# Calculate session statistics
PROGRESS_FILE="${ACTIVE_PLAN_DIR}/claude-progress.txt"
if [[ -f "$PROGRESS_FILE" ]]; then
    # Find last SESSION_START and count modifications since then
    SESSION_START_LINE=$(grep -n "SESSION_START" "$PROGRESS_FILE" | tail -1 | cut -d: -f1)
    if [[ -n "$SESSION_START_LINE" ]]; then
        TOTAL_LINES=$(wc -l < "$PROGRESS_FILE" | tr -d ' ')
        LINES_THIS_SESSION=$((TOTAL_LINES - SESSION_START_LINE))
        FILE_MODS=$(tail -n "$LINES_THIS_SESSION" "$PROGRESS_FILE" | grep -c "FILE_MODIFIED" 2>/dev/null || echo 0)
    else
        FILE_MODS=0
    fi
else
    FILE_MODS=0
fi

# Task status
STATS=$(plan task-stats 2>/dev/null || echo "?/?")

# Output session summary
echo ""
echo "=== Session Summary: ${ACTIVE_PLAN} ==="
echo "Files modified this session: ${FILE_MODS}"
echo "Task progress: ${STATS}"

# Check for uncommitted changes
if git rev-parse --git-dir > /dev/null 2>&1; then
    DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$DIRTY" -gt 0 ]]; then
        echo ""
        echo "TIP: ${DIRTY} uncommitted changes. Consider committing before ending."
    fi
fi

exit 0
