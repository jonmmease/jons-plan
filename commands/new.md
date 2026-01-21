---
description: Create a new jons-plan implementation plan
allowed-tools: WebSearch, Fetch, WebFetch, Bash(find:*), Bash(git status:*), Bash(tree:*), Bash(mkdir:*), Write(**/.claude/jons-plan/**), Edit(**/.claude/jons-plan/**), Edit(**/.git/info/exclude)
---

ultrathink

# Create New Plan

You are creating a new implementation plan for the jons-plan plugin.

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Search the web (WebSearch, WebFetch tools)
- Launch Explore/Plan subagents for research
- Write to `.claude/jons-plan/plans/[plan-name]/` directory ONLY
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
No topic provided. Ask the user what they want to build.
{{/if}}

## Workflow Selection

All plans use workflow-based execution. The workflow defines the phases of work.

### Explicit Workflow
If args start with `--workflow <name>` (e.g., `/jons-plan:new --workflow implementation add feature`), use the specified workflow template.

### Auto-Selection
If no `--workflow` is specified, analyze the user's request and suggest a workflow based on the heuristics below.

### Auto-Selection Heuristics

When no `--workflow` is specified, analyze the user's request and suggest a workflow:

| Pattern | Suggested Workflow | Examples |
|---------|-------------------|----------|
| Bug fix, error, issue | `implementation` | "fix the login bug", "resolve crash", "handle edge case" |
| Quick fix, simple change, familiar code | `direct-implementation` | "rename this function", "add a field", "update the config" |
| Design, architecture, RFC | `design` | "design auth system", "plan API structure", "evaluate options" |
| Implement, add, build feature | `implementation` | "add dark mode", "implement caching", "build search" |
| Review code changes, create PR | `code-review` | "review my changes", "audit security", "analyze branch" |
| Review PR description | `pr-review` | "review this PR description", "improve my PR writeup" |
| Deslop, clean up AI patterns | `deslop-pr` | "deslop this PR", "remove AI slop", "clean up PR description" |
| Review RFC, design doc, proposal | `tech-docs-review` | "review this RFC", "give feedback on design doc", "review proposal" |
| Document, explain, write docs | `tech-docs` | "document the API", "explain how X works", "write guide" |
| Complex, thorough, research | `deep-implementation` | "thoroughly research and implement", "complex feature with review" |
| Design then implement | `design-and-implementation` | "design and optionally implement", "explore then build" |
| Ambiguous, multi-component, unclear scope | `dynamic` | "build this feature" (unclear scope), "implement X" (multi-component) |

**Process:**
1. Parse the request for keywords
2. Match against patterns above
3. Use `AskUserQuestion` to confirm or let user override:
   - "Based on your request, I suggest the **{workflow}** workflow. This will {brief description}."
   - Options: Use suggested workflow, Choose different workflow
4. If user chooses "different workflow", present all available options

### Available Workflows
Built-in workflows in `~/.claude-plugins/jons-plan/workflows/`:
- `implementation` - Feature implementation with research and validation
- `direct-implementation` - Simple plan-implement-verify for familiar code (no research)
- `design` - Research and produce a design document
- `design-and-implementation` - Design first, optionally implement after approval
- `deep-implementation` - Complex features with thorough research and review
- `code-review` - Review code changes + generate PR description
- `pr-review` - Review existing PR description
- `deslop-pr` - Quick slop detection and cleanup for PR descriptions
- `tech-docs` - Technical documentation creation
- `tech-docs-review` - Review RFCs, design docs, proposals
- `dynamic` - Research-first workflow where phases are generated based on codebase exploration

### Workflow Schema (for custom workflows)

When creating a custom workflow, read the template workflow closest to your needs (in `~/.claude-plugins/jons-plan/workflows/`) as a reference. Use ONLY the fields documented below.

#### Top-level Structure
```toml
[workflow]
name = "workflow-name"           # Required
description = "What it does"     # Optional

[[phases]]                       # Required: array of phases
# phase fields...
```

