---
description: Create a new jons-plan design plan
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(tree:*), Bash(mkdir:*), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**), Edit(**/.git/info/exclude)
---

ultrathink

# Create New Design Plan

You are creating a **design plan** — a plan that will guide exploration, research, prototyping, and produce a design document as its final artifact.

**Important distinction:** You are writing a *plan* that describes what tasks to execute. You are NOT doing the research or writing the design document now. That happens when the user runs `/jons-plan:proceed`.

Design plans support a two-phase workflow:
1. **Discovery phase** (this plan): Research, explore, prototype, synthesize → `design.md`
2. **Implementation phase** (future plan): Build based on approved design

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore/Plan subagents for initial understanding
- Write to `.claude/jons-plan/plans/[plan-name]/` directory ONLY
- Ask user questions (AskUserQuestion tool)

Forbidden actions:
- Edit, Write, or create files outside the plan directory
- Run Bash commands that modify files (except in plan directory)
- Make git commits
- Modify configuration files

**Prototype location:** Any prototyping tasks must write to `.claude/jons-plan/plans/[plan-name]/prototypes/` — never to the main codebase.

## Topic

{{#if args}}
{{args}}
{{else}}
No topic provided. Ask the user what they want to explore and design.
{{/if}}

## Workflow

### Step 1: Derive Plan Name (Enforce -design Suffix)

Convert topic to kebab-case and **always append `-design` suffix**:
- "authentication strategy" → "authentication-strategy-design"
- "api-redesign" → "api-redesign-design"
- "caching" → "caching-design"

If the user provides a name already ending in `-design`, use it as-is.

### Step 2: Define Scope

Clarify the boundaries of the design exploration:
- What is in scope vs out of scope?
- What constraints must be respected?
- What are the success criteria for a good design?

Use AskUserQuestion to clarify any ambiguities before proceeding.

### Step 3: Initial Understanding

Launch up to 3 Explore agents IN PARALLEL to understand the problem space *enough to plan the tasks*:
- **Codebase exploration**: What exists today? What patterns are used?
- **External research**: What are the common approaches to this problem?
- **Requirements gathering**: What must the solution achieve?

**Model guidance**: Use `haiku` for all Explore agents (fast, cheap discovery).

This step gathers enough context to create a good task list. The detailed research happens during execution.

### Step 4: Identify Research Tasks

Based on initial understanding, determine what research tasks the plan needs:
- What areas of the codebase need thorough exploration?
- What external APIs, libraries, or patterns should be researched?
- What prototypes might help validate assumptions?
- What perspectives should be analyzed?

Don't do the research now — create tasks that will do it during execution.

### Step 5: Plan External Review

Include external review tasks using `gemini-reviewer` and `codex-reviewer` if available:
- These provides critical feedback from an outside perspective
- The reviews should happen after research tasks complete

### Step 6: Plan Synthesis

The final tasks should:
1. Synthesize all research findings (use `opus` model)
2. Write the `design.md` document to the plan directory

### Step 7: Create Plan Infrastructure

1. Ensure `.claude/jons-plan/` is in `.git/info/exclude` (do NOT modify `.gitignore`)
2. Create directory: `.claude/jons-plan/plans/[name]-design/`
3. Create `plan.md` with the design exploration plan
4. Create `tasks.json` with task list (all tasks start with `status: "todo"`)
5. Create `claude-progress.txt` with initial entry
6. Write plan name to `.claude/jons-plan/active-plan`

### Step 8: Present Summary

- Show plan name and task count
- List tasks with their dependencies
- Explain that final deliverable is `design.md`
- Tell user: "Type `/jons-plan:proceed` to execute the design exploration, or `/jons-plan:plan [feedback]` to refine."

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
| `status` | Yes | Always `"todo"` when creating |
| `subagent` | No | `Explore`, `general-purpose`, `gemini-reviewer`, `codex-reviewer` |
| `subagent_prompt` | No | Thoroughness hint (e.g., "very thorough analysis") — NOT for reviewers |
| `model` | No | `haiku` (exploration), `sonnet` (default), `opus` (synthesis) — NOT for reviewers |

### Example Task

```json
{
  "id": "research-codebase-patterns",
  "description": "Research existing patterns in the codebase related to the design topic",
  "subagent": "Explore",
  "subagent_prompt": "very thorough analysis",
  "model": "haiku",
  "parents": [],
  "steps": [
    "Find all files related to [topic]",
    "Document existing architecture patterns",
    "Identify constraints and conventions",
    "Write findings to task output directory"
  ],
  "status": "todo"
}
```

## Design Plan Task Types

| Task Type | `subagent` | `subagent_prompt` | `model` |
|-----------|------------|-------------------|---------|
| Quick codebase lookup | `Explore` | `quick search` | `haiku` |
| Thorough codebase research | `Explore` | `very thorough analysis` | `haiku` |
| External API/library research | `Explore` | `thorough web research` | `haiku` |
| Prototyping spike | (omit) | (omit) | `sonnet` |
| Trade-off analysis | (omit) | (omit) | `opus` |
| External review | `gemini-reviewer` or `codex-reviewer` | (omit) | (omit) |
| Design synthesis | (omit) | (omit) | `opus` |

**Important for reviewer tasks:**
- Do NOT include `model` field (reviewers use their own external models)
- Do NOT include `subagent_prompt` field (not used for reviewers)

## Recommended Task Structure

A well-structured design plan typically includes:

1. **Research tasks** (parallel, haiku/Explore)
   - Codebase exploration
   - External research (APIs, libraries, patterns)
   - Requirements analysis

2. **External review task** (gemini-reviewer or codex-reviewer)
   - Review research findings
   - Identify gaps and blind spots

3. **Synthesis task** (opus, depends on research + review)
   - Combine all findings
   - Document trade-offs
   - Write draft design

4. **Final design task** (opus)
   - Produce `design.md` in plan directory
   - Include implementation outline for next phase

## design.md Structure

The final `design.md` should include these sections:

```markdown
# Design: [Topic]

## Problem Statement
What problem are we solving? Why does it matter?

## Constraints
Non-negotiable requirements, technical limitations, and boundaries.

## Research Findings
Key discoveries from codebase exploration and external research.

## Considered Approaches
Options evaluated with pros/cons for each.

## Recommended Approach
The chosen path with clear rationale.

## Trade-offs Acknowledged
What we're accepting by choosing this approach.

## Implementation Outline
High-level tasks for the implementation phase.

## Open Questions
Remaining uncertainties to resolve during implementation.
```

## Parallelization Rules

Design tasks are often safe to parallelize since research tasks typically don't modify files:

**Safe to parallelize** (no parent dependency needed):
- Different research explorations (codebase, external APIs, etc.)
- Independent prototyping spikes (each writes to its own subdirectory in `prototypes/`)
- Multiple reviewer perspectives on the same material

**Must be sequential** (add parent dependency):
- Synthesis depends on all research completing
- Final design depends on synthesis
- Refinement depends on external review feedback

## Important Reminders

- You are creating a **plan**, not doing the research — the work happens during `/proceed`
- NEVER implement production code — this is a design plan
- Prototypes must go in `.claude/jons-plan/plans/[plan-name]/prototypes/`
- Keep `plan.md` and `tasks.json` in sync
- Use `haiku` for exploration tasks, `opus` for synthesis
- Include an external review task (ask user which reviewer to use)
- All tasks start with `status: "todo"`
- Final deliverable is `design.md`, not code changes
