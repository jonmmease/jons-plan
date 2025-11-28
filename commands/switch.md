---
description: Switch to a different jons-plan
allowed-tools: Write(.claude/jons-plan/active-plan)
---

# Switch Plan

Switch the active plan to a different existing plan.

{{#if args}}
**Target plan:** {{args}}
{{else}}
No plan name provided. Use `/jons-plan:status` to see available plans, then `/jons-plan:switch [name]`.
{{/if}}

## Workflow

1. **Validate plan exists**: Check if `.claude/jons-plan/plans/{{args}}/` directory exists
   - If not found, list available plans and stop

2. **Switch active plan**: Write the plan name to `.claude/jons-plan/active-plan`

3. **Load plan state**: Read the plan's `tasks.json` and calculate:
   - Total tasks
   - Tasks done
   - Tasks in-progress
   - Tasks todo (available to work on)

4. **Show summary**:
   ```
   Switched to: [plan-name]

   Tasks: X/Y done, Z in-progress, W available

   Next available tasks:
   - [task-id]: [description]
   - [task-id]: [description]
   ```

5. **Next steps**: Tell user: "Type `/jons-plan:proceed` to continue implementing, or `/jons-plan:plan [feedback]` to refine the plan."
