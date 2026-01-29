# Challenges Reporting

Record challenges when you encounter issues you **could not solve** during implementation.

## When to Record Challenges

Record a challenge when:
- You couldn't figure out how to do something and used a workaround
- You encountered a limitation or missing feature
- A tool or library didn't work as expected and you had to work around it
- You couldn't find documentation for something
- You ran into an issue but had to move on without resolving it

## When NOT to Record

Don't record challenges for:
- Issues you **solved** - those should be proposals instead
- Normal debugging that you worked through
- Expected complexity that was handled appropriately
- User requirements that were simply unclear (ask for clarification instead)

## Challenges vs Proposals

| Situation | Record as |
|-----------|-----------|
| Figured out a tricky pattern | **Proposal** |
| Couldn't find the right approach, used workaround | **Challenge** |
| Discovered a gotcha and documented solution | **Proposal** |
| Hit a limitation, no solution found | **Challenge** |

## Format

Create `challenges.md` in the task output directory:

```markdown
## Challenge: <brief title>

**What was attempted**:
<describe what you tried to do>

**What went wrong**:
<describe the issue or limitation>

**Workaround used**:
<describe how you worked around it, or "None - blocked" if you couldn't>
```

## Example

```markdown
## Challenge: Couldn't run single test

**What was attempted**:
Tried to run just the authentication test to speed up iteration.

**What went wrong**:
Couldn't figure out the pytest syntax for running a single test by name.
Tried `pytest test_auth.py::test_login` but got "not found" errors.

**Workaround used**:
Ran the entire test suite each time, which was slower but worked.
```

## Recording

After creating challenges.md:
```bash
TASK_DIR=$(uv run plan.py ensure-task-dir <task-id>)
# Write challenges.md to $TASK_DIR/challenges.md
```

Challenges are collected automatically when transitioning phases.

## Review Process

During the complete phase, challenges are presented for acknowledgement:
- User sees each challenge
- User acknowledges they've seen it
- No action required (unlike proposals which may be applied)

This helps surface issues for future improvement without blocking workflow completion.
