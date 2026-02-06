# Cache Reference Tasks

Tasks with `"type": "cache-reference"` read from the research cache instead of performing actual work.

## Identifying Cache Reference Tasks

Check if a task has `type: "cache-reference"` in its definition:
```json
{
  "id": "ref-sqlite-fts5",
  "type": "cache-reference",
  "cache_id": 42,
  "parents": [],
  "steps": []
}
```

## Execution Flow

1. **Get the cache entry**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py cache-get <cache_id>
   ```

2. **If entry not found or expired** (command returns error):
   - Create task directory: `uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>`
   - Write `blockers.md` explaining cache entry is expired/missing
   - Mark task as `blocked`
   - Stop execution - do not inject stale data

3. **If entry is valid**:
   - Create task directory: `uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir <task-id>`
   - Write the cache entry's findings to `findings.md` in the task directory
   - Mark task as `done`

## Example Execution

```bash
# Check if cache entry exists and is valid
uv run ~/.claude-plugins/jons-plan/plan.py cache-get 42
# If successful, create task dir and write findings
TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir ref-sqlite-fts5)
# Write findings to task directory (the findings content from cache-get)
# Mark done
uv run ~/.claude-plugins/jons-plan/plan.py set-status ref-sqlite-fts5 done
```

## Key Points

- **Never inject stale data**: If cache entry is expired, block the task rather than proceeding with outdated information
- **Downstream tasks**: Tasks that depend on a cache-reference task receive the findings via `build-task-prompt` just like any other parent task output
- **Zero cost execution**: These tasks are essentially instant - just reading from local cache
