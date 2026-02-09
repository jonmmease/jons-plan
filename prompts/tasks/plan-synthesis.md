# Plan Synthesis

You are evaluating two independently-generated plans and producing a single unified plan.

## Process

### Step 1: Read Both Plans
Read both parent plan outputs completely before making any judgments.
Ignore any conversational preamble or closing remarks — focus on the plan content.

### Step 2: Assess Each Plan Independently
For each plan, score 1-5 on these criteria (in order of importance):
1. **Completeness** — Does it address all requirements?
2. **Feasibility** — Can the tasks be executed as described?
3. **Task Decomposition** — Are tasks appropriately scoped? Are dependencies correct?
4. **Risk Awareness** — Does it identify what could go wrong?
5. **Clarity** — Could a coding agent execute this without ambiguity?

### Step 3: Compare Section by Section
Identify corresponding sections by content (not heading name).
For each section pair, declare a winner and explain why.
Note sections that appear in one plan but not the other.

### Step 4: Select Base Plan
Choose the higher-scoring plan as the base.
If total scores are within 1 point, prefer the plan with better task decomposition
(since tasks are what the coding agent will execute).

### Step 5: Merge Non-Task Sections
For non-task sections (Requirements, Approach, Alternatives, Risks, Verification):
review the non-base plan for better content, and incorporate where it improves the base.

### Step 6: Handle Task Breakdown
**CRITICAL**: Select the base plan's Task Breakdown in its entirety as the skeleton.
Do NOT merge individual tasks from the non-base plan into the base plan's task list,
as this risks breaking dependency chains.

Only add tasks from the non-base plan if they are:
- Standalone (no dependencies on the non-base plan's architectural choices)
- Clearly missing from the base plan
- Compatible with the base plan's approach

### Step 7: Produce Output
The final plan must be self-contained and conform to the phase's expected artifact format.

## Output

Write TWO files to your output directory:

1. **synthesis-evaluation.md** — Full evaluation reasoning:
   - Individual plan scores with justification
   - Section-by-section comparison results (with source: "Opus Plan" / "Codex Plan")
   - Base selection rationale
   - List of incorporations from non-base plan (citing source)

2. **The final merged plan** — write to the filename specified in the context below:
   - Self-contained (reader should not need to see the input plans)
   - Follows the document structure from the planning prompt
   - Best elements from both plans, coherently integrated

## Rules

- **Do not average** — pick the best version of each section
- **Do not invent** — draw only from the input plans and upstream context
- **Preserve coherence** — incorporations must fit the base plan's assumptions and terminology
- **Flag fundamental issues** — if both plans score below 3 on any criterion, note this prominently
- **Evaluate content, not format** — section names, list styles, and formatting differences are irrelevant
- **Task Breakdown is atomic** — do not mix individual tasks across plans
- **Attribute sources** — in the evaluation, always cite which plan an element came from
