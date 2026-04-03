# CodeTour Quality Review Specification

Use this specification to evaluate CodeTour `.tour` file quality. A CodeTour is a JSON file that provides an interactive, step-by-step guided walkthrough of code changes in VS Code.

## Output Structure

The CodeTour consists of a single `.tour` JSON file with:
- Top-level metadata: `$schema`, `title`, `description`, `ref`, `steps[]`
- Content-only steps (no `file`) as stop separators
- File steps with `file` + `pattern` for code anchoring

## Schema Compliance

The `.tour` file must conform to the CodeTour schema:

```json
{
  "$schema": "https://aka.ms/codetour-schema",
  "title": "Review: {PR title} (#{number})",
  "description": "{1-2 sentence summary}",
  "ref": "{commit SHA}",
  "steps": [...]
}
```

### Required Fields
- [ ] `title` — present and descriptive
- [ ] `description` — present, 1-2 sentence summary of the PR
- [ ] `steps` — non-empty array
- [ ] `ref` — present, set to the PR's head commit SHA (not a branch name)
- [ ] `$schema` — set to `https://aka.ms/codetour-schema`

### Step Fields
Every step must have:
- [ ] `title` — short, descriptive, scannable in tree view
- [ ] `description` — markdown text explaining the change

File steps must also have:
- [ ] `file` — relative path with forward slashes only (no leading `./`, no backslashes)
- [ ] `pattern` or `line` — `pattern` (JavaScript regex matching exactly one line) is strongly preferred. `line` (1-based line number) is an acceptable fallback when a unique pattern cannot be found. Steps using `line` instead of `pattern` should be flagged as Suggestion (not Critical).

## Pattern Validation

This is the most critical quality dimension. Broken patterns mean broken navigation.

### Uniqueness
- [ ] Every `pattern` matches exactly **one** line in its target file at the pinned `ref`
- [ ] Zero matches = broken step (Critical)
- [ ] Multiple matches = ambiguous step (Critical)

### Quality
- [ ] Patterns anchor to distinctive code: function signatures, class declarations, unique literals
- [ ] Patterns do NOT match generic lines: `import`, `return`, `}`, blank lines, common keywords
- [ ] Regex metacharacters are properly escaped: `\\(`, `\\[`, `\\{`, `\\.`, `\\*`, `\\+`, `\\?`
- [ ] JSON string escaping is correct (double backslashes in the JSON: `\\\\(` for regex `\(`)

### Durability
- [ ] Patterns are specific enough to survive minor edits nearby
- [ ] Patterns don't depend on whitespace or indentation that might change

## Step Count and Sizing

### Overall
- [ ] Tour has 5-15 steps total (including separator steps)
- [ ] If more than 15 steps needed, suggest splitting into chained tours via `nextTour`

### Per Stop
- [ ] Each stop has exactly one content-only separator step (no `file`)
- [ ] Each stop has 1-5 file steps
- [ ] No stop has zero file steps (empty stops should be removed)

### Balance
- [ ] No single stop dominates the tour (>50% of all steps)
- [ ] Steps are roughly evenly distributed across stops

## Step Content Quality

### Separator Steps (Content-Only)
- [ ] Title format: "Stop N: {thematic title}"
- [ ] Description starts with `##` heading matching the title
- [ ] Narrative explains WHY these changes exist, not WHAT they are
- [ ] Mentions risk level and key files in the stop
- [ ] 1-3 paragraphs, concise

### File Steps
- [ ] Title is short and descriptive (not just the filename)
- [ ] Description is 2-5 sentences
- [ ] Explains the change's purpose and design decisions
- [ ] Calls out non-obvious tradeoffs, risks, or edge cases
- [ ] Does NOT restate the code (the developer can see it in VS Code)
- [ ] References specific function names, types, or patterns where relevant

### Narrative Voice
- [ ] Developer reviewer audience, not PM
- [ ] Explains WHY, not WHAT
- [ ] Flags potential bugs, edge cases, error handling gaps
- [ ] Concise and direct — no filler

## Stop Ordering

- [ ] Dependencies come first (referenced changes before referencing changes)
- [ ] Broad structural changes before localized behavioral
- [ ] High-risk stops early (when attention is freshest)
- [ ] Tests, docs, formatting last (unless they clarify earlier stops)

## Overview Step

- [ ] First step is a content-only overview (no `file`)
- [ ] Title is "Overview" or similar
- [ ] Description provides 2-3 paragraph synthesis of the PR
- [ ] Mentions number of stops and key themes

## Trivial Changes

- [ ] Pure renames, generated files, lockfiles, formatting-only changes are mentioned in the overview or a dedicated stop, not spread across the tour
- [ ] Trivial changes don't get elaborate file steps

## Binary File Handling

- [ ] Binary files (no patch available) have file steps without `pattern`
- [ ] Description notes the binary change (e.g., "Updated the application icon")

## File Path Validation

- [ ] All `file` paths use forward slashes (`/`)
- [ ] No leading `./` prefix
- [ ] Paths are relative to workspace root
- [ ] Paths actually exist in the PR's file list

## Quality Gate Checks Summary

When reviewing, verify and tag each issue:

1. **Critical** — Must fix before presenting to user
   - Pattern matches 0 or 2+ lines (broken navigation)
   - Missing `ref` field (tour won't resolve)
   - Invalid JSON (parse error)
   - Missing `title` or `description` on any step
   - File paths that don't exist in the PR

2. **Suggestion** — Improves quality if fixed
   - Generic patterns that might break on refactor
   - Steps that restate code instead of explaining WHY
   - Missing overview step
   - Unbalanced stop sizes
   - Narrative that's too verbose or too terse

3. **Nit** — Minor polish
   - Inconsistent title formatting
   - Minor markdown formatting issues
   - Slightly verbose descriptions
   - Duplicate step titles (makes tree view confusing)
