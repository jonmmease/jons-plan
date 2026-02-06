# Evaluate Cache Findings

This task evaluates research findings for caching in the research cache.

## Purpose

The research cache stores valuable findings from web searches, documentation lookups, and prototype experiments so they can be reused in future plans without re-doing the research.

## When to Cache

Cache findings when:
- Web search produced useful documentation, patterns, or best practices
- Documentation lookup found relevant technical information
- Prototype experiments answered reusable questions
- Research could benefit future similar tasks

## Do NOT Cache

- Codebase exploration results (changes with code)
- Project-specific findings that won't apply elsewhere
- Very short findings (< 100 chars)
- Temporary or context-specific information

## Creating cache-candidates.json

Review completed research tasks and create a `cache-candidates.json` file:

```json
{
  "entries": [
    {
      "query": "How to use SQLite FTS5 for full-text search",
      "findings_file": "phases/01-research/tasks/research-sqlite/findings.md",
      "source_type": "web_search",
      "source_url": "https://sqlite.org/fts5.html"
    },
    {
      "query": "Best practices for async Python with SQLite",
      "findings_file": "phases/01-research/tasks/research-async-patterns/findings.md",
      "source_type": "documentation"
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `query` | Yes | The research question (used for cache search) |
| `findings_file` | Yes | Relative path to markdown file with findings |
| `source_type` | Yes | One of: `web_search`, `documentation`, `prototype`, `task_research` |
| `source_url` | No | URL of the source (if applicable) |

### Path Resolution

The `findings_file` path is relative to the plan directory. Use task directories:
```
phases/01-research/tasks/<task-id>/findings.md
```

Use `uv run plan.py task-dir <task-id>` to get the exact path.

## Steps

1. **List completed research tasks**
   ```bash
   uv run plan.py phase-tasks
   ```

2. **For each task, check if it produced external findings**
   - Was this web search or documentation lookup?
   - Are the findings general and reusable?
   - Is there a findings.md in the task directory?

3. **Create cache-candidates.json** in the current phase directory
   - Include only valuable, reusable findings
   - Use clear, searchable queries

4. **Record the artifact**
   ```bash
   uv run plan.py record-artifact cache-candidates cache-candidates.json
   ```

## Empty Cache

If no findings are worth caching, create an empty entries array:

```json
{
  "entries": []
}
```

This satisfies the required artifact while indicating nothing needs caching.

## Automatic Import

When transitioning out of the phase, the system automatically:
1. Validates cache-candidates.json against the schema
2. Reads each findings_file
3. Imports entries into the research cache
4. Reports how many entries were imported
