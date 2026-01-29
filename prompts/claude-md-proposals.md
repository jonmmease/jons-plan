# CLAUDE.md Improvement Proposals

**IMPORTANT:** This is a required artifact for implement phases. You MUST create a `proposals.json` file before leaving the phase.

## When to Propose

Propose CLAUDE.md updates when you discover:
- Common patterns that should be documented
- Gotchas or pitfalls that tripped you up
- File organization conventions
- Tool usage patterns specific to this project
- Configuration requirements

## When to Leave Empty

Create an empty proposals file when:
- The implementation was straightforward
- No patterns or gotchas were discovered
- The codebase is already well-documented

## JSON Format

Create `proposals.json` in the current phase directory:

### Empty Proposals (nothing to propose)
```json
{
  "proposals": []
}
```

### With Proposals
```json
{
  "proposals": [
    {
      "title": "Error handling pattern for API calls",
      "target_file": "src/api/CLAUDE.md",
      "content": "Always wrap fetch calls in try/catch and check response.ok before parsing JSON.",
      "rationale": "Discovered during implementation that silent failures were causing confusing errors."
    }
  ]
}
```

## Required Fields

Each proposal must have:
| Field | Description |
|-------|-------------|
| `title` | Brief title for the proposal |
| `target_file` | Path to CLAUDE.md (e.g., `CLAUDE.md` or `src/auth/CLAUDE.md`) |
| `content` | What to add to the file |
| `rationale` | Why this helps future agents |

## Recording the Artifact

After creating proposals.json:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact proposals proposals.json
```

## Guidelines

- **Prefer nested files**: `src/auth/CLAUDE.md` over root `CLAUDE.md` to avoid context bloat
- **Be specific**: Include concrete examples
- **Keep it brief**: Agents should be able to quickly scan CLAUDE.md
- **Focus on patterns**: Document what works, not implementation details

## Automatic Processing

When you leave the implement phase, proposals are automatically collected and stored. You don't need to manually run `collect-proposals`.
