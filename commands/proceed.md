---
description: Start implementing tasks from the active jons-plan
allowed-tools: "*"
---

# Implement Tasks

You are implementing tasks from the active jons-plan.

## Arguments

{{#if args}}
Arguments provided: `{{args}}`
{{/if}}

### Numeric Phase Selection

If the arguments start with a number (e.g., `/jons-plan:proceed 1` or `/jons-plan:proceed 2 focus on error handling`):

1. Parse the number and optional guidance text
2. Call the CLI to transition to that phase:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase-by-number <number> "<guidance>"
   ```
3. Continue with normal phase execution below

This is used when a phase presents numbered options (like `suggested_next` transitions) and the user selects one.

## Check Active Plan

First, read `.claude/jons-plan/active-plan` to get the active plan name.

If the file is empty or missing:
- Tell user: "No active plan. Use `/jons-plan:new [topic]` to create one."
- Stop here - do not proceed further.

## Set Session Mode

Set the session mode to `proceed` so hooks know we're implementing:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-mode proceed
```

## Check for Blocked Tasks

Before proceeding, check if any tasks are blocked:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py has-blockers
```

If exit code is 0 (has blockers):
- Run `uv run ~/.claude-plugins/jons-plan/plan.py blocked-tasks` to list them
- Tell user: "Cannot proceed - blocked tasks require attention. Run `/jons-plan:plan` to review blockers and update the plan."
- **STOP HERE** - do not proceed with any tasks

## Phase-Based Execution

Tasks are scoped to the **current phase** of the workflow.

### When to Ask Questions vs. Document and Continue

**Do NOT use AskUserQuestion** during task execution unless the phase has `requires_user_input: true`. Most phases should:
- Complete the work autonomously
- Document findings, trade-offs, and recommendations in artifacts
- Transition to the next phase where decisions are made

**Research phases** gather information and document options - they don't ask for decisions.
**Draft phases** produce artifacts based on research - they don't ask for approval.
**Review phases** provide feedback - they don't ask for direction.
**User-decision phases** (with `requires_user_input: true`) are where you stop and ask for user input.

If you're unsure whether to ask, **don't ask** - document your recommendation and continue.

### Execution Steps

1. **Get current phase context**:

   **Skip this step if you see "Current Phase Context" section above** - it was already injected.

   Otherwise, run:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-context
   ```
   This shows the phase prompt, input artifacts, and task execution instructions.

2. **Follow the phase prompt**: The phase context includes all task execution guidance assembled based on the workflow configuration.

3. **Create or check phase tasks**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-tasks-file
   uv run ~/.claude-plugins/jons-plan/plan.py phase-tasks
   ```

   **If tasks.json already has tasks** (some phases auto-seed required tasks on entry):
   1. Read the existing tasks to understand what's configured
   2. Note task configurations like `prompt_file`, `subagent`, `model` - these are intentional
   3. Add your own tasks if needed using the `add-task` command:
      ```bash
      echo '{"id": "my-task", "description": "...", "status": "todo", "parents": [], "steps": [...]}' | uv run ~/.claude-plugins/jons-plan/plan.py add-task -
      ```
   4. Do NOT modify the required tasks' `prompt_file`, `subagent`, or `model` fields

   **If tasks.json doesn't exist or is empty**, create it using the Write tool.
   The file will be validated automatically - invalid content will be rejected with helpful error messages.

   **Task Schema** (required fields marked with *):
   ```json
   [
     {
       "id": "task-id",           // *lowercase alphanumeric with hyphens
       "description": "...",      // *what the task accomplishes
       "status": "todo",          // *one of: todo, in-progress, done, blocked
       "steps": ["step 1", ...],  // ordered list of steps
       "parents": ["other-id"],   // task IDs that must complete first
       "subagent": "Explore",     // agent type (Explore, general-purpose)
       "model": "sonnet",         // optional: sonnet, haiku, opus
       "locks": ["cargo"]         // optional: exclusive access (files, tools, resources)
     }
   ]
   ```

   **Guidelines:**
   - ~10 steps max per task
   - Scope research to single topic, implementation to single file or related files
   - Use appropriate subagents (Explore for research, general-purpose for implementation)

   **After tasks exist**, check what's available:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-next-tasks
   ```

   Execute tasks from the phase's tasks.json using the Task Execution Loop below.

### Task Execution Loop

For each available task:

1. **Set status to in-progress**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> in-progress
   ```

2. **Execute the task steps**: Work through each step in the task's `steps` array.

3. **Log progress** as you work:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "Completed step: ..."
   ```

4. **On successful completion**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> done
   ```

5. **If task cannot be completed** (see When to Block below):
   - Create blockers.md explaining the issue
   - Mark as blocked and transition to planning

### Valid Task Statuses

There are exactly **four valid statuses**. You MUST use only these:

| Status | Meaning |
|--------|---------|
| `todo` | Not yet started |
| `in-progress` | Currently being worked on |
| `done` | Successfully completed |
| `blocked` | Cannot proceed - requires replanning |

**CRITICAL**: Never invent new statuses. "deferred", "skipped", "partial", etc. are NOT valid.

### When to Mark a Task as Blocked

Mark a task as `blocked` when you encounter issues that **require replanning**:

1. **Scope exceeded**: Task is much larger than anticipated and needs decomposition
2. **Missing prerequisites**: Required dependency, API, or resource isn't available
3. **Technical impossibility**: The approach described won't work
4. **Unclear requirements**: Task steps are ambiguous and you cannot make a reasonable choice
5. **External blockers**: Need user input, permissions, or third-party action

**Do NOT mark as blocked for:**
- Errors you can fix by trying a different approach
- Missing information you can find by exploring the codebase
- Test failures that just need debugging

### Scope Exceeded Handling

**When you realize a task is too large to complete:**

1. **Stop working on the task immediately** - do not attempt partial completion

2. **Create blockers.md** in the task directory:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```

   Write to `$TASK_DIR/blockers.md`:
   ```markdown
   # Blocker Report: <task-id>

   ## Scope Assessment

   Task requires significantly more work than anticipated:
   - Estimated: <original scope>
   - Actual: <discovered scope>

   ## Work Completed

   <what was accomplished before stopping>

   ## Recommended Decomposition

   Suggest breaking into these subtasks:
   1. <subtask 1>
   2. <subtask 2>
   3. ...
   ```

3. **Mark task as blocked**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> blocked
   ```

4. **Transition back to planning phase**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py suggested-next
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase plan --reason "Task <task-id> requires decomposition"
   ```

5. **STOP execution** - Do not continue with other tasks. The plan needs to be updated.

**NEVER do these when scope is exceeded:**
- Invent new statuses like "deferred" or "partial"
- Manually edit state.json to skip phases
- Mark the task as "done" with incomplete work
- Continue to other tasks without addressing the blocker

### Phase Re-entry (Loopback) Requirements

When looping back to a phase that was previously entered (re-entry), you **MUST** provide detailed context via `--reason-file`. This is required because:
- The re-entered phase needs to understand what went wrong
- Without context, it will likely repeat the same mistakes
- Detailed analysis helps identify what to do differently

**Steps to loop back:**

1. **Write a detailed markdown file** explaining the re-entry:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <current-task-id>)
   ```

   Write to `$TASK_DIR/reentry-analysis.md`:
   ```markdown
   ## Why Previous Attempt Failed
   <Specific issues that prevented success>

   ## What Was Learned
   <Key insights from the failed attempt>

   ## What Should Be Done Differently
   <Concrete changes to approach>

   ## Specific Issues to Address
   <Actionable items for the re-entered phase>
   ```

2. **Call enter-phase with --reason-file**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <phase-id> --reason-file "$TASK_DIR/reentry-analysis.md"
   ```

The file must be at least 100 characters to ensure sufficient detail.

4. **After phase tasks complete**:
   - Check `suggested-next` for the next phase
   - If phase has `requires_user_input: true`, set mode to `awaiting-feedback` and stop
   - Otherwise, transition to the next phase:
     ```bash
     uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <next-phase-id>
     ```

5. **Handling Expandable Phases (`__expand__` in suggested-next)**:

   If `suggested-next` returns `__expand__` (or includes it as an option):

   a. **Decide whether to expand**:
      - If research revealed simple changes → go to `complete` instead
      - If multiple components or unclear scope → proceed with expansion

   b. **Build the expansion prompt**:
      ```bash
      uv run ~/.claude-plugins/jons-plan/plan.py build-expand-prompt
      ```
      This outputs guidance with reference workflow templates.

   c. **Generate phases**:
      Based on your research findings and the expand_prompt guidance, generate a JSON structure with phases. Each phase must have `suggested_next` pointing to the next phase.

      **Phase transition format:**
      - Use strings for simple forward transitions: `"implement"`
      - Use objects for transitions requiring approval (typically loopbacks):
        ```json
        { "phase": "research", "requires_approval": true, "approval_prompt": "Return to research?" }
        ```

   d. **Preview with dry-run**:
      ```bash
      echo '<your-json>' | uv run ~/.claude-plugins/jons-plan/plan.py expand-phase --dry-run
      ```

   e. **Present to user for confirmation**:
      Show the planned workflow with a diagram and ask for confirmation using `AskUserQuestion`.

   f. **Expand the workflow**:
      ```bash
      echo '<your-json>' | uv run ~/.claude-plugins/jons-plan/plan.py expand-phase
      ```
      This backs up the workflow, injects new phases, and records the expansion.

   g. **Continue with generated phases**:
      ```bash
      uv run ~/.claude-plugins/jons-plan/plan.py suggested-next
      uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <first-generated-phase>
      ```

   **Rollback if needed**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py rollback-expansion
   ```

6. **On terminal phase**:
   The workflow is complete. Show summary and allow stop.

7. **Recording dead-ends**:
   If an approach fails, record it so it's not repeated:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py add-dead-end --task-id <id> --what-failed "..." --why-failed "..." --type WRONG_ASSUMPTION
   ```

## Progress Logging

### Task-Level Logging (Required)

During task execution, log key actions to enable resumption and provide visibility:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "<message>"
```

**What to log:**
- **File modifications**: `"Edited src/auth.py: Added login validation"`
- **Key decisions**: `"Chose JWT over sessions for stateless auth"`
- **Blockers encountered**: `"BLOCKED: Missing database schema for users table"`
- **Completion summary**: `"Implemented auth middleware with token validation"`

**Example log sequence:**
```bash
task-log implement-auth "Starting auth implementation"
task-log implement-auth "Edited src/middleware/auth.py: Created AuthMiddleware class"
task-log implement-auth "Edited src/routes/login.py: Added /login endpoint"
task-log implement-auth "Chose bcrypt for password hashing (industry standard)"
task-log implement-auth "Added tests in tests/test_auth.py"
task-log implement-auth "Complete: Auth middleware with JWT tokens and login endpoint"
```

### Phase-Level Logging

Log significant phase-level progress and decisions:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py phase-log "<message>"
```

Use for cross-task observations, phase decisions, and major milestones.

### Plan-Level Logging

Log high-level progress visible across sessions:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py log "Completed task X: brief description"
```

### Decision Logging

When making significant technical choices, log them with context so future phases (especially loopbacks) understand why an approach was chosen.

**Use this format for decisions:**
```
DECISION: <what you chose>
  Context: <why this choice was made>
  Alternatives: <what was rejected and why>
```

**Task-level decisions:**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "DECISION: Chose SQLite over PostgreSQL. Context: Single-user app, no concurrent writes needed. Alternatives: PostgreSQL (rejected: overkill for this use case)"
```

**Plan-level decisions:**
```bash
uv run ~/.claude-plugins/jons-plan/plan.py log "DECISION: Using JWT for auth. Context: Need stateless auth for horizontal scaling. Alternatives: Sessions (rejected: requires sticky sessions)"
```

**When to log decisions:**
- Choosing between libraries or frameworks
- Selecting architectural patterns
- Deciding on data formats or schemas
- Rejecting an approach that seemed viable
- Any choice that could be questioned in future phases

**Why this matters:** When a validation phase fails and loops back to research or implementation, these decision logs explain what was already tried and why. Without them, agents may repeat failed approaches.

### CLAUDE.md Proposals

When you discover patterns, gotchas, or conventions that would help future agents, write a `proposals.md` file in the task output directory:

```bash
TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
# Write proposals to $TASK_DIR/proposals.md
```

**When to propose:**
- Common patterns that should be documented
- Gotchas or pitfalls that tripped you up
- File organization conventions
- Tool usage patterns specific to this project

See `phase-context` output for the full proposal format.

## When All Tasks Complete

After all tasks are `done`:
1. Run any verification/tests if appropriate
2. Collect and present CLAUDE.md proposals (if any were written):
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py collect-proposals
   uv run ~/.claude-plugins/jons-plan/plan.py list-proposals
   ```
   If proposals exist, present them to the user for approval before committing.
3. Summarize what was accomplished
4. Ask user if they want to commit the changes
