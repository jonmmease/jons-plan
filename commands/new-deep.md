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

The phases below run within this single command invocation. You do NOT create tasks for phases 1-6; you execute them directly.

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
└─ Combine explorations into draft-plan.md with confidence score

Phase 3: External Review (parallel)
├─ gemini-reviewer: Structure, completeness, blind spots
└─ codex-reviewer: Technical approach, architecture

Phase 4: Feedback Processing (opus)
└─ Categorize feedback, assess confidence, user checkpoint if score < 4

Phase 5: Targeted Investigation (conditional, haiku)
└─ Explore INVESTIGATE items, write investigation-findings.md

Phase 6: Final Synthesis (opus)
└─ Integrate all artifacts, final confidence check

Phase 7: Create Plan Infrastructure
└─ Write plan.md, tasks.json, clean up drafts
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

Using the exploration findings, synthesize a **draft implementation plan** with confidence assessment.

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

4. **Assess confidence** in the draft plan:
   - Score each dimension 1-5
   - Identify areas of uncertainty
   - Note questions for reviewers

5. **Write draft plan** to a temporary location:
   - Save to `.claude/jons-plan/plans/[plan-name]/draft-plan.md`
   - Include: overview, approach, task list, open questions, AND confidence assessment

### Confidence Assessment Format

Include this section at the end of `draft-plan.md`:

```markdown
## Confidence Assessment

**Overall Score: [1-5]**

| Dimension | Score | Explanation |
|-----------|-------|-------------|
| Feasibility | [1-5] | Can this be implemented with the current codebase? |
| Scope | [1-5] | Is the scope well-defined and achievable? |
| Technical Risk | [1-5] | Are there unknowns or risky assumptions? |

**Areas of Uncertainty:**
- [List specific uncertainties to resolve via review]

**Questions for Reviewers:**
- [Specific questions you want external reviewers to address]
```

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

## Phase 4: Feedback Processing

Categorize the review feedback and assess confidence in proceeding.

This phase runs as the main agent (you), using opus-level reasoning.

### Categorization Process

1. **For each reviewer's feedback**, categorize each point as:
   - **ACCEPT** — Valid feedback that should be incorporated into the plan
   - **INVESTIGATE** — Raises a question that needs exploration before deciding
   - **REJECT** — Doesn't apply to this context or is based on misunderstanding

2. **Assess overall confidence** in proceeding:
   - Score 1-5 based on how well feedback was understood and addressed
   - Low scores indicate unresolved concerns needing user input

3. **Write categorized feedback** to `.claude/jons-plan/plans/[plan-name]/categorized-feedback.md`

### Categorized Feedback Format

```markdown
# Categorized Feedback

## Confidence: [1-5]
[Brief rationale for the confidence score]

## Source: gemini-reviewer

### ACCEPT
- [Feedback point]: [How this will be addressed in the plan]
- [Feedback point]: [How this will be addressed in the plan]

### INVESTIGATE
- [Feedback point]: [Question that needs exploration]
  - Domain: codebase|technical|requirements
  - Specific question: "[Precise question for an explore agent]"

### REJECT
- [Feedback point]: [Why this doesn't apply or is incorrect]

## Source: codex-reviewer

### ACCEPT
- [Feedback point]: [How this will be addressed in the plan]

### INVESTIGATE
- [Feedback point]: [Question that needs exploration]
  - Domain: codebase|technical|requirements
  - Specific question: "[Precise question for an explore agent]"

### REJECT
- [Feedback point]: [Why this doesn't apply or is incorrect]

## Investigation Questions Summary

**Codebase questions:**
- [Question 1]
- [Question 2]

**Technical questions:**
- [Question 1]

**Requirements questions:**
- [Question 1]
```

### User Checkpoint (if confidence < 4)

**If your confidence score is below 4**, you MUST stop and discuss concerns with the user before proceeding.

Use `AskUserQuestion` to present the situation:

```
Question: "I have concerns about the implementation plan. How should I proceed?"

Options:
1. "Proceed anyway" - Continue despite concerns
2. "Investigate further" - Run targeted explorations
3. "Let's discuss" - Explain the concerns in detail
```

**Do NOT proceed to Phase 5 if confidence < 4 without user acknowledgment.**

---

## Phase 5: Targeted Investigation (Conditional)

**SKIP this phase if there are no INVESTIGATE items in categorized-feedback.md.**

For each INVESTIGATE question, launch a haiku exploration agent to find the answer.

### Investigation Process

1. **Parse investigation questions** from `categorized-feedback.md`

2. **Launch explore agents** for each question:
   - Use `haiku` model for efficiency
   - Group related questions if appropriate
   - Run independent investigations in parallel

3. **Collect findings** and write to `.claude/jons-plan/plans/[plan-name]/investigation-findings.md`

### Investigation Findings Format

```markdown
# Investigation Findings

## Question: [Original question from categorized-feedback.md]
**Domain:** codebase|technical|requirements
**Finding:** [What was discovered]
**Impact on Plan:** [How this affects the draft plan]
**Recommendation:** accept-feedback|reject-feedback|modify-approach

## Question: [Next question]
...
```

