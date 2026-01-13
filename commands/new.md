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

## Workflow Selection

All plans use workflow-based execution. The workflow defines the phases of work.

### Explicit Workflow
If args start with `--workflow <name>` (e.g., `/jons-plan:new --workflow implementation add feature`), use the specified workflow template.

### Auto-Selection
If no `--workflow` is specified, analyze the user's request and suggest a workflow based on the heuristics below.

### Auto-Selection Heuristics

When no `--workflow` is specified, analyze the user's request and suggest a workflow:

| Pattern | Suggested Workflow | Examples |
|---------|-------------------|----------|
| Bug fix, error, issue | `implementation` | "fix the login bug", "resolve crash", "handle edge case" |
| Design, architecture, RFC | `design` | "design auth system", "plan API structure", "evaluate options" |
| Implement, add, build feature | `implementation` | "add dark mode", "implement caching", "build search" |
| Review code changes, create PR | `code-review` | "review my changes", "audit security", "analyze branch" |
| Review PR description | `pr-review` | "review this PR description", "improve my PR writeup" |
| Review RFC, design doc, proposal | `tech-docs-review` | "review this RFC", "give feedback on design doc", "review proposal" |
| Document, explain, write docs | `tech-docs` | "document the API", "explain how X works", "write guide" |
| Complex, thorough, research | `deep-implementation` | "thoroughly research and implement", "complex feature with review" |
| Design then implement | `design-and-implementation` | "design and optionally implement", "explore then build" |

**Process:**
1. Parse the request for keywords
2. Match against patterns above
3. Use `AskUserQuestion` to confirm or let user override:
   - "Based on your request, I suggest the **{workflow}** workflow. This will {brief description}."
   - Options: Use suggested workflow, Choose different workflow
4. If user chooses "different workflow", present all available options

### Available Workflows
Built-in workflows in `~/.claude-plugins/jons-plan/workflows/`:
- `implementation` - Feature implementation with research and validation
- `design` - Research and produce a design document
- `design-and-implementation` - Design first, optionally implement after approval
- `deep-implementation` - Complex features with thorough research and review
- `code-review` - Review code changes + generate PR description
- `pr-review` - Review existing PR description
- `tech-docs` - Technical documentation creation
- `tech-docs-review` - Review RFCs, design docs, proposals

## Plan Creation Steps

### Step 1: Derive Plan Name
Convert topic to kebab-case (e.g., "add user authentication" → "add-user-authentication")

### Step 2: Create Plan Infrastructure
1. Ensure `.claude/jons-plan/` is in `.git/info/exclude` (do NOT modify `.gitignore`)
2. Create directory: `.claude/jons-plan/plans/[name]/`
3. Copy workflow.toml to plan directory:
   ```bash
   cp ~/.claude-plugins/jons-plan/workflows/<name>.toml .claude/jons-plan/plans/<plan-name>/workflow.toml
   ```
4. Create `request.md` with the user's request
5. Create `claude-progress.txt` with initial entry
6. Set as active plan:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-active <plan-name>
   ```

### Step 3: Initialize State Machine
1. Initialize state.json with first phase
2. Create first phase directory:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <first-phase-id>
   ```

### Step 4: Present Summary
1. Display workflow diagram:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py workflow-diagram --flow east
   ```
2. Show current phase and its prompt
3. Tell user: "Type `/jons-plan:proceed` to start, or `/jons-plan:plan` to refine the request."

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

## Using Multiple Choice Questions

Use `AskUserQuestion` with multiple choice options when you encounter:

**Ambiguous Requirements**
- Scope is unclear (e.g., "should this also handle X?")
- Multiple valid interpretations of the request
- Missing information needed to proceed

**Key Architectural Decisions**
- Multiple valid approaches with different trade-offs
- Technology/library choices that affect the plan significantly
- Design patterns where user preference matters

Example scenarios:
- "The user asked to 'improve performance' - ask which areas to focus on"
- "Authentication could use JWT or sessions - ask which approach they prefer"
- "This feature could be simple or comprehensive - clarify desired scope"

Do NOT use multiple choice for routine decisions or minor implementation details. Reserve it for decisions that meaningfully shape the plan.

## Important Reminders

- NEVER implement code - only create the plan infrastructure
- Use appropriate subagent types for each task
- All tasks start with `status: "todo"`
- Ensure task dependencies prevent file conflicts
