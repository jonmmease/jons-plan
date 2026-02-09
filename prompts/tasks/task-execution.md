# Task Execution

Core guidance for executing tasks in a phase.

## Load Plan State

1. Read `tasks.json` from the current phase directory
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

**These status updates are MANDATORY:**
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

4. **Execute the task**: Follow the task's `steps` array

5. **Write outputs if needed**: Only for research/planning tasks that produce artifacts:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```

## Task Progress Logging

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

**If ANY task becomes blocked:**
- All parallel execution must stop
- Subagents should complete their current work gracefully
- No new tasks should be started
- Report the blocker to the user

## Subagent Configuration

Honor each task's configuration when launching subagents:
- `subagent`: Agent type (default: `general-purpose`). Always use `general-purpose` — do not use `Explore` or `Plan` as they cannot write output files.
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
- Artifact task guidance (proposals, challenges) if phase has `required_json_artifacts`

Use this prompt directly when launching the subagent via the Task tool:
```
Task(
  subagent_type: task.subagent or "general-purpose",
  model: task.model (if specified),
  prompt: $PROMPT
)
```

## Codex CLI Execution

When a task has `"executor": "codex-cli"`, execute it via the codex CLI instead of the Task tool.

### Pre-flight Check (once per phase)
```bash
codex --version >/dev/null 2>&1 || echo "ERROR: codex CLI not found in PATH"
```

### Execution
Run the command with a **15-minute timeout** (Bash tool `timeout: 900000`):
```bash
CMD=$(uv run ~/.claude-plugins/jons-plan/plan.py get-execution-cmd <task-id>)
eval "$CMD"
EXIT_CODE=$?
```

### Post-execution
- If exit code is non-zero or output file is empty:
  1. Create `blockers.md` in the task directory with the command, exit code, and stderr excerpt
  2. Mark the task as blocked
- If successful: log completion and mark the task done

Do NOT use the Task tool for codex-cli tasks. The codex CLI is invoked directly via Bash.

## Gemini CLI Execution

When a task has `"executor": "gemini-cli"`, execute it via the Gemini CLI instead of the Task tool.

### Pre-flight Check (once per phase)
```bash
gemini --version >/dev/null 2>&1 || echo "ERROR: gemini CLI not found in PATH"
```

### Execution
Run the command with a **15-minute timeout** (Bash tool `timeout: 900000`):
```bash
CMD=$(uv run ~/.claude-plugins/jons-plan/plan.py get-execution-cmd <task-id>)
eval "$CMD"
EXIT_CODE=$?
```

### Post-execution
- If exit code is non-zero or output file is empty:
  1. Create `blockers.md` in the task directory with the command, exit code, and stderr excerpt
  2. Mark the task as blocked
- If successful: log completion and mark the task done

Do NOT use the Task tool for gemini-cli tasks. The gemini CLI is invoked directly via Bash.

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

### Step 3: Consider Phase Loopback

If the workflow supports loopbacks (check `suggested_next` for self-referential or cross-phase transitions):

**Before looping, record important artifacts:**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact blockers phases/XX-{phase}/tasks/{task-id}/blockers.md
```

**Self-loop (retry current phase):**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py loop-phase --reason "Task blocked: <brief description>"
```
This creates a new phase directory. Create new tasks.json addressing the blockers.

**Cross-phase loop (e.g., validate → implement):**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py loop-to-phase <target-phase> --reason "<description>"
```

**Check prior phase outputs for context:**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py prior-phase-outputs
```

**If max retries exceeded or loopback not configured:** STOP and inform user.

### Step 4: STOP Execution (if not looping)

**CRITICAL: After marking a task as blocked without looping, you MUST STOP all task execution.**

- Do NOT continue to other tasks
- Do NOT try workarounds
- Tell the user: "Task `<task-id>` is blocked. Run `/jons-plan:plan` to review and update the plan."
- End your response

The blocked task requires replanning before any more work can be done.
