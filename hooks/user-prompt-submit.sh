#!/bin/bash
# UserPromptSubmit hook: Clears session mode for non-jons-plan messages
# This ensures that normal conversation doesn't trigger auto-resume behavior

# Helper to run plan CLI from plugin location
plan() {
    uv run ~/.claude-plugins/jons-plan/plan.py "$@"
}

# Read hook input from stdin (JSON with user's message)
INPUT=$(cat)

# Extract the user's message from the JSON input
# The input format is: {"session_id": "...", "message": "..."}
MESSAGE=$(echo "$INPUT" | grep -o '"message"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"message"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//' || echo "")

# Check if message starts with /jons-plan:
if [[ "$MESSAGE" == /jons-plan:* ]]; then
    # This is a jons-plan command - don't clear the mode
    # The slash command itself will set the appropriate mode
    exit 0
fi

# Not a jons-plan command - clear the session mode
plan clear-mode 2>/dev/null || true

exit 0
