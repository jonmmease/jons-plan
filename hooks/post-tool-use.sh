#!/bin/bash
# PostToolUse hook: Log file modifications to progress
# Runs after Write/Edit operations to create an audit trail

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

# Extract tool info from JSON input
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)

# Get active plan directory
ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")

# Skip if no active plan
if [[ -z "$ACTIVE_PLAN_DIR" ]]; then
    exit 0
fi

# Skip if file is in .claude/jons-plan/plans/ (avoid recursive logging)
if [[ "$FILE_PATH" == *".claude/jons-plan/plans/"* ]]; then
    exit 0
fi

# Skip if file is in .claude/ directory (don't log hook/config changes)
if [[ "$FILE_PATH" == *".claude/"* ]]; then
    exit 0
fi

# Log the file modification
if [[ -n "$FILE_PATH" ]]; then
    # Make path relative to project for cleaner logging
    REL_PATH="${FILE_PATH#$PROJECT_DIR/}"
    plan log "FILE_MODIFIED [${TOOL_NAME}] ${REL_PATH}" 2>/dev/null || true
fi

exit 0
