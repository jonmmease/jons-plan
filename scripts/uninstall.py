#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""jons-plan Plugin Uninstaller - Removes plugin registration and hooks from Claude Code configuration."""

import json
import sys
from pathlib import Path


def main():
    plugin_dir = Path(__file__).parent.parent.resolve()
    plugin_name = plugin_dir.name
    marketplace_name = f"{plugin_name}-local"

    print("jons-plan Plugin Uninstaller")
    print("============================")
    print()
    print(f"Plugin directory: {plugin_dir}")
    print()
    print("This will:")
    print("  1. Remove marketplace registration from ~/.claude/plugins/known_marketplaces.json")
    print("  2. Remove plugin from ~/.claude/settings.json")
    print("  3. Remove hooks from ~/.claude/settings.json")
    print()

    response = input("Continue? [y/N] ").strip().lower()
    if response != "y":
        print("Uninstallation cancelled.")
        return 0

    print()
    print("Removing...")

    claude_dir = Path.home() / ".claude"
    plugins_dir = claude_dir / "plugins"

    # === Update known_marketplaces.json ===
    marketplaces_file = plugins_dir / "known_marketplaces.json"
    if marketplaces_file.exists():
        try:
            marketplaces = json.loads(marketplaces_file.read_text())
            if marketplace_name in marketplaces:
                del marketplaces[marketplace_name]
                marketplaces_file.write_text(json.dumps(marketplaces, indent=2))
                print(f"  [OK] Removed marketplace: {marketplace_name}")
            else:
                print(f"  [--] Marketplace not found: {marketplace_name}")
        except json.JSONDecodeError:
            print("  [WARN] Could not parse known_marketplaces.json")
    else:
        print("  [--] known_marketplaces.json not found")

    # === Update settings.json ===
    settings_file = claude_dir / "settings.json"
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())

            # Remove from enabledPlugins
            plugin_key = f"{plugin_name}@{marketplace_name}"
            if "enabledPlugins" in settings and plugin_key in settings["enabledPlugins"]:
                del settings["enabledPlugins"][plugin_key]
                print(f"  [OK] Removed from enabledPlugins: {plugin_key}")
            else:
                print(f"  [--] Plugin not in enabledPlugins: {plugin_key}")

            # Remove hooks containing this plugin's path
            if "hooks" in settings:
                hooks_removed = 0
                for hook_name in list(settings["hooks"].keys()):
                    original_entries = settings["hooks"][hook_name]
                    filtered_entries = []
                    for entry in original_entries:
                        # Keep entry if it doesn't reference our plugin
                        should_keep = True
                        for hook in entry.get("hooks", []):
                            if plugin_name in hook.get("command", ""):
                                should_keep = False
                                hooks_removed += 1
                                break
                        if should_keep:
                            filtered_entries.append(entry)
                    settings["hooks"][hook_name] = filtered_entries

                    # Remove empty hook arrays
                    if not settings["hooks"][hook_name]:
                        del settings["hooks"][hook_name]

                if hooks_removed > 0:
                    print(f"  [OK] Removed {hooks_removed} hook(s)")
                else:
                    print("  [--] No hooks found for this plugin")

            settings_file.write_text(json.dumps(settings, indent=2))
            print("  [OK] Saved settings.json")
        except json.JSONDecodeError:
            print("  [WARN] Could not parse settings.json")
    else:
        print("  [--] settings.json not found")

    print()
    print("========================================")
    print("Uninstallation complete!")
    print("========================================")
    print()
    print("The plugin directory was NOT removed:")
    print(f"  {plugin_dir}")
    print()
    print("To completely remove, run:")
    print(f'  rm -rf "{plugin_dir}"')

    return 0


if __name__ == "__main__":
    sys.exit(main())
