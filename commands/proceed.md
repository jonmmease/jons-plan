---
description: Start implementing tasks from the active jons-plan
allowed-tools: "*"
---

# Implement Tasks

You are implementing tasks from the active jons-plan.

## Check Active Plan

First, read `.claude/jons-plan/active-plan` to get the active plan name.

If the file is empty or missing:
- Tell user: "No active plan. Use `/jons-plan:new [topic]` to create one."
- Stop here - do not proceed further.

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

1. **Resume in-progress tasks first**: If any tasks have `status: "in-progress"`, complete those before starting new ones

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

## Progress Logging

Log significant progress:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py log "Completed task X: brief description"
```

## When All Tasks Complete

After all tasks are `done`:
1. Run any verification/tests if appropriate
2. Summarize what was accomplished
3. Ask user if they want to commit the changes
