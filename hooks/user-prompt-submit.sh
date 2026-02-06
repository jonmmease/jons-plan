#!/bin/bash
# UserPromptSubmit hook: Sets session mode for jons-plan commands
# - Auto-sets mode when /jons-plan:* commands are detected
# - Preserves planning modes (new, plan) on regular messages
# - Clears proceed mode on regular messages (require explicit opt-in for auto-resume)

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

# Read hook input from stdin (JSON with user's message)
INPUT=$(cat)

# Extract the user's message from the JSON input
# Try jq first (handles all JSON edge cases), fall back to grep/sed
if command -v jq &>/dev/null; then
    MESSAGE=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || echo "")
else
    # Fallback: The input format is: {"session_id": "...", "prompt": "..."}
    MESSAGE=$(echo "$INPUT" | grep -o '"prompt"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"prompt"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//' || echo "")
fi

# Skip system-injected messages (task notifications, etc.)
if [[ "$MESSAGE" == "<"* ]]; then
    exit 0
fi

# Skip if no active plan (except for /jons-plan:new which creates plans)
ACTIVE_PLAN=$(plan active-plan 2>/dev/null || echo "")
if [[ -z "$ACTIVE_PLAN" && "$MESSAGE" != "/jons-plan:new"* ]]; then
    exit 0
fi

# Find project root (where .claude/ lives or should live)
PROJECT_DIR="$(pwd)"
while [[ "$PROJECT_DIR" != "/" ]]; do
    if [[ -d "${PROJECT_DIR}/.claude" ]]; then
        break
    fi
    PROJECT_DIR="$(dirname "$PROJECT_DIR")"
done
# If no .claude found, use current directory
if [[ "$PROJECT_DIR" == "/" ]]; then
    PROJECT_DIR="$(pwd)"
fi
JONS_PLAN_DIR="${PROJECT_DIR}/.claude/jons-plan"

# Check for /jons-plan:* commands and set appropriate mode
if [[ "$MESSAGE" == "/jons-plan:plan"* ]]; then
    plan set-mode plan 2>/dev/null || true
    # Store the args (everything after "/jons-plan:plan ")
    ARGS="${MESSAGE#/jons-plan:plan}"
    ARGS="${ARGS# }"  # Trim leading space
    mkdir -p "$JONS_PLAN_DIR"
    echo "$ARGS" > "${JONS_PLAN_DIR}/command-args"
elif [[ "$MESSAGE" == "/jons-plan:proceed"* ]]; then
    plan set-mode proceed 2>/dev/null || true
    # Reset auto_iteration_counter on manual proceed
    ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")
    if [[ -n "$ACTIVE_PLAN_DIR" ]]; then
        STATE_FILE="${ACTIVE_PLAN_DIR}/state.json"
        if [[ -f "$STATE_FILE" ]] && command -v jq &>/dev/null; then
            TMP_FILE=$(mktemp)
            jq '.auto_iteration_counter = 0' < "$STATE_FILE" > "$TMP_FILE" 2>/dev/null && mv "$TMP_FILE" "$STATE_FILE"
        fi
    fi
    # Store the args (may include task count or guidance)
    ARGS="${MESSAGE#/jons-plan:proceed}"
    ARGS="${ARGS# }"
    mkdir -p "$JONS_PLAN_DIR"
    echo "$ARGS" > "${JONS_PLAN_DIR}/command-args"
elif [[ "$MESSAGE" == "/jons-plan:new"* ]]; then
    plan set-mode new 2>/dev/null || true
    # Store the args (the topic/request)
    ARGS="${MESSAGE#/jons-plan:new}"
    ARGS="${ARGS# }"  # Trim leading space
    mkdir -p "$JONS_PLAN_DIR"
    echo "$ARGS" > "${JONS_PLAN_DIR}/command-args"
elif [[ "$MESSAGE" == "/jons-plan:switch"* ]] || [[ "$MESSAGE" == "/jons-plan:status"* ]]; then
    # Informational commands - don't change mode
    :
else
    # Regular message - check current mode
    CURRENT_MODE=$(plan get-mode 2>/dev/null || echo "")

    if [[ "$CURRENT_MODE" == "proceed" ]]; then
        # Check if we're in an auto-iteration loop - preserve mode if so
        ACTIVE_PLAN_DIR=$(plan active-plan-dir 2>/dev/null || echo "")
        AUTO_COUNTER=0
        if [[ -n "$ACTIVE_PLAN_DIR" ]]; then
            STATE_FILE="${ACTIVE_PLAN_DIR}/state.json"
            if [[ -f "$STATE_FILE" ]] && command -v jq &>/dev/null; then
                AUTO_COUNTER=$(jq -r '.auto_iteration_counter // 0' < "$STATE_FILE" 2>/dev/null || echo 0)
            fi
        fi
        if [[ "$AUTO_COUNTER" -gt 0 ]]; then
            # In auto-iteration loop - preserve proceed mode
            :
        else
            # Clear proceed mode - require explicit /jons-plan:proceed for auto-resume
            plan clear-mode 2>/dev/null || true
        fi
    fi
    # Planning modes (new, plan) are preserved
    # No mode set - no action needed
fi

exit 0
