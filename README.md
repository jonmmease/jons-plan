# jons-plan Plugin

A Claude Code plugin inspired by Anthropic's [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) blog post for managing complex, multi-session coding tasks.

## Overview

When AI agents work on complex projects that span multiple context windows, each new session starts with no memory of what came before. This plugin solves that problem by providing:

- **Structured task management** with dependencies and status tracking
- **Progress logging** to orient Claude at the start of each session
- **Task-level progress** for fine-grained resumption context
- **Automatic session resumption** when tasks were interrupted
- **PreCompact hook** to preserve state during context compaction
- **Parallel task execution** via subagents for independent work
- **Workflow-based execution** with phase transitions and state machine

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## How It Works

The plugin uses a two-agent architecture:

### Planning Agent (`/jons-plan:new`)

Creates the infrastructure for a new plan:
- Analyzes your request and suggests an appropriate workflow
- Sets up the plan structure and initial phase
- Creates `request.md` with the refined/approved request

### Coding Agent (`/jons-plan:proceed`)

Works incrementally on tasks across sessions:
- Reads progress log to understand current state
- Resumes any `in-progress` tasks first
- Handles phase transitions automatically
- Updates task status and logs progress for the next session

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create new plan (auto-suggests workflow type) |
| `/jons-plan:plan [feedback]` | Refine the active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to a different plan |
| `/jons-plan:status` | Show all plans and task progress |

Use `--workflow <name>` with `/new` to specify workflow type explicitly.

## Workflow Types

| Workflow | Purpose |
|----------|---------|
| `implementation` | Build features, fix bugs with research and validation |
| `design` | Research, explore, produce design.md |
| `design-and-implementation` | Design first, optionally implement after approval |
| `deep-implementation` | Thorough research + external review before implementation |
| `code-review` | Review code changes + generate PR description |
| `pr-review` | Review existing PR description for quality |
| `tech-docs` | Technical documentation with multi-source research |
| `tech-docs-review` | Review RFCs, design docs, proposals with structured criteria |

**Auto-selection:** When no `--workflow` is specified, the plugin analyzes your request and suggests the most appropriate workflow.

## Plan Directory Structure

```
.claude/jons-plan/
├── active-plan              # Name of the currently active plan
├── session-mode             # Current command mode
└── plans/
    └── [plan-name]/
        ├── workflow.toml        # Phase definitions
        ├── state.json           # Current phase state
        ├── request.md           # Refined/approved request
        ├── dead-ends.json       # Failed approaches (for learning)
        ├── claude-progress.txt  # Plan-level progress log
        └── phases/
            └── NN-{phase-id}/
                ├── tasks.json   # Phase-specific tasks
                └── tasks/       # Task outputs
```

### Task Schema

```json
{
  "id": "implement-auth",
  "description": "Implement user authentication",
  "parents": ["research-auth-patterns"],
  "steps": ["Create auth middleware", "Add login endpoint"],
  "status": "todo",
  "subagent": "general-purpose",
  "model": "sonnet"
}
```

Tasks can optionally specify:
- `subagent`: Agent type (`general-purpose`, `Explore`, `Plan`, `gemini-reviewer`, `codex-reviewer`)
- `subagent_prompt`: Additional context (e.g., "very thorough analysis")
- `model`: Model to use (`sonnet`, `haiku`, `opus`)

## Hooks

The plugin uses five hooks to manage session lifecycle:

### SessionStart Hook

Runs at the beginning of each Claude Code session:
- Shows the active plan and working directory
- Displays recent git commits and uncommitted changes
- Shows workflow phase context (for workflow plans)
- Lists in-progress and available tasks
- Prompts for auto-resume if tasks were interrupted

### PreCompact Hook

Runs before context compaction:
- Injects jons-plan state into the compaction summary
- Includes session mode, active plan, and in-progress tasks
- Shows phase context for workflow plans
- Provides pointers to progress files for post-compaction resumption

### UserPromptSubmit Hook

Runs when user submits a message:
- Sets session mode based on command type
- Preserves planning modes on regular messages

### PostToolUse Hook

Runs after `Write` and `Edit` operations:
- Logs file modifications to `claude-progress.txt`
- Skips files in `.claude/` to avoid recursive logging

### Stop Hook

Runs when the session ends:
- Auto-continue behavior in proceed mode
- Shows session summary (files modified, task progress)
- Warns about uncommitted changes

## CLI Reference

The plugin includes a Python CLI for programmatic access:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py <command>
```

See `CLAUDE.md` for complete CLI reference.

## Installation

1. Clone or copy this plugin to `~/.claude-plugins/jons-plan/`
2. Add the hooks to your Claude settings (see workaround below)
3. Add `.claude/jons-plan/` to your project's `.git/info/exclude`

---

## Known Issue: Plugin Hook Output Not Passed to Agent

**Bug:** https://github.com/anthropics/claude-code/issues/12151

Plugin-based hooks execute successfully but their stdout is not passed to the agent's context. This affects all hooks defined in `hooks/hooks.json`.

### Workaround

Until the bug is fixed, hooks must be defined in `~/.claude/settings.json` instead of in the plugin's `hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/session-start.sh",
            "timeout": 10000
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/pre-compact.sh",
            "timeout": 5000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/user-prompt-submit.sh",
            "timeout": 5000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/post-tool-use.sh",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/stop.sh",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

### When Issue #12151 is Fixed

1. Remove the `hooks` section from `~/.claude/settings.json`
2. The plugin's `hooks/hooks.json` will work automatically (uses `${CLAUDE_PLUGIN_ROOT}` for portable paths)

## References

- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) - Anthropic engineering blog post
- [Claude Agent SDK Quickstart](https://github.com/anthropics/claude-agent-sdk) - Reference implementation
