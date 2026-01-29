# Evaluate CLAUDE.md Proposals

This task evaluates what CLAUDE.md improvements to propose based on your implementation experience.

## Required Output

You MUST create a `proposals.json` file in the current phase directory before transitioning out of the implement phase. This is a **required artifact**.

## When to Propose

Propose CLAUDE.md updates when you discovered:
- **Common patterns**: Recurring code patterns that should be documented
- **Gotchas or pitfalls**: Issues that tripped you up that others would hit
- **File organization**: Where different types of code belong
- **Tool usage patterns**: Project-specific tool configurations or workflows
- **Configuration requirements**: Environment setup, build flags, etc.

## When to Leave Empty

Create an empty proposals file (`{"proposals": []}`) when:
- The implementation was straightforward
- No surprising patterns or gotchas were discovered
- The codebase is already well-documented
- Changes were isolated and don't establish new patterns

**An empty proposals file is perfectly valid** - not every implementation reveals documentation-worthy insights.

## JSON Structure

```json
{
  "proposals": [
    {
      "title": "Brief title for the proposal",
      "target_file": "path/to/CLAUDE.md",
      "content": "What to add to the file",
      "rationale": "Why this helps future agents"
    }
  ]
}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `title` | Brief title summarizing the proposal |
| `target_file` | Path to target CLAUDE.md (prefer nested over root) |
| `content` | The actual text to add to the file |
| `rationale` | Why this information helps future agents |

### Empty Proposals

When nothing to propose:
```json
{
  "proposals": []
}
```

### Populated Example

```json
{
  "proposals": [
    {
      "title": "Error handling pattern for API calls",
      "target_file": "src/api/CLAUDE.md",
      "content": "Always wrap fetch calls in try/catch and check response.ok before parsing JSON. The API returns non-JSON error bodies for 4xx responses.",
      "rationale": "Discovered during implementation that silent failures were causing confusing errors downstream."
    },
    {
      "title": "Test database setup",
      "target_file": "tests/CLAUDE.md",
      "content": "Run `npm run db:test:setup` before running integration tests. Tests use a separate SQLite database at `test.db`.",
      "rationale": "Tests were failing without obvious reason until I discovered the test database wasn't initialized."
    }
  ]
}
```

## Guidelines

### Prefer Nested CLAUDE.md Files

Target specific directories rather than the root CLAUDE.md:
- `src/auth/CLAUDE.md` over `CLAUDE.md` for auth patterns
- `tests/CLAUDE.md` over `CLAUDE.md` for test setup
- `src/api/CLAUDE.md` over `CLAUDE.md` for API conventions

This avoids context bloat in the root file.

### Be Specific

Include concrete examples:
- Bad: "Handle errors properly"
- Good: "Wrap API calls in try/catch and check response.ok before calling response.json()"

### Keep Content Brief

Agents should quickly scan CLAUDE.md. Each proposal's content should be:
- 1-3 sentences for simple patterns
- A short code snippet for complex patterns
- Never more than a paragraph

### Focus on Patterns, Not Implementation

Document **what works** for future agents, not implementation details:
- Bad: "I added a try/catch in line 42 of api.ts"
- Good: "API errors return non-JSON bodies; always check response.ok first"

## Recording the Artifact

After creating proposals.json in the phase directory:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact proposals proposals.json
```

## Automatic Processing

When you transition out of the implement phase:
1. The proposals artifact is validated against the schema
2. Valid proposals are auto-imported into the proposals manifest
3. You'll see: "Auto-collected N proposals" in the log

Proposals are surfaced at workflow completion for user review and approval.
