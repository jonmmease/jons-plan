# Generating the Challenges Artifact

Before leaving this phase, you must consolidate any challenge reports from task outputs into a single JSON artifact.

## Step 1: Collect Task Challenges

Scan task directories for `challenges.md` files:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py collect-challenges
```

This scans all `phases/*/tasks/*/challenges.md` files and prints a summary.

## Step 2: Review

Read through the collected challenges. Consolidate duplicates where multiple tasks hit the same issue.

## Step 3: Build challenges.json

Create `challenges.json` in the current phase directory.

**If challenges were found:**
```json
{
  "challenges": [
    {
      "title": "Brief title describing the challenge",
      "attempted": "What was tried",
      "issue": "What went wrong or why it didn't work",
      "workaround": "How it was worked around (optional)"
    }
  ]
}
```

**If no challenges were found** (all tasks completed without issues):
```json
{
  "challenges": []
}
```

## Step 4: Record the Artifact

```bash
uv run ~/.claude-plugins/jons-plan/plan.py record-artifact challenges challenges.json
```

Then retry the phase transition.
