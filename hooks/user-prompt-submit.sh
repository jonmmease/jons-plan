#!/bin/bash
# UserPromptSubmit hook: Sets session mode for jons-plan commands
# - Auto-sets mode when /jons-plan:* commands are detected
# - Preserves planning modes (new, new-design, new-deep, plan) on regular messages
# - Clears proceed mode on regular messages (require explicit opt-in for auto-resume)

# Helper to run plan CLI from plugin location
plan() {
    uv run ~/.claude-plugins/jons-plan/plan.py "$@"
}

# Read hook input from stdin (JSON with user's message)
INPUT=$(cat)

# Extract the user's message from the JSON input
# The input format is: {"session_id": "...", "prompt": "..."}
MESSAGE=$(echo "$INPUT" | grep -o '"prompt"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"prompt"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//' || echo "")

# Check for /jons-plan:* commands and set appropriate mode
# Order matters: check new-deep and new-design before new
if [[ "$MESSAGE" == "/jons-plan:plan"* ]]; then
    plan set-mode plan 2>/dev/null || true
elif [[ "$MESSAGE" == "/jons-plan:proceed"* ]]; then
    plan set-mode proceed 2>/dev/null || true
elif [[ "$MESSAGE" == "/jons-plan:new-deep"* ]]; then
    plan set-mode new-deep 2>/dev/null || true
elif [[ "$MESSAGE" == "/jons-plan:new-design"* ]]; then
    plan set-mode new-design 2>/dev/null || true
elif [[ "$MESSAGE" == "/jons-plan:new"* ]]; then
    plan set-mode new 2>/dev/null || true
elif [[ "$MESSAGE" == "/jons-plan:deactivate"* ]]; then
    # Deactivate is deterministic - run directly from hook
    plan clear-mode 2>/dev/null || true
    plan deactivate
elif [[ "$MESSAGE" == "/jons-plan:switch"* ]] || [[ "$MESSAGE" == "/jons-plan:status"* ]]; then
    # Informational commands - don't change mode
    :
else
    # Regular message - check current mode
    CURRENT_MODE=$(plan get-mode 2>/dev/null || echo "")

    if [[ "$CURRENT_MODE" == "proceed" ]]; then
        # Clear proceed mode - require explicit /jons-plan:proceed for auto-resume
        plan clear-mode 2>/dev/null || true
    fi
    # Planning modes (new, new-design, new-deep, plan) are preserved
    # No mode set - no action needed
fi

exit 0
