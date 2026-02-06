# Generating the Proposals Artifact

Before leaving this phase, you must consolidate any CLAUDE.md proposals from task outputs into a single JSON artifact.

## Step 1: Collect Task Proposals

Scan task directories for `proposals.md` files:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py collect-proposals
```

This scans all `phases/*/tasks/*/proposals.md` files and prints a summary.

## Step 2: Review and Consolidate

Read through the collected proposals. If multiple tasks reported similar patterns, consolidate them into a single proposal. Remove duplicates.

## Step 3: Build proposals.json

Create `proposals.json` in the current phase directory.

**If proposals were found:**
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

**If no proposals were found** (tasks had no discoveries):
```json
{
  "proposals": []
}
```

## Step 4: Record the Artifact

```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact proposals proposals.json
```

Then retry the phase transition.
