# jons-plan Plugin

A Claude Code plugin inspired by Anthropic's [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) blog post for managing complex, multi-session coding tasks.

## Prerequisites

- **Claude Code** - The Anthropic CLI tool
- **uv** - Python package runner (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **graphviz** (optional) - For workflow viewer (`brew install graphviz`)
- **macOS** - Linux/Windows (WSL) support is untested

## Quick Start

```bash
# 1. Clone anywhere you want
git clone https://github.com/youruser/jons-plan ~/path/to/jons-plan

# 2. Run the installer
cd ~/path/to/jons-plan
uv run scripts/install.py

# 3. Restart Claude Code and test
/jons-plan:status
```

The install script will:
- Register the plugin with Claude Code
- Configure all necessary hooks
- Verify the installation

## Verify Installation

```bash
# Run the verification script
uv run scripts/verify.py

# Or test in Claude Code
/jons-plan:status
```

You should see: "No plans exist yet..." or a list of your plans.

## Uninstallation

```bash
uv run scripts/uninstall.py
```

This removes the plugin registration and hooks but leaves the plugin directory intact.

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

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## How It Works

The plugin uses a two-agent architecture:

### Planning Agent (`/jons-plan:new`)

Creates the infrastructure for a new plan:
- Analyzes your request and suggests an appropriate workflow
- Sets up the plan structure and initial phase
- Creates `request.md` with the refined/approved request

### Coding Agent (`/jons-plan:proceed`)

Works incrementally on tasks across sessions:
- Reads progress log to understand current state
- Resumes any `in-progress` tasks first
- Handles phase transitions automatically
- Updates task status and logs progress for the next session

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/jons-plan:new [topic]` | Create new plan (auto-suggests workflow type) |
| `/jons-plan:plan [feedback]` | Refine the active plan |
| `/jons-plan:proceed` | Start/continue implementing tasks |
| `/jons-plan:switch [name]` | Switch to a different plan |
| `/jons-plan:status` | Show all plans and task progress |

Use `--workflow <name>` with `/new` to specify workflow type explicitly.

## Workflow Types

| Workflow | Purpose |
|----------|---------|
| `implementation` | Build features, fix bugs with research and validation |
| `design` | Research, explore, produce design.md |
| `design-and-implementation` | Design first, optionally implement after approval |
| `deep-implementation` | Thorough research + external review before implementation |
| `code-review` | Review code changes + generate PR description |
| `pr-review` | Review existing PR description for quality |
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
  "model": "sonnet"
}
```

Tasks can optionally specify:
- `subagent`: Agent type (`general-purpose`, `Explore`, `Plan`, `gemini-reviewer`, `codex-reviewer`)
- `subagent_prompt`: Additional context (e.g., "very thorough analysis")
- `model`: Model to use (`sonnet`, `haiku`, `opus`)

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

## Known Issue: Plugin Hook Output Not Passed to Agent

**Bug:** https://github.com/anthropics/claude-code/issues/12151

Plugin-based hooks execute successfully but their stdout is not passed to the agent's context. This affects all hooks defined in `hooks/hooks.json`.

The install script works around this by adding hooks directly to `~/.claude/settings.json`.

### When Issue #12151 is Fixed

The `hooks/hooks.json` file already uses `${CLAUDE_PLUGIN_ROOT}` for portable paths. Once the bug is fixed:
1. Run `./scripts/uninstall.sh` to remove the workaround hooks
2. The plugin's native hooks will work automatically

## References

- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) - Anthropic engineering blog post
- [Claude Agent SDK Quickstart](https://github.com/anthropics/claude-agent-sdk) - Reference implementation
