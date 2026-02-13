#!/bin/bash
# SessionStart hook: Implements the Coding Agent startup routine
# Loads plan context and orients Claude at the start of each session

set -e

# Determine plugin root: use CLAUDE_PLUGIN_ROOT if set, otherwise detect from script location
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
    PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"
else
    PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# Debug logging - writes to file while still outputting to stdout
DEBUG_LOG="/tmp/jons-plan-hook-debug.log"
echo "=== SessionStart hook started at $(date) ===" >> "$DEBUG_LOG"
echo "PWD: $(pwd)" >> "$DEBUG_LOG"
echo "PLUGIN_ROOT: ${PLUGIN_ROOT}" >> "$DEBUG_LOG"

# Helper to run plan CLI from plugin location
plan() {
    uv run "${PLUGIN_ROOT}/plan.py" "$@"
}

# Read hook input from stdin
INPUT=$(cat)

# Find project root (where .claude/ lives)
PROJECT_DIR="$(pwd)"
while [[ "$PROJECT_DIR" != "/" ]]; do
    if [[ -d "${PROJECT_DIR}/.claude" ]]; then
        break
    fi
    PROJECT_DIR="$(dirname "$PROJECT_DIR")"
done
echo "PROJECT_DIR: ${PROJECT_DIR}" >> "$DEBUG_LOG"

PLANS_DIR="${PROJECT_DIR}/.claude/jons-plan/plans"

# Get active plan
ACTIVE_PLAN=$(plan active-plan 2>/dev/null || echo "")
echo "ACTIVE_PLAN: '${ACTIVE_PLAN}'" >> "$DEBUG_LOG"

