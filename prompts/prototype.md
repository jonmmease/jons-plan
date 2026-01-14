# Prototype Tasks

Tasks with `"type": "prototype"` are standalone experiments that answer questions through implementation rather than research.

## Identifying Prototype Tasks

Check if a task has `type: "prototype"` in its definition:
```json
{
  "id": "proto-library-compat",
  "type": "prototype",
  "question": "Are library-a and library-b compatible when used together?",
  "hypothesis": "They should work since both use standard asyncio patterns",
  "description": "Prototype: Test library compatibility",
  "parents": ["research-library-a"],
  "context_artifacts": ["research"],
  "steps": [
    "Create test script in task directory",
    "Install dependencies",
    "Run experiment",
    "Document findings"
  ],
  "status": "todo"
}
```

### Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Must be `"prototype"` |
| `question` | Yes | The question being answered |
| `hypothesis` | No | Expected outcome (helps with validation) |
| `context_artifacts` | No | Artifact names to include from phase history |

## Execution Flow

1. **Create task directory**:
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>)
   cd "$TASK_DIR"
   ```

2. **Review the question**:
   - Question: `task.question`
   - Hypothesis: `task.hypothesis` (if present)

3. **Execute experiment**:
   - Follow task steps
   - Set up runtime environment as needed
   - Create test scripts, install dependencies
   - Run the experiment
   - Log progress with `task-log <task-id> "message"`

4. **Write findings**:
   Create `findings.md` in task directory:
   ```markdown
   # Findings: <question>

   ## Hypothesis
   <hypothesis if present>

   ## Experiment
   <what was tried>

   ## Results
   <what happened>

   ## Conclusion
   <answer to the question>
   ```

5. **Cache (optional)**:
   If findings are general and reusable:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py cache-add \
     --query "<question>" \
     --findings-file findings.md \
     --source-type prototype \
     --plan-id "<plan-name>"
   ```

6. **Mark done**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> done
   ```

## Failure Handling

If the experiment fails or is inconclusive:
1. Write partial findings to `findings.md` documenting what was tried
2. If blocked (needs external input), create `blockers.md` and mark task blocked
3. Otherwise, mark done with negative findings (answering "no" is still a finding)

## Standard Artifacts

| File | Purpose |
|------|---------|
| `findings.md` | Required - experiment results and conclusion |
| `progress.txt` | Auto-managed - task progress log |
| `blockers.md` | If blocked - what's preventing completion |
| `logs/` | Optional - captured stdout/stderr |

## When to Cache

Cache findings when:
- The question is general (not project-specific)
- The answer could benefit future similar questions
- The experiment was non-trivial

Do NOT cache:
- Project-specific findings
- Version-dependent results (unless versioning is included in the question)
- Trivial experiments

## MCP Server Warning

If the prototype needs to interact with stateful MCP servers (browser automation, database connections), ensure only one prototype runs at a time. Parallel prototypes cannot safely share stateful connections.