---

## Phase 6: Final Synthesis

Integrate all artifacts and produce the final implementation plan.

This phase runs as the main agent (you), using opus-level reasoning.

### Required Reading

Before synthesizing, read all available artifacts:
- `draft-plan.md` — Original plan with initial confidence assessment
- `categorized-feedback.md` — Processed reviewer feedback
- `investigation-findings.md` — (if exists) Results of targeted investigations

### Refinement Process

1. **Integrate accepted feedback**:
   - Incorporate all ACCEPT items from categorized-feedback.md
   - Address any concerns raised

2. **Apply investigation findings** (if any):
   - Update the plan based on what was discovered
   - Resolve INVESTIGATE items based on findings

3. **Finalize task list**:
   - Ensure all tasks are well-defined
   - Verify parallelization safety (see rules below)
   - Assign appropriate models to tasks

4. **Final confidence assessment**:
   - Score 1-5 confidence in the final plan
   - Document any remaining uncertainties

### Final Confidence Check

**If your final confidence score is below 4**, you MUST stop and discuss with the user.

Use `AskUserQuestion`:

```
Question: "The final plan has unresolved concerns. How should I proceed?"

Options:
1. "Create the plan anyway" - Accept the risks and proceed
2. "Let's discuss the concerns" - Explain what's uncertain
3. "Abandon this plan" - Start over with different approach
```

**Do NOT proceed to Phase 7 if final confidence < 4 without user acknowledgment.**

---

## Phase 7: Create Plan Infrastructure

### Step 7.1: Derive Plan Name

Convert topic to kebab-case:
- "authentication system" → "authentication-system"
- "API rate limiting" → "api-rate-limiting"

### Step 7.2: Ensure Git Exclusion

Check that `.claude/jons-plan/` is in `.git/info/exclude`. If not, add it.

### Step 7.3: Create Plan Directory

```bash
mkdir -p .claude/jons-plan/plans/[plan-name]
```

### Step 7.4: Write Plan Files

Create these files in the plan directory:

**plan.md** — The implementation plan with:
- Overview of what's being built
- Key design decisions and rationale
- Summary of exploration findings
- Notes from external reviews
- Final confidence assessment

**tasks.json** — Task list following schema below

**claude-progress.txt** — Initial entry:
```
[timestamp] Plan created via /jons-plan:new-deep
[timestamp] Exploration phases completed: [list what was explored]
[timestamp] Reviews: gemini-reviewer, codex-reviewer
[timestamp] Final confidence: [score]/5
```

### Step 7.5: Set Active Plan

```bash
echo "[plan-name]" > .claude/jons-plan/active-plan
```

### Step 7.6: Clean Up Draft Artifacts

Remove all intermediate artifacts:
```bash
rm -f .claude/jons-plan/plans/[plan-name]/draft-plan.md
rm -f .claude/jons-plan/plans/[plan-name]/categorized-feedback.md
rm -f .claude/jons-plan/plans/[plan-name]/investigation-findings.md
```

These artifacts are temporary working files. The final `plan.md` contains all relevant information.

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
3. **Reference saved artifacts**: Check for these files to determine state:
   - `draft-plan.md` — Phase 2 complete
   - `categorized-feedback.md` — Phase 4 complete
   - `investigation-findings.md` — Phase 5 complete (if it was needed)
4. **Don't restart completed phases**: Use logged progress and artifact presence to determine state

---

## Command Comparison

| Aspect | `/new` | `/new-design` | `/new-deep` |
|--------|--------|---------------|-------------|
| Exploration | Light exploration | Creates tasks for later | Auto-executes exploration |
| External review | No | Creates review task | Auto-executes review |
| Synthesis | Single-shot | Task in plan | Multi-round with feedback |
| Confidence checks | No | No | Yes (phases 4 and 6) |
| Output | Implementation plan | design.md | Implementation plan |
| User intervention | After planning | After each /proceed | After all phases complete (or at confidence checkpoints) |
| Best for | Simple features | Complex research | Complex implementation |

---

## Present Summary

After completing all phases, show:

1. Plan name and task count
2. Final confidence score
3. Key insights from exploration
4. Notable feedback from reviewers (accepted items)
5. Task list with dependencies
6. Next step: "Type `/jons-plan:proceed` to implement, or `/jons-plan:plan [feedback]` to refine."

---

## Important Reminders

- Execute phases 1-6 directly — do NOT create tasks for them
- The only tasks in `tasks.json` are the **implementation tasks** from Phase 7
- All implementation tasks start with `status: "todo"`
- Use `haiku` for exploration, `opus` for synthesis and feedback processing
- Wait for parallel operations to complete before proceeding
- Save intermediate artifacts to the plan directory (cleaned up in Phase 7)
- Stop and ask user if confidence score < 4 at checkpoints (phases 4 and 6)
- The final deliverable is plan.md + tasks.json (NOT design.md)
