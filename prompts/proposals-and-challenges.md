# Review CLAUDE.md Proposals

Proposals are auto-collected from implement phases. Check for pending proposals:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py list-proposals
```

For each pending proposal, present to user via AskUserQuestion:
- Show: target file, proposed content, rationale
- Options: Accept, Reject
- If Accept: use Edit tool to apply the change to the target file
- Update status: `uv run ~/.claude-plugins/jons-plan/plan.py update-proposal-status <id> accepted|rejected`

# Review Challenges

Challenges are auto-collected from implement phases. Check for pending challenges:

```bash
uv run ~/.claude-plugins/jons-plan/plan.py list-challenges
```

For each pending challenge, present to user for acknowledgement:
- Show: title, what was attempted, what went wrong, workaround used
- No action needed - just acknowledge
- Update status: `uv run ~/.claude-plugins/jons-plan/plan.py acknowledge-challenge <id>`
