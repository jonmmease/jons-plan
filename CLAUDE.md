# Long-Running Agent Harness (jons-plan plugin)

Based on Anthropic's "Effective Harnesses for Long-Running Agents" pattern.

## Two Agent Roles

### Planning Agent (`/jons-plan:new` command)
Creates infrastructure for a new plan:
- `plan.md` - Implementation plan
- `tasks.json` - Task list with dependencies (all `status: "todo"`)
- `claude-progress.txt` - Progress log

### Coding Agent (Normal Sessions)
Works incrementally on tasks:
- Runs startup routine (pwd, git logs, progress, tasks)
- Resumes any `in-progress` tasks first
- Picks from available tasks (status `todo`, all parents `done`)
- Sets task to `in-progress` when starting, `done` when complete
- Can parallelize independent tasks via subagents

## Plan Commands

Use these slash commands to manage plans:

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create new implementation plan (explores codebase, creates tasks) |
| `/jons-plan:new-design [topic]` | Create new design plan (research, exploration, produces `design.md`) |
| `/jons-plan:new-deep [topic]` | Create implementation plan with deep automated exploration and review |
| `/jons-plan:plan [feedback]` | Refine active plan |
| `/jons-plan:proceed` | Start implementing tasks (enforces status workflow) |
| `/jons-plan:switch [name]` | Switch to different plan |
| `/jons-plan:status` | Show all plans and task progress |

## Plan Types Comparison

The plugin supports three plan creation commands:

| Aspect | `/new` | `/new-design` | `/new-deep` |
|--------|--------|---------------|-------------|
| **Purpose** | Build features, fix bugs | Research, explore, design | Complex implementation with thorough research |
| **Naming** | `[topic]` | `[topic]-design` (enforced) | `[topic]` |
| **Deliverable** | Code changes | `design.md` document | Code changes |
| **Exploration** | Light exploration | Creates tasks for later | Auto-executes exploration |
| **External review** | No | Creates review task | Auto-executes review |
| **Synthesis** | Single-shot | Task in plan | Multi-round with feedback |
| **User intervention** | After planning | After each /proceed | After all phases complete |

**When to use each:**
- **`/new`** — Simple features, bug fixes, clear requirements
- **`/new-design`** — Research projects, design decisions, when you need `design.md`
- **`/new-deep`** — Complex features requiring thorough exploration and external review before implementation

## Refining Plans (`/jons-plan:plan`)

When the user asks for updates or changes to a plan, **always modify tasks.json**:

- **Add new tasks** based on user feedback
- **Reset tasks to `todo`** if they need rework
- **Add tasks even when all are `done`** - a "complete" plan can always be extended

**Never say "all tasks are complete" and stop.** If the user asks for changes, updates, or more work:
1. Add the requested tasks to `tasks.json`
2. Set appropriate parent dependencies
3. Tell the user to run `/jons-plan:proceed` to continue working

Example: If a user says "now add a review task" after all tasks are done, add a new task with `status: "todo"` and prompt them to proceed.

## Plan Structure

Plans live in `.claude/jons-plan/plans/[plan-name]/`:
- `plan.md` - Implementation plan
- `tasks.json` - Task list with dependencies and status
- `claude-progress.txt` - Log of agent actions
- `tasks/[task-id]/` - Created only when a task writes output (not pre-created)

Active plan: `.claude/jons-plan/active-plan`

## Task Rules (Critical)

- All tasks start with `status: "todo"`
- Each task has a unique `id` and optional `parents` array (task IDs it depends on)
- Task statuses: `todo` → `in-progress` → `done` (or `blocked` if stuck)

### Blocked Tasks

When a task cannot proceed due to issues beyond the coding agent's control, mark it as `blocked`:

1. **Create blockers.md** in the task directory with:
   - What was attempted
   - Why it failed
   - Suggested resolution

2. **Set status to blocked**:
   ```bash
   uv run ~/.claude-plugins/jons-plan/plan.py set-status <task-id> blocked
   ```
   Note: This command validates that `blockers.md` exists first.

3. **Stop execution** - Do not continue with other tasks. Tell the user to run `/jons-plan:plan` to address the blocker.

When replanning with `/jons-plan:plan`, the planner reads all `blockers.md` files and updates the task graph to resolve them.

### Test-First Planning