#### Valid Phase Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | **Required.** Unique phase identifier (kebab-case) |
| `prompt` | string | **Required.** Instructions for this phase |
| `suggested_next` | array | Valid transitions - strings or `{ phase = "id", requires_approval = true, approval_prompt = "..." }` |
| `terminal` | bool | If true, workflow ends here |
| `use_tasks` | bool | Phase uses tasks.json |
| `requires_user_input` | bool | Stop for user approval |
| `required_artifacts` | array | Artifact names that must be recorded before leaving this phase |
| `context_artifacts` | array | Artifact names to inject from upstream phases into phase prompt |
| `on_blocked` | string | Phase to go to when blocked (`"self"` or phase ID) |
| `max_retries` | int | Max re-entries before escalation |
| `supports_proposals` | bool | Enable CLAUDE.md proposals |
| `supports_prototypes` | bool | Enable prototype tasks |
| `expand_prompt` | string | For dynamic phase expansion |

#### Artifact Flow Between Phases

Artifacts create a contract between phases:
- `required_artifacts` = what this phase **must produce** (outputs)
- `context_artifacts` = what this phase **needs from upstream** (inputs)

**Example workflow:**
```toml
[[phases]]
id = "research"
required_artifacts = ["research"]  # Must produce research.md
prompt = "Research the topic and write research.md"

[[phases]]
id = "plan"
context_artifacts = ["research"]   # Gets research.md injected into prompt
required_artifacts = ["implementation-plan"]
prompt = "Create a plan based on the research findings (injected above)"

[[phases]]
id = "implement"
context_artifacts = ["implementation-plan"]  # Gets plan injected
prompt = "Execute the implementation plan (injected above)"
```

**How it works:**
1. Research phase creates `research.md` and records it: `record-artifact research research.md`
2. Transition to plan phase is blocked until `research` artifact is recorded
3. Plan phase runs `phase-context` → research.md content is automatically injected
4. Plan phase prompt says "(injected above)" because content appears before the prompt

**Recording artifacts:**
```bash
uv run plan.py record-artifact <name> <filename>
```

The `phase-context` command automatically shows required artifacts that need to be recorded before transitioning.

#### INVALID Patterns (DO NOT USE)

```toml
# WRONG - nested tables don't exist
[[phases.transitions]]
trigger = "done"
target = "next"

# WRONG - unknown fields
[[phases]]
id = "foo"
transitions = [...]  # NOT a valid field
```

## Plan Creation Steps

### Step 1: Clarify Requirements

**Before creating any files**, use `AskUserQuestion` to clarify the request. This is MANDATORY for non-trivial requests.

**Ask about:**
1. **Scope boundaries** - What's in/out of scope?
2. **Technical choices** - Libraries, patterns, approaches with trade-offs
3. **Ambiguous terms** - Anything that could be interpreted multiple ways
4. **Constraints** - Performance, compatibility, timeline considerations
5. **Preferences** - When multiple valid approaches exist

**Format:** Use 2-4 questions per `AskUserQuestion` call. Continue asking until requirements are clear enough to create a concrete plan.

**Example questions:**
- "What database approach would you prefer?" → Options: SQLite, Realm, Hive, Research alternatives
- "How should priorities be represented?" → Options: Simple (High/Med/Low), Numeric (1-10), Custom labels
- "Should the app support..." → Options for scope clarification

**Skip this step only if:**
- Request is extremely specific with no ambiguity
- It's a simple bug fix with clear reproduction steps
- User explicitly says "just do it, don't ask questions"

### Step 2: Derive Plan Name and Set Active
Convert topic to kebab-case (e.g., "add user authentication" → "add-user-authentication")

**Immediately after deriving the plan name**, set it as active and set mode:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-active <plan-name>
uv run ~/.claude-plugins/jons-plan/plan.py set-mode new
```

This ensures the plan context is preserved if compaction occurs during plan creation.

### Step 3: Create Plan Infrastructure

**IMPORTANT:** Use git root (or cwd if not in a repo) to avoid creating `.claude/` in subdirectories:
```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
```

1. If in a git repo, ensure `.claude/jons-plan/` is in `.git/info/exclude` (do NOT modify `.gitignore`)
2. Create directory:
   ```bash
   mkdir -p "$PROJECT_ROOT/.claude/jons-plan/plans/<plan-name>"
   ```
3. Copy workflow.toml to plan directory:
   ```bash
   cp ~/.claude-plugins/jons-plan/workflows/<name>.toml "$PROJECT_ROOT/.claude/jons-plan/plans/<plan-name>/workflow.toml"
   ```
4. Create `request.md` with the user's request (use absolute path: `$PROJECT_ROOT/.claude/jons-plan/plans/<plan-name>/request.md`)
5. Create `claude-progress.txt` with initial entry (use absolute path)

### Step 4: Initialize State Machine
1. Initialize state.json with first phase
2. Create first phase directory:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py enter-phase <first-phase-id>
   ```

