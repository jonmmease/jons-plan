#!/bin/bash
# SessionStart hook: Implements the Coding Agent startup routine
# Loads plan context and orients Claude at the start of each session

set -e

# Helper to run plan CLI from plugin location
plan() {
    uv run ~/.claude-plugins/jons-plan/plan.py "$@"
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

PLANS_DIR="${PROJECT_DIR}/.claude/jons-plan/plans"

# Get active plan
ACTIVE_PLAN=$(plan active-plan 2>/dev/null || echo "")

# Count existing plans
PLAN_COUNT=0
if [[ -d "$PLANS_DIR" ]]; then
    PLAN_COUNT=$(find "$PLANS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
fi

# Auto-select logic when no active plan
if [[ -z "$ACTIVE_PLAN" ]]; then
    if [[ "$PLAN_COUNT" -eq 0 ]]; then
        # No plans exist - instruct to create default
        echo "## Session Start: No Plans"
        echo ""
        echo "No plans exist yet. Create the \`default\` plan to get started:"
        echo ""
        echo "1. Write \`default\` to \`.claude/jons-plan/active-plan\`"
        echo "2. Ensure \`.claude/jons-plan/plans/\` and \`.claude/jons-plan/active-plan\` are in \`.gitignore\`"
        echo "3. Enter plan mode (shift+tab) to create the plan structure"
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
        echo "Enter plan mode (shift+tab) to select a plan."
        exit 0
    fi
fi

ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")

if [[ -n "$ACTIVE_PLAN_DIR" && -d "$ACTIVE_PLAN_DIR" ]]; then
    # Active plan exists - full startup routine
    echo "## Session Start: Plan Active"
    echo ""
    echo "**Active Plan:** \`${ACTIVE_PLAN}\`"
    echo "**Working Directory:** \`$(pwd)\`"
    echo ""

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
        ! -name "plan.md" \
        ! -name "tasks.json" \
        ! -name "claude-progress.txt" \
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

    # Plan mode instruction
    echo "---"
    echo "**Plan Mode:** Edit plans in place at \`.claude/jons-plan/plans/${ACTIVE_PLAN}/plan.md\`"

    # Log session start
    plan log "SESSION_START" 2>/dev/null || true

else
    # Active plan set but directory missing - reset and retry
    echo "## Session Start: Plan Not Found"
    echo ""
    echo "Active plan \`${ACTIVE_PLAN}\` not found. Clearing..."
    rm -f "${PROJECT_DIR}/.claude/jons-plan/active-plan"
    echo ""
    echo "Enter plan mode (shift+tab) to select or create a plan."
fi

exit 0
