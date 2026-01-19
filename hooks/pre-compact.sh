#!/bin/bash
# PreCompact hook: Injects jons-plan state into compaction summary
# This ensures the agent "remembers" its jons-plan context after compaction

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

# Include workflow phase context
echo "### Workflow Phase"
echo ""
plan phase-summary 2>/dev/null || echo "_No current phase_"
echo ""

# Check if phase requires tasks but none exist
if ! plan check-tasks-required 2>/dev/null; then
    CURRENT_PHASE=$(plan current-phase 2>/dev/null || echo "")
    echo "### ⚠️ TASKS REQUIRED"
    echo ""
    echo "Phase \`${CURRENT_PHASE}\` has \`use_tasks = true\` but no tasks.json exists."
    echo ""
    echo "**Before implementing anything**, you MUST:"
    echo "1. Run \`uv run ~/.claude-plugins/jons-plan/plan.py phase-context\` to see the phase prompt"
    echo "2. Create tasks in tasks.json for this phase"
    echo "3. Execute tasks using the Task Execution Loop"
    echo ""
    echo "**Do NOT start implementing without creating tasks first.**"
    echo ""
fi

# Mode-specific context injection
if [[ "$SESSION_MODE" == "new" ]]; then
    # Creating a new plan - inject full instructions
    echo "### Session Mode: Creating Plan (Resuming after compaction)"
    echo ""
    echo "**You were in the middle of creating a new plan and should continue.**"
    echo "**Do NOT execute tasks or modify code outside the plan directory.**"
    echo ""

    # MOST IMPORTANT: Show the user's original request/topic
    # Find project root for the command-args file
    PROJECT_DIR="$(pwd)"
    while [[ "$PROJECT_DIR" != "/" ]]; do
        if [[ -d "${PROJECT_DIR}/.claude" ]]; then
            break
        fi
        PROJECT_DIR="$(dirname "$PROJECT_DIR")"
    done
    if [[ "$PROJECT_DIR" == "/" ]]; then
        PROJECT_DIR="$(pwd)"
    fi
    COMMAND_ARGS_FILE="${PROJECT_DIR}/.claude/jons-plan/command-args"
    if [[ -f "$COMMAND_ARGS_FILE" ]]; then
        STORED_ARGS=$(cat "$COMMAND_ARGS_FILE")
        if [[ -n "$STORED_ARGS" ]]; then
            echo "### User's Original Request"
            echo ""
            echo "**Topic:** $STORED_ARGS"
            echo ""
        fi
    fi

    # Show plan progress log for context
    PROGRESS_FILE="${ACTIVE_PLAN_DIR}/claude-progress.txt"
    if [[ -f "$PROGRESS_FILE" ]]; then
        echo "### Progress So Far"
        echo "\`\`\`"
        cat "$PROGRESS_FILE"
        echo "\`\`\`"
        echo ""
    fi

    # Inject the full /jons-plan:new instructions
    echo "### Continue with /jons-plan:new Instructions"
    echo ""
    NEW_CMD_FILE="${PLUGIN_ROOT}/commands/new.md"
    if [[ -f "$NEW_CMD_FILE" ]]; then
        # Skip the frontmatter (--- ... ---)
        tail -n +5 "$NEW_CMD_FILE"
    else
        echo "_Could not load new.md instructions_"
    fi

elif [[ "$SESSION_MODE" == "plan" ]]; then
    # Refining the plan - inject full instructions
    echo "### Session Mode: Refining Plan (Resuming after compaction)"
    echo ""
    echo "**You were in the middle of refining the plan and should continue.**"
    echo "**Do NOT execute tasks or modify code outside the plan directory.**"
    echo ""

    # MOST IMPORTANT: Show the user's feedback/guidance
    # Find project root for the command-args file
    PROJECT_DIR="$(pwd)"
    while [[ "$PROJECT_DIR" != "/" ]]; do
        if [[ -d "${PROJECT_DIR}/.claude" ]]; then
            break
        fi
        PROJECT_DIR="$(dirname "$PROJECT_DIR")"
    done
    if [[ "$PROJECT_DIR" == "/" ]]; then
        PROJECT_DIR="$(pwd)"
    fi
    COMMAND_ARGS_FILE="${PROJECT_DIR}/.claude/jons-plan/command-args"
    if [[ -f "$COMMAND_ARGS_FILE" ]]; then
        STORED_ARGS=$(cat "$COMMAND_ARGS_FILE")
        if [[ -n "$STORED_ARGS" ]]; then
            echo "### User's Feedback"
            echo ""
            echo "**Guidance:** $STORED_ARGS"
            echo ""
        fi
    fi

    # Show plan progress log for context
    PROGRESS_FILE="${ACTIVE_PLAN_DIR}/claude-progress.txt"
    if [[ -f "$PROGRESS_FILE" ]]; then
        echo "### Progress So Far"
        echo "\`\`\`"
        tail -20 "$PROGRESS_FILE"
        echo "\`\`\`"
        echo ""
    fi

    # Inject the full /jons-plan:plan instructions
    echo "### Continue with /jons-plan:plan Instructions"
    echo ""
    PLAN_CMD_FILE="${PLUGIN_ROOT}/commands/plan.md"
    if [[ -f "$PLAN_CMD_FILE" ]]; then
        # Skip the frontmatter (--- ... ---)
        tail -n +5 "$PLAN_CMD_FILE"
    else
        echo "_Could not load plan.md instructions_"
    fi

elif [[ "$SESSION_MODE" == "proceed" ]]; then
    # In proceed mode - show task context
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
    fi

    echo "### After Compaction"
    echo ""
    echo "Continue with \`/jons-plan:proceed\` to resume task execution."
else
    echo "_No specific mode set_"
fi

exit 0
