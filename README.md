# jons-plan Plugin

A Claude Code plugin inspired by Anthropic's [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) blog post for managing complex, multi-session coding tasks.

## Prerequisites

- **Claude Code** v2.1.3+ (the Anthropic CLI tool)
- **uv** - Python package runner (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **graphviz** (optional) - For workflow viewer (`brew install graphviz`)
- **Codex CLI** (optional) - For planning panel (`npm install -g @openai/codex`)
- **Gemini CLI** (optional) - For planning panel (`npm install -g @anthropic/gemini-cli`)

## Installation

Install via Claude Code's plugin marketplace:

```
/plugin marketplace add jonmmease/jons-plan
/plugin install jons-plan@jonmmease-jons-plan
```

Then restart Claude Code and test with `/jons-plan:status`.

---

## Overview

When AI agents work on complex projects that span multiple context windows, each new session starts with no memory of what came before. This plugin solves that problem by providing:

- **Structured task management** with dependencies and status tracking
- **Progress logging** to orient Claude at the start of each session
- **Task-level progress** for fine-grained resumption context
- **Automatic session resumption** when tasks were interrupted
- **PreCompact hook** to preserve state during context compaction
- **Parallel task execution** via subagents for independent work
- **Workflow-based execution** with phase transitions and state machine
- **Planning panel** — 3-agent parallel planning (Opus + Codex CLI + Gemini CLI) with senior-architect synthesis
- **Artifact system** with phase-level and plan-level artifact tracking
- **Dead-end tracking** to prevent repeating failed approaches

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## How It Works

The plugin uses a two-agent architecture:

### Planning Agent (`/jons-plan:new`)

Creates the infrastructure for a new plan:
- Analyzes your request and suggests an appropriate workflow
- Conducts pre-research and records a research brief
- Sets up the plan structure and initial phase
- Creates `request.md` with the refined/approved request

### Coding Agent (`/jons-plan:proceed`)

Works incrementally on tasks across sessions:
- Reads progress log to understand current state
- Resumes any `in-progress` tasks first
- Handles phase transitions automatically
- Updates task status and logs progress for the next session

### Planning Panel

Workflows with `planning_panel = true` use three independent agents to generate plans in parallel, then a senior synthesis agent reviews all three and produces the definitive plan:

1. **Opus** — via Claude Code Task tool
2. **Codex** — via Codex CLI (background)
3. **Gemini** — via Gemini CLI (background)
4. **Synthesis** — Opus reviews all three, investigates disagreements, dismisses weak ideas, and produces the final plan

The synthesis agent has full authority to investigate the codebase, dismiss incorrect concerns, add missing elements, and restructure the plan. It is not a mechanical merger — it is the decision-maker.

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create new plan (auto-suggests workflow type) |
| `/jons-plan:plan [feedback]` | Refine the active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to a different plan |
| `/jons-plan:status` | Show all plans and task progress |
| `/jons-plan:viewer` | Open the workflow viewer |

Use `--workflow <name>` with `/new` to specify workflow type explicitly.

## Workflow Types

| Workflow | Purpose |
|----------|---------|
| `implementation` | Build features, fix bugs with research and validation |
| `direct-implementation` | Simple plan-implement-verify for familiar code (no research) |
| `design` | Research, explore, produce design.md |
| `design-and-implementation` | Design first, optionally implement after approval |
| `deep-implementation` | Thorough research + external review before implementation |
| `dynamic` | Research-first, phases generated based on codebase exploration |
| `iteration` | Iterative execute-evaluate-generate loops for long-horizon goals |
| `review-tour` | Generate guided PR review tour from a GitHub PR URL |
| `code-review` | Review code changes + generate PR description |
| `pr-review` | Review existing PR description for quality |
| `deslop-pr` | Detect and remove AI-generated patterns from PR descriptions |
| `tech-docs` | Technical documentation with multi-source research |
| `tech-docs-review` | Review RFCs, design docs, proposals with structured criteria |

**Auto-selection:** When no `--workflow` is specified, the plugin analyzes your request and suggests the most appropriate workflow.

## Plan Directory Structure

```
.claude/jons-plan/
├── active-plan              # Name of the currently active plan
├── session-mode             # Current command mode
└── plans/
    └── [plan-name]/
        ├── workflow.toml        # Phase definitions
        ├── state.json           # Current phase state
        ├── request.md           # Refined/approved request
        ├── research-brief.md    # Pre-research from plan creation
        ├── dead-ends.json       # Failed approaches (for learning)
        ├── claude-progress.txt  # Plan-level progress log
        └── phases/
            └── NN-{phase-id}/
                ├── tasks.json   # Phase-specific tasks
                └── tasks/       # Task outputs
```

### Task Schema

```json
{
  "id": "implement-auth",
  "description": "Implement user authentication",
  "parents": ["research-auth-patterns"],
  "steps": ["Create auth middleware", "Add login endpoint"],
  "status": "todo",
  "subagent": "general-purpose",
  "model": "sonnet",
  "context_artifacts": ["research"],
  "executor": "task-tool",
  "locks": ["src/auth.rs"]
}
```

Key optional fields:
- `subagent`: Agent type (`general-purpose`, `gemini-reviewer`, `codex-reviewer`)
- `model`: Model override (`sonnet`, `haiku`, `opus`)
- `executor`: Execution method (`task-tool`, `codex-cli`, `gemini-cli`)
- `context_artifacts`: Artifact names to inject from phase history
- `prompt_file`: Plugin prompt to inject (e.g., `"slop-detection"`)
- `inject_phase_prompt`: Include phase prompt in task context
- `inject_project_context`: Include project CLAUDE.md in task prompt
- `locks`: Resource names for exclusive access (parallel tasks sharing locks are serialized)

## Hooks

The plugin uses five hooks to manage session lifecycle:

### SessionStart Hook

Runs at the beginning of each Claude Code session:
- Shows the active plan and working directory
- Displays recent git commits and uncommitted changes
- Shows workflow phase context (for workflow plans)
- Lists in-progress and available tasks
- Prompts for auto-resume if tasks were interrupted

### PreCompact Hook

Runs before context compaction:
- Injects jons-plan state into the compaction summary
- Includes session mode, active plan, and in-progress tasks
- Shows phase context for workflow plans
- Provides pointers to progress files for post-compaction resumption

### UserPromptSubmit Hook

Runs when user submits a message:
- Sets session mode based on command type
- Preserves planning modes on regular messages

### PostToolUse Hook

Runs after `Write` and `Edit` operations:
- Logs file modifications to `claude-progress.txt`
- Skips files in `.claude/` to avoid recursive logging

### Stop Hook

Runs when the session ends:
- Auto-continue behavior in proceed mode
- Shows session summary (files modified, task progress)
- Warns about uncommitted changes

## Workflow Viewer

A Qt/QML desktop application that visualizes plan execution in real-time. The viewer launches automatically after `/jons-plan:new` or `/jons-plan:plan` completes, or can be launched manually:

```bash
uv run /path/to/viewer.py /path/to/plan
# Example: uv run ~/.claude-plugins/jons-plan/viewer.py .claude/jons-plan/plans/my-plan
```

**Requirements:** graphviz (`brew install graphviz`)

### Features

**Workflow Diagram**
- Interactive state machine visualization with Graphviz-computed layout
- Color-coded phase status: current (blue), completed (green), terminal (gray), pending (white)
- Click nodes to select phases; hover for visual feedback
- Auto-follows current phase as Claude progresses

**Phase History**
- Chronological list of all phase entries with timestamps
- Navigate between different executions of the same phase
- Keyboard navigation (up/down arrows)

**Progress Timeline**
- Live stream of progress events from `claude-progress.txt`
- Color-coded by type: phase transitions, task updates, session events

**Details Panel**
- **Phase tab**: Entry reason, phase prompt (rendered markdown), artifacts with rich/plain toggle, logs
- **Tasks tab**: Dependency tree visualization, task details with steps/artifacts/logs
- Copy buttons with visual feedback; clickable links navigate within viewer

**Live Updates**
- File system watcher detects changes in real-time
- Task logs stream as Claude writes them
- New artifacts appear automatically
- Selection and scroll position preserved during updates

---

## References

- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) - Anthropic engineering blog post
- [Claude Agent SDK Quickstart](https://github.com/anthropics/claude-agent-sdk) - Reference implementation
