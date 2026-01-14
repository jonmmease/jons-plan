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

Tasks are scoped to the **current phase** of the workflow:

1. **Get current phase context**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-context
   ```
   This shows the phase prompt, input artifacts, and task execution instructions.

2. **Follow the phase prompt**: The phase context includes all task execution guidance assembled based on the workflow configuration.

3. **Check phase tasks**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py phase-tasks
   uv run ~/.claude-plugins/jons-plan/plan.py phase-next-tasks
   ```
   Execute tasks from the current phase's tasks.json.

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
      Based on your research findings and the expand_prompt guidance, generate a JSON structure with phases and transitions.

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

Log significant progress:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py log "Completed task X: brief description"
```

## When All Tasks Complete

After all tasks are `done`:
1. Run any verification/tests if appropriate
2. Summarize what was accomplished
3. Ask user if they want to commit the changes
