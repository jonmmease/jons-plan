---
description: Create implementation plan with deep automated exploration
allowed-tools: "*"
---

## FIRST: Set Session Mode

Before doing anything else, set the session mode so compaction recovery works correctly:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-mode new-deep
```

Run this command NOW before proceeding.

---

ultrathink

# Create Implementation Plan with Deep Exploration

You are creating an **implementation plan** using a multi-phase automated exploration and review process. This command combines the exploration depth of `/jons-plan:new-design` with the final output of `/jons-plan:new`.

**Key difference from other commands:**
- `/new` — Light exploration, creates implementation plan quickly
- `/new-design` — Creates tasks for later execution, produces design.md
- `/new-deep` — **Auto-executes** exploration and review phases, produces implementation plan

The phases below run within this single command invocation. You do NOT create tasks for phases 1-4; you execute them directly.

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore agents for research
- Launch gemini-reviewer and codex-reviewer for reviews
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
No topic provided. Ask the user what they want to implement.
{{/if}}

## Workflow Overview

```
Phase 1: Exploration (haiku agents)
└─ Launch exploration agents as needed for the topic

Phase 2: Draft Plan Synthesis (opus)
└─ Combine explorations into draft implementation plan

Phase 3: External Review (parallel)
├─ gemini-reviewer: Structure, completeness, blind spots
└─ codex-reviewer: Technical approach, architecture

Phase 4: Final Synthesis (opus)
└─ Consider review feedback, produce final plan

Phase 5: Create Plan Infrastructure
└─ Write plan.md, tasks.json, set active plan
```

---

## Phase 1: Exploration

Launch exploration agents using `haiku` model to understand the problem space. **You decide** how many agents to launch and what each explores based on the topic's complexity.

### Guidance

**Determine what needs exploration** for this specific topic. Common angles include:
- **Codebase patterns** — Existing implementations, architectural conventions, file organization
- **External approaches** — Web research on best practices, libraries, how others solve this
- **Requirements analysis** — Constraints, edge cases, acceptance criteria
- **Prototyping** — Quick spikes to validate assumptions (write to plan directory only)
- **API/library research** — Documentation, capabilities, integration patterns
- **Performance considerations** — Bottlenecks, scaling concerns, benchmarks

**Launch agents appropriately:**
- Run independent explorations in parallel for speed
- Chain explorations that depend on each other (e.g., "research library X" → "prototype with library X")
- Use more agents for complex topics with many angles
- Use fewer for focused topics with clear scope

### Example Exploration Patterns

**Simple feature** (2-3 agents):
- Codebase patterns + requirements analysis

**Integration feature** (3-4 agents):
- Codebase patterns + external API docs + requirements + compatibility research

**Architectural change** (4-6 agents):
- Current architecture analysis + alternative approaches research + performance implications + migration patterns + requirements

**Wait for all explorations to complete before proceeding.**

Collect the findings from each exploration for use in Phase 2.

---

## Phase 2: Draft Plan Synthesis

Using the exploration findings, synthesize a **draft implementation plan**.

This phase runs as the main agent (you), using opus-level reasoning.

### Synthesis Process

1. **Identify key insights** from each exploration:
   - What patterns should the implementation follow?
   - What external approaches are most relevant?
   - What requirements are most critical?

2. **Determine implementation approach**:
   - What is the recommended architecture?
   - What are the main components/changes needed?
   - What is the logical order of implementation?

3. **Draft task breakdown**:
   - Break the work into discrete, testable tasks
   - Identify dependencies between tasks
   - Estimate complexity (guides model selection)

4. **Write draft plan** to a temporary location:
   - Save to `.claude/jons-plan/plans/[plan-name]/draft-plan.md`
   - Include: overview, approach, task list, open questions

---

## Phase 3: External Review

Launch **2 reviewer agents IN PARALLEL**:

### 3.1 Gemini Reviewer
```
subagent_type: gemini-reviewer

Review the draft plan at: .claude/jons-plan/plans/[plan-name]/draft-plan.md

Focus on:
- Is the plan complete? Any missing steps?
- Are there blind spots or unconsidered edge cases?
- Is the task breakdown logical and well-sequenced?
- Are dependencies correctly identified?
- Any structural improvements to suggest?
```

### 3.2 Codex Reviewer
```
subagent_type: codex-reviewer

Review the draft plan at: .claude/jons-plan/plans/[plan-name]/draft-plan.md

