# Plan Synthesis

You are evaluating three independently-generated plans (from Opus, Codex, and Gemini) and producing a single unified plan.

## Process

### Step 1: Read All Plans
Read all three parent plan outputs completely before making any judgments.
Ignore any conversational preamble or closing remarks — focus on the plan content.

### Step 2: Assess Each Plan Independently
For each plan, score 1-5 on these criteria (in order of importance):
1. **Completeness** — Does it address all requirements?
2. **Feasibility** — Can the tasks be executed as described?
3. **Task Decomposition** — Are tasks appropriately scoped? Are dependencies correct?
4. **Risk Awareness** — Does it identify what could go wrong?
5. **Clarity** — Could a coding agent execute this without ambiguity?

### Step 3: Compare Section by Section
Identify corresponding sections across all three plans by content (not heading name).
For each section, rank the three versions and explain why the winner is best.
Note sections that appear in one or two plans but not the others.

### Step 4: Select Base Plan
Choose the highest-scoring plan as the base.
If top scores are within 1 point, prefer the plan with better task decomposition
(since tasks are what the coding agent will execute).

### Step 5: Merge Non-Task Sections
For non-task sections (Requirements, Approach, Alternatives, Risks, Verification):
review the two non-base plans for better content, and incorporate where they improve the base.

### Step 6: Handle Task Breakdown
**CRITICAL**: Select the base plan's Task Breakdown in its entirety as the skeleton.
Do NOT merge individual tasks from the non-base plans into the base plan's task list,
as this risks breaking dependency chains.

Only add tasks from non-base plans if they are:
- Standalone (no dependencies on the non-base plan's architectural choices)
- Clearly missing from the base plan
- Compatible with the base plan's approach

### Step 7: Produce Output
The final plan must be self-contained and conform to the phase's expected artifact format.

## Output

Write TWO files to your output directory:

1. **synthesis-evaluation.md** — Full evaluation reasoning:
   - Individual plan scores with justification (Opus Plan, Codex Plan, Gemini Plan)
   - Section-by-section comparison results (with source attribution)
   - Base selection rationale
   - List of incorporations from non-base plans (citing source)

2. **The final merged plan** — write to the filename specified in the context below:
   - Self-contained (reader should not need to see the input plans)
   - Follows the document structure from the planning prompt
   - Best elements from all three plans, coherently integrated

## Rules

- **Do not average** — pick the best version of each section
- **Do not invent** — draw only from the input plans and upstream context
- **Preserve coherence** — incorporations must fit the base plan's assumptions and terminology
- **Flag fundamental issues** — if all three plans score below 3 on any criterion, note this prominently
- **Evaluate content, not format** — section names, list styles, and formatting differences are irrelevant
- **Task Breakdown is atomic** — do not mix individual tasks across plans
- **Attribute sources** — in the evaluation, always cite which plan an element came from
