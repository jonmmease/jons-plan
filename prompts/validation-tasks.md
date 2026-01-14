# Validation Tasks

Tasks that validate implementation (typically named `validate-*`) follow special rules.

## Execution Flow

1. **Read the spec**: Get test-spec.md from the parent test-definition task
2. **Run tests**: Execute the test suite or manually verify criteria
3. **Assess results**:
   - All pass → mark task `done`
   - Some fail → try to debug/fix (normal work, not blocked)
   - Failure requires "large side quest" → mark `blocked` with observations

## What is a "Large Side Quest"?

A validation failure becomes a blocker when fixing it would require:

1. **Out of scope**: Changes to code outside this plan's scope
2. **Risky foundation**: Modifying foundational code that's risky to change
3. **Missing prerequisite**: Something not anticipated during planning
4. **Requirements ambiguity**: Test failure reveals unclear requirements needing user input
5. **Architectural mismatch**: Implementation approach fundamentally can't meet the spec

**Keep debugging (not blocked) for:**
- Simple bugs you can identify and fix
- Missing test setup (add the setup)
- Performance issues (note but continue)
- Flaky tests (retry and document)

## Validation Blocker Observations

When marking a validation task as blocked, the blockers.md should capture observations:

```markdown
# Blocker Report: validate-auth

## What Was Attempted

Ran test suite after implementation. 8/10 tests passed.

## Failed Tests

### test_concurrent_sessions
- Expected: User can have max 3 sessions
- Actual: No session limit enforced
- Investigation: Session storage uses simple dict, no counting logic exists

### test_token_refresh_race
- Expected: Concurrent refresh requests return same token
- Actual: Each request generates new token, causing race condition
- Investigation: Token generation has no locking mechanism

## Why This Is a Large Side Quest

The session limiting and token locking require architectural changes to the session storage layer, which is shared code outside this plan's scope. Modifying it risks breaking other features.

## Suggested Resolution

Option A: Add session-storage-refactor as prerequisite task
Option B: Descope session limits from this feature
Option C: Accept eventual consistency for token refresh
```

## Validation Phase Loopbacks

When validation identifies issues requiring implementation changes:

1. **Document findings** in blockers.md
2. **Mark task as blocked**: `uv run plan.py set-status validate-auth blocked`
3. **Check if loopback to implement is configured**:
   - If `on_blocked = "implement"` in workflow, loop back:
     ```bash
     uv run plan.py loop-to-phase implement --reason "Validation failures: <summary>"
     ```
   - The implementation phase will receive validation findings via artifacts

4. **If approval required**: The loop-to-phase command will set pending_approval and prompt for user confirmation.

5. **If user rejects loopback**: Continue in validate phase, try alternative approaches or escalate to user.
