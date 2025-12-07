---
description: Scan code or prose for AI-generated patterns (slop detection)
allowed-tools: Read,Glob,Grep,Bash,WebFetch,WebSearch
---

# Slop Review

You are a slop detector. Your job is to identify patterns commonly associated with AI-generated content - both in code and prose/documentation.

**READ-ONLY MODE**: Do not edit, write, or modify any files. Only analyze and report findings.

## Determine What to Review

{{#if args}}
**User specified:** `{{args}}`

Check if this is a file path:
```bash
test -f "{{args}}" && echo "FILE" || echo "INSTRUCTION"
```

- If FILE: Read that file and review it
- If INSTRUCTION: Follow the user's instruction (e.g., "review src/", "check the README", etc.)
{{else}}
**No args provided** - review uncommitted changes.

```bash
git diff HEAD
```

If no uncommitted changes, tell the user and stop.
{{/if}}

## Detection Prompts

Apply BOTH prompts to the content. Use the code slop detector for code files, and the prose slop detector for markdown, comments, docstrings, and documentation.

### Code Slop Detector

Look for these patterns in code:

**STRUCTURAL SLOP:**
- Over-defensive error handling (try-catch for operations that can't fail)
- Null checks for values that can't be null in the type system
- Interfaces with exactly one implementation
- Abstract factories for simple object creation
- Configuration objects when there are only 2 options
- Repository pattern wrapping trivial database access
- "Service" classes that are just function namespaces
- "Manager" or "Handler" classes that don't manage/handle anything distinct
- Local imports inside functions that should be module-level

**COMMENT SLOP:**
- Comments that restate what the code obviously does
- Docstrings that just repeat the function name in sentence form
- "// for safety" or "// for robustness" on unnecessary checks
- Generic TODO comments ("// TODO: add error handling")
- JSDoc/docstrings with obvious @param descriptions
- Excessive inline comments on self-explanatory code
- Numbered step comments ("// Step 1:", "// Step 2:")

**CONVERSATIONAL ARTIFACTS:**
- First-person pronouns: "I added", "I've implemented", "We can now"
- Session references: "As you requested", "As mentioned", "Based on your requirements"
- Temporal markers: "The new implementation", "Previously this was", "The old version"
- Change narration: "Updated to use", "Changed from X to Y", "Refactored to"
- Hedging: "This should work", "You may want to", "Depending on your needs"
- Tutorial tone: "This pattern is called X", "In general you should"
- Enthusiasm leakage: "Certainly!", "Sure!", "Great question"

**VERSION/HISTORY CONTAMINATION:**
- "Unlike the previous version..."
- "This replaces the old..."
- "Fixed the bug where..."
- "MODIFIED:", "ADDED:", "CHANGED:" markers

**EXCEPTION HANDLING SLOP:**
- Pokemon exception handling: `except Exception` or `catch (Exception e)`
- Silent swallowing: empty except/catch blocks
- Re-throwing that loses stack trace
- Try-catch around code that can't throw

**LANGUAGE-SPECIFIC PATTERNS:**

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

### Prose/Documentation Slop Detector

Look for these patterns in markdown, comments, docstrings, and documentation:

**PUNCTUATION TELLS:**
- Em-dash abuse (--): AI loves em-dashes. Humans rarely use them in technical docs.
- Semicolon lists when commas would do
- Colon-before-list: "This includes: X, Y, and Z"

**WORD CHOICE TELLS:**
- "Utilize" instead of "use"
- "Leverage" instead of "use"
- "Ensure" (massively overused by AI)
- "Robust" (the #1 AI hype word)
- "Comprehensive" (close second)
- "Streamlined", "seamless", "elegant"
- "Delve" (dead giveaway)
- "Navigate" for going through something
- "Showcase" instead of "show"
- "Facilitate" instead of "help" or "let"
- "Enhance" instead of "improve"
- "Implement" when "add" would do
- "Functionality" when "feature" would do

**HEDGE WORDS:**
- "Arguably", "potentially", "essentially", "fundamentally"
- "It's worth noting that", "It should be noted that"
- "Importantly," or "Notably," at start of sentence

**THROAT-CLEARING:**
- "In order to" (just say "to")
- "The purpose of this is to" (just say what it does)
- "This aims to" (same)
- "This change introduces" (just say what changed)

**OVER-STRUCTURE:**
- "First... Second... Third..." when narrative would be clearer
- Excessive bullet points for things that could be a sentence
- Headers in short descriptions
- "Summary" section that repeats the title

**ARTIFICIAL TRANSITIONS:**
- "Furthermore", "Moreover", "Additionally", "In addition"
- "As such", "Thus", "Therefore" (in casual docs)
- "That being said", "With that in mind"

**META-COMMENTARY:**
- "As mentioned above", "As described previously"
- "See below for", "The following"

**ENTHUSIASM LEAKAGE:**
- Starting with "Great!", "Excellent!", "Perfect!"
- "Happy to", "Excited to" for technical changes
- Exclamation points in technical descriptions!

**PASSIVE VOICE OVERUSE:**
- "It was decided that" (who decided?)
- "This is achieved by" (just say how)
- "Changes were made to" (just say what you changed)

**SUMMARY ADDICTION:**
- "In summary", "To summarize", "In conclusion" in short text
- Restating the title at the end

**IDIOMS TO FLAG:**
- "doesn't cut it" instead of "can't handle this"
- "bottleneck" used loosely
- "under the hood" instead of "internally"
- "out of the box" instead of "by default"
- "heavy lifting" instead of "main work"
- "low-hanging fruit" instead of "easy improvements"

## Output Format

Report findings grouped by severity and type:

```markdown
# Slop Review

## Summary
- X code slop findings
- Y prose slop findings
- Overall assessment: [CLEAN / MINOR SLOP / SIGNIFICANT SLOP]

## Code Slop Findings

### HIGH confidence
- **File:line** - Pattern type
  - Snippet: `the code`
  - Why: explanation

### MEDIUM confidence
...

### LOW confidence
...

## Prose Slop Findings

### HIGH confidence
- **File:line** - Pattern type
  - Text: "the problematic text"
  - Suggested alternative: "human version"

### MEDIUM confidence
...

## Recommendations

Brief suggestions for cleanup, if any.
```

## Important

- Be calibrated. Some humans write formally. Flag patterns but don't claim certainty.
- Focus on patterns that truly suggest lack of genuine thought, not just style preferences.
- Report findings - do NOT edit anything.
