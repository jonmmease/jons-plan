# CLAUDE.md Improvement Proposals

During implementation, you may discover improvements to CLAUDE.md that would help future agents work more effectively with this codebase.

## When to Propose

Propose CLAUDE.md updates when you discover:
- Common patterns that should be documented
- Gotchas or pitfalls that tripped you up
- File organization conventions
- Tool usage patterns specific to this project
- Configuration requirements

## How to Propose

Write `proposals.md` in your task output directory:

```bash
TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
```

## Proposal Format

```markdown
# CLAUDE.md Proposals

## Proposal: <title>

**Target File**: `path/to/CLAUDE.md`

**Content**:
[What to add to the CLAUDE.md file]

**Rationale**:
[Why this helps future agents]

---

## Proposal: <another-title>
...
```

## Guidelines

- **Prefer nested files**: `src/auth/CLAUDE.md` over root `CLAUDE.md` to avoid context bloat
- **Be specific**: Include concrete examples
- **Keep it brief**: Agents should be able to quickly scan CLAUDE.md
- **Focus on patterns**: Document what works, not implementation details
