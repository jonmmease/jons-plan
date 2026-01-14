# Long-Running Agent Harness (jons-plan plugin)

Based on Anthropic's "Effective Harnesses for Long-Running Agents" pattern.

## Overview

Two agent roles:
- **Planning Agent** (`/jons-plan:new`) - Creates plan infrastructure
- **Coding Agent** (`/jons-plan:proceed`) - Executes tasks incrementally

For detailed architecture, see [docs/architecture.md](docs/architecture.md).

## Commands

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create new plan (auto-suggests workflow type) |
| `/jons-plan:plan [feedback]` | Refine active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to different plan |
| `/jons-plan:status` | Show all plans and task progress |

Use `--workflow <name>` with `/new` to specify workflow type explicitly.

## Workflow Types

| Workflow | Purpose |
|----------|---------|
| `implementation` | Build features, fix bugs |
| `design` | Research, explore, produce design.md |
| `design-and-implementation` | Design first, optionally implement |
| `deep-implementation` | Thorough research + external review |
| `code-review` | Review code changes + generate PR description |
| `pr-review` | Review existing PR description |
| `tech-docs` | Technical documentation |
| `tech-docs-review` | Review RFCs, design docs, proposals |
| `dynamic` | Research-first, phases generated based on exploration |

Workflow templates are in `~/.claude-plugins/jons-plan/workflows/`.

## Plan Structure

```
.claude/jons-plan/plans/[plan-name]/
├── workflow.toml        # Phase definitions
├── state.json           # Current phase state
├── request.md           # Refined/approved request
├── dead-ends.json       # Failed approaches
├── claude-progress.txt  # Progress log
└── phases/
    └── NN-{phase-id}/
        ├── tasks.json   # Phase-specific tasks
        └── tasks/       # Phase task outputs
```

Active plan: `.claude/jons-plan/active-plan`

## Task Status Flow

```
todo → in-progress → done
                  → blocked (requires replanning)
```

**Critical**: Always use CLI to update status (ensures proper logging):
```bash
uv run plan.py set-status <task-id> in-progress
uv run plan.py set-status <task-id> done
```

## Task Schema

Tasks in `tasks.json` support these fields:

```json
{
  "id": "implement-auth",
  "description": "Implement authentication middleware",
  "steps": ["Create middleware", "Add JWT validation"],
  "parents": ["design-auth"],
  "context_artifacts": ["request", "design"],
  "subagent": "general-purpose",
  "subagent_prompt": "Focus on security",
  "model": "sonnet"
}
```

| Field | Description |
|-------|-------------|
| `id` | Unique task identifier |
| `type` | Task type: `cache-reference`, `prototype`. Default: normal task |
| `description` | What the task accomplishes |
| `steps` | Ordered list of steps |
| `parents` | Task IDs that must complete first |
| `context_artifacts` | Artifact names to include (e.g., `["request", "design"]`) |
| `subagent` | Agent type for execution |
| `subagent_prompt` | Additional context for subagent |
| `model` | Model override (`sonnet`, `haiku`, `opus`) |
| `question` | For prototype tasks: the question being answered |
| `hypothesis` | For prototype tasks: expected outcome |
| `inject_project_context` | Include project CLAUDE.md in task prompt (default: false) |

The `context_artifacts` field lets tasks selectively request artifacts from phase history. Use `build-task-prompt` to resolve them.

### Prototype Tasks

Prototype tasks (`type: "prototype"`) are standalone experiments that answer questions through implementation. They include `question` and `hypothesis` fields, run in isolated task directories, and produce `findings.md` with the answer.

## Subagent Capabilities

Subagents launched via the Task tool have access to:
- All file tools (Read, Write, Edit, Glob, Grep)
- Bash commands
- MCP tools (same as parent agent)
- Web tools (WebFetch, WebSearch)

**Caution with stateful MCP servers:** Some MCP servers (e.g., browser automation, database connections) maintain state and cannot be safely used by parallel subagents. Only one agent should interact with stateful MCP servers at a time.

## Hook Files

