#!/bin/bash
# PreCompact hook: Injects jons-plan state into compaction summary
# This ensures the agent "remembers" its jons-plan context after compaction

set -e

# Helper to run plan CLI from plugin location
plan() {
    uv run ~/.claude-plugins/jons-plan/plan.py "$@"
}

# Read hook input from stdin
INPUT=$(cat)

# Get active plan
ACTIVE_PLAN=$(plan active-plan 2>/dev/null || echo "")
if [[ -z "$ACTIVE_PLAN" ]]; then
    # No active plan - nothing to preserve
    exit 0
fi

ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")
if [[ -z "$ACTIVE_PLAN_DIR" || ! -d "$ACTIVE_PLAN_DIR" ]]; then
    exit 0
fi

# Get session mode
SESSION_MODE=$(plan get-mode 2>/dev/null || echo "")

# Get in-progress tasks
IN_PROGRESS=$(plan in-progress 2>/dev/null || echo "")

# Output structured state for compaction summary
echo "## jons-plan State (preserve this context)"
echo ""
echo "**Mode:** ${SESSION_MODE:-not set}"
echo "**Active Plan:** \`${ACTIVE_PLAN}\`"
echo ""

if [[ -n "$IN_PROGRESS" ]]; then
    echo "### Current Task(s)"
    echo ""
    echo "$IN_PROGRESS" | while IFS=':' read -r task_id task_desc; do
        task_id=$(echo "$task_id" | tr -d ' ')
        if [[ -n "$task_id" ]]; then
            echo "**Task:** \`${task_id}\`"
            echo "**Description:** ${task_desc}"

            # Show last 3 progress entries
            TASK_PROGRESS=$(plan task-progress "$task_id" --lines 3 2>/dev/null || echo "")
            if [[ -n "$TASK_PROGRESS" ]]; then
                echo "**Recent Progress:**"
                echo "\`\`\`"
                echo "$TASK_PROGRESS"
                echo "\`\`\`"
            fi
            echo ""
        fi
    done

    echo "### After Compaction"
    echo ""
    echo "Read task progress file(s) for full context:"
    echo "$IN_PROGRESS" | while IFS=':' read -r task_id task_desc; do
        task_id=$(echo "$task_id" | tr -d ' ')
        if [[ -n "$task_id" ]]; then
            echo "- \`.claude/jons-plan/plans/${ACTIVE_PLAN}/tasks/${task_id}/progress.txt\`"
        fi
    done
else
    echo "_No tasks currently in progress_"
fi

exit 0
