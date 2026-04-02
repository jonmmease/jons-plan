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

## Codex Rescue Execution

When a task has `"executor": "codex-rescue"`, execute it via the `/codex:rescue` skill instead of the Task tool. This passes the full task prompt to Codex.

### Execution
1. Build the task prompt:
   ```bash
   PROMPT=$(uv run ~/.claude-plugins/jons-plan/plan.py build-task-prompt <task-id>)
   ```
2. Ensure the task output directory exists:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```
3. Invoke the skill:
   - **Foreground** (standalone tasks): `Skill(skill: "codex:rescue", args: "--fresh --wait <prompt>")`
   - **Background** (parallel tasks, e.g. planning panel): `Skill(skill: "codex:rescue", args: "--fresh --background <prompt>")`
4. **Symlink the Codex log** so the viewer shows live progress:
   ```bash
   WS=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
   CODEX_LOG=$(ls -t "${CLAUDE_PLUGIN_DATA}/state/${WS}-"*/jobs/*.log 2>/dev/null | head -1)
   if [[ -n "$CODEX_LOG" ]]; then ln -sf "$CODEX_LOG" "$TASK_DIR/progress.txt"; fi
   ```
5. Save Codex's response to `output.md` in the task directory.

### Post-execution
- If Codex fails or returns empty output: mark the task as blocked with `blockers.md`
- If successful: write the output, log completion, and mark the task done

Do NOT use the Task tool for codex-rescue tasks.

## Codex Review Execution

When a task has `"executor": "codex-review"`, run a general Codex code review against the git diff via the `/codex:review` skill. This does not accept custom instructions — it's a general-purpose diff review.

### Execution
1. Ensure the task output directory exists:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```
2. Invoke the skill with appropriate scope:
   - Branch review: `Skill(skill: "codex:review", args: "--wait --scope branch")`
   - With explicit base: `Skill(skill: "codex:review", args: "--wait --base <ref>")`
   - Use `--base` if you know the merge-base from the gather phase or earlier context
3. **Symlink the Codex log** so the viewer shows live progress:
   ```bash
   WS=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
   CODEX_LOG=$(ls -t "${CLAUDE_PLUGIN_DATA}/state/${WS}-"*/jobs/*.log 2>/dev/null | head -1)
   if [[ -n "$CODEX_LOG" ]]; then ln -sf "$CODEX_LOG" "$TASK_DIR/progress.txt"; fi
   ```
4. Save Codex's response to `output.md` in the task directory.

### Post-execution
- If Codex fails or returns empty output: mark the task as blocked with `blockers.md`
- If successful: write the output, log completion, and mark the task done

## Codex Adversarial Review Execution

When a task has `"executor": "codex-adversarial-review"`, run a Codex adversarial review against the git diff via the `/codex:adversarial-review` skill. This reviews the diff while challenging design choices and implementation approach, with custom focus text from the task description.

### Execution
1. Ensure the task output directory exists:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```
2. Invoke the skill with focus text from the task description:
   - Branch review: `Skill(skill: "codex:adversarial-review", args: "--wait --scope branch <focus-text>")`
   - With explicit base: `Skill(skill: "codex:adversarial-review", args: "--wait --base <ref> <focus-text>")`
   - The focus text should come from the task's `description` field
   - Use `--base` if you know the merge-base from the gather phase or earlier context
3. **Symlink the Codex log** so the viewer shows live progress:
   ```bash
   WS=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
   CODEX_LOG=$(ls -t "${CLAUDE_PLUGIN_DATA}/state/${WS}-"*/jobs/*.log 2>/dev/null | head -1)
   if [[ -n "$CODEX_LOG" ]]; then ln -sf "$CODEX_LOG" "$TASK_DIR/progress.txt"; fi
   ```
4. Save Codex's response to `output.md` in the task directory.

### Post-execution
- If Codex fails or returns empty output: mark the task as blocked with `blockers.md`
- If successful: write the output, log completion, and mark the task done

## Planning Panel: Parallel Execution

When a phase has `planning_panel = true`, it will have two independent planning tasks (opus-planning, codex-planning) that feed into a synthesis task. **Both planning tasks MUST be launched simultaneously in a single message.**

Each task uses a different execution mechanism, but they can both be dispatched in one response:
- **opus-planning** (executor: `task-tool`) — launch via Task tool
- **codex-planning** (executor: `codex-rescue`) — launch via Skill with `--background`

### Example: Single message with 2 parallel tool calls

```
1. Skill tool → codex:rescue --fresh --background <codex-prompt>
2. Task tool → opus-planning subagent (model: opus)
```

**Set both to `in-progress` before launching.** Launch the background Codex skill first so it starts immediately, then the Task tool call for Opus which blocks.

### Waiting for Completion

After launching both tasks:
1. The Skill call with `--background` returns immediately — Codex runs in the background
2. The Task tool call (opus) blocks until complete
3. After opus completes, you will be notified when the background Codex task finishes
4. Save the Codex output to `output.md` in the codex-planning task directory

Only after **both tasks complete** should you proceed to the synthesis task.

**Do NOT run these sequentially.** The entire point of the planning panel is to get independent perspectives generated in parallel.

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
