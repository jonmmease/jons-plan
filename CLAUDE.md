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
| `/jons-plan:plan [feedback]` | Refine active plan |
| `/jons-plan:proceed` | Start implementing tasks (enforces status workflow) |
| `/jons-plan:switch [name]` | Switch to different plan |
| `/jons-plan:status` | Show all plans and task progress |

## Design Plans vs Implementation Plans

The plugin supports two types of plans:

| Aspect | Implementation Plan (`/new`) | Design Plan (`/new-design`) |
|--------|------------------------------|----------------------------|
| **Purpose** | Build features, fix bugs | Research, explore, design |
| **Naming** | `[topic]` | `[topic]-design` (enforced) |
| **Deliverable** | Code changes | `design.md` document |
| **Model strategy** | Balanced (sonnet default) | Exploration (haiku), synthesis (opus) |
| **External review** | Optional | Emphasized |

**Two-phase workflow:**
1. `/jons-plan:new-design auth` → Research, explore → `design.md`
2. User reviews design
3. `/jons-plan:new auth` → Implement based on approved design

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
- Task statuses: `todo` → `in-progress` → `done`

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
| `status` | Yes | `todo`, `in-progress`, or `done` |
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

## Session Workflow

### Startup (Automated by SessionStart hook)
1. Confirm working directory (`pwd`)
2. Show recent git logs
3. Show recent progress entries
4. Show in-progress and available tasks
5. Auto-resume prompt if tasks were in-progress

### During Work
- PostToolUse hook logs file modifications
- Commit at logical checkpoints
- Add context notes to progress file

### Session End (Automated by Stop hook)
- Shows session summary
- Reminds about uncommitted changes

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
| `set-status <task-id> <status>` | Set task status (todo, in-progress, done) |

### Progress Logging
| Command | Description |
|---------|-------------|
| `log <message>` | Append message to progress log |
| `recent-progress [-n N]` | Show recent progress entries (default: 10) |

### Task Outputs
| Command | Description |
|---------|-------------|
| `task-dir <task-id>` | Print task output directory path |
| `ensure-task-dir <task-id>` | Create task directory if needed, print path |
| `parent-dirs <task-id>` | List parent task directories that exist |
| `has-outputs <task-id>` | Check if task has outputs (exit code 0/1) |
