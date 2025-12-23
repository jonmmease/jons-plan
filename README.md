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
| `/jons-plan:new [topic]` | Create new implementation plan (explores codebase, creates tasks) |
| `/jons-plan:new-design [topic]` | Create new design plan (research, exploration, produces `design.md`) |
| `/jons-plan:new-deep [topic]` | Create implementation plan with deep automated exploration and review |
| `/jons-plan:new-tech-docs [topic]` | Create technical documentation plan (multi-source research, produces markdown docs) |
| `/jons-plan:new-review` | Create multi-agent code review plan for current branch |
| `/jons-plan:plan [feedback]` | Refine the active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to a different plan |
| `/jons-plan:status` | Show all plans and task progress |

## Plan Types

The plugin supports four plan creation commands:

| Aspect | `/new` | `/new-design` | `/new-deep` | `/new-tech-docs` |
|--------|--------|---------------|-------------|------------------|
| **Purpose** | Build features, fix bugs | Research, explore, design | Complex implementation with thorough research | Generate technical documentation |
| **Naming** | `[topic]` | `[topic]-design` (enforced) | `[topic]` | `[topic]-docs` (enforced) |
| **Deliverable** | Code changes | `design.md` document | Code changes | `[topic].md` documentation |
| **Exploration** | Light exploration | Creates tasks for later | Auto-executes exploration | Multi-source research (code, web, GitHub, MCPs) |
| **External review** | No | Creates review task | Auto-executes review | Link validation + slop detection + gemini/codex reviews |
| **Synthesis** | Single-shot | Task in plan | Multi-round with feedback | Draft → review → final with feedback synthesis |
| **User intervention** | After planning | After each /proceed | After all phases complete | After planning |

**When to use each:**
- **`/new`** — Simple features, bug fixes, clear requirements
- **`/new-design`** — Research projects, design decisions, when you need `design.md`
- **`/new-deep`** — Complex features requiring thorough exploration and external review before implementation
- **`/new-tech-docs`** — Generating technical documentation about a codebase topic (current state, example-based, version-anchored)

**Two-phase workflow (for design plans):**
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

The plugin uses five hooks to manage session lifecycle:

### SessionStart Hook

Runs at the beginning of each Claude Code session:
- Shows the active plan and working directory
- Displays recent git commits and uncommitted changes
- Shows recent progress log entries
- Lists in-progress and available tasks with their task-level progress
- Prompts for auto-resume if tasks were interrupted

### PreCompact Hook

Runs before context compaction:
- Injects jons-plan state into the compaction summary
- Includes session mode, active plan, and in-progress tasks
- Shows recent task-level progress entries
- Provides pointers to progress files for post-compaction resumption

### UserPromptSubmit Hook

Runs when user submits a message:
- Clears session mode for non-jons-plan commands
- Ensures fresh sessions show neutral state

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

### Overview Commands

| Command | Description |
|---------|-------------|
| `status` | Comprehensive overview - all plans, active plan stats, in-progress tasks, next available |
| `list-plans` | List all plans (marks active) |
| `active-plan` | Print active plan name |
| `active-plan-dir` | Print active plan directory path |

### Plan Management

| Command | Description |
|---------|-------------|
| `set-active <plan>` | Switch active plan |
| `deactivate` | Deactivate current plan without switching to another |

### Task Management

| Command | Description |
|---------|-------------|
| `task-stats` | Print task counts (done/total, in-progress, todo) |
| `in-progress` | List tasks currently in progress |
| `blocked-tasks` | List blocked tasks |
| `has-blockers` | Check if plan has blocked tasks (exit 0 if yes) |
| `next-tasks` | List available tasks (todo with all parents done) |
| `set-status <task-id> <status>` | Set task status |

### Progress Logging

| Command | Description |
|---------|-------------|
| `log <message>` | Append message to plan-level progress log |
| `recent-progress [-n N]` | Show recent plan-level progress entries (default: 10) |

### Task-Level Progress

| Command | Description |
|---------|-------------|
| `task-log <task-id> <message>` | Append message to task's progress.txt |
| `task-progress <task-id> [-n N]` | Show recent entries from task's progress.txt (default: 10) |
| `build-task-prompt <task-id>` | Build complete prompt with all context (description, steps, parent outputs, prior progress) |

### Task Outputs

| Command | Description |
|---------|-------------|
| `task-dir <task-id>` | Print task output directory path |
| `ensure-task-dir <task-id>` | Create task directory if needed |
| `parent-dirs <task-id>` | List parent task directories that exist |
| `has-outputs <task-id>` | Check if task has outputs (exit code 0/1) |

### Confidence Scoring

| Command | Description |
|---------|-------------|
| `record-confidence <task-id> <score> <rationale>` | Record confidence score (1-5) |
| `check-confidence <task-id>` | Check recorded confidence score for a task |
| `low-confidence-tasks` | List tasks with confidence score < 4 |

### Dynamic Task Modification

| Command | Description |
|---------|-------------|
| `add-task <json-file>` | Add task from JSON file or stdin |
| `update-task-parents <task-id> <parent-ids...>` | Update task parent dependencies |
| `update-task-steps <task-id> <json-file>` | Update task steps from JSON

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