### Step 5: Present Summary
1. Display workflow diagram:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py workflow-diagram
   ```
2. Show current phase and its prompt
3. Launch the workflow viewer in the background and show the command:
   ```bash
   PLAN_DIR="$(uv run ~/.claude-plugins/jons-plan/plan.py active-plan-dir)"
   echo "Launching viewer: uv run ~/.claude-plugins/jons-plan/viewer.py \"$PLAN_DIR\""
   nohup uv run ~/.claude-plugins/jons-plan/viewer.py "$PLAN_DIR" &>/dev/null &
   ```
4. Tell user: "Type `/jons-plan:proceed` to start, or `/jons-plan:plan` to refine the request. To relaunch the viewer, ask me to 'launch the viewer'."

## Task Schema

The `tasks.json` file is a JSON array of task objects:

```json
[
  { "id": "task-1", ... },
  { "id": "task-2", ... }
]
```

Each task should follow this schema:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier (kebab-case) |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Array of task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Array of steps to complete the task |
| `status` | Yes | Always `"todo"` when creating (execution changes to `in-progress`, `done`) |
| `subagent` | No | `general-purpose` (default), `Explore`, `Plan`, `claude-code-guide` |
| `subagent_prompt` | No | Additional context (e.g., "very thorough analysis") |
| `model` | No | `sonnet` (default), `haiku`, `opus` |
| `resources` | No | Array of resource identifiers requiring exclusive access |

Example task:
```json
{
  "id": "research-auth-patterns",
  "description": "Research existing authentication patterns in codebase",
  "subagent": "Explore",
  "subagent_prompt": "very thorough analysis",
  "model": "haiku",
  "parents": [],
  "steps": ["Find auth-related files", "Document existing patterns"],
  "status": "todo"
}
```

## Parallelization Rules

Tasks can run in parallel ONLY if they won't conflict:

**Safe to parallelize** (no parent dependency needed):
- Research tasks that only write to their task output directory: `.claude/jons-plan/plans/[plan]/phases/[phase]/tasks/[task-id]/` (use `ensure-task-dir` CLI to get path)
- Monorepo tasks that modify separate packages (e.g., `packages/foo/` vs `packages/bar/`)
- Tasks that only read from the codebase without writing

**Must be sequential** (add parent dependency):
- Multiple tasks editing files in the same directory
- Tasks that both modify the same config files
- Implementation tasks that build on each other's code

**Resource-based exclusion** (use `resources` field):
When tasks need exclusive access to shared resources but don't have a logical parent dependency, use the `resources` field:

```json
{
  "id": "browser-test-login",
  "description": "Test login flow in browser",
  "resources": ["chrome-devtools"],
  "parents": [],
  "steps": ["..."],
  "status": "todo"
},
{
  "id": "browser-test-checkout",
  "description": "Test checkout flow in browser",
  "resources": ["chrome-devtools"],
  "parents": [],
  "steps": ["..."],
  "status": "todo"
}
```

Tasks sharing resources are serialized even without parent dependencies. Use for:
- MCP servers that maintain state (browser automation, database connections)
- Shared files that multiple tasks may modify
- External services with rate limits or connection constraints

## Task Type Guidelines

| Task Type | `subagent` | `subagent_prompt` | `model` |
|-----------|------------|-------------------|---------|
| Quick file lookup | `Explore` | `quick search` | `haiku` |
| Thorough codebase research | `Explore` | `very thorough analysis` | `haiku` |
| Simple implementation | (omit) | (omit) | (omit) |
| Complex implementation | (omit) | (omit) | `opus` |
| Architecture decisions | (omit) | (omit) | `opus` |
| Test definition | (omit) | (omit) | (omit) |
| Validation/verification | (omit) | (omit) | (omit) |

## Task Sizing Guidelines

- Tasks should complete in one subagent session (~10 steps max)
- Each step should be independently verifiable
- If task exceeds scope, decompose into subtasks with parent dependencies
- Research tasks: scope to single topic/question
- Implementation tasks: scope to single file or closely related files

## Test-First Planning Pattern

For features with clear acceptance criteria, consider structuring tasks in a test-first pattern:

### When to Use Test-First

- Feature has measurable success criteria
- Multiple implementation tasks depend on consistent expectations
- You want explicit validation gates before marking complete
- Complex features that benefit from upfront test design

### Task Structure

```
define-tests-* (early)     → Write test-spec.md
    ↓
