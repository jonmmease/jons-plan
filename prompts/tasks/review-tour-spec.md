# PR Review Tour Specification

Use this specification to evaluate review tour quality. A review tour is a markdown file that presents a GitHub PR's changes as a guided, narrative walkthrough with thematic "stops".

## Document Structure

1. **Header** — PR identification and key stats
2. **Overview** — Narrative summarizing the PR's purpose and approach
3. **Stops** — Ordered groups of related changes, each with a narrative preamble and inline diffs
4. **Review Notes** — Placeholder for the reviewer's summary

## Header Format

```markdown
# Review Tour: {PR title} (#{number})

**Repository:** {owner}/{repo}
**Author:** @{pr_author}
**Branch:** {head_branch} → {base_branch}
**Files changed:** {file_count} | **Additions:** +{additions} | **Deletions:** -{deletions}
```

## Overview

2-4 paragraphs synthesized from PR title, description, and actual code changes. Not a verbatim copy of the PR description. If PR description is empty/low-quality, generate entirely from the diff.

If the PR description makes claims about what the PR does, note any discrepancies with the actual changes — features mentioned but not implemented, undocumented changes, or scope differences.

## Stop Format

Each stop = a thematic group of related changes, separated by horizontal rules.

```markdown
---

### Stop {n}: {Thematic title}

- [ ] Reviewed

{Narrative preamble: 1-3 paragraphs}

#### `{file_path}` ({change_summary})

[View on GitHub]({permalink})

```diff
{diff hunks}
```

**Candidate comments:**

> **suggestion** `{file_path}:{line}` — {Self-contained review comment.}

> **concern** `{file_path}:{line}` — {Potential issue to raise.}
```

## Candidate Comments

After each stop's diff blocks, include actionable review comments as blockquotes. Each comment has:

- **Type tag**: `nit` (style/naming), `suggestion` (concrete improvement), `question` (needs clarification), `concern` (potential bug/edge case)
- **File and line number** (`filename:line`) — exact line for the PR comment
- **Self-contained text** — ready to copy-paste as a PR review comment without editing

Only include comments where genuinely warranted. Zero comments on a clean stop is fine.

## Completeness

Every changed file must appear in exactly one stop. No omissions. Cross-reference with the file manifest to verify.

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

**Group** files implementing same interface, function+tests, migration+model+schema, config+feature.
**Split** files with logically unrelated changes or both structural and behavioral changes.
**Isolate** large self-contained new modules, standalone refactors/renames/deletions.

## Diff Presentation

- Fenced code blocks with `diff` language tag
- Hunk headers preserved for line context
- Files split across stops show only relevant hunks per stop

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

GitHub permalinks at head commit with line anchors:
`https://github.com/{owner}/{repo}/blob/{head_sha}/{file_path}#L{start}-L{end}`

Line numbers extracted from hunk headers: `@@ -old_start,old_count +new_start,new_count @@`
- Use `new_start` as `{start}`
- Use `new_start + new_count - 1` as `{end}`

## Checkboxes

`- [ ] Reviewed` per stop (GFM task list)

## Narrative Voice

- Developer reviewer audience, not PM
- Explain *why*, not *what* (the diff shows what)
- Call out non-obvious decisions, tradeoffs, risks
- **Critique**: Flag potential bugs, edge cases, error handling gaps, or questionable patterns. Be specific — name the function, the missing check, or the risk.
- **Description vs. implementation**: Compare what the PR description claims with what the code actually does. Note any discrepancies, missing features, or undocumented changes.
- Reference specific function names, types, or patterns
- Concise: 1-3 short paragraphs, not a wall of text
- Do NOT restate what the diff shows