| Hook | File | Purpose |
|------|------|---------|
| SessionStart | `hooks/session-start.sh` | Show plan state on startup |
| PreCompact | `hooks/pre-compact.sh` | Preserve state during compaction |
| Stop | `hooks/stop.sh` | Auto-continue or show summary |
| PostToolUse | `hooks/post-tool-use.sh` | Log file modifications |

## CLI Reference

All commands: `uv run ~/.claude-plugins/jons-plan/plan.py <subcommand>`

### Plan Management
| Command | Description |
|---------|-------------|
| `status` | Comprehensive overview |
| `list-plans` | List all plans |
| `active-plan` | Print active plan name |
| `active-plan-dir` | Print active plan directory |
| `set-active <plan>` | Switch active plan |
| `deactivate` | Deactivate current plan |

### Task Management
| Command | Description |
|---------|-------------|
| `task-stats` | Print task counts |
| `in-progress` | List in-progress tasks |
| `next-tasks` | List available tasks |
| `set-status <task-id> <status>` | Update task status |
| `blocked-tasks` | List blocked tasks |
| `has-blockers` | Check for blocked tasks (exit code) |

### Progress Logging
| Command | Description |
|---------|-------------|
| `log <message>` | Log to plan progress |
| `recent-progress [-n N]` | Show recent progress |
| `task-log <task-id> <message>` | Log to task progress |
| `task-progress <task-id> [-n N]` | Show task progress |
| `build-task-prompt <task-id>` | Build subagent prompt with context |

### Task Outputs
| Command | Description |
|---------|-------------|
| `task-dir <task-id>` | Print task directory path |
| `ensure-task-dir <task-id>` | Create task directory |
| `parent-dirs <task-id>` | List parent directories |
| `has-outputs <task-id>` | Check for outputs (exit code) |

### Dynamic Task Modification
| Command | Description |
|---------|-------------|
| `add-task <json-file>` | Add task from JSON |
| `update-task-parents <task-id> <ids...>` | Update parents |
| `update-task-steps <task-id> <json-file>` | Update steps |

### Workflow Commands
| Command | Description |
|---------|-------------|
| `workflow-diagram [--flow east\|south]` | Show phase diagram |
| `current-phase` | Print current phase ID |
| `current-phase-dir` | Print current phase directory |
| `enter-phase <phase-id> [--reason]` | Enter/re-enter a phase |
| `enter-phase-by-number <n> [guidance]` | Enter phase by option number |
| `suggested-next` | List possible transitions |
| `phase-history` | Show all phase entries |
| `phase-context [--json]` | Show full phase context |
| `phase-summary` | Compact phase summary |
| `phase-tasks-file` | Print phase tasks.json path |
| `phase-tasks` | List tasks in current phase |
| `phase-next-tasks` | List available phase tasks |

### Workflow Expansion
| Command | Description |
|---------|-------------|
| `build-expand-prompt` | Build expansion prompt with workflow templates |
| `expand-phase [--dry-run]` | Expand current phase (reads JSON from stdin) |
| `rollback-expansion` | Restore workflow from backup |
| `validate-workflow` | Validate workflow including expandable rules |

### Artifact Management
| Command | Description |
|---------|-------------|
| `record-artifact <name> <path>` | Record phase artifact |
| `input-artifacts [--phase-id] [--json]` | Resolve input artifacts |

### Dead-End Tracking
| Command | Description |
|---------|-------------|
| `add-dead-end --task-id --what-failed --why-failed --type` | Record failed approach |
| `get-dead-ends [--json] [--recent N]` | Get dead ends |
| `clear-dead-end <id>` | Remove dead end |

### Session Mode
| Command | Description |
|---------|-------------|
| `set-mode <mode>` | Set session mode |
| `get-mode` | Get current mode |
| `clear-mode` | Clear session mode |
| `get-user-guidance` | Get guidance from user decision |
| `clear-user-guidance` | Clear guidance after processing |

Valid modes: `new`, `plan`, `proceed`, `awaiting-feedback`

### Confidence Scoring
| Command | Description |
|---------|-------------|
| `record-confidence <task-id> <score> <rationale>` | Record score |
| `check-confidence <task-id>` | Check score |
| `low-confidence-tasks` | List low-confidence tasks |

## Plugin Metadata

Version and metadata are in `.claude-plugin/plugin.json`.
