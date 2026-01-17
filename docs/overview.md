# jons-plan Overview (Critical)

This document summarizes the jons-plan Claude Code plugin and calls out gaps, partially implemented features, and wiring issues. It also explains what the agent sees at each step (including after compaction) and whether the agent is set up to succeed.

## Purpose

jons-plan is a “long-running agent harness” for Claude Code. It keeps multi-session work on track by:
- Persisting plan/task state on disk.
- Providing CLI commands for phase/task transitions.
- Using Claude Code hooks to restore context after compaction.
- Offering workflows with phase prompts and optional task execution.
- Optionally running parallel subagents for independent tasks.

## Core Components

1. **CLI: `plan.py`**
   - Manages active plans, tasks, phases, progress logs, dead-ends, research cache, and workflow transitions.
   - Generates prompts for tasks and phases.
   - Performs workflow expansion (`__expand__`).

2. **Hooks (lifecycle)**
   - `SessionStart`: prints active plan, progress, tasks, and auto-resume instructions.
   - `PreCompact`: injects plan state into compaction summary.
   - `UserPromptSubmit`: sets/clears session-mode.
   - `PostToolUse`: logs file modifications.
   - `Stop`: blocks stop if work remains (in proceed mode), otherwise prints summary.

3. **Workflow Templates (`workflows/*.toml`)**
   - Define phases, prompts, transitions, and flags (use_tasks, supports_cache_reference, etc).

4. **Prompts (`prompts/*.md`)**
   - Phase/task execution guidance. Some are conditional (prototype/cache/validation).

5. **Viewer (`viewer.py` + QML)**
   - Desktop UI showing workflow state, task graph, progress timeline.

6. **Schemas/Templates**
   - `schemas/tasks-schema.json` used by PreToolUse validation.
   - `templates/` for initial plan artifacts.

## Data Model (On-Disk)

```
.claude/jons-plan/
├── active-plan
├── session-mode
└── plans/
    └── <plan-name>/
        ├── workflow.toml
        ├── state.json
        ├── request.md
        ├── dead-ends.json
        ├── claude-progress.txt
        └── phases/
            └── NN-<phase-id>/
                ├── tasks.json
                └── tasks/
                    └── <task-id>/
                        ├── progress.txt
                        ├── output.md / findings.md / ...
                        └── blockers.md
```

## Execution Flow (High-Level)

1. **/jons-plan:new** (Planning agent)
   - Clarifies scope via AskUserQuestion.
   - Creates plan directory, copies workflow, initializes state.
   - Enters first phase.

2. **/jons-plan:plan** (Plan refinement)
   - Adjusts request.md and tasks.json (current phase).
   - Resolves blockers, adds or updates tasks.

3. **/jons-plan:proceed** (Coding agent)
   - Loads phase context (prompt + task guidance).
   - Creates/updates tasks if needed.
   - Executes tasks in dependency order.
   - Transitions phases via `suggested_next` when complete.

4. **Phase transitions**
   - Normal: `enter-phase <id>`
   - User-approved transitions: propose/approve/reject flow.
   - Expandable phases: `__expand__` generates new phases via JSON.

## What the Agent Sees

### SessionStart (Normal Session)
Printed to the agent at session start:
- Active plan name, plan path, working directory.
- Blocked tasks (with attempted reason extraction).
- Git status (recent commits, dirty count).
- Recent progress (last 5 log entries).
- Plan status summary (current phase tasks only).
- In-progress tasks with last 5 progress lines.
- Workflow phase summary.
- Input artifacts (if any).
- Recent dead-ends (last 3).
- Auto-resume instructions based on session-mode.

### PreCompact (Before Compaction)
Injected into the compaction summary:
- Session mode and active plan.
- Current phase summary.
- In-progress task IDs, descriptions, and last 3 progress lines.
- Pointers to task progress files for full context.

### After Compaction
The agent’s “memory” is:
1. The compaction summary (contains PreCompact output).
2. A fresh SessionStart output (reads disk state).

### Mode-Specific Behavior After Compaction
- **new**: SessionStart warns to continue planning only; no auto-resume.
- **plan**: Same as new, with refinement instructions.
- **proceed**: Auto-resume is enforced if tasks are available or in-progress.
- **awaiting-feedback**: SessionStart allows stop; expects user input.

