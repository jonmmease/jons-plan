# jons-plan: Long-Running Agent Harness Architecture

This document explains the architecture of the jons-plan Claude Code plugin, designed to help AI agents work on complex, multi-session coding tasks.

## Problem Statement

When AI agents work on complex projects, they face several challenges:

1. **Context window limits**: Long conversations get compacted, losing important context
2. **Session boundaries**: Each new session starts with no memory of previous work
3. **Task complexity**: Large features require decomposition into smaller, trackable units
4. **Parallelization**: Independent tasks could run concurrently but need coordination
5. **State persistence**: Progress must survive across sessions and compactions

## Inspiration

This plugin implements patterns from Anthropic's blog post ["Effective Harnesses for Long-Running Agents"](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), which describes how to build effective scaffolding for agents that work across multiple context windows.

Key insights from the post:
- Use external state files (not in-context memory) for persistence
- Implement a "coding agent" that can resume work from external state
- Log progress for orientation at session start
- Structure tasks with dependencies to enable safe parallelization

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Claude Code                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Slash Commands                            ││
│  │  /jons-plan:new    Create implementation plan                ││
│  │  /jons-plan:new-design  Create design/research plan          ││
│  │  /jons-plan:new-deep  Deep exploration + implementation plan ││
│  │  /jons-plan:plan   Refine active plan                        ││
│  │  /jons-plan:proceed  Execute tasks                           ││
│  │  /jons-plan:status   Show all plans                          ││
│  │  /jons-plan:switch   Change active plan                      ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      Hooks                                   ││
│  │  SessionStart      → Orient agent, check for resume          ││
│  │  PreCompact        → Inject state into compaction summary    ││
│  │  UserPromptSubmit  → Clear session mode for non-jons-plan    ││
│  │  PostToolUse       → Log file modifications                  ││
│  │  Stop              → Session cleanup                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    CLI (plan.py)                             ││
│  │  Task management, status updates, progress logging           ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    File System State                             │
│  .claude/jons-plan/                                              │
│  ├── active-plan           # Current plan name                   │
│  ├── session-mode          # Current command mode                │
│  └── plans/                                                      │
│      └── [plan-name]/                                            │
│          ├── plan.md              # Human-readable plan          │
│          ├── tasks.json           # Machine-readable tasks       │
│          ├── claude-progress.txt  # Plan-level timestamped log   │
│          └── tasks/[task-id]/                                    │
│              ├── progress.txt     # Task-level progress log      │
│              └── output.md        # Task artifacts (optional)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two-Agent Model

The system conceptually uses two agent "roles" that the same Claude instance plays at different times:

### Planning Agent
Activated by: `/jons-plan:new`, `/jons-plan:new-design`, `/jons-plan:plan`

Responsibilities:
- Explore the codebase to understand existing patterns
- Research external options (APIs, libraries)
- Create structured task plans with dependencies
- Write to plan files only (read-only for codebase)

The planning agent does NOT implement code — it only creates plans.

### Coding Agent
Activated by: `/jons-plan:proceed`

Responsibilities:
- Read task list and identify available work
- Execute tasks following the steps array
- Update task status (todo → in-progress → done)
- Log progress for future sessions
- Launch subagents for parallel work

---

## State Model

### Task States

```
┌───────┐     set-status      ┌─────────────┐     set-status     ┌──────┐
│  todo │ ──────────────────► │ in-progress │ ─────────────────► │ done │
└───────┘                     └─────────────┘                    └──────┘
     ▲                               │                                │
     │                               │ set-status                     │
     │                               ▼                                │
     │                        ┌─────────┐                             │
     │                        │ blocked │                             │
     │                        └────┬────┘                             │
     │                             │                                  │
     └─────────────────────────────┴──────────────────────────────────┘
                           (can reset for rework/unblock)
```

**Rules:**
- All tasks start as `todo`
- A task MUST be marked `in-progress` before any work begins
- A task MUST be marked `done` immediately after completion (no batching)
- A task can be marked `blocked` if it cannot proceed (requires `blockers.md` first)
- Blocked tasks stop all execution until replanned
- Status changes are logged to `claude-progress.txt`

### Test-First Task Pattern

