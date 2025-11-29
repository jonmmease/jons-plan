---
description: Create a new jons-plan implementation plan
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(tree:*), Bash(mkdir:*), Bash(uv run ~/.claude-plugins/jons-plan/plan.py set-mode *), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**), Edit(**/.git/info/exclude)
---

## FIRST: Set Session Mode

Before doing anything else, set the session mode so compaction recovery works correctly:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-mode new
```

Run this command NOW before proceeding.

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
| Test definition | (omit) | (omit) | (omit) |
| Validation/verification | (omit) | (omit) | (omit) |

## Test-First Planning Pattern

For features with clear acceptance criteria, consider structuring tasks in a test-first pattern:

### When to Use Test-First

- Feature has measurable success criteria
- Multiple implementation tasks depend on consistent expectations
- You want explicit validation gates before marking complete
- Complex features that benefit from upfront test design

### Task Structure

```
define-tests-* (early)     → Write test-spec.md
    ↓
implement-* (middle)       → Read spec, build feature & tests
    ↓
validate-* (late)          → Run tests, verify criteria
```

### Test Specification Output

Test definition tasks write to: `tasks/[task-id]/test-spec.md`

Simple format:
```markdown
# Test Specification: [Feature]

## Tests to Add/Modify
- [ ] Test: [description] - [expected behavior]
- [ ] Test: [description] - [expected behavior]

## Acceptance Criteria
- [Criterion with measurable verification method]
- [Criterion with measurable verification method]

## Edge Cases
- [Edge case to handle]
```

### Example Task Structure

```json
[
  {
    "id": "define-tests-auth",
    "description": "Define test cases for authentication",
    "parents": [],
    "steps": [
      "Document required test scenarios",
      "Define acceptance criteria with measurable verification",
      "Write test-spec.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "implement-auth",
    "description": "Implement authentication to meet test spec",
    "parents": ["define-tests-auth"],
    "steps": [
      "Read test-spec.md from parent task",
      "Implement feature to satisfy criteria",
      "Write tests matching the specification"
    ],
    "status": "todo"
  },
  {
    "id": "validate-auth",
    "description": "Validate auth implementation against spec",
    "parents": ["implement-auth"],
    "steps": [
      "Read test-spec.md from define-tests-auth",
      "Run test suite and verify all tests pass",
      "If failures require large side quest, mark blocked with observations"
    ],
    "status": "todo"
  }
]
```

See `proceed.md` for validation task execution details and blocking criteria.

## Important Reminders

- NEVER implement code - only create the plan
- Keep `plan.md` and `tasks.json` in sync
- Use appropriate subagent types for each task
- All tasks start with `status: "todo"`
- Ensure task dependencies prevent file conflicts
