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
| `direct-implementation` | Simple plan-implement-verify (no research) |
| `design` | Research, explore, produce design.md |
| `design-and-implementation` | Design first, optionally implement |
| `deep-implementation` | Thorough research + external review |
| `code-review` | Review code changes + generate PR description |
| `pr-review` | Review existing PR description |
| `deslop-pr` | Quick slop detection and cleanup for PR descriptions |
| `tech-docs` | Technical documentation |
| `tech-docs-review` | Review RFCs, design docs, proposals |
| `dynamic` | Research-first, phases generated based on exploration |

Workflow templates are in `~/.claude-plugins/jons-plan/workflows/`.

## Plan Structure

**IMPORTANT:** The `.claude/` directory must be at the **git repository root** (or working directory if not in a repo), not in subdirectories. The CLI uses `git rev-parse --show-toplevel` (falling back to cwd) to locate plans. When creating plans, always use absolute paths based on `$(git rev-parse --show-toplevel 2>/dev/null || pwd)`.

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

**Valid statuses**: `todo`, `in-progress`, `done`, `blocked` - these are the ONLY valid values.

**CRITICAL prohibitions**:
- **Never invent new statuses** - "deferred", "skipped", "partial" etc. are NOT valid
- **Never manually edit state.json** - always use CLI commands (`enter-phase`, `set-status`)
- **Never mark done if incomplete** - use `blocked` if task cannot be completed

**Critical**: Always use CLI to update status (ensures proper logging):
```bash
uv run plan.py set-status <task-id> in-progress
uv run plan.py set-status <task-id> done
uv run plan.py set-status <task-id> blocked
```

When a task is blocked due to scope issues, transition back to planning phase - see proceed.md "Scope Exceeded Handling" section.

## Phase Transitions

Phase transitions are defined via `suggested_next` in workflow.toml. Items can be:
- **Strings** for simple transitions: `"implement"`
- **Objects** for transitions requiring approval:

```toml
suggested_next = [
    "implement",
    { phase = "research", requires_approval = true, approval_prompt = "Return to research?" }
]
```

| Field | Description |
|-------|-------------|
| `phase` | Target phase ID |
| `requires_approval` | If true, user must approve transition |
| `approval_prompt` | Message shown when asking for approval |

Use object format for loopback transitions (e.g., validate → research when issues found).

## Workflow Schema Reference

The `workflow.toml` file defines phases and transitions. **Only use the fields documented below** - unknown fields will cause validation errors.

### Top-level Structure

```toml
[workflow]
name = "workflow-name"           # Required: workflow identifier
description = "What it does"     # Optional: human-readable description

[[phases]]                       # Required: array of phase definitions
# ... phase fields ...
```

### Phase Fields

Each `[[phases]]` entry supports these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique phase identifier (kebab-case) |
| `prompt` | string | Yes | Instructions for this phase |
| `suggested_next` | array | No | Valid transitions (strings or objects) |
| `terminal` | bool | No | If true, workflow ends at this phase |
| `use_tasks` | bool | No | Phase uses tasks.json for work breakdown |
| `required_tasks` | array | No | Tasks to auto-seed in tasks.json when entering phase |
| `requires_user_input` | bool | No | Stop and wait for user before proceeding |
| `required_artifacts` | array | No | Artifact names that must be recorded before leaving phase |
| `context_artifacts` | array | No | Artifact names to inject from upstream phases |
| `on_blocked` | string | No | Phase to transition to when blocked ("self" or phase ID) |
| `max_retries` | int | No | Max re-entries before requiring user intervention |
| `max_iterations` | int | No | Legacy: max iterations for research loops |
| `supports_proposals` | bool | No | Enable CLAUDE.md improvement proposals |
| `supports_prototypes` | bool | No | Enable prototype tasks |
| `supports_cache_reference` | bool | No | Enable research cache lookups |
| `expand_prompt` | string | No | Instructions for dynamic phase expansion |
| `required_json_artifacts` | array | No | JSON artifacts validated against schemas before leaving phase |

### Required JSON Artifacts

The `required_json_artifacts` field specifies JSON artifacts that must exist and validate against a schema before leaving a phase. This enables structured data validation for phase outputs.

```toml
[[phases]]
id = "research"
use_tasks = true
required_json_artifacts = [
  { name = "cache-candidates", schema = "cache-candidates" }
]
```

**Schema storage:** Schemas are stored in `~/.claude-plugins/jons-plan/schemas/<name>.schema.json`

**Behavior:**
- On phase transition: each artifact is validated against its schema
- Validation failures block the transition with clear error messages
- Special handling: `cache-candidates` artifacts are auto-imported to the research cache

**Built-in schemas:**
- `cache-candidates` - Research cache entries with file references

### Required Tasks

The `required_tasks` field auto-seeds tasks.json when entering a phase. This ensures critical tasks with specific configurations (like `prompt_file`) are always present.

```toml
[[phases]]
id = "analyze"
use_tasks = true
required_tasks = [
  { id = "slop-detection", description = "Scan for AI patterns", prompt_file = "slop-detection", model = "haiku" },
  { id = "synthesize", description = "Combine findings", parents = ["slop-detection"] },
]
prompt = """
Run the required tasks. Add additional reviewer tasks as needed.
"""
```

