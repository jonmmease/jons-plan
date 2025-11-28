---
description: Show all jons-plan plans and task progress
allowed-tools: Read(.claude/jons-plan/**)
---

# Plan Status

Show all existing plans and their task progress.

## Workflow

1. **Find plans directory**: Look for `.claude/jons-plan/plans/` in the project

2. **Get active plan**: Read `.claude/jons-plan/active-plan` to identify which plan is active (if any)

3. **List all plans**: For each subdirectory in `.claude/jons-plan/plans/`:
   - Read its `tasks.json`
   - Count tasks by status (done, in-progress, todo)
   - Note if it's the active plan

4. **Display results**:
   ```
   Plans:
   - plan-name-1 (active) - 3/7 tasks done, 1 in-progress
   - plan-name-2 - 0/5 tasks done
   - plan-name-3 - 5/5 tasks done [completed]
   ```

   If no plans exist:
   ```
   No plans found. Create one with `/jons-plan:new [topic]`.
   ```

5. **Next steps**:
   - If there's an active plan with tasks remaining: "Use `/jons-plan:proceed` to continue implementing, `/jons-plan:switch [name]` to switch plans, or `/jons-plan:new [topic]` to create a new one."
   - If no active plan: "Use `/jons-plan:switch [name]` to select a plan, or `/jons-plan:new [topic]` to create a new one."
