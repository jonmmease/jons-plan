# Implement Phase

Execute the plan (injected above).

## Setup
1. Create tasks.json in this phase directory based on the plan
2. All tasks start with `status: "todo"`

## Task Execution
1. Work through tasks in dependency order
2. Set each task to in-progress before starting
3. Mark tasks done immediately after completion
4. Log progress for each significant step

## Guidelines
- Make minimal, focused changes
- Don't over-engineer or add unnecessary features
- Test changes as you go
