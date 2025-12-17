---
description: Create a technical documentation plan for a codebase topic
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(git log:*), Bash(git rev-parse:*), Bash(tree:*), Bash(mkdir:*), Bash(gh pr list:*), Bash(gh issue list:*), Bash(gh pr view:*), Bash(gh issue view:*), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**), Edit(**/.git/info/exclude)
---

ultrathink

# Create Technical Documentation Plan

You are creating a plan to generate technical documentation about a topic in the current codebase.

**Final deliverable:** A technical documentation file (markdown) that:
- Documents how something works in its current state
- Uses examples with search instructions (not exhaustive lists)
- Links to source files
- Is written for developers with baseline language/framework knowledge

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore agents for research
- Write to `.claude/jons-plan/plans/[plan-name]/` directory ONLY
- **Exception:** Edit `.git/info/exclude` to hide `.claude/jons-plan/` from git
- Ask user questions (AskUserQuestion tool)

Forbidden actions:
- Edit, Write, or create files outside the plan directory
- Run Bash commands that modify files (except in plan directory)
- Make git commits
- Modify configuration files

## Topic

{{#if args}}
{{args}}
{{else}}
No topic provided. Ask the user what they want to document.
{{/if}}

## Workflow

### Step 1: Derive Plan Name

Convert topic to kebab-case and append `-docs`:
- "authentication flow" → "authentication-flow-docs"
- "api-endpoints" → "api-endpoints-docs"

### Step 2: Initial Understanding

Launch 1-2 quick Explore agents to understand the topic scope. This informs task creation.

### Step 3: Check MCP Availability

Before creating tasks, check which MCP servers are connected:

**Notion MCP:** Look for tools containing "notion" (e.g., `notion_search`, `notion_query_database`). If found, create `research-notion` task.

**Linear MCP:** Look for tools containing "linear" (e.g., `linear_search_issues`, `linear_get_issue`). If found, create `research-linear` task.

Record which MCPs are available. Only create research tasks for available sources.

### Step 4: Get Version Anchor

Record the current git commit for version anchoring:
```bash
git rev-parse HEAD
```

This commit hash will appear in the generated documentation.

### Step 5: Create Plan Infrastructure

1. Ensure `.claude/jons-plan/` is in `.git/info/exclude`
2. Create directory: `.claude/jons-plan/plans/[plan-name]/`
3. Create `plan.md` with the documentation plan
4. Create `tasks.json` with task list (all tasks start with `status: "todo"`)
5. Create `claude-progress.txt` with initial entry
6. Write plan name to `.claude/jons-plan/active-plan`

### Step 6: Present Summary

- Show plan name and task count
- List tasks with dependencies
- Tell user: "Type `/jons-plan:proceed` to generate documentation, or `/jons-plan:plan [feedback]` to refine."

## Target Audience

Write for developers who:
- Know the programming language and framework basics
- Have not used this specific codebase before
- Will search for specific answers, not read front-to-back

Do not write for beginners, experts, or managers.

## Source Hierarchy (Code is Truth)

| Priority | Source | Role | Validation |
|----------|--------|------|------------|
| 1 | Current source code | Ground truth | None needed |
| 2 | Official documentation | Design intent | Verify against code |
| 3 | GitHub issues/PRs (recent, closed) | Historical context | Verify current state |
| 4 | GitHub issues/PRs (old, open) | Low confidence | Likely stale |
| 5 | External resources | Background | Always verify |

**Core principle:** If documentation contradicts code, code wins. Claims from sources 2-5 must be verified.

## Task Structure

### Phase 1: Research (Parallel)

Core research tasks (always included):

```json
[
  {
    "id": "research-codebase",
    "description": "Explore codebase for [TOPIC]: architecture, patterns, and implementation",
    "subagent": "Explore",
    "subagent_prompt": "very thorough analysis across multiple locations and naming conventions",
    "model": "haiku",
    "parents": [],
    "steps": [
      "Search for files, classes, and functions related to [TOPIC]",
      "Identify core implementation locations",
      "Document architecture and data flow",
      "Find configuration options",
      "Identify public APIs vs internal implementation",
      "Note common patterns (1-2 examples, not exhaustive lists)",
      "Write findings.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "research-online-docs",
    "description": "Search web for official documentation about [TOPIC]",
    "subagent": "Explore",
    "subagent_prompt": "medium exploration",
    "model": "haiku",
    "parents": [],
    "steps": [
      "Search for official documentation",
      "Find API references and guides",
      "Note version requirements",
      "Mark claims with VALIDATION_NEEDED for code verification",
      "Write findings.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "research-github",
    "description": "Search GitHub PRs and issues for [TOPIC] context",
    "subagent": "Explore",
    "subagent_prompt": "medium exploration",
    "model": "haiku",
    "parents": [],
    "steps": [
      "Run: gh pr list --search '[TOPIC] in:title,body' --state merged --json number,title,url,body --limit 20",
      "Run: gh issue list --search '[TOPIC]' --state closed --json number,title,url,body --limit 20",
      "Prioritize recent items (last 6 months)",
      "Extract design rationale",
      "Mark historical claims with HISTORICAL_CONTEXT",
      "Write findings.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "research-dependencies",
    "description": "Explore dependency source for [TOPIC] context",
    "subagent": "Explore",
    "subagent_prompt": "quick search",
    "model": "haiku",
    "parents": [],
    "steps": [
      "Identify dependencies related to [TOPIC]",
      "Search dependency source for relevant APIs",
      "Note version constraints",
      "Mark claims with VERIFY_USAGE",
      "Write findings.md to task output directory"
    ],
    "status": "todo"
  }
]
```

Conditional MCP research tasks (only include if MCP is available per Step 3):

```json
{
  "id": "research-notion",
  "description": "Search Notion workspace for [TOPIC] documentation",
  "subagent": "Explore",
  "subagent_prompt": "medium exploration",
  "model": "haiku",
  "parents": [],
  "steps": [
    "Use Notion MCP tools to search for [TOPIC]",
    "Look for design docs, ADRs, and internal documentation",
    "Extract relevant content and context",
    "Mark claims with VALIDATION_NEEDED for code verification",
    "Write findings.md to task output directory"
  ],
  "status": "todo"
}
```

```json
{
  "id": "research-linear",
  "description": "Search Linear issues for [TOPIC] context",
  "subagent": "Explore",
  "subagent_prompt": "quick search",
  "model": "haiku",
  "parents": [],
  "steps": [
    "Use Linear MCP tools to search issues related to [TOPIC]",
    "Look for completed issues with design rationale",
    "Extract relevant decisions and context",
    "Mark historical claims with HISTORICAL_CONTEXT",
    "Write findings.md to task output directory"
  ],
  "status": "todo"
}
```

### Phase 2: Draft Documentation

Parents should include all Phase 1 research tasks that were created (core tasks + any conditional MCP tasks):

```json
{
  "id": "draft-documentation",
  "description": "Synthesize research into draft documentation following all guidelines",
  "model": "opus",
  "parents": ["research-codebase", "research-online-docs", "research-github", "research-dependencies"],
  "steps": [
    "Read documentation guidelines from ~/.claude-plugins/jons-plan/commands/new-tech-docs.md (sections: Target Audience, Source Hierarchy, Anti-Slop Guidelines, Example-Based Pattern, Cross-References, Version Anchoring, Negative Space, Durable Documentation, Document Structure)",
    "Read all research findings from parent tasks",
    "Validate external claims against codebase findings",
    "Structure documentation: Purpose → Quick Start → Examples → Details → See Also",
    "Use example-based pattern (1-2 examples + search instructions)",
    "Add cross-references to source files",
    "Include version anchor (commit hash from plan creation)",
    "Write draft-docs.md to task output directory"
  ],
  "status": "todo"
}
```

**Note:** Add `"research-notion"` and/or `"research-linear"` to parents if those tasks were created.

### Phase 3: Review (Parallel)

Five parallel review tasks:

```json
[
  {
    "id": "validate-links",
    "description": "Verify all source file links resolve",
    "model": "haiku",
    "parents": ["draft-documentation"],
    "steps": [
      "Extract all markdown links from draft",
      "Verify source file links exist",
      "Check line number references are valid",
      "Report broken links with suggested fixes",
      "Write link-validation.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "doc-slop-detect",
    "description": "Detect AI writing patterns in documentation using anti-slop guidelines",
    "model": "haiku",
    "parents": ["draft-documentation"],
    "steps": [
      "Read anti-slop guidelines from ~/.claude-plugins/jons-plan/commands/new-tech-docs.md (section: Documentation Anti-Slop Guidelines)",
      "Scan draft for forbidden words (utilize, leverage, robust, seamless, elegant, delve, etc.)",
      "Scan for forbidden phrases (In order to, It's worth noting, Furthermore, Let's dive in, etc.)",
      "Scan for forbidden patterns (em-dashes, rhetorical questions, headers without content, lists > 7 items)",
      "Scan for tutorial voice (In this section, we will explore...)",
      "Scan for vague quantifiers (various, multiple, several)",
      "Scan for marketing speak (best practices, cutting-edge, transformative)",
      "Write doc-slop-findings.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "gemini-editorial",
    "description": "Review documentation structure, clarity, and completeness",
    "subagent": "gemini-reviewer",
    "parents": ["draft-documentation"],
    "steps": [
      "Read guidelines from ~/.claude-plugins/jons-plan/commands/new-tech-docs.md (sections: Target Audience, Document Structure, Example-Based Pattern)",
      "Evaluate document structure and navigation",
      "Check logical flow between sections",
      "Identify gaps (unanswered reader questions)",
      "Verify examples appear before explanations",
      "Write review.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "codex-accuracy",
    "description": "Review documentation for technical accuracy",
    "subagent": "codex-reviewer",
    "parents": ["draft-documentation"],
    "steps": [
      "Verify code examples compile/parse",
      "Check function signatures match code",
      "Verify claimed behavior matches implementation",
      "Check configuration options exist",
      "Flag unverifiable claims",
      "Write review.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "technical-documentation-expert-review",
    "description": "Expert review of documentation quality and effectiveness",
    "model": "opus",
    "parents": ["draft-documentation"],
    "steps": [
      "Read the review prompt at ~/.claude-plugins/jons-plan/prompts/technical-documentation-review.md",
      "Apply the review criteria and methodology from the prompt to the documentation",
      "Use domain-specific scrutiny levels: rigorous for auth/data model/context, pragmatic for implementation scope",
      "For each concern, provide concrete scenarios and suggest alternatives",
      "Write review.md to task output directory following the output format from the prompt"
    ],
    "status": "todo"
  }
]
```

### Phase 4: Synthesis

```json
[
  {
    "id": "synthesize-feedback",
    "description": "Categorize and prioritize review feedback",
    "model": "opus",
    "parents": ["validate-links", "doc-slop-detect", "gemini-editorial", "codex-accuracy", "technical-documentation-expert-review"],
    "steps": [
      "Read all review outputs",
      "Categorize each finding as ACCEPT or DISCARD",
      "Priority order: correctness > broken links > completeness > clarity > style",
      "ACCEPT: broken links, inaccuracies, missing critical info, high-severity slop",
      "DISCARD: style preferences, short lists flagged as exhaustive, pedantic changes",
      "Write categorized-feedback.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "final-documentation",
    "description": "Produce final documentation incorporating feedback",
    "model": "opus",
    "parents": ["synthesize-feedback"],
    "steps": [
      "Read all guidelines from ~/.claude-plugins/jons-plan/commands/new-tech-docs.md (sections: Target Audience through Document Structure)",
      "Read draft-docs.md from draft-documentation task",
      "Read categorized-feedback.md",
      "Apply all ACCEPT feedback items",
      "Verify version anchor is present",
      "Write final documentation to plan directory as [TOPIC].md"
    ],
    "status": "todo"
  }
]
```

## Documentation Anti-Slop Guidelines

### Forbidden Words
utilize, leverage, ensure, robust, comprehensive, streamlined, seamless, elegant, delve, navigate, showcase, facilitate, enhance, functionality, pivotal, tapestry, multifaceted, testament, underscore, realm, embark, unwavering, transformative, holistic, intricate

### Forbidden Phrases
- "In order to" → "to"
- "It's worth noting" → just say it
- "Furthermore", "Moreover" → new sentence
- "not only... but also..." → say both directly
- "In conclusion" → omit
- "Let's dive in" → omit
- "Let's get started" → omit

### Forbidden Patterns
- Em-dashes (—)
- Headers without content
- Rhetorical questions
- "In this section, we will explore..."
- "This code does X" → prefer "Code X"
- Lists > 7 items (link to source instead)

### Voice
- Active: "The parser reads" not "is read by"
- Short sentences
- Plain words: "use" not "utilize"

## Example-Based Documentation Pattern

Bad (exhaustive list):
```markdown
## Hooks
Available hooks: PreToolUse, PostToolUse, Stop, PreCompact, SessionStart, Notification, SubagentStop, SubagentStart
```

Good (example + search):
```markdown
## Hooks

The SessionStart hook runs at conversation start:

```python
def session_start_hook():
    print("Session started")
```

To find all hooks, search for `hook_type` in hooks.py.
```

## Cross-Reference Guidelines

### To Source Code
```markdown
See [`src/parser.py:45-60`](../src/parser.py) for tokenization.
```

### To Related Documentation
```markdown
For configuration, see [config.md](./config.md).
```

### To External Resources
```markdown
For regex syntax, see [Python re module](https://docs.python.org/3/library/re.html#regular-expression-syntax).
```

## Version Anchoring

Include at top of generated documentation:
```markdown
---
generated_from_commit: [full SHA]
generated_date: [YYYY-MM-DD]
---
```

## Negative Space Documentation

Document what the system does NOT do only when:
- A developer would reasonably assume it does
- The misconception leads to bugs or wasted debugging
- It's a deliberate design choice, not missing feature

Good:
```markdown
Note: The cache does not persist across restarts.
```

Bad:
```markdown
Note: This function does not make coffee.
```

Omit negative space entirely if nothing meets criteria.

## Durable Documentation

Write documentation that survives code changes:

Fragile:
```markdown
The third argument controls buffering.
```

Durable:
```markdown
Pass `buffer_size` to control memory. Search for "buffer_size" in file_processor.py.
```

Principles:
- Reference by name, not position
- Include search terms for discovery
- Point to source for exhaustive details

## Document Structure

1. **Purpose** - One sentence
2. **Quick Start** - Minimal working example
3. **Examples** - 2-3 common patterns
4. **Details** - Deeper explanation
5. **See Also** - Cross-references

Skip empty sections.

## Task Schema

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (kebab-case) |
| `description` | Yes | What task accomplishes |
| `parents` | Yes | Task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Steps to complete |
| `status` | Yes | Always `"todo"` when creating (valid: `todo`, `in-progress`, `done`, `blocked`) |
| `subagent` | No | `Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `gemini-reviewer`, `codex-reviewer` |
| `subagent_prompt` | No | Thoroughness (NOT for reviewers) |
| `model` | No | `haiku`, `sonnet`, `opus` (NOT for reviewers) |

## Important Reminders

- You are creating a **plan**, not writing documentation now
- The work happens during `/jons-plan:proceed`
- All tasks start with `status: "todo"`
- Reviewers (gemini-reviewer, codex-reviewer) do NOT use `model` or `subagent_prompt`
- Final deliverable is documentation markdown, not code changes
