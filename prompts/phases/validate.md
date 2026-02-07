# Validate Phase

Verify the implementation using the verification plan (injected above).

## Execution

### 1. Run Automated Checks
Execute each command from the verification plan:
- Run test suite
- Run type checker
- Run linter
- Run build

Log results for each check.

### 2. Interactive Verification (if applicable)
If the verification plan includes MCP-based checks:
- Execute browser automation steps
- Verify UI behavior
- Test API endpoints

### 3. Acceptance Criteria
Verify each criterion from the verification plan is met.

## Outcomes

**All checks pass:** Transition to complete.

**Checks fail:**
- If fixable: Fix and re-run checks
- If needs rework: Transition back to implement