## Is the Agent Optimally Set Up?

Strengths:
- Strong persistence: task progress + phase history + plan progress.
- Hooks cover compaction, session start, and stop behavior.
- Clear task status discipline with logging requirements.
- Phase-based prompts assemble extra guidance (validation, prototypes, cache).
- Optional viewer for richer visibility.

Weaknesses:
- The SessionStart output is mostly summary; the agent must manually run
  `plan.py phase-context` to see the actual phase prompt and request.
- PreCompact only includes in-progress tasks; if the agent forgets to mark
  a task in-progress, compaction loses critical context.
- Several features are defined in prompts/docs but not enforced or wired.

## Critical Findings (Half-Implemented or Not Wired)

1. **cache-reference tasks are invalid by schema**
   - `prompts/cache-reference.md` and `cache-suggest` emit tasks with
     `"cache_id"`, but `schemas/tasks-schema.json` disallows `cache_id`
     (additionalProperties=false). The PreToolUse hook will reject the write.
   - Result: cache-reference tasks cannot be created as specified.

2. **User guidance is stored but never surfaced**
   - `/jons-plan:proceed <number> [guidance]` stores `user_guidance` in
     `state.json`, but `phase-context` never displays it and `proceed.md`
     doesn’t instruct the agent to read it. Guidance is effectively invisible
     unless the agent manually runs `get-user-guidance`.

3. **SessionStart uses legacy task paths**
   - For blocked reasons and progress file hints, it reads:
     `ACTIVE_PLAN_DIR/tasks/<task-id>/...`, but workflow tasks live in
     `phases/NN-<phase>/tasks/<task-id>/...`.
   - Result: blocker reasons and progress file paths are often missing or wrong.

4. **Task schema mismatch across docs vs validation**
   - `TASK_SCHEMA` (injected into phase context) omits fields that the actual
     schema allows (e.g., `type`, `context_artifacts`, `inject_project_context`,
     `resources`).
   - `schemas/tasks-schema.json` requires only `id`, `description`, `status`,
     but instructions say `parents` and `steps` are required.
   - This creates confusion for planners and subagents.

5. **Status output is phase-scoped only**
   - `plan.py status` reports task stats from the current phase only, yet docs
     imply plan-level progress. Cross-phase task completion is not surfaced.

6. **Minor CLI messaging mismatch**
   - `cmd_set_status` prints `Updated: <plan_dir>/tasks.json` even though
     workflow tasks live in `phases/NN-<phase>/tasks.json`.

7. **Feature discipline is manual**
   - Prototype tasks, cache tasks, dead-ends, and confidence scores rely on the
     agent to follow guidance. There is minimal enforcement or automation.
   - This is workable but brittle under compaction or when multiple agents run.

8. **Project root detection is inconsistent**
   - Hooks find `.claude/` by walking up from CWD, while `plan.py` uses git root.
   - In nonstandard repo layouts (monorepos, subprojects), this can desync
     session-mode and plan paths.

## Assessment: Per-Step Context Sufficiency

### /new (planning)
- Context from SessionStart is minimal for planning tasks (no auto request.md).
- After compaction, the agent must manually open request and phase prompt.
- Adequate but not optimal; missing direct prompt injection.

### /plan (refinement)
- Same as /new. Blocker visibility exists but blocker reason retrieval is broken
  in workflow plans (wrong path).
- Requires manual cleanup to be reliable.

### /proceed (implementation)
- Good: SessionStart shows tasks, progress, and auto-resume.
- Weak: phase prompt and request are not auto-injected; agent must run
  `phase-context`. If the agent skips that (e.g., due to auto-resume urgency),
  it may proceed without the full spec.

## Recommendations (High-Impact Fixes)

1. Add `cache_id` to `schemas/tasks-schema.json`.
2. Surface `user_guidance` in `phase-context` output and SessionStart.
3. Fix SessionStart paths for blockers/progress (use `plan.py task-dir`).
4. Align `TASK_SCHEMA` and docs with the actual schema fields.
5. Decide whether `status` should aggregate all phases or be explicit that it is
   current-phase-only (and update docs accordingly).
6. Consider injecting request.md and phase prompt directly into SessionStart
   (or a short excerpt + “read full context” pointer).

---

If you want, I can turn these recommendations into a concrete patch plan or fix them directly.
