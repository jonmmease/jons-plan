# Research Iteration Guidance

This phase supports multiple iterations. After completing tasks, decide whether to proceed to the next phase or loop back for additional investigation.

## Research Phase Flow

```
research (round 1: initial research tasks)
    |
[synthesize findings -> research.md]
    |
+-- requirements clear -> proceed to draft/plan
+-- open questions -> research (round 2: more research + prototypes)
    |
[append to research.md]
    |
+-- requirements clear -> proceed to draft/plan
+-- still unclear -> research (round 3)
...
```

Each iteration gets its own numbered directory:
- `phases/01-research/` - initial research
- `phases/02-research/` - prototypes + follow-up research
- `phases/03-draft/` - when everything is clear

## Synthesizing research.md

After tasks complete, synthesize findings into `research.md` with one section per task. Group by iteration round:

```markdown
# Research Findings

## Round 1 (phases/01-research)

### Task: research-sqlite-fts

Brief overview of important findings from this task.

[Full report](.claude/jons-plan/plans/<plan-name>/phases/01-research/tasks/research-sqlite-fts/findings.md)

### Task: research-caching-patterns

Brief overview of important findings from this task.

[Full report](.claude/jons-plan/plans/<plan-name>/phases/01-research/tasks/research-caching-patterns/findings.md)

## Round 2 (phases/02-research)

### Prototype: proto-async-compat

**Question**: Can library-x work in async context?
**Answer**: Yes, with run_in_executor

Brief overview of the experiment and conclusion.

[Full experiment](.claude/jons-plan/plans/<plan-name>/phases/02-research/tasks/proto-async-compat/findings.md)
```

Use `uv run plan.py task-dir <task-id>` to get the exact path for each task.

## Re-entry Behavior

When re-entering research for additional investigation:
1. Read existing `research` artifact from previous iteration via `input-artifacts`
2. Run new research/prototype tasks
3. **Append** new task summaries to research.md (don't overwrite)
4. Record updated research.md as `research` artifact

## Iteration Limit

This phase has a maximum iteration limit. If you've reached the limit, you must proceed to the next phase rather than looping back.

Check the current iteration count before deciding to re-enter:
- The system will enforce the limit automatically
- If the limit is reached, `enter-phase` will fail with an error

## Decision Criteria

**Proceed to next phase when:**
- All key questions are answered
- Requirements are clear enough to design/implement
- Remaining uncertainty is acceptable

**Loop back for more research when:**
- Critical questions remain unanswered
- Prototype results raise new questions
- External dependencies need clarification