For features with measurable acceptance criteria, use a three-task pattern:

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ define-tests-*   │────►│ implement-*     │────►│ validate-*   │
│ (early)          │     │ (middle)        │     │ (late)       │
│                  │     │                 │     │              │
│ Output:          │     │ Reads spec,     │     │ Runs tests,  │
│ test-spec.md     │     │ builds feature  │     │ verifies     │
└──────────────────┘     └─────────────────┘     └──────────────┘
```

**Validation blocking:** If tests fail and fixing requires a "large side quest" (changes outside plan scope, architectural mismatch, missing prerequisite), the validation task marks `blocked` with observations about what failed and why.

The planner then reads these observations and updates the task graph (fix spec, add prereqs, modify approach, or descope).

### Task Availability

A task is "available" when:
1. Its status is `todo`
2. All tasks in its `parents` array have status `done`

```json
{
  "id": "implement-auth",
  "description": "Implement authentication module",
  "parents": ["research-auth-patterns", "design-auth-flow"],
  "steps": ["Create middleware", "Add routes", "Write tests"],
  "status": "todo"
}
```

This task becomes available only after both parent tasks are done.

### Session Mode

To handle compaction correctly, we track which command is currently active:

```
┌─────────────────┐
│  session-mode   │
│  (file on disk) │
└────────┬────────┘
         │
    ┌────┴────┐
    │  Value  │
    ├─────────┤
    │ new         │  → Creating implementation plan
    │ new-design  │  → Creating design plan
    │ new-deep    │  → Deep exploration + implementation plan
    │ plan        │  → Refining plan
    │ proceed     │  → Implementing tasks
    │ (empty)     │  → No active jons-plan command
    └─────────────┘
```

**Flow:**
1. Slash command sets mode at start
2. If compaction occurs, SessionStart hook reads mode
3. Hook adjusts behavior based on mode:
   - `proceed`: Auto-resume implementation
   - `new`/`new-design`/`plan`: Continue planning (no auto-resume)
   - (empty): Show neutral commands
4. UserPromptSubmit hook clears mode when user sends non-jons-plan message

### Task-Level Progress

Each task can have its own progress log for fine-grained resumption context:

```
.claude/jons-plan/plans/[plan]/tasks/[task-id]/
├── progress.txt    # Timestamped progress entries
└── output.md       # Task artifacts (optional)
```

**Automatic entries:** When task status changes:
- `in-progress` → Logs `TASK_STARTED` and task steps
- `done` → Logs `TASK_COMPLETED`

**Agent-driven entries:** The agent logs progress using:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "message"
```

**Resumption:** When a task needs resuming (after compaction or session boundary):
1. SessionStart hook shows recent task progress
2. PreCompact hook includes task progress in compaction summary
3. Agent reads full progress file if more context needed

**Subagent context injection:** When launching a subagent for a task with prior progress, include the progress in the prompt so the subagent can continue from where the previous work left off.

---

## Task Schema

```json
{
  "id": "unique-kebab-case-id",
  "description": "What this task accomplishes",
  "parents": ["parent-task-1", "parent-task-2"],
  "steps": [
    "Step 1: Do something",
    "Step 2: Do something else"
  ],
  "status": "todo",

  // Optional execution configuration:
  "subagent": "Explore",           // Agent type for parallel execution
  "subagent_prompt": "thorough",   // Additional context for agent
  "model": "haiku"                 // Model to use (haiku, sonnet, opus)
}
```

### Subagent Types

| Type | Use Case |
|------|----------|
| `general-purpose` | Default. Implementation, complex multi-step work |
| `Explore` | Fast codebase exploration, file finding |
| `Plan` | Same as Explore |
| `gemini-reviewer` | External review via Gemini 3 Pro |
| `codex-reviewer` | External review via GPT-5-codex |

### Model Selection

| Model | Use Case |
|-------|----------|
| `haiku` | Fast, cheap — exploration, simple lookups |
| `sonnet` | Balanced — default for most tasks |
| `opus` | Most capable — synthesis, architecture decisions |

---

## Hooks System

Claude Code supports lifecycle hooks that execute shell scripts at specific events.

### SessionStart

**When:** Beginning of each session (including after compaction)

**Purpose:** Orient the agent with current state

