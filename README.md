# jons-plan Plugin

A Claude Code plugin inspired by Anthropic's [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) blog post for managing complex, multi-session coding tasks.

## Overview

When AI agents work on complex projects that span multiple context windows, each new session starts with no memory of what came before. This plugin solves that problem by providing:

- **Structured task management** with dependencies and status tracking
- **Progress logging** to orient Claude at the start of each session
- **Automatic session resumption** when tasks were interrupted
- **Parallel task execution** via subagents for independent work

## How It Works

The plugin uses a two-agent architecture:

### Planning Agent (`/jons-plan:new`)

Creates the infrastructure for a new implementation plan:
- Explores the codebase to understand existing patterns
- Creates a structured plan with tasks and dependencies
- All tasks start with `status: "todo"`

### Coding Agent (`/jons-plan:proceed`)

Works incrementally on tasks across sessions:
- Reads progress log to understand current state
- Resumes any `in-progress` tasks first
- Picks from available tasks (status `todo`, all parents `done`)
- Updates task status and logs progress for the next session

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create a new implementation plan |
| `/jons-plan:new-design [topic]` | Create a new design plan (research/exploration) |
| `/jons-plan:plan [feedback]` | Refine the active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to a different plan |
| `/jons-plan:status` | Show all plans and task progress |

## Two Types of Plans

### Implementation Plans (`/jons-plan:new`)

Standard plans for building features, fixing bugs, or making code changes. The tasks produce code modifications in the repository.

### Design Plans (`/jons-plan:new-design`)

Plans for research, exploration, and design work. Key differences:

- **Enforced `-design` suffix**: Plan names must end with `-design` (e.g., `auth-design`)
- **Research-focused tasks**: Codebase exploration, API research, prototyping
- **Model strategy**: Uses `haiku` for fast exploration, `opus` for synthesis
- **External review**: Emphasizes `gemini-reviewer` or `codex-reviewer` for outside perspective
- **Deliverable**: Produces `design.md` document, not code changes

**Two-phase workflow:**
1. `/jons-plan:new-design auth` → Research and explore → `design.md`
2. User reviews and approves the design
3. `/jons-plan:new auth` → Implement based on the approved design

## Plan Directory Structure

Plans are stored in `.claude/jons-plan/` within your project:

```
.claude/jons-plan/
├── active-plan              # Name of the currently active plan
└── plans/
    └── [plan-name]/
        ├── plan.md              # Implementation plan document
        ├── tasks.json           # Task list with dependencies and status
        ├── claude-progress.txt  # Log of agent actions across sessions
        └── tasks/
            └── [task-id]/       # Output directory for tasks (created on demand)
                └── output.md    # Task artifacts for downstream tasks
```

### File Descriptions

| File | Purpose |
|------|---------|
| `plan.md` | Human-readable implementation plan with design decisions and approach |
| `tasks.json` | Machine-readable task list with `id`, `description`, `parents`, `steps`, and `status` |
| `claude-progress.txt` | Timestamped log of session starts, file modifications, and task completions |
| `tasks/[id]/` | Output directory for research/planning tasks that produce artifacts needed by child tasks |

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

The plugin uses three hooks to manage session lifecycle:

### SessionStart Hook

Runs at the beginning of each Claude Code session:
- Shows the active plan and working directory
- Displays recent git commits and uncommitted changes
- Shows recent progress log entries
- Lists in-progress and available tasks
- Prompts for auto-resume if tasks were interrupted

### PostToolUse Hook

Runs after `Write` and `Edit` operations:
- Logs file modifications to `claude-progress.txt`
- Skips files in `.claude/` to avoid recursive logging
- Creates an audit trail for the next session

### Stop Hook

Runs when the session ends:
- Logs `SESSION_STOP` to progress file
- Shows session summary (files modified, task progress)
- Warns about uncommitted changes

## CLI Reference

The plugin includes a Python CLI for programmatic access:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py <command>
```

| Command | Description |
|---------|-------------|
| `status` | Comprehensive overview of all plans and tasks |
| `list-plans` | List all available plans |
| `active-plan` | Print active plan name |
| `set-active <plan>` | Switch active plan |
| `task-stats` | Print task counts (done/total) |
| `in-progress` | List in-progress tasks |
| `next-tasks` | List available tasks |
| `set-status <id> <status>` | Update task status |
| `log <message>` | Append to progress log |
| `recent-progress` | Show recent progress entries |

## Installation

1. Clone or copy this plugin to `~/.claude-plugins/jons-plan/`
2. Add the hooks to your Claude settings (see workaround below)
3. Add `.claude/jons-plan/` to your project's `.git/info/exclude`

---

## Known Issue: Plugin Hook Output Not Passed to Agent

**Bug:** https://github.com/anthropics/claude-code/issues/12151

Plugin-based hooks execute successfully but their stdout is not passed to the agent's context. This affects `SessionStart`, `PostToolUse`, and `Stop` hooks defined in `hooks/hooks.json`.

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
