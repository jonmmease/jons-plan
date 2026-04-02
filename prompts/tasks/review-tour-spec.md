# PR Review Tour Specification

Use this specification to evaluate review tour quality. A review tour is a set of markdown files that present a GitHub PR's changes as a guided, narrative walkthrough with thematic "stops".

## Output Structure

The review tour consists of:
- `review-tour.json` — Structured source of truth (stops, files, hunks, comments, risk)
- `review-tour/index.md` — Overview, table of contents, per-file checkboxes
- `review-tour/stop-01.md`, `stop-02.md`, ... — One file per stop

## Index File Format

```markdown
# Review Tour: {PR title} (#{number})

**Repository:** {owner}/{repo}
**Author:** @{pr_author}
**Branch:** {head_branch} → {base_branch}
**Files changed:** {file_count} | **Additions:** +{additions} | **Deletions:** -{deletions}

## Overview

{2-4 paragraph synthesis}

## Tour Guide

### Stop 1: {title} ({risk} risk, ~{minutes}m)
Files: `file1.ts:12-28`, `file2.ts`
- [ ] Review file1.ts:12-28 (auth middleware changes)
- [ ] Review file2.ts (new auth types)

### Stop 2: {title} ({risk} risk, ~{minutes}m)
...

## Trivial Changes
{Collapsed summary of renames, generated files, lockfiles — not full stops}

## Review Notes

```

## Stop File Format

Each `stop-NN.md` file:

```markdown
# Stop {n}: {Thematic title}

**Risk:** {low|medium|high} | **Files:** {count} | **Est. review:** ~{minutes}m

{Narrative preamble: 1-3 paragraphs explaining WHY, not WHAT. Use the rationale from the stop plan as a seed, but expand with specific observations from the code.}

---

#### `{file_path}` ({change_summary}) — lines {start}-{end}

[View on GitHub]({pr_files_url}#diff-{sha256_of_filepath}R{line})

```diff
{diff hunks — ONLY the hunks assigned to this stop, not the entire file diff}
```

**Candidate comments:**

> **suggestion** `{file_path}:{line}` — {Self-contained review comment text
> that can be copied directly to the PR.}

> **question** `{file_path}:{line}` — {Question about the implementation
> that the reviewer might want to ask.}
```

## Hunk Coverage

Every changed hunk across all files must appear in exactly one stop. No omissions, no duplicates.

- A file MAY appear in multiple stops if its hunks belong to different thematic groups
- Use hunk indices from stop-plan.json to verify coverage
- Each stop shows ONLY its assigned hunks, not the entire file diff
- Cross-reference hunk line ranges against the full patch data

## Completeness Validation

1. List all files and their hunk count from pr-files.json
2. For each hunk, verify it appears in exactly one stop
3. Report any missing or duplicate hunks
4. Trivial files (renames, generated, lockfiles) must be listed in the index trivial section

## Stop Ordering

- **Dependency first:** Referenced changes come earlier
- **Scope first:** Broad structural before localized behavioral
- **Risk first:** Complex/high-risk when attention is freshest
- **Convention last:** Tests, docs, formatting last unless they clarify earlier stops

## Stop Sizing

- Single stop for very small PRs (<30 lines), overview still required
- 3-7 stops for typical PR (50-500 lines)
- 5-10 stops for larger PRs (500-1000 lines)
- Up to 15 stops for large PRs (>1000 lines)

## Chunking Rules

The unit of assignment is the **hunk**, not the file.

**Group** hunks implementing same interface, function+tests, migration+model+schema, config+feature.
**Split** files with logically unrelated hunks across different stops.
**Isolate** large self-contained new modules, standalone refactors/renames/deletions.
**Collapse** trivial changes (pure renames, generated files, lockfiles) into the index summary.

## Diff Presentation

- Fenced code blocks with `diff` language tag
- Hunk headers preserved for line context
- **Only show hunks assigned to this stop** — not the entire file diff
- When a file appears in multiple stops, each stop shows only its assigned hunks

## Risk Tags

Each stop has a risk level:
- `low` — Trivial changes, tests, docs, formatting
- `medium` — Standard feature code, configuration
- `high` — Complex logic, security, error handling, concurrency

## Navigation Headers

Each stop file includes a navigation header:
```
**Risk:** {level} | **Files:** {count} | **Est. review:** ~{minutes}m
```

Estimated review time: ~1 min per 50 lines of non-trivial changes. Adjust up for high-risk stops.

## Checkboxes

**Index file:** Per-file checkboxes within each stop section:
```markdown
- [ ] Review src/auth.ts:12-28 (auth middleware changes)
- [ ] Review src/types.ts (new type definitions)
```

Labels should be action-oriented and include the file path with line ranges where applicable.

**Stop files** do NOT include checkboxes — the index is the checklist.

## Candidate Comments

After each file's diff blocks within a stop, include actionable review comments as blockquotes. Each comment has:

- **Type tag**: `nit` (style/naming), `suggestion` (concrete improvement), `question` (needs clarification), `concern` (potential bug/edge case)
- **File and line number** (`filename:line`) — exact line for the PR comment
- **Self-contained text** — ready to copy-paste as a PR review comment without editing

Only include comments where genuinely warranted. Zero comments on a clean stop is fine.

## Change Summary Format

- New file: `(new file)`
- Deleted: `(deleted)`
- Renamed: `(renamed from {old_path})`
- Modified: `(+{n} -{m})`
- Binary: `(binary file)`

## Binary File Handling

For binary files (where `has_patch` is false):
- Include the file header with change summary `(binary file)`
- Include the permalink
- Omit the diff code block entirely
- In the narrative, note the binary change (e.g., "Updated the application icon")

## Links

Links point to the PR Files Changed tab for direct commenting:
```
https://github.com/{owner}/{repo}/pull/{number}/files#diff-{hash}R{line}
```

- `{hash}` = SHA-256 hex digest of the file path (UTF-8)
- `R{line}` = right-side (new file) line number from diff hunk header
- For exact line references within hunks, use the specific line number, not just `new_start`

## Trivial File Handling

Trivial files are NOT assigned to regular stops. They are:
- Listed in the index under "Trivial Changes" with a one-line summary each
- Not given their own stop files
- Examples: pure renames, lockfile updates, generated files, formatting-only changes

## Narrative Voice

- Developer reviewer audience, not PM
- Explain *why*, not *what* (the diff shows what)
- Call out non-obvious decisions, tradeoffs, risks
- **Critique**: Flag potential bugs, edge cases, error handling gaps, or questionable patterns. Be specific — name the function, the missing check, or the risk.
- **Description vs. implementation**: Compare what the PR description claims with what the code actually does. Note any discrepancies, missing features, or undocumented changes.
- Reference specific function names, types, or patterns
- Concise: 1-3 short paragraphs, not a wall of text
- Do NOT restate what the diff shows

## Quality Gate Checks

When reviewing a tour for quality, verify:

1. **Hunk coverage** — every hunk covered exactly once, no gaps, no duplicates
2. **Anchor correctness** — line numbers in links and comments match actual diff lines
3. **Stop sizing** — no oversized stops (>200 lines of diff in a single stop)
4. **Checkbox presence** — index has per-file checkboxes for every non-trivial file
5. **JSON/markdown consistency** — review-tour.json matches the rendered markdown
6. **Trivial file handling** — renames/generated/lockfiles are in trivial section, not stops
7. **Narrative quality** — explains WHY not WHAT, concise, no restating the diff
8. **Format correctness** — proper markdown structure, working permalink format, diff fencing
