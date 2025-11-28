---
description: Create a new jons-plan implementation plan
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(tree:*), Bash(mkdir:*), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**), Edit(**/.git/info/exclude)
---

ultrathink

# Create New Plan

You are creating a new implementation plan for the jons-plan plugin.

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore/Plan subagents for research
- Write to `.claude/jons-plan/plans/[plan-name]/` directory ONLY
- Ask user questions (AskUserQuestion tool)

Forbidden actions:
- Edit, Write, or create files outside the plan directory
- Run Bash commands that modify files (except in plan directory)
- Make git commits
- Modify configuration files

## Topic

{{#if args}}
{{args}}
{{else}}
No topic provided. Ask the user what they want to build.
{{/if}}

## Workflow

### Step 1: Derive Plan Name
Convert topic to kebab-case (e.g., "add user authentication" → "add-user-authentication")

### Step 2: Initial Understanding
Launch up to 3 Explore agents IN PARALLEL to understand the codebase:
- Each focuses on different aspect (existing patterns, related code, test structure)
- Use appropriate thoroughness ("quick search", "medium exploration", or "very thorough analysis")
- Clarify requirements with AskUserQuestion
- Quality over quantity - use fewer agents for simpler tasks

### Step 3: Multi-Agent Planning
Launch up to 3 Plan agents IN PARALLEL with different perspectives:
- Example perspectives: simplicity vs performance, minimal change vs clean architecture
- Each returns a detailed approach
- Quality over quantity - use fewer agents for simpler tasks

### Step 4: Synthesis
- Combine agent perspectives, identify trade-offs
- Ask user about preferences using AskUserQuestion
- Converge on recommended approach

### Step 5: Create Plan Infrastructure
1. Ensure `.claude/jons-plan/` is in `.git/info/exclude` (do NOT modify `.gitignore`)
2. Create directory: `.claude/jons-plan/plans/[name]/`
3. Create `plan.md` with the implementation plan
4. Create `tasks.json` with task list (all tasks start with `status: "todo"`)
5. Create `claude-progress.txt` with initial entry
6. Write plan name to `.claude/jons-plan/active-plan`

### Step 6: Present Summary
- Show plan name and task count
- List tasks with their dependencies
- Tell user: "Type `/jons-plan:proceed` to implement, or `/jons-plan:plan [feedback]` to refine."

## Task Schema

The `tasks.json` file is a JSON array of task objects:

```json
[
  { "id": "task-1", ... },
  { "id": "task-2", ... }
]
```

Each task should follow this schema:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier (kebab-case) |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Array of task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Array of steps to complete the task |
| `status` | Yes | Always `"todo"` when creating (execution changes to `in-progress`, `done`) |
| `subagent` | No | `general-purpose` (default), `Explore`, `Plan`, `claude-code-guide` |
| `subagent_prompt` | No | Additional context (e.g., "very thorough analysis") |
| `model` | No | `sonnet` (default), `haiku`, `opus` |

Example task:
```json
{
  "id": "research-auth-patterns",
  "description": "Research existing authentication patterns in codebase",
  "subagent": "Explore",
  "subagent_prompt": "very thorough analysis",
  "model": "haiku",
  "parents": [],
  "steps": ["Find auth-related files", "Document existing patterns"],
  "status": "todo"
}
```

## Parallelization Rules

Tasks can run in parallel ONLY if they won't conflict:

**Safe to parallelize** (no parent dependency needed):
- Research tasks that only write to their own `tasks/[task-id]/` output directory
- Monorepo tasks that modify separate packages (e.g., `packages/foo/` vs `packages/bar/`)
- Tasks that only read from the codebase without writing

**Must be sequential** (add parent dependency):
- Multiple tasks editing files in the same directory
- Tasks that both modify the same config files
- Implementation tasks that build on each other's code

## Task Type Guidelines

| Task Type | `subagent` | `subagent_prompt` | `model` |
|-----------|------------|-------------------|---------|
| Quick file lookup | `Explore` | `quick search` | `haiku` |
| Thorough codebase research | `Explore` | `very thorough analysis` | `haiku` |
| Simple implementation | (omit) | (omit) | (omit) |
| Complex implementation | (omit) | (omit) | `opus` |
| Architecture decisions | (omit) | (omit) | `opus` |

## Important Reminders

- NEVER implement code - only create the plan
- Keep `plan.md` and `tasks.json` in sync
- Use appropriate subagent types for each task
- All tasks start with `status: "todo"`
- Ensure task dependencies prevent file conflicts