For features with clear acceptance criteria, use a test-first task structure:

```
define-tests-* (early)     → Write test-spec.md
    ↓
implement-* (middle)       → Read spec, build feature
    ↓
validate-* (late)          → Run tests, verify criteria
```

**Test definition tasks** write `test-spec.md` to their output directory. This flows automatically to child tasks via `build-task-prompt`.

**Validation tasks** run tests and either mark `done` (all pass) or `blocked` with observations if failures require a "large side quest" (out of scope, architectural mismatch, missing prerequisite, etc.).

See `proceed.md` for detailed validation task guidance and blocking criteria.

**Parallelization rules:** Tasks without parent dependencies can run in parallel, but **only if they won't mutate files in the same directories**. Add parent dependencies to force sequential execution when:
- Tasks modify files in the same directory
- Tasks edit the same configuration files
- Tasks have logical ordering requirements

Safe to parallelize (no shared parents needed):
- Research tasks that only write to their own `tasks/[task-id]/` output directory
- Monorepo tasks that modify separate packages (e.g., `packages/foo/` vs `packages/bar/`)
- Tasks that only read from the codebase without writing

Must be sequential (add parent dependency):
- Multiple tasks editing `src/` files
- Tasks that both modify `pyproject.toml` or config files
- Implementation tasks that build on each other's code

## Subagent Configuration

Tasks can specify optional fields to control how they're executed:

```json
{
  "id": "research-apis",
  "description": "Research available APIs",
  "subagent": "Explore",
  "subagent_prompt": "very thorough analysis",
  "model": "haiku",
  "parents": [],
  "steps": ["Find all API endpoints", "Document patterns"],
  "status": "todo"
}
```

### Task Schema

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier |
| `description` | Yes | What the task accomplishes |
| `parents` | Yes | Array of task IDs that must complete first (empty `[]` if none) |
| `steps` | Yes | Array of steps to complete the task |
| `status` | Yes | `todo`, `in-progress`, `done`, or `blocked` |
| `subagent` | No | Agent type (default: `general-purpose`) |
| `subagent_prompt` | No | Additional prompt text for the agent (e.g., thoroughness level) |
| `model` | No | Model to use (default: `sonnet`) |

### Subagent Types

| Type | Use For |
|------|---------|
| `general-purpose` | **(default)** Implementation tasks, complex multi-step work, code changes |
| `Explore` | Fast codebase exploration, finding files, searching keywords, understanding architecture |
| `Plan` | Same as Explore |
| `claude-code-guide` | Questions about Claude Code features, hooks, MCP servers |
| `gemini-reviewer` | Second opinions via Gemini 3 Pro - plan reviews, code reviews, image/diagram analysis, large context synthesis |
| `codex-reviewer` | Second opinions via GPT-5-codex - code reviews, architectural decisions, debugging assistance |

### Subagent Prompt

The `subagent_prompt` field adds context to the agent's prompt. For `Explore` agents, use it to specify thoroughness:

| Thoroughness | When to Use |
|--------------|-------------|
| `"quick search"` | Simple file/pattern lookup, known locations |
| `"medium exploration"` | Moderate search across likely locations |
| `"very thorough analysis across multiple locations and naming conventions"` | Comprehensive search, unknown codebase structure |

Examples:
```json
{"subagent": "Explore", "subagent_prompt": "quick search"}
{"subagent": "Explore", "subagent_prompt": "very thorough analysis"}
{"subagent": "general-purpose", "subagent_prompt": "focus on error handling"}
```

### Model Options

| Model | Use For |
|-------|---------|
| `sonnet` | **(default)** Balanced speed/capability |
| `haiku` | Fast, cheap - research tasks, simple exploration, quick lookups |
| `opus` | Most capable - complex implementation, architecture decisions, nuanced code |

### Planning Guidelines

When creating tasks in plan mode, choose the right combination:

| Task Type | `subagent` | `subagent_prompt` | `model` |
|-----------|------------|-------------------|---------|
| Quick file lookup | `Explore` | `quick search` | `haiku` |
| Thorough codebase research | `Explore` | `very thorough analysis...` | `haiku` |
| Simple implementation | (omit) | (omit) | (omit) |
| Complex implementation | (omit) | (omit) | `opus` |
| Architecture decisions | (omit) | (omit) | `opus` |
| Test definition | (omit) | (omit) | (omit) |
| Validation/verification | (omit) | (omit) | (omit) |
| Plan/design review | `gemini-reviewer` | (omit) | (omit) |
| Code review before commit | `codex-reviewer` | (omit) | (omit) |
| Image/diagram analysis | `gemini-reviewer` | (omit) | (omit) |

