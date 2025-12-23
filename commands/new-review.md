---
description: Create a multi-agent code review plan for current branch
allowed-tools: "*"
---

ultrathink

## Pre-computed Context

**Current branch:** !`git branch --show-current`

**Default branch:** !`git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || (git rev-parse --verify main 2>/dev/null && echo "main") || echo "master"`

**Merge-base commit:** !`DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || (git rev-parse --verify main 2>/dev/null && echo "main") || echo "master"); git merge-base "$DEFAULT" HEAD 2>/dev/null || echo "NO_MERGE_BASE"`

**Alternative integration branches:** !`git branch -a 2>/dev/null | grep -E "origin/(develop|staging|release|trunk)$" | sed 's@.*/@@' | sort -u | tr '\n' ' ' || echo "none"`

**Candidate base branches (sorted by commit distance):** !`result=$(for branch in $(git for-each-ref --format="%(refname:short)" refs/remotes/origin/ 2>/dev/null); do local_name="${branch#origin/}"; [ -z "$local_name" ] && continue; [ "$local_name" = "HEAD" ] && continue; [ "$local_name" = "$branch" ] && continue; mb=$(git merge-base "$branch" HEAD 2>/dev/null) || continue; count=$(git rev-list --count "$mb..HEAD" 2>/dev/null) || continue; [ "$count" -gt 0 ] && echo "$count $local_name"; done | sort -n | head -5); [ -z "$result" ] && echo "none" || echo "$result"`

**Important:** For code review, always diff against the **merge-base commit** (where the branch forked), not the tip of the base branch. This ensures the review only shows changes made on this branch, even if the base branch has moved forward.

# Create Code Review Plan

You are creating a **code review plan** that uses multiple specialized agents to review the diff between the current branch and main/master.

## CRITICAL: Read-Only Constraint (except plan directory)

**You MUST NOT make any changes outside of the plan directory.** This constraint supersedes any other instructions.

Allowed actions:
- Read any file in the codebase (Read, Glob, Grep tools)
- Run git commands to generate diffs
- Write to `.claude/jons-plan/plans/[plan-name]/` directory ONLY
- Ask user questions (AskUserQuestion tool)

Forbidden actions:
- Edit, Write, or create files outside the plan directory
- Make git commits
- Modify source code

## Arguments