**Supported task fields in required_tasks:**
- `id`, `description` (required)
- `prompt_file`, `subagent`, `subagent_prompt`, `model`, `parents`, `steps`
- `context_artifacts`, `type`, `question`, `hypothesis`, `inject_project_context`, `locks`

**Behavior:**
- On first entry: creates tasks.json with required tasks (status="todo")
- On re-entry: merges missing tasks, warns if protected fields differ
- Protected fields: `prompt_file`, `subagent`, `model`

Use `validate-required-tasks` to check tasks.json against the workflow definition.

### Transition Format

The `suggested_next` array accepts two formats:

```toml
# Simple string transitions
suggested_next = ["implement", "plan"]

# Object transitions (for approval requirements)
suggested_next = [
    "implement",
    { phase = "research", requires_approval = true, approval_prompt = "Return to research?" }
]

# Special values
suggested_next = ["__expand__", "complete"]  # Dynamic expansion
```

### Example Workflow

```toml
[workflow]
name = "implementation"
description = "Feature implementation with validation"

[[phases]]
id = "research"
use_tasks = true
prompt = """
Research the codebase...
"""
suggested_next = ["plan"]

[[phases]]
id = "plan"
requires_user_input = true
prompt = """
Create implementation plan...
"""
suggested_next = ["implement", "plan"]

[[phases]]
id = "implement"
use_tasks = true
on_blocked = "self"
max_retries = 3
prompt = """
Execute the plan...
"""
suggested_next = [
    "validate",
    { phase = "plan", requires_approval = true, approval_prompt = "Return to planning?" }
]

[[phases]]
id = "validate"
prompt = """
Verify implementation...
"""
suggested_next = ["complete", "implement"]
on_blocked = "implement"

[[phases]]
id = "complete"
terminal = true
prompt = """
Finalize...
"""
```

### Invalid Patterns

**DO NOT use these patterns** - they will cause errors:

```toml
# WRONG: Nested transitions table (doesn't exist)
[[phases.transitions]]
trigger = "done"
target = "next-phase"

# WRONG: Unknown phase fields
[[phases]]
id = "research"
transitions = [...]  # Not a valid field

# WRONG: Missing required fields
[[phases]]
prompt = "Do something"  # Missing 'id'
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
  "prompt_file": "security-review",
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
| `prompt_file` | Plugin prompt to inject (e.g., `"slop-detection"` loads `prompts/slop-detection.md`) |
| `subagent` | Agent type for execution |
| `subagent_prompt` | Additional context for subagent |
| `model` | Model override (`sonnet`, `haiku`, `opus`) |
| `question` | For prototype tasks: the question being answered |
| `hypothesis` | For prototype tasks: expected outcome |
| `inject_project_context` | Include project CLAUDE.md in task prompt (default: false) |
| `locks` | Lock names for exclusive access - files, tools, or resources (e.g., `"cargo"`, `"browser"`) |

The `context_artifacts` field lets tasks selectively request artifacts from phase history. The `prompt_file` field injects specialized prompts from the plugin's `prompts/` directory. Use `build-task-prompt` to resolve them.

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
| SessionStart | `hooks/session-start.sh` | Show plan state on startup and after compaction |
| Stop | `hooks/stop.sh` | Auto-continue or show summary |

## CLI Reference

All commands: `uv run ~/.claude-plugins/jons-plan/plan.py <subcommand>`

### CLI Notes

The `status` command shows tasks from the **current phase only**. Each phase has its own `tasks.json`. To see all phase entries, use `phase-history`.

User guidance is set via `/jons-plan:proceed <number> <guidance>` and persists until the next phase transition or explicit `clear-user-guidance` call.

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
| `add-task <json-file>` | Add single task from JSON |
| `update-task-parents <task-id> <ids...>` | Update parents |
| `update-task-steps <task-id> <json-file>` | Update steps |

### Workflow Commands
| Command | Description |
|---------|-------------|
| `workflow-diagram [--flow east\|south]` | Show phase diagram |
| `current-phase` | Print current phase ID |
| `current-phase-dir` | Print current phase directory |
| `enter-phase <phase-id> [--reason-file]` | Enter phase (re-entry requires --reason-file with detailed context) |
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
| `validate-required-tasks` | Validate tasks.json contains all required tasks |

### Artifact Management
| Command | Description |
|---------|-------------|
| `record-artifact <name> <path>` | Record phase artifact |
| `input-artifacts [--phase-id] [--json]` | Resolve input artifacts |
| `validate-json-artifact <name> [--schema]` | Validate JSON artifact against schema |
| `cache-import <path> [--plan-id] [--dry-run]` | Import cache entries from JSON file |

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

### Proposals and Challenges
| Command | Description |
|---------|-------------|
| `collect-proposals` | Scan for proposals.md files |
| `list-proposals` | List all CLAUDE.md proposals |
| `update-proposal-status <id> <status>` | Accept/reject proposal |
| `collect-challenges` | Scan for challenges.md files |
| `list-challenges` | List all challenges |
| `acknowledge-challenge <id>` | Mark challenge as acknowledged |

**Proposals** record advice for future agents when you overcome an issue.
**Challenges** record issues you couldn't solve and had to work around.

## Plugin Metadata

Version and metadata are in `.claude-plugin/plugin.json`.
