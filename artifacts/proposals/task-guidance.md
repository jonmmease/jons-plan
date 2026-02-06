# CLAUDE.md Proposals

If you discover patterns, gotchas, or conventions that would help future agents working in this codebase, write a `proposals.md` file in your task output directory.

## When to Write

- You discovered a non-obvious pattern that should be documented
- You hit a gotcha or pitfall that took time to figure out
- You found file organization conventions that aren't documented
- You encountered tool usage patterns specific to this project

## When to Skip

- The implementation was straightforward with no surprises
- The codebase is already well-documented for what you worked on

## Format

Write `proposals.md` in your task output directory:

```markdown
## Proposal: <brief title>

**Target File**: `path/to/CLAUDE.md`

**Content**:
<what to add to the file - be specific, include concrete examples>

**Rationale**:
<why this helps future agents>

---

## Proposal: <second proposal if needed>
...
```

## Guidelines

- Prefer nested CLAUDE.md files (`src/auth/CLAUDE.md`) over root `CLAUDE.md`
- Be specific with concrete examples, not vague advice
- Keep content brief (1-3 sentences or a short snippet)
- Focus on patterns and gotchas, not implementation details
