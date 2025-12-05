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

Launch Explore agents to understand the problem space *enough to plan the tasks*. **You decide** how many agents and what each explores based on the topic.

**Common exploration angles:**
- **Codebase exploration** — What exists today? What patterns are used?
- **External research** — What are the common approaches to this problem?
- **Requirements gathering** — What must the solution achieve?
- **API/library research** — What tools or integrations are relevant?
- **Prototyping** — Quick spikes to validate assumptions (write to `prototypes/` in plan directory)

**Launch agents appropriately:**
- Run independent explorations in parallel for speed
- Chain explorations that depend on each other if needed
- Use more agents for complex topics with many angles
- Use fewer for focused topics with clear scope

**Model guidance**: Use `haiku` for all Explore agents (fast, cheap discovery).

This step gathers enough context to create a good task list. The detailed research happens during execution.

### Step 4: Identify Research Tasks

Based on initial understanding, determine what research tasks the plan needs:
- What areas of the codebase need thorough exploration?
- What external APIs, libraries, or patterns should be researched?
- What prototypes might help validate assumptions?
- What perspectives should be analyzed?

Don't do the research now — create tasks that will do it during execution.

### Step 5: Plan Draft Synthesis

After research tasks, add a **draft-synthesis** task that:
1. Synthesizes all research findings into a draft design (use `opus` model)
2. Provides a confidence score (1-5) with rationale
3. Stops and uses AskUserQuestion if confidence < 4

### Step 6: Plan External Review

Include external review tasks using `gemini-reviewer` and `codex-reviewer` if available:
- These provide critical feedback from an outside perspective
- The reviews should happen after draft-synthesis completes

### Step 7: Plan Feedback Processing

Add a **process-feedback** task that:
1. Reads feedback from external reviewers
2. Categorizes feedback as ACCEPT/INVESTIGATE/REJECT
3. Can **dynamically add investigation tasks** if needed
4. Updates final-synthesis parents to include any new tasks
5. Provides confidence score; stops if < 4

### Step 8: Plan Final Synthesis

The final synthesis task should:
1. Read draft design, categorized feedback, and any investigation outputs
2. Incorporate accepted feedback and investigation findings
3. Provide final confidence score (1-5); stop if < 4
4. Write the `design.md` document to the plan directory

### Step 9: Create Plan Infrastructure

1. Ensure `.claude/jons-plan/` is in `.git/info/exclude` (do NOT modify `.gitignore`)
2. Create directory: `.claude/jons-plan/plans/[name]-design/`
3. Create `plan.md` with the design exploration plan
4. Create `tasks.json` with task list (all tasks start with `status: "todo"`)
5. Create `claude-progress.txt` with initial entry
6. Write plan name to `.claude/jons-plan/active-plan`

### Step 10: Present Summary

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

2. **Draft synthesis task** (opus, depends on research)
   - Synthesize research findings
   - Provide confidence score
   - Write draft-design.md

3. **External review tasks** (gemini-reviewer and/or codex-reviewer)
   - Review draft design
   - Identify gaps, risks, and blind spots

4. **Process feedback task** (opus, depends on reviews)
   - Categorize feedback as ACCEPT/INVESTIGATE/REJECT
   - Dynamically add investigation tasks if needed
   - Update final-synthesis parents

5. **Final synthesis task** (opus, depends on process-feedback)
   - Incorporate feedback and investigations
   - Provide final confidence score
   - Produce `design.md` in plan directory

## Core Task Templates

### Draft Synthesis Task

```json
{
  "id": "draft-synthesis",
  "description": "Synthesize research findings into draft design",
  "model": "opus",
  "parents": ["research-codebase", "research-external"],
  "steps": [
    "Read all research findings from parent task outputs",
    "Synthesize into coherent draft design approach",
    "Identify any areas of uncertainty",
    "Record confidence score using: uv run ~/.claude-plugins/jons-plan/plan.py record-confidence draft-synthesis <score> '<rationale>'",
    "If confidence < 4: STOP and use AskUserQuestion to discuss concerns with user",
    "Write draft-design.md to task output directory"
  ],
  "status": "todo"
}
```

### Process Feedback Task (Dynamic Task Modification)

This task has special capabilities to modify the task graph:

```json
{
  "id": "process-feedback",
  "description": "Process reviewer feedback and update task graph if needed",
  "model": "opus",
  "parents": ["gemini-review", "codex-review"],
  "steps": [
    "Read feedback from parent review tasks",
    "For each piece of feedback, categorize as:",
    "  - ACCEPT: Will incorporate in final design",
    "  - INVESTIGATE: Needs more research before deciding",
    "  - REJECT: Explain why not applicable",
    "Record confidence score for categorization decisions",
    "If confidence < 4: STOP and use AskUserQuestion",
    "If INVESTIGATE items exist, dynamically add investigation tasks (see Dynamic Task Modification below)",
    "Write categorized-feedback.md to task output directory"
  ],
  "status": "todo"
}
```

