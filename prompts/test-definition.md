# Test Definition Tasks

Tasks that define test specifications (typically named `define-tests-*`) should produce a test-spec.md file.

## Creating test-spec.md

1. **Create task directory**:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   ```

2. **Write test-spec.md** to the task output directory with:
   - Clear test names
   - Expected behavior for each test
   - How to verify each criterion

## Format

```markdown
# Test Specification: <feature-name>

## Tests

### test_user_login
- **Given**: User with valid credentials
- **When**: User submits login form
- **Then**: User is redirected to dashboard
- **Verify**: Check response status is 302, location header points to /dashboard

### test_invalid_password
- **Given**: User with valid email but wrong password
- **When**: User submits login form
- **Then**: Error message displayed, user stays on login page
- **Verify**: Check response contains "Invalid credentials" text

## Acceptance Criteria

1. All tests must pass
2. No regressions in existing auth tests
3. Response times under 200ms for happy path
```

## Guidelines

- **Include measurable criteria**: Each test/criterion should explain how to verify it
- **Keep it focused**: Only tests relevant to this plan's scope
- **Be specific**: Avoid vague criteria like "works correctly"

The test-spec.md flows automatically to child tasks via `build-task-prompt`.
