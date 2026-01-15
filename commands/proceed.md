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

   **If tasks.json doesn't exist or is empty**, you MUST create it before proceeding:
   - Write tasks.json to the path returned by `phase-tasks-file`
   - Follow the Task Schema from the `/jons-plan:new` command documentation
   - Break the phase work into discrete, trackable tasks
   - Use appropriate subagents (Explore for research, general-purpose for implementation)

   **After tasks exist**, check what's available:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-next-tasks
   ```

   Execute tasks from the phase's tasks.json using the Task Execution Loop below.

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

## When All Tasks Complete

After all tasks are `done`:
1. Run any verification/tests if appropriate
2. Summarize what was accomplished
3. Ask user if they want to commit the changes
