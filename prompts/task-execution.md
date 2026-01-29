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

## Check Cache Before Research

Before starting a research task that involves external sources (web search, documentation lookup), check the research cache for existing findings.

### When to Check Cache

**DO check cache for:**
- Web searches and documentation lookups
- Tasks with keywords: "research", "investigate", "explore", "find out", "lookup"
- Tasks using subagent type "Explore" for external research
- Any task that might duplicate prior web/documentation research

**Do NOT check cache for:**
- Codebase exploration (project-specific, changes with code)
- Implementation tasks
- Validation/testing tasks
- Tasks that are clearly project-specific

### How to Check

Search the cache with your research query:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py cache-search "your research query"
```

Or get suggestions based on task description:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py cache-suggest --description "task description"
```

### If Cache Has Results

1. **Review the cached findings** - Run `cache-get <id>` to see full content
2. **If findings are sufficient** - Use them directly and skip redundant research
3. **If findings are partial** - Use as a starting point and supplement with additional research
4. **Log that you used cached findings**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "Used cached findings from entry <id>"
   ```

### If No Cache Results

Proceed with the research normally. After completing, consider caching valuable findings (see "Caching Research Findings" below).

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

## Caching Research Findings

After completing research tasks that produce valuable external findings, consider caching them for future reuse.

### When to Cache

Cache findings when:
- Web search produced useful documentation or patterns
- Documentation lookup found relevant best practices
- External research could benefit future similar tasks

Do NOT cache:
- Codebase exploration results (changes with code)
- Temporary or context-specific findings
- Very short findings (< 100 chars)

### How to Cache

```bash
uv run ~/.claude-plugins/jons-plan/plan.py cache-add \
  --query "the search query or question" \
  --findings-file path/to/findings.md \
  --source-type web_search \
  --source-url "https://source.url" \
  --plan-id "current-plan-name"
```

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
- CLAUDE.md proposals guidance (if phase has `supports_proposals = true`)

Use this prompt directly when launching the subagent via the Task tool:
```
Task(
  subagent_type: task.subagent or "general-purpose",
  model: task.model (if specified),
  prompt: $PROMPT
)
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

### Step 3: Consider Phase Loopback

If the workflow supports loopbacks (check if `on_blocked` or `max_retries` are configured):

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