**Note:** The `gemini-reviewer` and `codex-reviewer` agents are proxies to external models (Gemini 3 Pro and GPT-5-codex). They ignore the `model` field since they always call their respective CLIs.

### Execution Guidelines

When executing tasks via subagents, **honor the task's configuration**:

```
Task tool call:
  subagent_type: task.subagent or "general-purpose"
  model: task.model (omit if not specified to use default)
  prompt: Construct from task fields (see below)
```

**Prompt construction:**
```
{task.subagent_prompt}: {task.description}

Steps:
- {step 1}
- {step 2}
...

{context from parent task outputs if any}
```

If `subagent_prompt` is not specified, omit that prefix.

**Task workflow:**
1. **BEFORE starting work** on a task, set status to `in-progress` first
2. **IMMEDIATELY after completing** a task, set status to `done` (do NOT batch - update each task as soon as it's done)
3. Tasks are "available" when: status is `todo` AND all parents are `done`
4. Multiple available tasks can run in parallel via subagents

**⚠️ Status updates are mandatory:**
- Never start working on a task without first marking it `in-progress`
- Never delay marking a task `done` - do it right away, not after finishing multiple tasks

**Updating task status:** Always use the plan CLI instead of editing tasks.json directly. This ensures proper logging.
```bash
uv run ~/.claude-plugins/jons-plan/plan.py set-status task-id in-progress  # starting
uv run ~/.claude-plugins/jons-plan/plan.py set-status task-id done         # finished
```

## Task Outputs

Each task can optionally write outputs to: `.claude/jons-plan/plans/[plan]/tasks/[task-id]/`

**Outputs are optional.** Implementation tasks that only modify repo files don't need outputs. Research/planning tasks that produce findings for downstream tasks should write outputs.

**Starting a task:**
1. Set status to `in-progress`
2. If task has parents, check for their outputs:
   ```bash
   # List parent directories that have outputs
   uv run ~/.claude-plugins/jons-plan/plan.py parent-dirs my-task-id
   ```
3. Read any parent output files for context
4. Do the work

**Completing a task (only if outputs needed):**
1. Create task directory and write outputs (only do this if you have output to save):
   ```bash
   TASK_DIR=$(uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir my-task-id)
   echo "# Research Findings..." > "${TASK_DIR}/output.md"
   ```
2. Set status to `done`

**Do NOT create task directories for tasks without output.** Only call `ensure-task-dir` when you have actual artifacts to write.

**Important: Follow explicit paths in task steps.** If a task's steps specify a file location (e.g., "Save to reports/comparison.md"), write there. The `tasks/[task-id]/` directory is only for intermediate artifacts passed to child tasks when no explicit path is given.

**When to use `tasks/[task-id]/`:**
- Intermediate findings that child tasks need
- No explicit output path in task steps
- Data that doesn't belong in the main repo

**When NOT to use `tasks/[task-id]/`:**
- Task steps specify an explicit path → write there instead
- Implementation tasks (code goes in repo)
- Bug fixes, refactoring (changes are in repo)

## Task-Level Progress (Best Effort)

Each task can have its own progress log at: `.claude/jons-plan/plans/[plan]/tasks/[task-id]/progress.txt`

**Automatic entries:**
- `set-status in-progress` → writes TASK_STARTED with description and steps
- `set-status done` → writes TASK_COMPLETED

**Manual logging (best effort):**
Log your progress as you work. This helps with resumption after compaction or session boundaries.

```bash
uv run ~/.claude-plugins/jons-plan/plan.py task-log <task-id> "message"
```

**When to log:**
- After completing each step: `"Completed step 1: Created middleware skeleton"`
- When modifying files: `"Modified src/auth/middleware.ts"`
- Before significant decisions: `"Choosing JWT over sessions for stateless auth"`
- When encountering blockers: `"Blocked: need to resolve dependency conflict"`

## Subagent Context Injection

Use `build-task-prompt` to automatically gather all context when launching a subagent:

```bash
PROMPT=$(uv run ~/.claude-plugins/jons-plan/plan.py build-task-prompt <task-id>)
```

This command outputs a complete prompt containing:
- Task description (with `subagent_prompt` prefix if configured)
- Steps as bullet list
- Parent task outputs (contents of output files from parent tasks)
- Prior progress entries (if any, with resumption instructions)

Use this prompt when launching the subagent:
```
Task(
  subagent_type: task.subagent or "general-purpose",
  model: task.model (if specified),
  prompt: $PROMPT
)
```

This eliminates manual context gathering and ensures subagents always have complete context.

## Session Workflow

### Startup (Automated by SessionStart hook)
1. Confirm working directory (`pwd`)
2. Show recent git logs
3. Show recent plan-level progress entries
4. Show in-progress and available tasks
5. Show task-level progress for in-progress tasks
6. Auto-resume prompt if tasks were in-progress

### PreCompact Hook
Before compaction, the hook injects jons-plan state into the compaction summary:
- Session mode (proceed, plan, etc.)
- Active plan name
- In-progress tasks with recent progress entries
- Pointers to task progress files

This ensures jons-plan context survives compaction.

### During Work
- PostToolUse hook logs file modifications to plan-level progress
- Agent logs task-level progress using `task-log` (best effort)
- Commit at logical checkpoints

### Session End (Automated by Stop hook)
The Stop hook provides **auto-continue** behavior:

**When session mode is `proceed`:**
- If there are available tasks → **blocks the stop** and tells Claude to continue
- If there are blocked tasks → allows stop (human intervention needed)
- If all tasks are done → allows stop with session summary

**Otherwise:**
- Shows session summary
- Reminds about uncommitted changes

This means `/jons-plan:proceed` will keep Claude working until all tasks are complete or a task becomes blocked. No need to re-run the command after each batch of tasks.

## CLI Reference

All commands: `uv run ~/.claude-plugins/jons-plan/plan.py <subcommand>`

### Overview Commands
| Command | Description |
|---------|-------------|
| `status` | **Comprehensive overview** - all plans, active plan stats, in-progress tasks, next available |
| `list-plans` | List all plans (marks active) |
| `active-plan` | Print active plan name |
| `active-plan-dir` | Print active plan directory path |

### Plan Management
| Command | Description |
|---------|-------------|
| `set-active <plan>` | Switch active plan |

### Task Management
| Command | Description |
|---------|-------------|
| `task-stats` | Print task counts (done/total, in-progress, todo) |
| `in-progress` | List tasks currently in progress |
| `next-tasks` | List available tasks (todo with all parents done) |
| `set-status <task-id> <status>` | Set task status (todo, in-progress, done, blocked) |

### Progress Logging
| Command | Description |
|---------|-------------|
| `log <message>` | Append message to plan-level progress log |
| `recent-progress [-n N]` | Show recent plan-level progress entries (default: 10) |

### Task-Level Progress
| Command | Description |
|---------|-------------|
| `task-log <task-id> <message>` | Append message to task's progress.txt |
| `task-progress <task-id> [-n N]` | Show recent entries from task's progress.txt (default: 10) |
| `build-task-prompt <task-id>` | Build complete prompt with all context (description, steps, parent outputs, prior progress) |

### Blocked Task Management
| Command | Description |
|---------|-------------|
| `blocked-tasks` | List all blocked tasks |
| `has-blockers` | Check if plan has blocked tasks (exit 0 if yes) |

### Task Outputs
| Command | Description |
|---------|-------------|
| `task-dir <task-id>` | Print task output directory path |
| `ensure-task-dir <task-id>` | Create task directory if needed, print path |
| `parent-dirs <task-id>` | List parent task directories that exist |
| `has-outputs <task-id>` | Check if task has outputs (exit code 0/1) |

### Confidence Scoring
| Command | Description |
|---------|-------------|
| `record-confidence <task-id> <score> <rationale>` | Record confidence score (1-5) for a task |
| `check-confidence <task-id>` | Check recorded confidence score for a task |
| `low-confidence-tasks` | List tasks with confidence score < 4 |

### Dynamic Task Modification
| Command | Description |
|---------|-------------|
| `add-task <json-file>` | Add a new task from JSON file (use `-` for stdin) |
| `update-task-parents <task-id> <parent-ids...>` | Update a task's parent dependencies |
| `update-task-steps <task-id> <json-file>` | Update a task's steps from JSON (use `-` for stdin) |

## Confidence Scoring

Synthesis tasks should provide a confidence assessment indicating how tractable the plan is.

### Score Scale

| Score | Meaning | Action |
|-------|---------|--------|
| 5 | Fully confident | Proceed automatically |
| 4 | Minor uncertainties | Proceed, note concerns in plan |
| 3 | Moderate concerns | **STOP and discuss with user** |
| 2 | Significant doubts | **STOP**, recommend descoping |
| 1 | Not tractable | **STOP**, recommend abandoning or major pivot |

### Confidence Dimensions

- **Feasibility**: Can this be implemented with current architecture/tools?
- **Scope**: Is this achievable in a reasonable task count?
- **Technical Risk**: Are there unknowns that could derail implementation?

### Recording Confidence

```bash
# Record confidence score for a synthesis task
uv run ~/.claude-plugins/jons-plan/plan.py record-confidence draft-synthesis 4 "Minor uncertainty about API compatibility"

# Check confidence for a task
uv run ~/.claude-plugins/jons-plan/plan.py check-confidence draft-synthesis

# List all low-confidence tasks
uv run ~/.claude-plugins/jons-plan/plan.py low-confidence-tasks
```

### When Confidence < 4

If confidence is below 4, the agent must **STOP** and use `AskUserQuestion` to discuss concerns:

```
If confidence < 4:
  - Present the confidence assessment to the user
  - List specific concerns and dimensions
  - Ask for guidance: proceed anyway, descope, or abandon
  - Wait for user response before continuing
```

## Feedback Categorization

When processing reviewer feedback (gemini-reviewer, codex-reviewer), categorize each piece as:

| Category | Meaning | Action |
|----------|---------|--------|
| **ACCEPT** | Valid criticism, straightforward to address | Apply immediately |
| **INVESTIGATE** | Challenges assumptions, needs validation | Launch explore agents |
| **REJECT** | Misunderstands context or constraints | Document rationale, skip |

### categorized-feedback.md Format

```markdown
# Categorized Feedback

## Confidence: [1-5]
[Brief rationale]

## Source: gemini-reviewer

### ACCEPT
- [Feedback point]: [How to address]

### INVESTIGATE
- [Feedback point]: [Question for explore agent]
  - Domain: codebase|technical|requirements
  - Specific question: "Does X exist? How does Y work?"

### REJECT
- [Feedback point]: [Why this doesn't apply]

## Source: codex-reviewer
[Same structure]

## Investigation Questions Summary
- Codebase: [list of questions]
- Technical: [list of questions]
- Requirements: [list of questions]
```

## Dynamic Task Modification

For `/new-design` plans, the `process-feedback` task can modify `tasks.json` at runtime to add investigation tasks based on reviewer feedback.

### When to Add Investigation Tasks

Add investigation tasks when feedback items are categorized as **INVESTIGATE**:
- Reviewer challenges a core assumption
- Need to validate something in the codebase
- Technical approach needs verification

### CLI Commands for Dynamic Modification

```bash
# Add a new investigation task
echo '{"id": "investigate-api", "description": "Validate API compatibility concern", "subagent": "Explore", "model": "haiku", "parents": ["process-feedback"], "steps": ["Search for X", "Verify Y"], "status": "todo"}' | uv run ~/.claude-plugins/jons-plan/plan.py add-task -

# Update final-synthesis to depend on new investigation task
uv run ~/.claude-plugins/jons-plan/plan.py update-task-parents final-synthesis process-feedback investigate-api

# Update steps for an existing task
echo '["Updated step 1", "Updated step 2"]' | uv run ~/.claude-plugins/jons-plan/plan.py update-task-steps final-synthesis -
```

### Task Schema Validation

All task modifications are validated against the schema:
- Required fields: `id`, `description`, `parents`, `steps`, `status`
- Valid statuses: `todo`, `in-progress`, `done`, `blocked`
- Valid subagents: `general-purpose`, `Explore`, `Plan`, `claude-code-guide`, `gemini-reviewer`, `codex-reviewer`
- Valid models: `sonnet`, `haiku`, `opus`
- Parent references must exist in tasks.json