**Actions:**
1. Show active plan and working directory
2. **Check for blocked tasks** - if any exist, show them prominently
3. Display recent git commits
4. Show recent progress log entries
5. List in-progress and available tasks
6. Show task-level progress for in-progress tasks
7. Check session mode and decide on auto-resume
   - **Skip auto-resume if blocked tasks exist** - require replanning first
8. Log SESSION_START to progress file

### PreCompact

**When:** Before context compaction occurs

**Purpose:** Inject jons-plan state into the compaction summary

**Actions:**
1. Output session mode and active plan
2. For each in-progress task:
   - Show task ID and description
   - Show recent task-level progress entries
3. Provide pointers to progress files for post-compaction resumption

**Why this matters:** The compaction summary is what the agent "remembers" after compaction. By injecting jons-plan state into this summary, the agent can recover context without relying solely on SessionStart.

### UserPromptSubmit

**When:** User submits a message (before processing)

**Purpose:** Clear session mode for non-jons-plan messages

**Actions:**
1. Parse user message from JSON input
2. If message starts with `/jons-plan:`, do nothing (command will set mode)
3. Otherwise, clear the session-mode file

### PostToolUse

**When:** After Write or Edit tool calls

**Purpose:** Track file modifications

**Actions:**
1. Log modified file path to progress file
2. Skip files in `.claude/` to avoid recursive logging

### Stop

**When:** Session ends

**Purpose:** Clean up and remind about uncommitted changes

**Actions:**
1. Log SESSION_STOP
2. Show session summary
3. Warn about uncommitted git changes

---

## Compaction Handling

### The Problem

Claude Code uses "compaction" to manage context window limits. When a conversation grows too long, older messages are summarized and removed. This loses important context about current work.

### The Solution: Two-Hook Approach

The plugin uses two hooks to survive compaction:

1. **PreCompact hook**: Runs BEFORE compaction, injects state INTO the compaction summary
2. **SessionStart hook**: Runs AFTER compaction, reads state FROM disk

```
User runs /jons-plan:proceed
         │
         ▼
┌────────────────────┐
│ Command sets       │
│ mode = "proceed"   │
└─────────┬──────────┘
          │
          ▼
    [Agent works on task]
    [Logs progress to task-level progress.txt]
          │
          ▼
┌────────────────────┐
│ COMPACTION BEGINS  │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ PreCompact fires   │
│ - Outputs mode     │
│ - Outputs task IDs │
│ - Outputs progress │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Compaction creates │
│ summary including  │
│ jons-plan state    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ SessionStart fires │
│ - Reads mode       │
│ - Shows tasks      │
│ - Shows progress   │
│ - Auto-resume      │
└────────────────────┘
```

### Session Mode Behavior

The session mode determines how the agent behaves after compaction:

| Mode | After Compaction |
|------|------------------|
| `proceed` | Auto-resume: immediately continue implementation |
| `new`/`new-design`/`new-deep` | Continue creating plan (no auto-resume) |
| `plan` | Continue refining plan (no auto-resume) |
| (empty) | Show neutral command options |

---

## Parallelization

### Safe Parallelization

Tasks can run in parallel (via subagents) when:
- They have no shared parent dependencies
- They won't modify files in the same directories
- They only write to their own `tasks/[task-id]/` output directory

### Unsafe Parallelization

Tasks must be sequential when:
- They edit files in the same directory
- They modify the same configuration files
- They have logical ordering requirements

### Implementation

```python
# Identify available tasks
for task in tasks:
    if task.status == "todo":
        if all(parent.status == "done" for parent in task.parents):
            available.append(task)

# Launch in parallel (if safe)
for task in available:
    if no_file_conflicts(task, other_available_tasks):
        launch_subagent(task)
```

---

## Plan Types

### Implementation Plans (`/jons-plan:new`)

- **Purpose:** Build features, fix bugs
- **Deliverable:** Code changes in repository
- **Naming:** `[topic]` (e.g., `add-auth`)

### Design Plans (`/jons-plan:new-design`)

- **Purpose:** Research, explore, design
- **Deliverable:** `design.md` document
- **Naming:** `[topic]-design` (enforced suffix)
- **Model strategy:** haiku for exploration, opus for synthesis
- **Workflow:** design.md → user review → implementation plan

### Deep Exploration Plans (`/jons-plan:new-deep`)

