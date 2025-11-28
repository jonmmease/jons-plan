# jons-plan Plugin

Long-running agent harness with task management, progress tracking, and parallel task execution.

## Known Issue: Plugin Hook Output Not Passed to Agent

**Bug:** https://github.com/anthropics/claude-code/issues/12151

Plugin-based hooks execute successfully but their stdout is not passed to the agent's context. This affects `SessionStart`, `PostToolUse`, and `Stop` hooks defined in `hooks/hooks.json`.

### Workaround

Until the bug is fixed, hooks must be defined in `~/.claude/settings.json` instead of in the plugin's `hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/session-start.sh",
            "timeout": 10000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/post-tool-use.sh",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude-plugins/jons-plan/hooks/stop.sh",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

### When Issue #12151 is Fixed

1. Remove the `hooks` section from `~/.claude/settings.json`
2. The plugin's `hooks/hooks.json` will work automatically (uses `${CLAUDE_PLUGIN_ROOT}` for portable paths)
