---
description: Refine the active jons-plan implementation plan
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(tree:*), Bash(mkdir:*), Bash(uv run ~/.claude-plugins/jons-plan/plan.py set-mode *), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**)
---

## FIRST: Set Session Mode

Before doing anything else, set the session mode so compaction recovery works correctly:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-mode plan
```

Run this command NOW before proceeding.

---

# Refine Active Plan

You are refining an existing implementation plan for the jons-plan plugin.

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore agents for research
- Write to `.claude/jons-plan/plans/[active-plan]/` directory ONLY
- Ask user questions (AskUserQuestion tool)

Forbidden actions:
- Edit, Write, or create files outside the plan directory
- Run Bash commands that modify files (except in plan directory)
- Make git commits
- Modify configuration files

## Check Active Plan

First, read `.claude/jons-plan/active-plan` to get the active plan name.

If the file is empty or missing:
- Tell user: "No active plan. Use `/jons-plan:new [topic]` to create one."
- Stop here - do not proceed further.

## Check for Blocked Tasks

Before processing user feedback, check for blocked tasks:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py has-blockers
```

If exit code is 0 (has blockers):

1. **List blocked tasks**: `uv run ~/.claude-plugins/jons-plan/plan.py blocked-tasks`

2. **Read each blocker file**: For each blocked task, read its `blockers.md`:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py task-dir <task-id>)
   # Read ${TASK_DIR}/blockers.md
   ```

3. **Summarize blockers** to the user:
   - What tasks are blocked
   - Why (from blockers.md)
   - Suggested resolutions (from blockers.md)

4. **Propose plan updates**: Based on the blockers, suggest:
   - **Modify task**: Change the approach/steps to avoid the issue
   - **Add prerequisites**: Insert new tasks that must complete first
   - **Split task**: Break into smaller pieces where some can proceed
   - **Remove task**: If no longer needed or not feasible

5. **Resolve the blockers**: After updating the plan:
   - Reset resolved tasks from `blocked` back to `todo`:
     ```bash
     uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> todo
     ```
   - The blocker file remains for reference but is no longer active

### Validation Task Blockers

When a validation task (typically `validate-*`) is blocked, the blockers.md contains **observations** about test failures:

1. **Read the observations carefully**: They explain what tests failed and why fixing is a "large side quest"

2. **Interpret the investigation**: The agent documented what it found during debugging - use this context

3. **Resolution options**:
   - **Fix the spec**: If tests were too strict or requirements unclear, update the test-definition task
   - **Add prerequisite**: If missing infrastructure, add a task before the validation
   - **Modify approach**: If architectural mismatch, change implementation strategy
   - **Descope**: Remove criteria that can't be met in this plan
   - **Split feature**: Break into smaller pieces where some can pass validation

4. **After resolving**:
   - Update tasks.json with any new/modified tasks
   - Reset the validation task to `todo`
   - Consider if the test-definition task also needs updates

If user provides feedback, consider how it relates to any blockers before proceeding.

## User Feedback

{{#if args}}
{{args}}
{{else}}
No feedback provided. Read the current `plan.md` and `tasks.json`, show a summary, and ask what the user wants to change.
{{/if}}

## Workflow

1. **Read current state**: Load `plan.md` and `tasks.json` from the active plan directory

2. **Interpret user feedback**: Understand what changes the user wants

3. **Check if feedback fits the plan**: If the feedback seems like a completely different topic/feature than the active plan:
   - Ask user: "This seems like a different project than '[active-plan-name]'. Would you like to:
     1. Update the current plan to include this
     2. Create a new plan with `/jons-plan:new [topic]`"
   - Wait for user response before proceeding

4. **Explore if needed**: If the feedback requires understanding new parts of the codebase, launch Explore agents

5. **Update plan files**:
   - Edit `plan.md` to reflect changes in approach/design
   - Edit `tasks.json` to add/remove/modify tasks
   - Keep both files in sync

6. **Present summary**: Show what was changed (tasks added, removed, modified)

7. **Next steps**: Tell user: "Type `/jons-plan:proceed` to implement, or `/jons-plan:plan [more feedback]` to continue refining."

## Task Schema Reference

The `tasks.json` file is a JSON array of task objects. Each task has:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Array of task IDs that must complete first |
| `steps` | Yes | Array of steps to complete the task |
| `status` | Yes | `todo`, `in-progress`, or `done` |
| `subagent` | No | Agent type (default: `general-purpose`) |
| `subagent_prompt` | No | Additional context for the agent |
| `model` | No | `sonnet` (default), `haiku`, `opus` |

## Important Reminders

- NEVER implement code - only refine the plan
- Keep `plan.md` and `tasks.json` in sync
- New tasks should start with `status: "todo"`
- Don't change status of existing tasks (that happens during implementation)
- Preserve task IDs when modifying existing tasks (to maintain dependency references)
