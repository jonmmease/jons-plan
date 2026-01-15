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

# Note: We intentionally don't check stop_hook_active here.
# Our termination condition is "no available tasks", which naturally
# prevents infinite loops. We want Claude to keep working until done.

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

# Auto-continue logic: Block stop if in proceed mode with work remaining
# Also handle awaiting-feedback mode for workflow phases requiring user input
if [[ "$SESSION_MODE" == "proceed" ]]; then
    # Check for blocked tasks first - need human intervention
    if plan has-blockers 2>/dev/null; then
        # Don't auto-continue if there are blocked tasks
        :
    else
        # Get current phase info from phase-context --json
        PHASE_JSON=$(plan phase-context --json 2>/dev/null || echo "{}")

        # Check if current phase is terminal - allow stop at terminal phases
        IS_TERMINAL=$(echo "$PHASE_JSON" | grep -o '"terminal": *true' || echo "")
        if [[ -n "$IS_TERMINAL" ]]; then
            # At terminal phase - allow stop
            :
        else
            # Check if phase requires user input
            REQUIRES_USER=$(echo "$PHASE_JSON" | grep -o '"requires_user_input": *true' || echo "")
            if [[ -n "$REQUIRES_USER" ]]; then
                # Phase needs user input - allow stop (user will review and proceed)
                :
            else
                # Check for phase tasks
                PHASE_TASKS=$(plan phase-next-tasks 2>/dev/null || echo "")
                if [[ -n "$PHASE_TASKS" && "$PHASE_TASKS" != "No tasks in current phase" && "$PHASE_TASKS" != "All phase tasks complete" ]]; then
                    TASK_COUNT=$(echo "$PHASE_TASKS" | wc -l | tr -d ' ')
                    echo '{"decision": "block", "reason": "Phase has '"$TASK_COUNT"' available tasks. Continue working on the next task. Run: uv run ~/.claude-plugins/jons-plan/plan.py phase-next-tasks"}'
                    exit 2
                fi

                # Check if there are suggested next phases (workflow not complete)
                SUGGESTED_NEXT=$(echo "$PHASE_JSON" | grep -o '"suggested_next": *\[[^]]*\]' | grep -v '\[\]' || echo "")
                if [[ -n "$SUGGESTED_NEXT" ]]; then
                    echo '{"decision": "block", "reason": "Current phase complete but workflow continues. Check suggested_next phases and transition. Run: uv run ~/.claude-plugins/jons-plan/plan.py suggested-next"}'
                    exit 2
                fi
            fi
        fi
    fi
elif [[ "$SESSION_MODE" == "awaiting-feedback" ]]; then
    # In awaiting-feedback mode - user review required, allow stop
    :
fi

# If we get here, allow the stop - log it and clear session mode
plan log "SESSION_STOP" 2>/dev/null || true
plan clear-mode 2>/dev/null || true

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
