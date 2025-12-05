---
description: Create a multi-agent code review plan for current branch
allowed-tools: "*"
---

ultrathink

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
**PR Document Path:** `{{args}}`
{{else}}
No PR document provided. Review will focus on code only.
{{/if}}

## Workflow

### Step 1: Detect Base Branch

```bash
# Check if 'main' exists, otherwise use 'master'
git rev-parse --verify main 2>/dev/null && echo "main" || echo "master"
```

Store the result as `BASE_BRANCH`.

### Step 2: Validate There Are Changes

```bash
git diff $BASE_BRANCH..HEAD --stat
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
    "description": "Generate diff files and commit archaeology data for reviewers",
    "parents": [],
    "steps": [
      "Detect main/master branch (BASE_BRANCH)",
      "Identify the merge-base: git merge-base $BASE_BRANCH HEAD",
      "Count commits in scope: git rev-list --count $BASE_BRANCH..HEAD",
      "VERIFY: The range $BASE_BRANCH..HEAD means commits reachable from HEAD but NOT from $BASE_BRANCH.",
      "VERIFY: Run 'git log --oneline $BASE_BRANCH..HEAD' - this should ONLY show commits made on this branch.",
      "If any commit appears that seems unrelated, check: 'git branch --contains <hash>' - if $BASE_BRANCH contains it, something is wrong with the range.",
      "Create task output directory via: uv run ~/.claude-plugins/jons-plan/plan.py ensure-task-dir generate-diffs",
      "Write to task output directory:",
      "  - full.diff (git diff $BASE_BRANCH..HEAD) - the actual code changes for reviewers",
      "  - commit-log.txt (git log --oneline $BASE_BRANCH..HEAD) - ONLY commits in this branch",
      "  - commit-log-full.txt (git log -p $BASE_BRANCH..HEAD) - full patches for archaeology",
      "  - per-commit/<hash>.diff for each commit in the range"
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

**If PR document was provided** ({{args}} is not empty), add these additional tasks:

```json
  {
    "id": "pr-slop-detect",
    "description": "Scan PR description for AI-generated writing patterns",
    "model": "haiku",
    "parents": ["generate-diffs"],
    "steps": [
      "Read PR document at: {{args}}",
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
    "parents": ["generate-diffs"],
    "steps": [
      "Read PR document at: {{args}}",
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
    "parents": ["generate-diffs"],
    "steps": [
      "Read PR document at: {{args}}",
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
    "parents": ["generate-diffs"],
    "steps": [
      "Read PR document at: {{args}}",
      "Read full.diff for context",
      "Apply gruff persona to PR description",
      "Check: would a reviewer understand the change?",
      "Write pr-review.md to task output"
    ],
    "status": "todo"
  },
  {
    "id": "synthesize-pr-feedback",
    "description": "Create actionable PR description improvements",
    "model": "opus",
    "parents": ["pr-slop-detect", "gemini-pr-review", "codex-pr-review", "opus-pr-review"],
    "steps": [
      "Read all PR review outputs",
      "Triage feedback: ACCEPT or DISCARD",
      "For accepted items, formulate specific edits",
      "Do NOT modify the PR document",
      "Write pr-recommendations.md to plan directory"
    ],
    "status": "todo"
  }
```

### Step 6: Create plan.md

Write a plan.md file that includes:
- Overview of the review
- Branch being reviewed
- Base branch
- PR document path (if provided)
- List of reviewers and their focus areas
- Link to the prompts (reference CLAUDE.md or inline key prompts)

### Step 7: Create claude-progress.txt

```
[timestamp] Plan created via /jons-plan:new-review
[timestamp] Reviewing: [branch-name] against [base-branch]
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

---

## Important Reminders

- This command creates a PLAN, it does not execute the review
- All tasks start with `status: "todo"`
- The 5 review tasks (slop, edge-case, gemini, codex, opus) run in parallel
- The synthesis task waits for all reviews to complete
- If PR document is provided, PR review tasks also run in parallel
- Tell user to run `/jons-plan:proceed` to execute the review