# Count existing plans
PLAN_COUNT=0
if [[ -d "$PLANS_DIR" ]]; then
    PLAN_COUNT=$(find "$PLANS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
fi
echo "PLANS_DIR: ${PLANS_DIR}" >> "$DEBUG_LOG"
echo "PLAN_COUNT: ${PLAN_COUNT}" >> "$DEBUG_LOG"

# Auto-select logic when no active plan
if [[ -z "$ACTIVE_PLAN" ]]; then
    if [[ "$PLAN_COUNT" -eq 0 ]]; then
        # No plans exist - instruct to create default
        echo "Taking no-plans branch" >> "$DEBUG_LOG"
        OUTPUT="## Session Start: No Plans

No plans exist yet. Create one with:

\`\`\`
/jons-plan:new [topic]
\`\`\`

Example: \`/jons-plan:new add user authentication\`"
        echo "OUTPUT: ${OUTPUT}" >> "$DEBUG_LOG"
        echo "$OUTPUT"
        echo "=== Hook exiting (no plans) ===" >> "$DEBUG_LOG"
        exit 0
    elif [[ "$PLAN_COUNT" -eq 1 ]]; then
        # Single plan - auto-select it
        ACTIVE_PLAN=$(basename "$(find "$PLANS_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)")
        mkdir -p "${PROJECT_DIR}/.claude/jons-plan"
        echo "$ACTIVE_PLAN" > "${PROJECT_DIR}/.claude/jons-plan/active-plan"
        echo "_Auto-selected single plan: ${ACTIVE_PLAN}_"
        echo ""
    else
        # Multiple plans - list them
        echo "## Session Start: Multiple Plans"
        echo ""
        echo "**Available plans:**"
        plan list-plans | while read p; do
            echo "- \`${p}\`"
        done
        echo ""

        # Show recent reflog entries so agent can suggest reactivating a recent plan
        REFLOG=$(plan reflog --limit 5 2>/dev/null || echo "")
        if [[ -n "$REFLOG" ]]; then
            echo "**Recently active plans:**"
            echo "\`\`\`"
            echo "$REFLOG"
            echo "\`\`\`"
            echo ""
        fi

        echo "Use \`/jons-plan:switch [name]\` to select a plan, or \`/jons-plan:new [topic]\` to create a new one."
        exit 0
    fi
fi

ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")

if [[ -n "$ACTIVE_PLAN_DIR" && -d "$ACTIVE_PLAN_DIR" ]]; then
    # Active plan exists - full startup routine
    echo "## Session Start: Plan Active"
    echo ""
    echo "**Active Plan:** \`${ACTIVE_PLAN}\`"
    echo "**Path:** \`${ACTIVE_PLAN_DIR}\`"
    echo "**Working Directory:** \`$(pwd)\`"
    echo ""

    # Check for blocked tasks first - most important status
    BLOCKED_TASKS=$(plan blocked-tasks 2>/dev/null || echo "")
    HAS_BLOCKERS=false
    if [[ -n "$BLOCKED_TASKS" ]]; then
        HAS_BLOCKERS=true
        echo "### ⚠️ BLOCKED TASKS"
        echo ""
        echo "The following tasks are blocked and require attention:"
        echo ""
        echo "$BLOCKED_TASKS" | while IFS=':' read -r task_id task_desc; do
            task_id=$(echo "$task_id" | tr -d ' ')
            if [[ -n "$task_id" ]]; then
                # Read first line of blocker reason
                TASK_DIR=$(plan task-dir "$task_id" 2>/dev/null || echo "")
                BLOCKER_FILE="${TASK_DIR}/blockers.md"
                if [[ -n "$TASK_DIR" && -f "$BLOCKER_FILE" ]]; then
                    REASON=$(grep -A1 "## Why It Failed" "$BLOCKER_FILE" 2>/dev/null | tail -1 | head -c 80)
                    echo "- \`${task_id}\`:${task_desc}"
                    if [[ -n "$REASON" && "$REASON" != "## Why It Failed" ]]; then
                        echo "  _${REASON}..._"
                    fi
                else
                    echo "- \`${task_id}\`:${task_desc}"
                fi
            fi
        done
        echo ""
        echo "**Action Required:** Run \`/jons-plan:plan\` to review blockers and update the plan."
        echo ""
    fi

    # Git status
    if git rev-parse --git-dir > /dev/null 2>&1; then
        echo "### Git Status"
        echo "\`\`\`"
        git log --oneline -5 2>/dev/null || echo "No commits yet"
        echo "\`\`\`"
        DIRTY_FILES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$DIRTY_FILES" -gt 0 ]]; then
            echo "_${DIRTY_FILES} uncommitted changes_"
        fi
        echo ""
    fi

    # Recent progress
    echo "### Recent Progress"
    RECENT=$(plan recent-progress --lines 5 2>/dev/null || echo "")
    if [[ -n "$RECENT" ]]; then
        echo "\`\`\`"
        echo "$RECENT"
        echo "\`\`\`"
    else
        echo "_No progress logged yet_"
    fi
    echo ""

    # Plan status overview
    plan status 2>/dev/null || echo "_Could not load status_"
    echo ""

    # Check for reference materials (files other than the standard ones)
    REFERENCE_FILES=$(find "$ACTIVE_PLAN_DIR" -type f \
        ! -name "request.md" \
        ! -name "workflow.toml" \
        ! -name "state.json" \
        ! -name "tasks.json" \
        ! -name "claude-progress.txt" \
        ! -name "dead-ends.json" \
        2>/dev/null)
    if [[ -n "$REFERENCE_FILES" ]]; then
        echo "### Reference Materials"
        echo "Read these files for additional context:"
        echo "$REFERENCE_FILES" | while read file; do
            REL_PATH="${file#$PROJECT_DIR/}"
            echo "- \`${REL_PATH}\`"
        done
        echo ""
    fi

    # CLI help
    plan help 2>/dev/null || true
    echo ""

    # Check session mode to determine if we should auto-resume
    SESSION_MODE=$(plan get-mode 2>/dev/null || echo "")
    echo "SESSION_MODE: '${SESSION_MODE}'" >> "$DEBUG_LOG"

    # Check for tasks that need resuming
    IN_PROGRESS=$(plan in-progress 2>/dev/null || echo "")
    NEXT_TASKS=$(plan next-tasks 2>/dev/null || echo "")

    # Show task-level progress for in-progress tasks
    if [[ -n "$IN_PROGRESS" ]]; then
        echo "### In-Progress Task Details"
        echo ""
        echo "$IN_PROGRESS" | while IFS=':' read -r task_id task_desc; do
            task_id=$(echo "$task_id" | tr -d ' ')
            if [[ -n "$task_id" ]]; then
                echo "**Task:** \`${task_id}\`"
                TASK_PROGRESS=$(plan task-progress "$task_id" --lines 5 2>/dev/null || echo "")
                if [[ -n "$TASK_PROGRESS" ]]; then
                    echo "\`\`\`"
                    echo "$TASK_PROGRESS"
                    echo "\`\`\`"
                    TASK_DIR=$(plan task-dir "$task_id" 2>/dev/null || echo "")
                    if [[ -n "$TASK_DIR" ]]; then
                        echo "_Continue logging to: \`${TASK_DIR}/progress.txt\`_"
                    fi
                else
                    echo "_No progress logged yet_"
                fi
                echo ""
            fi
        done
    fi

    # Phase context
    echo "### Workflow Phase Context"
    echo ""
    plan phase-summary 2>/dev/null || echo "_No current phase_"
    echo ""

    # Show input artifacts if any
    INPUT_ARTIFACTS=$(plan input-artifacts --json 2>/dev/null || echo "")
    if [[ -n "$INPUT_ARTIFACTS" && "$INPUT_ARTIFACTS" != "{}" ]]; then
        # Check if there are any found artifacts using jq
        FOUND_COUNT=$(echo "$INPUT_ARTIFACTS" | jq -r '.found | length' 2>/dev/null || echo "0")
        if [[ "$FOUND_COUNT" -gt 0 ]]; then
            echo "**Input Artifacts:** Available from upstream phases"
            echo ""
        fi
    fi

    # Show recent dead-ends (last 3)
    DEAD_ENDS=$(plan get-dead-ends --recent 3 2>/dev/null || echo "")
    if [[ -n "$DEAD_ENDS" ]]; then
        echo "### Recent Dead Ends"
        echo ""
        echo "These approaches have been tried and failed:"
        echo ""
        echo "$DEAD_ENDS"
        echo ""
    fi

    # Only auto-resume if we're in "proceed" mode AND no blocked tasks
    # Other modes (new, plan) are read-only planning modes
    if [[ "$SESSION_MODE" == "proceed" ]]; then
        if [[ "$HAS_BLOCKERS" == "true" ]]; then
            # Blocked tasks exist - do NOT auto-resume, require replanning
            echo "---"
            echo "### Cannot Auto-Resume: Blocked Tasks"
            echo ""
            echo "Implementation cannot continue due to blocked tasks."
            echo "**Run \`/jons-plan:plan\` to address the blockers before proceeding.**"
        else
            # In proceed mode - continue implementing
            echo "---"
            echo "### Session Mode: Implementing Tasks (Resuming)"
            echo ""
            echo "**You were in the middle of implementing tasks and should continue.**"
            echo ""

            if [[ -n "$IN_PROGRESS" ]]; then
                echo "**Status:** Tasks were in-progress when the previous session ended."
            elif [[ -n "$NEXT_TASKS" ]]; then
                echo "**Status:** Tasks are available to continue."
            elif ! plan check-tasks-required 2>/dev/null; then
                CURRENT_PHASE=$(plan current-phase 2>/dev/null || echo "")
                echo "**Status:** Phase \`${CURRENT_PHASE}\` requires tasks but none exist yet."
            fi
            echo ""

            # Show plan progress log for context
            PROGRESS_FILE="${ACTIVE_PLAN_DIR}/claude-progress.txt"
            if [[ -f "$PROGRESS_FILE" ]]; then
                echo "### Plan Progress"
                echo "\`\`\`"
                tail -10 "$PROGRESS_FILE"
                echo "\`\`\`"
                echo ""
            fi

            # Inject full phase context (request, phase prompt, artifacts, re-entry context, etc.)
            echo "### Current Phase Context"
            echo ""
            echo "_This context was automatically injected - you do not need to call phase-context._"
            echo ""
            plan phase-context 2>/dev/null || echo "_Could not load phase context_"
            echo ""

            # Inject the full /jons-plan:proceed instructions
            echo "### Continue with /jons-plan:proceed Instructions"
            echo ""
            PROCEED_CMD_FILE="${PLUGIN_ROOT}/commands/proceed.md"
            if [[ -f "$PROCEED_CMD_FILE" ]]; then
                # Skip the frontmatter (--- ... ---)
                tail -n +5 "$PROCEED_CMD_FILE"
            else
                echo "_Could not load proceed.md instructions_"
            fi
        fi
    elif [[ "$SESSION_MODE" == "new" ]]; then
        # In new mode - continue creating the plan
        echo "---"
        echo "### Session Mode: Creating Plan (Resuming)"
        echo ""
        echo "**You were in the middle of creating a new plan and should continue.**"
        echo "**Do NOT execute tasks or modify code outside the plan directory.**"
        echo ""

        # MOST IMPORTANT: Show the user's original request/topic
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
        # In plan mode - continue refining
        echo "---"
        echo "### Session Mode: Refining Plan (Resuming)"
        echo ""
        echo "**You were in the middle of refining the plan and should continue.**"
        echo "**Do NOT execute tasks or modify code outside the plan directory.**"
        echo ""

        # MOST IMPORTANT: Show the user's feedback/guidance
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
    elif [[ "$SESSION_MODE" == "awaiting-feedback" ]]; then
        # Check if at completed terminal phase (workflow finished)
        PHASE_JSON_FILE=$(mktemp)
        trap "rm -f '$PHASE_JSON_FILE'" EXIT
        plan phase-context --json > "$PHASE_JSON_FILE" 2>/dev/null || echo "{}" > "$PHASE_JSON_FILE"
        IS_TERMINAL=$(jq -r '.terminal // false' < "$PHASE_JSON_FILE" 2>/dev/null)

        if [[ "$IS_TERMINAL" == "true" ]]; then
            # Workflow complete - show completion guidance
            echo "---"
            echo "### Workflow Complete"
            echo ""
            echo "The previous workflow has finished at its terminal phase."
            echo ""
            echo "**Options:**"
            echo "- Start a new plan: \`/jons-plan:new [topic]\`"
            echo "- Extend workflow: \`/jons-plan:plan [describe new phases]\`"
            echo "- Review this plan: \`/jons-plan:status\`"
            echo "- Switch to another plan: \`/jons-plan:switch [name]\`"

            # Check for loopback transitions (some terminal phases allow going back)
            SUGGESTED_NEXT=$(plan suggested-next 2>/dev/null || echo "")
            if [[ -n "$SUGGESTED_NEXT" ]]; then
                echo ""
                echo "**Available loopbacks:** This terminal phase has optional transitions back to earlier phases."
                echo "Run \`/jons-plan:proceed\` to see options."
            fi
        else
            # Not at terminal - waiting for user to proceed or refine
            echo "---"
            echo "### Awaiting User Decision"
            echo ""
            echo "Planning is complete. Choose next action:"
            echo "- \`/jons-plan:proceed\` to start implementation"
            echo "- \`/jons-plan:plan [feedback]\` to refine further"
        fi
    else
        # No mode set - show neutral commands
        echo "---"
        echo "**Commands:** \`/jons-plan:plan [feedback]\` to refine | \`/jons-plan:status\` to see all | \`/jons-plan:proceed\` to implement"
    fi

    # Log session start
    plan log "SESSION_START" 2>/dev/null || true

else
    # Active plan set but directory missing - reset and retry
    echo "## Session Start: Plan Not Found"
    echo ""
    echo "Active plan \`${ACTIVE_PLAN}\` not found. Clearing..."
    rm -f "${PROJECT_DIR}/.claude/jons-plan/active-plan"
    echo ""
    echo "Use \`/jons-plan:new [topic]\` to create a new plan."
fi

echo "=== Hook exiting normally ===" >> "$DEBUG_LOG"
exit 0
