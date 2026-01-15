#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""jons-plan Plugin Installer - Registers the plugin with Claude Code and configures hooks."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    plugin_dir = Path(__file__).parent.parent.resolve()
    plugin_name = plugin_dir.name
    marketplace_name = f"{plugin_name}-local"
    parent_dir = plugin_dir.parent

    print("jons-plan Plugin Installer")
    print("==========================")
    print()
    print(f"Plugin directory: {plugin_dir}")
    print()

    # Check prerequisites
    print("Checking prerequisites...")

    # Check for graphviz (optional)
    dot_result = subprocess.run(["which", "dot"], capture_output=True)
    if dot_result.returncode == 0:
        print("  [OK] graphviz (for workflow viewer)")
    else:
        print("  [--] graphviz not found (workflow viewer won't work)")
        print("       Install with: brew install graphviz")

    print()
    print("This will:")
    print("  1. Register plugin marketplace in ~/.claude/plugins/known_marketplaces.json")
    print("  2. Enable plugin in ~/.claude/settings.json")
    print("  3. Add hooks to ~/.claude/settings.json (workaround for bug #12151)")
    print()

    response = input("Continue? [y/N] ").strip().lower()
    if response != "y":
        print("Installation cancelled.")
        return 0

    print()
    print("Installing...")

    # Ensure directories exist
    claude_dir = Path.home() / ".claude"
    plugins_dir = claude_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # === Update known_marketplaces.json ===
    marketplaces_file = plugins_dir / "known_marketplaces.json"
    marketplaces = {}
    if marketplaces_file.exists():
        try:
            marketplaces = json.loads(marketplaces_file.read_text())
        except json.JSONDecodeError:
            print("  Warning: Could not parse existing known_marketplaces.json, creating new one")
            marketplaces = {}

    marketplaces[marketplace_name] = {
        "source": {"source": "directory", "path": str(parent_dir)},
        "installLocation": str(parent_dir),
        "lastUpdated": datetime.now().isoformat() + "Z",
        "autoUpdate": False,
    }
    marketplaces_file.write_text(json.dumps(marketplaces, indent=2))
    print(f"  [OK] Registered marketplace: {marketplace_name}")

    # === Update settings.json ===
    settings_file = claude_dir / "settings.json"
    settings = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            print("  Warning: Could not parse existing settings.json, creating new one")
            settings = {}

    # Enable plugin
    if "enabledPlugins" not in settings:
        settings["enabledPlugins"] = {}
    settings["enabledPlugins"][f"{plugin_name}@{marketplace_name}"] = True
    print(f"  [OK] Enabled plugin: {plugin_name}@{marketplace_name}")

    # Add hooks (bug #12151 workaround)
    hooks_config = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": f"{plugin_dir}/hooks/session-start.sh", "timeout": 10000}]}
        ],
        "PreCompact": [
            {"hooks": [{"type": "command", "command": f"{plugin_dir}/hooks/pre-compact.sh", "timeout": 5000}]}
        ],
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": f"{plugin_dir}/hooks/user-prompt-submit.sh", "timeout": 5000}]}
        ],
        "PostToolUse": [
            {
                "matcher": "Write|Edit",
                "hooks": [{"type": "command", "command": f"{plugin_dir}/hooks/post-tool-use.sh", "timeout": 5000}],
            }
        ],
        "Stop": [{"hooks": [{"type": "command", "command": f"{plugin_dir}/hooks/stop.sh", "timeout": 10000}]}],
    }

    if "hooks" not in settings:
        settings["hooks"] = {}

    for hook_name, hook_config in hooks_config.items():
        if hook_name not in settings["hooks"]:
            settings["hooks"][hook_name] = []

        # Check if hook already exists (by command path containing plugin_name)
        existing = settings["hooks"][hook_name]
        already_present = False
        for entry in existing:
            for hook in entry.get("hooks", []):
                if plugin_name in hook.get("command", ""):
                    already_present = True
                    break
            if already_present:
                break

        if not already_present:
            settings["hooks"][hook_name].extend(hook_config)

    print("  [OK] Added hooks to settings.json")

    settings_file.write_text(json.dumps(settings, indent=2))
    print("  [OK] Saved settings.json")

    print()

    # Run verification
    print("Verifying installation...")
    verify_script = plugin_dir / "scripts" / "verify.py"
    result = subprocess.run(["uv", "run", str(verify_script), "--quiet"])

    print()
    print("========================================")
    print("Installation complete!")
    print("========================================")
    print()
    print("Next steps:")
    print("  1. Restart Claude Code (or start a new session)")
    print("  2. Run /plugins to see jons-plan listed")
    print("  3. Test with: /jons-plan:status")
    print()
    print("To uninstall later:")
    print(f"  uv run {plugin_dir}/scripts/uninstall.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
