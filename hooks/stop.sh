#!/bin/bash
# Stop hook: Auto-continue in proceed mode, otherwise provide session summary
# Blocks stop if in proceed mode with available tasks

set -e

# Determine plugin root: use CLAUDE_PLUGIN_ROOT if set, otherwise detect from script location
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
    PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"
else
    PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# Helper to run plan CLI from plugin location
plan() {
    uv run "${PLUGIN_ROOT}/plan.py" "$@"
}

# Read hook input from stdin
INPUT=$(cat)

# Note: We intentionally don't check stop_hook_active here.
# Our termination condition is "no available tasks", which naturally
# prevents infinite loops. We want Claude to keep working until done.

# Find project root - use git root like plan.py does for consistency
# This ensures session-mode file path matches between set-mode and this hook
PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

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

# Helper: Read auto_iteration_counter from state.json (default 0)
get_iteration_counter() {
    local state_file="${ACTIVE_PLAN_DIR}/state.json"
    if [[ -f "$state_file" ]]; then
        jq -r '.auto_iteration_counter // 0' < "$state_file" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

# Helper: Read max_auto_iterations from state.json (default 50)
get_max_iterations() {
    local state_file="${ACTIVE_PLAN_DIR}/state.json"
    if [[ -f "$state_file" ]]; then
        jq -r '.max_auto_iterations // 50' < "$state_file" 2>/dev/null || echo 50
    else
        echo 50
    fi
}

# Helper: Increment auto_iteration_counter in state.json
increment_iteration_counter() {
    local state_file="${ACTIVE_PLAN_DIR}/state.json"
    if [[ -f "$state_file" ]]; then
        local tmp_file=$(mktemp)
        jq '.auto_iteration_counter = ((.auto_iteration_counter // 0) + 1)' < "$state_file" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$state_file"
    fi
}

# Auto-continue logic: Block stop if in proceed mode with work remaining
# Also handle awaiting-feedback mode for workflow phases requiring user input
if [[ "$SESSION_MODE" == "proceed" ]]; then
    # Check for blocked tasks first - need human intervention
    if plan has-blockers 2>/dev/null; then
        # Don't auto-continue if there are blocked tasks
        :
    else
        # Get current phase info - write to temp file to avoid bash variable corruption
        # (bash command substitution corrupts multi-line JSON with certain characters)
        PHASE_JSON_FILE=$(mktemp)
        trap "rm -f '$PHASE_JSON_FILE'" EXIT
        plan phase-context --json > "$PHASE_JSON_FILE" 2>/dev/null || echo "{}" > "$PHASE_JSON_FILE"

        # Check if current phase is terminal - allow stop at terminal phases
        IS_TERMINAL=$(jq -r '.terminal // false' < "$PHASE_JSON_FILE" 2>/dev/null)
        if [[ "$IS_TERMINAL" == "true" ]]; then
            # At terminal phase - check if tasks are complete before transitioning mode
            PHASE_TASKS=$(plan phase-next-tasks 2>/dev/null || echo "")
            if [[ -z "$PHASE_TASKS" || "$PHASE_TASKS" == "All phase tasks complete" || "$PHASE_TASKS" == "No tasks in current phase" ]]; then
                # Workflow complete - transition to awaiting-feedback for next session
                plan set-mode awaiting-feedback 2>/dev/null || true
            fi
            # Allow stop
            :
        else
            # Check if phase requires user input
            REQUIRES_USER=$(jq -r '.requires_user_input // false' < "$PHASE_JSON_FILE" 2>/dev/null)
            if [[ "$REQUIRES_USER" == "true" ]]; then
                # Phase needs user input - allow stop (user will review and proceed)
                :
            else
                # Check for phase tasks
                PHASE_TASKS=$(plan phase-next-tasks 2>/dev/null || echo "")
                if [[ -n "$PHASE_TASKS" && "$PHASE_TASKS" != "No tasks in current phase" && "$PHASE_TASKS" != "All phase tasks complete" ]]; then
                    # Check safety limit before blocking
                    COUNTER=$(get_iteration_counter)
                    MAX_ITER=$(get_max_iterations)
                    if [[ "$COUNTER" -ge "$MAX_ITER" ]]; then
                        # Safety limit reached - allow stop
                        plan log "AUTO_ITERATION_LIMIT: counter=$COUNTER >= max=$MAX_ITER, allowing stop" 2>/dev/null || true
                    else
                        increment_iteration_counter
                        TASK_COUNT=$(echo "$PHASE_TASKS" | wc -l | tr -d ' ')
                        echo '{"decision": "block", "reason": "Phase has '"$TASK_COUNT"' available tasks. Continue working on the next task. Run: uv run ${PLUGIN_ROOT}/plan.py phase-next-tasks"}'
                        exit 2
                    fi
                fi

                # Check if there are suggested next phases (workflow not complete)
                SUGGESTED_NEXT_COUNT=$(jq -r '.suggested_next | length' < "$PHASE_JSON_FILE" 2>/dev/null || echo "0")
                if [[ "$SUGGESTED_NEXT_COUNT" -gt 0 ]]; then
                    # Check safety limit before blocking
                    COUNTER=$(get_iteration_counter)
                    MAX_ITER=$(get_max_iterations)
                    if [[ "$COUNTER" -ge "$MAX_ITER" ]]; then
                        # Safety limit reached - allow stop
                        plan log "AUTO_ITERATION_LIMIT: counter=$COUNTER >= max=$MAX_ITER, allowing stop" 2>/dev/null || true
                    else
                        increment_iteration_counter
                        # Get suggested phases for the message
                        SUGGESTED_PHASES=$(plan suggested-next 2>/dev/null | head -3 | tr '\n' ', ' | sed 's/,$//')
                        echo '{"decision": "block", "reason": "TRANSITION REQUIRED: Phase complete but workflow continues. You MUST transition to the next phase before stopping.\n\nAvailable transitions: '"${SUGGESTED_PHASES}"'\n\nRun these commands:\n  1. uv run ~/.claude-plugins/jons-plan/plan.py suggested-next\n  2. uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <phase-id>\n\nIf scope exceeded, see proceed.md Scope Exceeded Handling section.\n\nDO NOT manually edit state.json or invent statuses."}'
                        exit 2
                    fi
                fi
            fi
        fi
    fi
elif [[ "$SESSION_MODE" == "awaiting-feedback" ]]; then
    # In awaiting-feedback mode - user review required, allow stop
    :
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