implement-* (middle)       → Read spec, build feature & tests
    ↓
validate-* (late)          → Run tests, verify criteria
```

### Test Specification Output

Test definition tasks write to the task output directory:
`.claude/jons-plan/plans/[plan]/phases/[phase]/tasks/[task-id]/test-spec.md`

Use `ensure-task-dir <task-id>` CLI to get the path.

Simple format:
```markdown
# Test Specification: [Feature]

## Tests to Add/Modify
- [ ] Test: [description] - [expected behavior]
- [ ] Test: [description] - [expected behavior]

## Acceptance Criteria
- [Criterion with measurable verification method]
- [Criterion with measurable verification method]

## Edge Cases
- [Edge case to handle]
```

### Example Task Structure

```json
[
  {
    "id": "define-tests-auth",
    "description": "Define test cases for authentication",
    "parents": [],
    "steps": [
      "Document required test scenarios",
      "Define acceptance criteria with measurable verification",
      "Write test-spec.md to task output directory"
    ],
    "status": "todo"
  },
  {
    "id": "implement-auth",
    "description": "Implement authentication to meet test spec",
    "parents": ["define-tests-auth"],
    "steps": [
      "Read test-spec.md from parent task",
      "Implement feature to satisfy criteria",
      "Write tests matching the specification"
    ],
    "status": "todo"
  },
  {
    "id": "validate-auth",
    "description": "Validate auth implementation against spec",
    "parents": ["implement-auth"],
    "steps": [
      "Read test-spec.md from define-tests-auth",
      "Run test suite and verify all tests pass",
      "If failures require large side quest, mark blocked with observations"
    ],
    "status": "todo"
  }
]
```

See `proceed.md` for validation task execution details and blocking criteria.

## Cache Integration (Research Tasks)

Before creating research tasks (web search, documentation lookup), check the research cache for relevant cached findings that could be reused.

### When to Check Cache

Check the cache when creating tasks that:
- Have keywords: "research", "investigate", "explore", "find", "lookup", "search"
- Use subagent type `Explore`
- Involve external sources (web, documentation, APIs)

### How to Check

For each research-type task, run:
```bash
uv run ~/.claude-plugins/jons-plan/plan.py cache-suggest --description "task description here"
```

### If Cache Has Hits

When `has_hits` is true and suggestions are returned:

1. **Add the reference task** from the suggestion to tasks.json:
   ```json
   {
     "id": "ref-42",
     "type": "cache-reference",
     "cache_id": 42,
     "description": "Cached: Original query...",
     "parents": [],
     "steps": [],
     "status": "todo"
   }
   ```

2. **Make the research task depend on the reference task**:
   ```json
   {
     "id": "research-sqlite-fts5",
     "description": "Research SQLite FTS5 patterns",
     "parents": ["ref-42"],
     "steps": ["Review cached findings", "Supplement with additional research if needed"],
     "status": "todo"
   }
   ```

This allows cached research to be injected via the parent task output flow.

### If No Cache Hits

Proceed with creating a normal research task. After the research completes (during implementation), consider caching valuable findings using `cache-add`.

## Prototype Tasks

For questions that can only be answered by trying something, create prototype tasks.

### When to Use Prototypes

- Library compatibility questions ("Do X and Y work together?")
- API behavior clarification ("What does this actually do?")
- Performance experiments ("Is this approach fast enough?")
- "Does this work?" questions

### Task Schema

```json
{
  "id": "proto-async-compat",
  "type": "prototype",
  "question": "Can library-x be used in async context?",
  "hypothesis": "Should work with run_in_executor",
  "description": "Test async compatibility",
  "parents": ["research-library-x"],
  "context_artifacts": ["research"],
  "steps": ["Create test script", "Run experiment", "Document findings"],
  "status": "todo"
}
```

### Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Must be `"prototype"` |
| `question` | Yes | The question being answered |
| `hypothesis` | No | Expected outcome (recommended) |
| `context_artifacts` | No | Include research artifacts from phase history |

Prototypes run in their task directory and produce `findings.md` with the answer to the question.

## Important Reminders

- NEVER implement code - only create the plan infrastructure
- Use appropriate subagent types for each task
- All tasks start with `status: "todo"`
- Ensure task dependencies prevent file conflicts
