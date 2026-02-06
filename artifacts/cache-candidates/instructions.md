# Generating the Cache Candidates Artifact

Before leaving this phase, you must record any research findings worth caching for future reuse.

## Step 1: Review Task Outputs

Check task output directories for research findings (findings.md, analysis.md, etc.) that came from web searches or documentation lookups.

## Step 2: Build cache-candidates.json

Create `cache-candidates.json` in the current phase directory.

**If cacheable findings exist:**
```json
{
  "entries": [
    {
      "query": "The research question or search query",
      "findings_file": "phases/01-research/tasks/task-id/findings.md",
      "source_type": "web_search",
      "source_url": "https://source.url (optional)"
    }
  ]
}
```

Valid `source_type` values: `web_search`, `documentation`, `prototype`, `task_research`

**If no findings worth caching:**
```json
{
  "entries": []
}
```

## Step 3: Record the Artifact

```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact cache-candidates cache-candidates.json
```

Then retry the phase transition.
