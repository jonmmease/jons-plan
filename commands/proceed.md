---
description: Start implementing tasks from the active jons-plan
allowed-tools: "*"
---

# Implement Tasks

You are implementing tasks from the active jons-plan.

## Arguments

{{#if args}}
Arguments provided: `{{args}}`
{{/if}}

### Numeric Phase Selection

If the arguments start with a number (e.g., `/jons-plan:proceed 1` or `/jons-plan:proceed 2 focus on error handling`):

1. Parse the number and optional guidance text
2. Call the CLI to transition to that phase:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase-by-number <number> "<guidance>"
   ```
3. Continue with normal phase execution below

This is used when a phase presents numbered options (like `suggested_next` transitions) and the user selects one.

## Check Active Plan

First, read `.claude/jons-plan/active-plan` to get the active plan name.

If the file is empty or missing:
- Tell user: "No active plan. Use `/jons-plan:new [topic]` to create one."
- Stop here - do not proceed further.

## Set Session Mode

Set the session mode to `proceed` so hooks know we're implementing:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-mode proceed
```

## Phase-Based Execution

Tasks are scoped to the **current phase** of the workflow:

1. **Get current phase context**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-context
   ```
   This shows the phase prompt, input artifacts, and any re-entry context.

2. **Check phase tasks**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-tasks
   uv run ~/.claude-plugins/jons-plan/plan.py phase-next-tasks
   ```
   Execute tasks from the current phase's tasks.json.

3. **After phase tasks complete**:
   - Check `suggested-next` for the next phase
   - If phase has `requires_user_input: true`, set mode to `awaiting-feedback` and stop
   - Otherwise, transition to the next phase:
     ```bash
     uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <next-phase-id>
     ```

4. **On terminal phase**:
   The workflow is complete. Show summary and allow stop.

5. **Recording dead-ends**:
   If an approach fails, record it so it's not repeated:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py add-dead-end --task-id <id> --what-failed "..." --why-failed "..." --type WRONG_ASSUMPTION
   ```

## Check for Blocked Tasks

Before proceeding, check if any tasks are blocked:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py has-blockers
```

If exit code is 0 (has blockers):
- Run `uv run ~/.claude-plugins/jons-plan/plan.py blocked-tasks` to list them
- Tell user: "Cannot proceed - blocked tasks require attention. Run `/jons-plan:plan` to review blockers and update the plan."
- **STOP HERE** - do not proceed with any tasks

## Load Plan State

1. Read `tasks.json` from the active plan directory
2. Identify tasks that are `in-progress` (resume these first)
3. Identify tasks that are `todo` with all parents `done` (available to start)

## CRITICAL: Task Status Updates

**You MUST follow this workflow for EVERY task:**

### Before Starting Any Task
```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> in-progress
```

### After Completing Any Task
```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> done
```

**⚠️ These status updates are MANDATORY:**
- NEVER start working on a task without first marking it `in-progress`
- NEVER delay marking a task `done` - do it immediately after completion
- NEVER batch status updates - update each task individually as you go

## Execution Order

1. **Resume in-progress tasks first**: If any tasks have `status: "in-progress"`:
   - Read their progress file to understand where you left off:
     ```bash
     uv run ~/.claude-plugins/jons-plan/plan.py task-progress <task-id>
     ```
   - Continue from the last logged step

2. **Pick from available tasks**: Tasks are available when:
   - `status` is `"todo"`
   - All tasks in `parents` array have `status: "done"`

3. **Check for parent outputs**: Before starting a task with parents:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py parent-dirs <task-id>
   ```
   Read any output files from parent task directories for context.

4. **Execute the task**: Follow the task's `steps` array (but see special task types below)

5. **Write outputs if needed**: Only for research/planning tasks that produce artifacts:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```

## Task Progress Logging (Best Effort)

Log your progress as you work on each task. This helps with resumption after compaction or session boundaries.

```bash
uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "message"
```

**When to log:**
- After completing each step: `"Completed step 1: Created middleware skeleton"`
- When modifying files: `"Modified src/auth/middleware.ts"`
- Before significant decisions: `"Choosing JWT over sessions for stateless auth"`
- When encountering blockers: `"Blocked: need to resolve dependency conflict"`

This is **best effort** - log what you think is important for resumption.

## Cache Reference Tasks

Tasks with `"type": "cache-reference"` are special tasks that read from the research cache instead of performing actual work.

### Identifying Cache Reference Tasks

Check if a task has `type: "cache-reference"` in its definition:
```json
{
  "id": "ref-sqlite-fts5",
  "type": "cache-reference",
  "cache_id": 42,
  "parents": [],
  "steps": []
}
```

### Execution Flow

1. **Get the cache entry**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py cache-get <cache_id>
   ```

2. **If entry not found or expired** (command returns error):
   - Create task directory: `uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>`
   - Write `blockers.md` explaining cache entry is expired/missing
   - Mark task as `blocked`
   - Stop execution - do not inject stale data

3. **If entry is valid**:
   - Create task directory: `uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>`
   - Write the cache entry's findings to `findings.md` in the task directory
   - Mark task as `done`

### Example Execution

```bash
# Check if cache entry exists and is valid
uv run ~/.claude-plugins/jons-plan/plan.py cache-get 42
# If successful, create task dir and write findings
TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir ref-sqlite-fts5)
# Write findings to task directory (the findings content from cache-get)
# Mark done
uv run ~/.claude-plugins/jons-plan/plan.py set-status ref-sqlite-fts5 done
```

### Key Points

- **Never inject stale data**: If cache entry is expired, block the task rather than proceeding with outdated information
- **Downstream tasks**: Tasks that depend on a cache-reference task receive the findings via `build-task-prompt` just like any other parent task output
- **Zero cost execution**: These tasks are essentially instant - just reading from local cache

## When to Use Subagents vs Execute Directly

**Execute directly (no subagent) when:**
- Task is simple (1-3 steps, quick to complete)
- Task requires interactive decisions or user feedback
- You need to see results before deciding next steps
- Task output affects what you do next

**Use subagents (Task tool) when:**
- Task is self-contained with clear inputs/outputs
- Multiple independent tasks can run in parallel
- Task is complex enough to benefit from isolated context
- Task has `subagent` or `model` specified in its config

**Default behavior:** Execute tasks directly unless parallelization benefits are clear or task config specifies subagent settings.

## Parallelization

Tasks without shared parents can run in parallel via subagents, but ONLY if they won't edit files in the same directories.

When launching parallel subagents, each subagent must still follow the status workflow:
- Set `in-progress` before starting
- Set `done` immediately after completing

## Subagent Configuration

Honor each task's configuration when launching subagents:
- `subagent`: Agent type (default: `general-purpose`)
- `subagent_prompt`: Additional context for the agent
- `model`: Which model to use (`sonnet`, `haiku`, `opus`)

**Note:** Subagents have access to all tools including MCP tools, file tools, and web tools. However, stateful MCP servers (browser automation, database connections) cannot be safely used by parallel subagents.

### Subagent Context Injection

Use `build-task-prompt` to automatically gather all context for a subagent:

```bash
PROMPT=$(uv run ~/.claude-plugins/jons-plan/plan.py build-task-prompt <task-id>)
```

This command outputs a complete prompt containing:
- Task description (with `subagent_prompt` prefix if configured)
- Steps as bullet list
- Parent task outputs (contents of output files from parent tasks)
- Prior progress entries (if any, with resumption instructions)

Use this prompt directly when launching the subagent via the Task tool:
```
Task(
  subagent_type: task.subagent or "general-purpose",
  model: task.model (if specified),
  prompt: $PROMPT
)
```

This eliminates manual context gathering and ensures subagents always have complete context.

## Progress Logging

Log significant progress:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py log "Completed task X: brief description"
```

## Test Definition Tasks

Tasks that define test specifications (typically named `define-tests-*`) should:

1. **Write test-spec.md** to the task output directory:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```

2. **Include measurable criteria** - each test/criterion should explain how to verify it

3. **Keep it focused** - only tests relevant to this plan's scope

The test-spec.md flows automatically to child tasks via `build-task-prompt`.

## Validation Tasks

Tasks that validate implementation (typically named `validate-*`) follow special rules:

### Execution Flow

1. **Read the spec**: Get test-spec.md from the parent test-definition task
2. **Run tests**: Execute the test suite or manually verify criteria
3. **Assess results**:
   - All pass → mark task `done`
   - Some fail → try to debug/fix (normal work, not blocked)
   - Failure requires "large side quest" → mark `blocked` with observations

### What is a "Large Side Quest"?

A validation failure becomes a blocker when fixing it would require:

1. **Out of scope**: Changes to code outside this plan's scope
2. **Risky foundation**: Modifying foundational code that's risky to change
3. **Missing prerequisite**: Something not anticipated during planning
4. **Requirements ambiguity**: Test failure reveals unclear requirements needing user input
5. **Architectural mismatch**: Implementation approach fundamentally can't meet the spec

**Keep debugging (not blocked) for:**
- Simple bugs you can identify and fix
- Missing test setup (add the setup)
- Performance issues (note but continue)
- Flaky tests (retry and document)

### Validation Blocker Observations

When marking a validation task as blocked, the blockers.md should capture observations:

```markdown
# Blocker Report: validate-auth

## What Was Attempted

Ran test suite after implementation. 8/10 tests passed.

## Failed Tests

### test_concurrent_sessions
- Expected: User can have max 3 sessions
- Actual: No session limit enforced
- Investigation: Session storage uses simple dict, no counting logic exists

### test_token_refresh_race
- Expected: Concurrent refresh requests return same token
- Actual: Each request generates new token, causing race condition
- Investigation: Token generation has no locking mechanism

## Why This Is a Large Side Quest

The session limiting and token locking require architectural changes to the session storage layer, which is shared code outside this plan's scope. Modifying it risks breaking other features.

## Suggested Resolution

Option A: Add session-storage-refactor as prerequisite task
Option B: Descope session limits from this feature
Option C: Accept eventual consistency for token refresh
```

## When to Mark a Task as Blocked

Mark a task as `blocked` when you encounter issues that **cannot be resolved by the coding agent**:

1. **Missing prerequisites**: A required dependency, API, or external resource isn't available
2. **Unclear requirements**: Task steps are ambiguous or contradictory
3. **Technical impossibility**: The approach described won't work (discovered during implementation)
4. **External blockers**: Need user input, permissions, credentials, or third-party action
5. **Scope mismatch**: Task is much larger than anticipated and needs to be broken down

**Do NOT mark as blocked for:**
- Errors you can fix by trying a different approach
- Missing information you can find by exploring the codebase
- Test failures that just need debugging

## How to Mark a Task as Blocked

When you determine a task is blocked, follow this **exact workflow**:

### Step 1: Create blockers.md

First, create the task directory and write the blockers file:

```bash
TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
```

Then write `blockers.md` with this structure:

```markdown
# Blocker Report: <task-id>

## What Was Attempted

[Describe what you tried to do and how far you got]

## Why It Failed

[Explain the specific technical issue or blocker]

## Suggested Resolution

[Propose how this could be fixed - new prereqs, modified approach, etc.]
```

### Step 2: Set Status to Blocked

Only after `blockers.md` exists:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> blocked
```

### Step 3: STOP Execution

**⚠️ CRITICAL: After marking a task as blocked, you MUST STOP all task execution.**

- Do NOT continue to other tasks
- Do NOT try workarounds
- Tell the user: "Task `<task-id>` is blocked. Run `/jons-plan:plan` to review and update the plan."
- End your response

The blocked task requires replanning before any more work can be done.

## Parallelization

Tasks without shared parents can run in parallel via subagents, but ONLY if they won't edit files in the same directories.

When launching parallel subagents, each subagent must still follow the status workflow:
- Set `in-progress` before starting
- Set `done` immediately after completing

**⚠️ If ANY task becomes blocked:**
- All parallel execution must stop
- Subagents should complete their current work gracefully
- No new tasks should be started
- Report the blocker to the user

## When All Tasks Complete

After all tasks are `done`:
1. Run any verification/tests if appropriate
2. Summarize what was accomplished
3. Ask user if they want to commit the changes