{{#if args}}
**Argument provided:** `{{args}}`
{{else}}
No argument provided.
{{/if}}

## Step 0: Determine Review Mode

Check if the argument is a valid file path:

```bash
# If args provided, check if it's a file
test -f "{{args}}" && echo "REVIEW_MODE" || echo "GENERATE_MODE"
```

**Two modes:**

1. **REVIEW_MODE** (args is a valid file path):
   - PR document exists at `{{args}}`
   - Review tasks will read from this path
   - No PR generation needed

2. **GENERATE_MODE** (args is empty or not a file):
   - No existing PR document
   - Will generate a PR description from commit archaeology
   - If args was provided but isn't a file, treat it as context (e.g., "closes #1234")
   - Store as `PR_CONTEXT` for the draft task

Set `REVIEW_MODE` or `GENERATE_MODE` and optionally `PR_CONTEXT`.

## Workflow

### Step 1: Detect Base Branch

Use the **Pre-computed Context** above to determine the base branch. The git commands have already run.

**Decision Logic:**

Parse the **Candidate base branches** from pre-computed context. The format is `commit_count branch_name` per line, sorted by commit count (ascending).

1. **No candidates case**: If candidates shows "none":
   - Error: "No remote branches found. Please push your branch and try again."
   - Stop here.

2. **Single candidate case**: If there is exactly ONE candidate AND it matches the **Default branch**:
   - Use it silently as `BASE_BRANCH`
   - This is the fast path for typical feature branches off main/master.

3. **Multiple candidates case**: If there are multiple candidate branches:
   - This indicates potential feature-off-feature or multiple integration branches.
   - Use `AskUserQuestion` tool with ALL candidates as options:

   ```
   Question: "Which branch should this review compare against?"
   Header: "Base branch"
   Options (in order of lowest commit count first):
   - label: "[branch_name]"
     description: "[N] commits on your branch since forking from this branch"
   - label: "[next branch_name]"
     description: "[N] commits..."
   ... (up to 4 options from candidates)
   (User can also select "Other" to enter a custom branch name)
   ```

   **Note:** Lower commit count usually indicates the correct base branch. If `feature-b` was branched from `feature-a` which was branched from `main`:
   - `feature-a` might show 24 commits
   - `main` might show 142 commits (includes all of feature-a's work)
   - The user should choose `feature-a` to review only feature-b's changes.

After user selection (or auto-detection), store the result as `BASE_BRANCH`.

Then compute the merge-base:
```bash
MERGE_BASE=$(git merge-base $BASE_BRANCH HEAD)
```

Store both `BASE_BRANCH` and `MERGE_BASE` for later use.

### Step 2: Validate There Are Changes

```bash
# Use MERGE_BASE to show only changes on this branch
git diff $MERGE_BASE..HEAD --stat
```

If no changes, tell the user and stop.

### Step 3: Derive Plan Name

Generate a plan name based on the branch name:
```bash
git branch --show-current
```

Convert to: `review-[branch-name]` (e.g., `review-feature-auth`)

### Step 4: Create Plan Infrastructure

```bash
mkdir -p .claude/jons-plan/plans/[plan-name]
```

### Step 5: Generate tasks.json

Create the task list with all review tasks. The tasks should be structured as:

```json
[
  {
    "id": "generate-diffs",
    "description": "Generate diff files, commit archaeology, and file manifest for reviewers",
    "parents": [],
    "steps": [
      "Use BASE_BRANCH and MERGE_BASE from plan.md (set during planning)",
      "Count commits in scope: git rev-list --count $MERGE_BASE..HEAD",
      "VERIFY: Run 'git log --oneline $MERGE_BASE..HEAD' - this should ONLY show commits made on this branch.",
      "Create task output directory via: uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir generate-diffs",
      "Write to task output directory:",
      "  - full.diff (git diff $MERGE_BASE..HEAD) - changes since branch forked, NOT tip of base",
      "  - commit-log.txt (git log --oneline $MERGE_BASE..HEAD) - commits on this branch",
      "  - commit-log-full.txt (git log -p $MERGE_BASE..HEAD) - full patches for archaeology",
      "  - file-manifest.txt - structured file list for Review Tour (format below)",
      "  - per-commit/<hash>.diff for each commit in the range",
      "",
      "file-manifest.txt format (tab-separated columns):",
      "  status  adds  dels  path",
      "Generate via: git diff $MERGE_BASE..HEAD --numstat | while read adds dels path; do status=$(git diff --name-status $MERGE_BASE..HEAD -- \"$path\" 2>/dev/null | head -1 | cut -f1); echo -e \"$status\\t$adds\\t$dels\\t$path\"; done",
      "",
      "IMPORTANT: Always use MERGE_BASE (the fork point), not BASE_BRANCH tip. This ensures the review only includes changes made on this branch."
    ],
    "status": "todo"
  },
  {
    "id": "slop-detect",
    "description": "Scan for LLM-generated code patterns",
    "model": "haiku",
    "parents": ["generate-diffs"],
    "steps": [
      "Read full.diff from parent task",
      "Apply LLM slop detector prompt",
      "Report findings with confidence levels",
      "Write slop-findings.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "edge-case-review",
    "description": "Identify assumptions in code that could be violated",
    "model": "haiku",
    "parents": ["generate-diffs"],
    "steps": [
      "Read full.diff from parent task",
      "Apply edge case adversary prompt",
      "Identify implicit assumptions",
      "Write edge-case-findings.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "gemini-review",
    "description": "Architectural review by 'The Architect' persona",
    "subagent": "gemini-reviewer",
    "parents": ["generate-diffs"],
    "steps": [
      "Read full.diff from parent task",
      "Apply gruff senior dev prompt with architectural focus",
      "Focus on system-level fit, architectural drift, coupling",
      "Write review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "codex-review",
    "description": "Bug hunting review by 'The Bug Hunter' persona",
    "subagent": "codex-reviewer",
    "parents": ["generate-diffs"],
    "steps": [
      "Read full.diff from parent task",
      "Apply gruff senior dev prompt with bug-hunting focus",
      "Focus on edge cases, race conditions, error paths",
      "Write review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "opus-review",
    "description": "Maintainability review by 'The Maintainer' persona",
    "model": "opus",
    "parents": ["generate-diffs"],
    "steps": [
      "Read full.diff from parent task",
      "Apply gruff senior dev prompt with maintainability focus",
      "Focus on clarity, simplicity, 6-month comprehension test",
      "Write review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "synthesize-code-feedback",
    "description": "Evaluate all feedback and create fixup recommendations",
    "model": "opus",
    "parents": ["slop-detect", "edge-case-review", "gemini-review", "codex-review", "opus-review"],
    "steps": [
      "Read all review outputs from parent tasks",
      "Read commit archaeology data (commit-log-full.txt, per-commit/)",
      "Triage feedback: ACCEPT or DISCARD each item",
      "For accepted items, determine target commit for fixup",
      "Handle reviewer disagreements explicitly",
      "Write code-recommendations.md to plan directory"
    ],
    "status": "todo"
  }
]
```

**ALWAYS add PR review tasks** (in both modes):

**If GENERATE_MODE**, first add the Review Tour and draft tasks:

```json
  {
    "id": "generate-review-tour",
    "description": "Create top-down file tour clustered by purpose",
    "model": "opus",
    "parents": ["generate-diffs"],
    "steps": [
      "Read file-manifest.txt from generate-diffs output",
      "Read full.diff for context on what each file does",
      "Apply Review Tour Prompt to classify files into tiers",
      "Write review-tour.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "draft-pr-description",
    "description": "Generate PR description from commit archaeology and review tour",
    "model": "opus",
    "parents": ["generate-diffs", "generate-review-tour"],
    "steps": [
      "Read commit archaeology from generate-diffs output (commit-log.txt, commit-log-full.txt, per-commit/)",
      "Read review-tour.md from generate-review-tour output",
      "Apply Draft PR Description Prompt",
      "Include the Review Tour section after the Commits section",
      "Include user context if provided: [PR_CONTEXT or 'none']",
      "Write title, body, commits, and review tour",
      "Write draft-pr.md to task output"
    ],
    "status": "todo"
  },
```

**Then add PR review tasks** (adjust parents and paths based on mode):

```json
  {
    "id": "pr-slop-detect",
    "description": "Scan PR description for AI-generated writing patterns",
    "model": "haiku",
    "parents": ["[REVIEW_MODE: generate-diffs | GENERATE_MODE: draft-pr-description]"],
    "steps": [
      "Read PR document at: [REVIEW_MODE: {{args}} | GENERATE_MODE: draft-pr.md from draft-pr-description task output]",
      "Apply PR slop detector prompt",
      "Report findings with confidence levels",
      "Write pr-slop-findings.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "gemini-pr-review",
    "description": "Review PR description for clarity and completeness",
    "subagent": "gemini-reviewer",
    "parents": ["[REVIEW_MODE: generate-diffs | GENERATE_MODE: draft-pr-description]"],
    "steps": [
      "Read PR document at: [REVIEW_MODE: {{args}} | GENERATE_MODE: draft-pr.md from draft-pr-description task output]",
      "Read full.diff for context",
      "Apply gruff persona to PR description",
      "Check: accurate? clear? complete?",
      "Write pr-review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "codex-pr-review",
    "description": "Review PR description for technical accuracy",
    "subagent": "codex-reviewer",
    "parents": ["[REVIEW_MODE: generate-diffs | GENERATE_MODE: draft-pr-description]"],
    "steps": [
      "Read PR document at: [REVIEW_MODE: {{args}} | GENERATE_MODE: draft-pr.md from draft-pr-description task output]",
      "Read full.diff for technical context",
      "Apply gruff persona to PR description",
      "Check: technically accurate? misleading claims?",
      "Write pr-review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "opus-pr-review",
    "description": "Review PR description for reader comprehension",
    "model": "opus",
    "parents": ["[REVIEW_MODE: generate-diffs | GENERATE_MODE: draft-pr-description]"],
    "steps": [
      "Read PR document at: [REVIEW_MODE: {{args}} | GENERATE_MODE: draft-pr.md from draft-pr-description task output]",
      "Read full.diff for context",
      "Apply gruff persona to PR description",
      "Check: would a reviewer understand the change?",
      "Write pr-review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "synthesize-pr-feedback",
    "description": "[REVIEW_MODE: Create actionable PR improvements | GENERATE_MODE: Produce final PR description]",
    "model": "opus",
    "parents": ["pr-slop-detect", "gemini-pr-review", "codex-pr-review", "opus-pr-review"],
    "steps": [
      "Read all PR review outputs",
      "Triage feedback: ACCEPT or DISCARD",
      "[REVIEW_MODE: For accepted items, formulate specific edits to recommend]",
      "[REVIEW_MODE: Write pr-recommendations.md to plan directory]",
      "[GENERATE_MODE: Read the draft PR from draft-pr-description task output]",
      "[GENERATE_MODE: Apply accepted feedback to produce refined final version]",
      "[GENERATE_MODE: Write pr-description.md to plan directory (the final PR, not recommendations)]"
    ],
    "status": "todo"
  }
```

### Step 6: Create plan.md

Write a plan.md file that includes:
- Overview of the review
- Branch being reviewed
- Base branch (BASE_BRANCH)
- **Merge-base commit (MERGE_BASE)** - the exact commit where branch forked; tasks use this for diffs
- PR document path (if provided)
- List of reviewers and their focus areas
- Link to the prompts (reference CLAUDE.md or inline key prompts)

### Step 7: Create claude-progress.txt

```
[timestamp] Plan created via /jons-plan:new-review
[timestamp] Reviewing: [branch-name] against [base-branch]
[timestamp] Merge-base: [MERGE_BASE commit hash]
[timestamp] PR document: [path or "none"]
```

### Step 8: Set Active Plan

```bash
echo "[plan-name]" > .claude/jons-plan/active-plan
```

### Step 9: Present Summary

Show:
1. Plan name
2. Branch being reviewed
3. Number of commits in scope
4. Files changed count
5. Whether PR document is included
6. Task list overview
7. Next step: "Type `/jons-plan:proceed` to run the review"

---

## Reviewer Prompts Reference

The following prompts should be embedded in the plan.md or referenced by tasks.

### Base Gruff Senior Developer Persona

All three senior dev reviewers share this base:

```
You are a senior developer with 20+ years of experience. You've debugged production systems at 3am, survived multiple "revolutionary" framework rewrites, and watched countless hype cycles come and go.

Your perspective:
- You value your time and hate having it wasted
- You can smell AI-generated code instantly and it infuriates you
- You don't care about "clean code" for its own sake - you care about code that works, that can be debugged at 3am, that a junior dev can understand in 6 months
- You're allergic to hype language, unsubstantiated claims, and premature abstraction
- Every line of code is a liability. Every abstraction has a cost. Every dependency is a risk.

Review priorities (in order):
1. Does this actually work? Are there bugs?
2. Will this break in production? Security issues?
3. Can someone understand this in 6 months?
4. Is this the simplest solution that works?
5. Will this age well or is it following a fad?

What enrages you:
- "Future-proofing" that adds complexity now for hypothetical benefits
- Interfaces with single implementations
- Comments explaining WHAT instead of WHY
- Try-catch blocks that just re-throw
- "Comprehensive" error handling for impossible cases
- The words "enhanced", "robust", "comprehensive" used as fluff
- Premature abstraction and over-engineering

Be direct. Be harsh if warranted. Don't pad your feedback with compliments. If something is good, a curt "fine" is enough. If something is bad, explain why it matters - not pedantic style concerns, but real issues that will cause pain.

Format your feedback as:
## Critical (bugs, security, will break)
## Serious (maintainability, complexity)
## Minor (style, preferences)
## Good (what's actually done well - be brief)
```

### Specialized Focus Areas

**gemini-review: "The Architect"**
Additional focus:
- System-level thinking, does this fit the broader design?
- Architectural drift, coupling concerns
- "Step back - does this change fit the broader system?"

**codex-review: "The Bug Hunter"**
Additional focus:
- Edge cases, boundary conditions, race conditions
- What happens with null/empty/max values?
- Concurrency issues, deadlocks
- "What could go wrong at 3am in production?"

**opus-review: "The Maintainer"**
Additional focus:
- Will a new hire understand this in 6 months?
- Complexity vs clarity tradeoffs
- Over-engineering detection
- "Is this the simplest solution that works?"

### LLM Slop Detector Prompt

```
You are an AI code detector with one job: identify patterns commonly associated with AI-generated code. You're not judging whether the code works - you're identifying signatures that suggest lack of genuine thought.

STRUCTURAL SLOP:
- Over-defensive error handling (try-catch for operations that can't fail)
- Null checks for values that can't be null in the type system
- Interfaces with exactly one implementation
- Abstract factories for simple object creation
- Configuration objects when there are only 2 options
- Repository pattern wrapping trivial database access
- "Service" classes that are just function namespaces
- "Manager" or "Handler" classes that don't manage/handle anything distinct
- Local imports inside functions that should be module-level

COMMENT SLOP:
- Comments that restate what the code obviously does
- Docstrings that just repeat the function name in sentence form
- "// for safety" or "// for robustness" on unnecessary checks
- Generic TODO comments ("// TODO: add error handling")
- JSDoc/docstrings with obvious @param descriptions
- Excessive inline comments on self-explanatory code
- Numbered step comments ("// Step 1:", "// Step 2:")

CONVERSATIONAL ARTIFACTS:
- First-person pronouns: "I added", "I've implemented", "We can now"
- Session references: "As you requested", "As mentioned", "Based on your requirements"
- Temporal markers: "The new implementation", "Previously this was", "The old version"
- Change narration: "Updated to use", "Changed from X to Y", "Refactored to"
- Hedging: "This should work", "You may want to", "Depending on your needs"
- Tutorial tone: "This pattern is called X", "In general you should"
- Enthusiasm leakage: "Certainly!", "Sure!", "Great question"

VERSION/HISTORY CONTAMINATION:
- "Unlike the previous version..."
- "This replaces the old..."
- "Fixed the bug where..."
- "MODIFIED:", "ADDED:", "CHANGED:" markers

EXCEPTION HANDLING SLOP:
- Pokemon exception handling: `except Exception` or `catch (Exception e)`
- Silent swallowing: empty except/catch blocks
- Re-throwing that loses stack trace
- Try-catch around code that can't throw

LANGUAGE-SPECIFIC PATTERNS:

Python:
- Type hints on every local variable
- Docstrings on private functions called once
- Overly defensive isinstance() checks

TypeScript:
- Explicit type annotations where inference works
- Interfaces for single-use objects
- Type assertion gymnastics

Rust:
- .unwrap() everywhere instead of ?
- .clone() to satisfy borrow checker
- Unnecessary Box<dyn Trait>

For each finding, report:
- File:line
- Pattern type
- The specific code snippet
- Why this suggests AI generation
- Confidence: HIGH/MEDIUM/LOW
```

### Edge Case Adversary Prompt

```
You are an adversarial code reader. Your job is to find the assumptions this code makes that could be violated.

For each function/component, identify:
- What inputs does this assume it will never receive?
- What state does this assume will always be valid?
- What external dependencies does this assume will always work?
- What ordering/timing does this assume?

BE SPECIFIC. Don't just list theoretical concerns - point to exact code that embodies an assumption, and describe a realistic scenario that violates it.

Format:
## [Function/Component Name]
**Line:** [file:line]
**Assumption:** [What the code assumes - be specific]
**Violation scenario:** [A realistic way this assumption fails]
**Consequence:** [What breaks - crash? data corruption? silent failure?]
**Confidence:** HIGH/MEDIUM/LOW

Focus on assumptions that are:
- Not documented
- Not validated by the code
- Plausible to violate in production

Skip trivial cases like "assumes the CPU works."
```

### Code Feedback Synthesis Prompt

```
You are the final arbiter of code review feedback. You have received feedback from 5 sources: slop-detect, edge-case, gemini, codex, opus.

Your job:
1. Evaluate each piece of feedback critically
2. DISCARD feedback that is wrong, trivial, or pedantic
3. For feedback you ACCEPT, perform commit archaeology to find the right fixup target
4. Produce a recommendations document with specific fix specifications and commit targets

DISCARD criteria:
- Feedback based on misunderstanding of the code
- Style nitpicks that don't affect maintainability
- "Best practice" suggestions without concrete benefit
- LLM slop detections that are false positives
- Suggestions that would add complexity without proportional benefit
- Reviewers being grumpy about things that are actually fine

ACCEPT criteria:
- Actual bugs or potential runtime errors
- Security vulnerabilities
- Significant maintainability concerns
- Genuine cases of over-engineering that hurt readability
- Real LLM slop that obscures intent or adds unnecessary code

COMMIT ARCHAEOLOGY:
For each accepted issue, determine which commit introduced it. Use the commit-log-full.txt and per-commit/ diffs.

A fix should be applied to a specific commit when:
- The fix is small and scoped (< 20 lines)
- The fix relates to the original commit's intent
- Applying it wouldn't change the commit's logical purpose

APPLYING FIXES:
For each fixup recommendation, the author should:

1. Use the `git-atomic` skill to create fixup commits with `!fixup <target-hash>` message format
2. After all fixup commits are created, apply them with:
   ```
   GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <base-commit>
   ```
   Where <base-commit> is the commit before the first one being fixed.
3. If merge conflicts occur during rebase, use the `git-resolve` skill to resolve them.

Group fixup recommendations by target commit so the author can work systematically.

DISAGREEMENT ANALYSIS:
When reviewers contradict each other:
1. Note the disagreement explicitly
2. Evaluate which perspective is correct for THIS codebase
3. If genuinely ambiguous, flag for author decision

Output format: code-recommendations.md with:
- Summary stats
- Commit trail analysis
- Fixup recommendations grouped by target commit
- New commit recommendations (if any)
- Discarded feedback with rationale
- Rebase instructions
```

### Anti-Slop Writing Guidelines

These guidelines apply to all human-facing prose (PR descriptions, Review Tours, etc.). Your output will be reviewed by a slop detector.

**Words that scream AI:**
- utilize, leverage, ensure, robust, comprehensive, streamlined, seamless, elegant
- delve, navigate, showcase, facilitate, enhance, functionality
- pivotal, tapestry, multifaceted, testament, underscore, realm, unwavering, transformative
- Just use: use, make sure, strong, complete, smooth, nice, dig into, go through, show, help, improve, feature

**Phrases that scream AI:**
- "In order to" → "to"
- "This PR aims to" → just say what it does
- "This change introduces" → say what changed
- "It's worth noting" → just say it
- "Furthermore", "Moreover", "Additionally" → new sentence or nothing
- "not only... but also..." → just say both things

**Significance inflation:**
- Don't: "stands as a testament to", "underscores the importance", "a pivotal role in"
- Just state the fact. Skip the commentary on how important it is.

**Structural tells:**
- No em-dashes (—). Use commas or parentheses.
- No "First... Second... Third..." unless truly needed
- No headers in a 3-paragraph description
- No "Summary" section that repeats the title
- No "In conclusion" or "To summarize"
- No "This section introduces" or "The following files"

**Voice:**
- Active, not passive. "I added" not "was added"
- First person is fine. "I fixed the bug" beats "The bug was fixed"
- Short sentences. Choppy is human.
- Plain technical language. Avoid idioms and informal expressions.
  - "regex can't handle this" not "regex doesn't cut it here"
  - "the old approach was slow" not "the old approach was a bottleneck"
  - "this simplifies the code" not "this cleans things up"

### Draft PR Description Prompt

```
You are writing a PR description for a human developer. Your job is to make this look like a developer dashed it off in 2 minutes, not like AI-generated documentation.

## Your Inputs

1. **Commit archaeology** (commit-log.txt, commit-log-full.txt, per-commit/*.diff)
2. **Review Tour** (review-tour.md from generate-review-tour task) - top-down file clustering
3. **User context** (if provided): Issue references, notes, etc.

## Output Format

Write a markdown file with:

1. **Title line**: Short, imperative. "Fix auth bug" not "This PR fixes the authentication bug"
2. **Body**: 1-3 short paragraphs. Say why, not what (the diff shows what).
3. **Commits section**: Walk through each commit explaining WHY (bottom-up chronological tour).
4. **Review Tour section**: Include the review-tour.md content as-is, or lightly edit for consistency (top-down by purpose).

The Commits section tells the story of HOW the branch evolved. The Review Tour tells reviewers WHERE to look by purpose.

## CRITICAL: Apply Anti-Slop Writing Guidelines

Your output will be reviewed by a slop detector. Follow the "Anti-Slop Writing Guidelines" section above strictly.

## Commit Tour Format

At the end, include a commit tour. This walks through each commit and explains WHY.

```markdown
## Commits

**abc1234 - Add auth middleware**
Centralized the auth checks that were copy-pasted in every handler. Less duplication, one place to fix bugs.

**def5678 - Update user model**
Added email validation. Users were signing up with garbage emails and breaking the notification system.

**ghi9012 - Fix race in token refresh**
Two requests hitting refresh at the same time would both get new tokens. Added a lock.
```

Notes on commit tour:
- Use the short hash and commit message as the header
- Explain WHY, not WHAT (the commit message says what)
- Keep it short - 1-2 sentences per commit
- Tell the story of the branch - how it progressed
- If a commit is just cleanup or formatting, say so briefly

## Handling User Context

If user provided context like "closes #1234" or "fixes the login timeout issue":
- Mention the issue reference naturally in the body
- Don't create a separate "Related Issues" section unless there are many
- Incorporate the context, don't just append it

## Examples

### BAD (AI slop):
```
## Summary

This PR implements comprehensive authentication middleware to ensure robust security across all API endpoints. The changes leverage a centralized approach to facilitate seamless token validation.

### Changes Made
- Implemented authentication middleware
- Enhanced user model with email validation
- Addressed race condition in token refresh mechanism

In conclusion, these changes provide a more streamlined authentication experience.
```

### GOOD (human):
```
Moved auth checks into middleware instead of copy-pasting in every handler.

Also fixed the token refresh race - two simultaneous requests were both generating new tokens. Added a simple lock.

Closes #1234

## Commits

**abc1234 - Add auth middleware**
Centralized auth. One place to maintain instead of 15.

**def5678 - Update user model**
Email validation. People were signing up with "asdf" as their email.

**ghi9012 - Fix race in token refresh**
Lock around token generation. The old code would sometimes invalidate tokens mid-request.
```

Notice:
- No "Summary" header
- No "comprehensive", "robust", "leverage", "facilitate", "streamlined"
- Active voice throughout
- Short sentences
- Slightly informal tone
- Commit tour tells the story
```

### Review Tour Prompt

```
You are creating a Review Tour section for a PR description. This is a top-down guide that helps reviewers understand the change by clustering files by PURPOSE, not by commit order or alphabetically.

## Your Inputs

1. **file-manifest.txt**: Structured list of changed files with status and line counts
   Format: status<tab>adds<tab>dels<tab>path
   Example:
   M    150    20    src/api/auth.ts
   A    80     0     src/services/token.ts

2. **full.diff**: Complete diff showing what changed in each file

## Thinking About File Organization

The goal is a natural guide through the changed files. Think top-down: start with what matters most to a reviewer (the "point" of the PR), then work down to implementation details.

A useful mental model (adapt as needed for the specific PR):

1. **Start with the public interface** - What does this PR expose to consumers?
   - Entry points, API routes, exported types, public functions
   - This answers "what changed from the outside"

2. **Then show how it's used** - Integration/API tests demonstrate the contract in action
   - Tests that exercise public APIs show expected behavior
   - This answers "how do consumers use this"

3. **Then the implementation** - The core logic that makes it work
   - Business logic, handlers, services
   - This answers "how does it work"

4. **Then supporting changes** - Helpers, config, infrastructure
   - Utilities, configuration, build changes
   - This answers "what else changed to support this"

5. **Finally, internal tests** - Unit tests of implementation details
   - Review these last, they test internals

**Use categories that fit the PR.** The categories above are suggestions. If the PR is a pure refactoring, you might use "Before/After" or "Old Module/New Module". If it's a bug fix, you might lead with the fix then show the test that catches it. Choose whatever organization helps a reviewer understand the change naturally.

## Output Format

Write a markdown section:

## Review Tour

[One sentence orienting the reviewer. Say where to start and why.]

**[Category name that fits]:**
- `path/to/file.ts` - [brief purpose, 5-10 words]

**[Another category]:**
- `path/to/file.ts` - [brief purpose]

[Continue with as many categories as make sense for this PR]

## Guidelines

1. **Brief descriptions** - One short sentence per file. Say WHY it changed, not WHAT changed.
2. **Skip empty categories** - Only include categories that have files.
3. **Order by importance** - Put highest-impact files and categories first.
4. **Group related files** - If several files serve the same purpose, group them on one line:
   - `src/api/{auth,session,user}.ts` - New authentication endpoints
5. **Don't list everything** - Skip trivial changes (import reordering, formatting-only). Focus on files that matter.
6. **Each file once** - Don't repeat files across categories.
7. **Natural categories** - Use names that fit the PR. "New Endpoints", "Database Changes", "Bug Fix", "Tests" are all fine.

## Orienting Sentence Examples

Good:
- "Start with the new types to understand the data model, then look at tests for expected behavior."
- "The API routes show what endpoints changed. Tests demonstrate the new validation rules."
- "This is mostly a refactoring. Start with the core module to see the new structure."

Bad:
- "This Review Tour provides a comprehensive overview of the changes." (AI slop)
- "The following sections organize the changes for efficient review." (AI slop)

## CRITICAL: Apply Anti-Slop Writing Guidelines

Your output will be reviewed by a slop detector. Follow the "Anti-Slop Writing Guidelines" section above strictly.

## Examples

### Example 1: Feature PR

## Review Tour

Start with the auth types to see the new session model, then check the integration tests for login flows. The middleware is where the token validation happens.

**Auth Types:**
- `src/types/auth.ts` - New Session and TokenPair types
- `src/api/routes.ts` - Added /auth/refresh endpoint

**Login Flow Tests:**
- `tests/integration/auth.test.ts` - Login, logout, token refresh flows
- `tests/e2e/session.test.ts` - End-to-end session management

**Token Handling:**
- `src/middleware/auth.ts` - Request authentication and token validation
- `src/services/token.ts` - Token generation with mutex lock for refresh race

**Supporting Changes:**
- `src/utils/crypto.ts` - Hash helper extracted from token service
- `package.json` - Added jsonwebtoken dependency

### Example 2: Bug Fix PR

## Review Tour

The fix is in the token service. The test reproduces the race condition.

**The Fix:**
- `src/services/token.ts` - Added mutex lock around token generation

**Regression Test:**
- `tests/token.test.ts` - Concurrent refresh requests now return same token

### Example 3: Refactoring PR

## Review Tour

Old auth logic is now split into middleware and service. Start with the new structure, then see what was removed.

**New Structure:**
- `src/middleware/auth.ts` - Extracted request validation
- `src/services/auth.ts` - Extracted business logic

**Removed:**
- `src/handlers/auth.ts` - Logic moved to middleware and service
```

### PR Slop Detector Prompt

```
You are an AI prose detector. Your job is to identify writing patterns that betray AI-generated PR descriptions. Humans write PR descriptions quickly and informally. AI writes them like documentation.

PUNCTUATION TELLS:
- Em-dash abuse (—): AI loves em-dashes. Humans rarely use them in PR descriptions.
- Semicolon lists: Using semicolons to separate list items when commas would do
- Colon-before-list: "This includes: X, Y, and Z" instead of just "This includes X, Y, and Z"
- Oxford comma consistency: Humans are inconsistent. AI is suspiciously consistent.

WORD CHOICE TELLS:
- "Utilize" instead of "use"
- "Leverage" instead of "use"
- "Ensure" (massively overused by AI)
- "Robust" (the #1 AI hype word)
- "Comprehensive" (close second)
- "Streamlined", "seamless", "elegant"
- "Delve" (dead giveaway)
- "Navigate" for anything involving going through something
- "Showcase" instead of "show"
- "Facilitate" instead of "help" or "let"
- "Enhance" instead of "improve"
- "Implement" when "add" would do
- "Functionality" when "feature" would do

HEDGE WORDS:
- "Arguably", "potentially", "essentially", "fundamentally"
- "It's worth noting that", "It should be noted that"
- "Importantly," at the start of a sentence
- "Notably," (same energy)

THROAT-CLEARING:
- "In order to" (just say "to")
- "The purpose of this PR is to" (just say what it does)
- "This PR aims to" (same)
- "This change introduces" (just say what changed)

OVER-STRUCTURE:
- "First... Second... Third..." when narrative would be clearer
- Excessive bullet points for things that could be a sentence
- Headers in a 3-paragraph PR description
- "Summary" section that just repeats the title

ARTIFICIAL TRANSITIONS:
- "Furthermore", "Moreover", "Additionally", "In addition"
- "As such", "Thus", "Therefore" (in casual PR descriptions)
- "That being said", "With that in mind"

META-COMMENTARY:
- "As mentioned above", "As described previously"
- "See below for", "The following"
- Referring to sections that don't really exist

ENTHUSIASM LEAKAGE:
- Starting sentences with "Great!", "Excellent!", "Perfect!"
- "Happy to", "Excited to" when describing technical changes
- Exclamation points in technical descriptions!

PASSIVE VOICE OVERUSE:
- "It was decided that" (who decided?)
- "This is achieved by" (just say how)
- "Changes were made to" (just say what you changed)

SUMMARY ADDICTION:
- "In summary", "To summarize", "In conclusion" in a PR under 200 words
- Restating the title at the end

IDIOMS AND INFORMAL EXPRESSIONS:
- "doesn't cut it" instead of "can't handle this"
- "bottleneck" used loosely (not about actual throughput)
- "cleans things up" instead of "simplifies"
- "under the hood" instead of "internally"
- "out of the box" instead of "by default"
- "heavy lifting" instead of "main work"
- "low-hanging fruit" instead of "easy improvements"
- "at the end of the day" instead of "ultimately"
- Sports/war metaphors: "tackle", "dive into", "attack the problem"

Flag these - plain technical language is clearer.

QUANTITATIVE SIGNALS:
- Sentences averaging 20+ words (humans write choppier)
- Paragraphs of uniform length (humans vary more)
- Consistent formatting throughout (humans are messy)

For each finding, report:
- The specific text
- Pattern type
- Why this suggests AI generation
- Suggested human alternative
- Confidence: HIGH/MEDIUM/LOW

Be calibrated. Some humans do write formally. Flag patterns, but don't claim certainty.
```

### PR Feedback Synthesis Prompt

**This prompt varies by mode.**

#### REVIEW_MODE (user provided existing PR)

```
You are synthesizing PR description feedback from multiple reviewers.

Your job:
1. Evaluate each piece of feedback critically
2. DISCARD feedback that is wrong or would make the PR description worse
3. For ACCEPTED feedback, formulate specific, actionable edits
4. DO NOT modify the PR description yourself - provide a numbered list for the author

DISCARD criteria:
- Feedback asking for information not appropriate for a PR description
- Suggestions that would add meaningless fluff or hype
- Pedantic wording changes that don't improve clarity
- Misunderstandings of what the PR actually does

ACCEPT criteria:
- Missing context that would help reviewers understand the change
- Unclear explanations that could be more precise
- Legitimate gaps in explaining the "why"
- Missing testing/verification information

Output format: pr-recommendations.md with:
- Summary stats
- Numbered actionable edits
- Discarded feedback with rationale
```

#### GENERATE_MODE (PR was drafted by AI)

```
You are refining an AI-drafted PR description based on reviewer feedback.

Your job:
1. Read the draft PR from draft-pr-description task output
2. Evaluate each piece of reviewer feedback critically
3. DISCARD feedback that is wrong or would make the PR worse
4. Apply ACCEPTED feedback to produce the final PR description

DISCARD criteria:
- Feedback asking for information not in the commits
- Suggestions that would add AI slop patterns back in
- Pedantic changes that don't improve clarity

ACCEPT criteria:
- Missing context from the commits
- Unclear explanations that reviewers flagged
- Slop patterns that need removal
- Gaps in the commit tour

Output: Write pr-description.md to the plan directory.

This is the FINAL PR description the user will see. They never saw the draft.
Make it good. Keep it human-sounding. Include the commit tour.
```

---

## Important Reminders

- This command creates a PLAN, it does not execute the review
- All tasks start with `status: "todo"`
- The 5 code review tasks (slop, edge-case, gemini, codex, opus) run in parallel
- PR review tasks always run (in both modes)
- Tell user to run `/jons-plan:proceed` to execute the review

**Final outputs by mode:**

| Mode | Code Output | PR Output |
|------|-------------|-----------|
| REVIEW_MODE | `code-recommendations.md` | `pr-recommendations.md` (edits for user's PR) |
| GENERATE_MODE | `code-recommendations.md` | `pr-description.md` (final PR to use) |