- **Purpose:** Complex features requiring thorough exploration
- **Deliverable:** Code changes in repository
- **Naming:** `[topic]` (e.g., `add-auth`)
- **Workflow:** Auto-executes 5 phases within a single command:
  1. Parallel Exploration (3 haiku agents)
  2. Draft Plan Synthesis (opus)
  3. External Review (gemini + codex in parallel)
  4. Final Synthesis (opus)
  5. Create Plan Infrastructure
- **Use when:** Complex features, unclear architecture, benefits from external review

---

## CLI Reference

```bash
uv run ~/.claude-plugins/jons-plan/plan.py <command>
```

### Overview Commands
| Command | Description |
|---------|-------------|
| `status` | Comprehensive overview |
| `list-plans` | List all plans |
| `active-plan` | Print active plan name |
| `active-plan-dir` | Print active plan path |

### Plan Management
| Command | Description |
|---------|-------------|
| `set-active <plan>` | Switch active plan |

### Task Management
| Command | Description |
|---------|-------------|
| `task-stats` | Print task counts |
| `in-progress` | List in-progress tasks |
| `next-tasks` | List available tasks |
| `set-status <id> <status>` | Update task status (validates blockers.md for blocked) |
| `blocked-tasks` | List blocked tasks |
| `has-blockers` | Check if blocked tasks exist (exit 0 if yes) |

### Session Mode
| Command | Description |
|---------|-------------|
| `set-mode <mode>` | Set session mode |
| `get-mode` | Get current mode |
| `clear-mode` | Clear session mode |

### Progress Logging
| Command | Description |
|---------|-------------|
| `log <message>` | Append to plan-level progress log |
| `recent-progress [-n N]` | Show recent plan-level entries |

### Task-Level Progress
| Command | Description |
|---------|-------------|
| `task-log <id> <message>` | Append to task's progress.txt |
| `task-progress <id> [-n N]` | Show recent task progress entries |
| `build-task-prompt <id>` | Build complete subagent prompt with all context |

### Task Outputs
| Command | Description |
|---------|-------------|
| `task-dir <id>` | Print task output directory |
| `ensure-task-dir <id>` | Create task directory |
| `parent-dirs <id>` | List parent task directories |
| `has-outputs <id>` | Check if task has outputs |

---

## Comparison to Other Approaches

### vs. In-Context Task Lists

**In-context:** Task list in conversation, lost on compaction
**jons-plan:** Task list on disk, survives compaction

### vs. Simple TODO Comments

**TODO comments:** Scattered, no dependencies, no status
**jons-plan:** Centralized, dependency graph, status workflow

### vs. GitHub Issues

**GitHub Issues:** External, requires API calls, no local state
**jons-plan:** Local, instant access, integrated with Claude Code

### vs. Memory Systems

**Memory:** Stores facts/context, agent must interpret
**jons-plan:** Structured task data, explicit workflow

---

## Known Limitations

1. **Single active plan:** Only one plan can be active at a time
2. **Manual status updates:** Agent must remember to update status
3. **Hook bug workaround:** Hooks must be in `~/.claude/settings.json` due to Claude Code bug #12151
4. **No automatic conflict detection:** Parallel task safety relies on task design

---

## Future Improvement Areas

1. **Automatic parallelization analysis:** Detect file conflicts automatically
2. **Plan branching:** Work on multiple plans simultaneously
3. **Checkpoint/rollback:** Save and restore plan states
4. **Progress visualization:** Better UI for task progress
5. **Integration with git branches:** One branch per plan
6. **Smarter compaction handling:** Preserve more context
7. **Cross-session learning:** Learn from completed plans

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude-plugins/jons-plan/` | Plugin installation |
| `~/.claude-plugins/jons-plan/plan.py` | CLI tool |
| `~/.claude-plugins/jons-plan/commands/` | Slash command definitions |
| `~/.claude-plugins/jons-plan/hooks/` | Lifecycle hook scripts |
| `[project]/.claude/jons-plan/` | Project-specific plan data |
| `[project]/.claude/jons-plan/active-plan` | Current plan name |
| `[project]/.claude/jons-plan/session-mode` | Current command mode |
| `[project]/.claude/jons-plan/plans/[name]/` | Individual plan directories |