Focus on:
- Is the technical approach sound?
- Are there better architectural choices?
- Any potential implementation pitfalls?
- Are the tasks appropriately scoped?
- Any code organization concerns?
```

**Wait for both reviews to complete before proceeding.**

Collect the feedback from each reviewer for use in Phase 4.

---

## Phase 4: Final Synthesis

Consider the review feedback and produce the final implementation plan.

This phase runs as the main agent (you), using opus-level reasoning.

### Refinement Process

1. **Evaluate feedback**:
   - What critiques are valid and should be addressed?
   - What suggestions improve the plan?
   - What feedback can be noted but doesn't require changes?

2. **Refine the plan**:
   - Address valid concerns
   - Incorporate useful suggestions
   - Resolve any conflicting feedback between reviewers
   - Ensure task dependencies are correct

3. **Finalize task list**:
   - Ensure all tasks are well-defined
   - Verify parallelization safety (see rules below)
   - Assign appropriate models to tasks

---

## Phase 5: Create Plan Infrastructure

### Step 5.1: Derive Plan Name

Convert topic to kebab-case:
- "authentication system" → "authentication-system"
- "API rate limiting" → "api-rate-limiting"

### Step 5.2: Ensure Git Exclusion

Check that `.claude/jons-plan/` is in `.git/info/exclude`. If not, add it.

### Step 5.3: Create Plan Directory

```bash
mkdir -p .claude/jons-plan/plans/[plan-name]
```

### Step 5.4: Write Plan Files

Create these files in the plan directory:

**plan.md** — The implementation plan with:
- Overview of what's being built
- Key design decisions and rationale
- Summary of exploration findings
- Notes from external reviews

**tasks.json** — Task list following schema below

**claude-progress.txt** — Initial entry:
```
[timestamp] Plan created via /jons-plan:new-deep
[timestamp] Exploration phases completed: [list what was explored]
[timestamp] Reviews: gemini-reviewer, codex-reviewer
```

### Step 5.5: Set Active Plan

```bash
echo "[plan-name]" > .claude/jons-plan/active-plan
```

### Step 5.6: Clean Up

Remove the draft plan file:
```bash
rm .claude/jons-plan/plans/[plan-name]/draft-plan.md
```

---

## Task Schema

The `tasks.json` file must be a JSON object with a `tasks` array:

```json
{
  "tasks": [
    { "id": "task-1", ... },
    { "id": "task-2", ... }
  ]
}
```

Each task follows this schema:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier (kebab-case) |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Array of task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Array of steps to complete the task |
| `status` | Yes | Always `"todo"` when creating |
| `subagent` | No | Agent type (default: `general-purpose`) |
| `subagent_prompt` | No | Additional context for the agent |
| `model` | No | `haiku`, `sonnet` (default), or `opus` |

### Example Task

```json
{
  "id": "implement-auth-middleware",
  "description": "Create authentication middleware for API routes",
  "model": "opus",
  "parents": ["setup-auth-types"],
  "steps": [
    "Create middleware function in src/middleware/auth.ts",
    "Implement token validation logic",
    "Add request context augmentation",
    "Export middleware for use in routes"
  ],
  "status": "todo"
}
```

---

## Parallelization Rules

Tasks without parent dependencies can run in parallel, but **only if they won't mutate files in the same directories**.

**Safe to parallelize** (no parent dependency needed):
- Research tasks that only write to their own `tasks/[task-id]/` output directory
- Monorepo tasks that modify separate packages
- Tasks that only read from the codebase without writing

**Must be sequential** (add parent dependency):
- Multiple tasks editing `src/` files
- Tasks that both modify config files
- Implementation tasks that build on each other's code

---

## Model Selection Guidelines

| Task Type | Recommended Model |
|-----------|-------------------|
| Simple file changes | `sonnet` (default) |
| Complex implementation | `opus` |
| Architecture decisions | `opus` |
| Boilerplate/scaffolding | `haiku` |
| Test writing | `sonnet` |
| Documentation | `haiku` |

---

## Handling Compaction

If context compaction occurs during any phase:

1. **Check session mode**: The `new-deep` mode will be detected by the session-start hook
2. **Resume current phase**: Continue from where you left off
3. **Reference saved artifacts**: Check for `draft-plan.md` or partial outputs
4. **Don't restart completed phases**: Use logged progress to determine state

---

## Command Comparison

| Aspect | `/new` | `/new-design` | `/new-deep` |
|--------|--------|---------------|-------------|
| Exploration | Light exploration | Creates tasks for later | Auto-executes exploration |
| External review | No | Creates review task | Auto-executes review |
| Synthesis | Single-shot | Task in plan | Multi-round with feedback |
| Output | Implementation plan | design.md | Implementation plan |
| User intervention | After planning | After each /proceed | After all phases complete |
| Best for | Simple features | Complex research | Complex implementation |

---

## Present Summary

After completing all phases, show:

1. Plan name and task count
2. Key insights from exploration
3. Notable feedback from reviewers
4. Task list with dependencies
5. Next step: "Type `/jons-plan:proceed` to implement, or `/jons-plan:plan [feedback]` to refine."

---

## Important Reminders

- Execute phases 1-4 directly — do NOT create tasks for them
- The only tasks in `tasks.json` are the **implementation tasks** from Phase 5
- All implementation tasks start with `status: "todo"`
- Use `haiku` for exploration, `opus` for synthesis
- Wait for parallel operations to complete before proceeding
- Save intermediate artifacts to the plan directory
- The final deliverable is plan.md + tasks.json (NOT design.md)