### Final Synthesis Task

```json
{
  "id": "final-synthesis",
  "description": "Produce final design document",
  "model": "opus",
  "parents": ["process-feedback"],
  "steps": [
    "Read draft-design.md from draft-synthesis task output",
    "Read categorized-feedback.md from process-feedback task output",
    "Check for and read any investigation task outputs (from dynamically added tasks)",
    "Incorporate all ACCEPT feedback items",
    "Integrate investigation findings where applicable",
    "Record final confidence score",
    "If confidence < 4: STOP and use AskUserQuestion to discuss remaining concerns",
    "Write final design.md to plan directory (not task output)"
  ],
  "status": "todo"
}
```

## Dynamic Task Modification

The `process-feedback` task can modify the task graph at runtime. This enables the plan to evolve based on reviewer feedback.

### When to Add Investigation Tasks

Add investigation tasks when reviewer feedback:
- Raises valid technical concerns that need verification
- Identifies gaps that require additional research
- Questions assumptions that weren't validated in initial research

Do NOT add tasks for:
- Feedback that can be addressed directly in final synthesis
- Nitpicks or style preferences
- Suggestions already covered by existing research

### How to Add Investigation Tasks

Use the CLI to add tasks and update dependencies:

```bash
# 1. Add a new investigation task
echo '{
  "id": "investigate-scaling",
  "description": "Investigate scaling concerns raised by reviewer",
  "subagent": "Explore",
  "subagent_prompt": "thorough analysis",
  "model": "haiku",
  "parents": ["process-feedback"],
  "steps": [
    "Research the specific scaling concern",
    "Analyze current codebase for related patterns",
    "Document findings and recommendations"
  ],
  "status": "todo"
}' | uv run ~/.claude-plugins/jons-plan/plan.py add-task -

# 2. Update final-synthesis to depend on the new task
uv run ~/.claude-plugins/jons-plan/plan.py update-task-parents final-synthesis process-feedback investigate-scaling
```

### JSON Structure for New Tasks

Investigation tasks should follow this pattern:

```json
{
  "id": "investigate-[topic]",
  "description": "Investigate [specific concern from reviewer]",
  "subagent": "Explore",
  "subagent_prompt": "thorough analysis",
  "model": "haiku",
  "parents": ["process-feedback"],
  "steps": [
    "Research [specific aspect]",
    "Analyze [relevant code/docs]",
    "Document findings with recommendations"
  ],
  "status": "todo"
}
```

### CLI Commands for Dynamic Modification

| Command | Description |
|---------|-------------|
| `add-task <json_file>` | Add task from JSON file or stdin (`-`) |
| `update-task-parents <task_id> <parent_ids...>` | Set new parent dependencies |
| `update-task-steps <task_id> <json_file>` | Update task steps from JSON |
| `record-confidence <task_id> <score> <rationale>` | Record confidence (1-5) |

### Example: Multiple Investigations

If reviewers raise multiple concerns:

```bash
# Add first investigation
echo '{"id": "investigate-auth", "description": "...", ...}' | uv run ~/.claude-plugins/jons-plan/plan.py add-task -

# Add second investigation
echo '{"id": "investigate-perf", "description": "...", ...}' | uv run ~/.claude-plugins/jons-plan/plan.py add-task -

# Update final-synthesis to depend on both (plus process-feedback)
uv run ~/.claude-plugins/jons-plan/plan.py update-task-parents final-synthesis process-feedback investigate-auth investigate-perf
```

## Confidence Scoring

Design tasks should record confidence scores to surface uncertainty early.

### Recording Confidence

```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-confidence <task-id> <score> "<rationale>"
```

Score meanings:
- **5** - Very confident, no concerns
- **4** - Confident, minor uncertainties that won't block progress
- **3** - Moderate confidence, some concerns that should be discussed
- **2** - Low confidence, significant concerns
- **1** - Not confident, major blockers or missing information

### Confidence Gating

When confidence < 4, the task should:
1. **NOT** mark itself as done
2. Use `AskUserQuestion` to discuss concerns with user
3. Wait for user input before proceeding

Example in task steps:
```
"Record confidence score using record-confidence CLI",
"If confidence < 4: STOP and use AskUserQuestion to surface concerns",
"Only proceed to write output if confidence >= 4"
```

### Checking Confidence

```bash
# Check a specific task's confidence
uv run ~/.claude-plugins/jons-plan/plan.py check-confidence <task-id>

# List all tasks with low confidence
uv run ~/.claude-plugins/jons-plan/plan.py low-confidence-tasks
```

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
