#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""jons-plan Plugin Verification - Checks that the plugin is correctly installed and configured."""

import json
import py_compile
import subprocess
import sys
from pathlib import Path


def main():
    quiet = "--quiet" in sys.argv

    plugin_dir = Path(__file__).parent.parent.resolve()

    if not quiet:
        print("Verifying jons-plan installation...")
        print(f"Plugin directory: {plugin_dir}")
        print()

    errors = 0

    # Check required files exist
    required_files = [
        "plan.py",
        "CLAUDE.md",
        "hooks/hooks.json",
        ".claude-plugin/plugin.json",
        "hooks/session-start.sh",
        "hooks/stop.sh",
        "hooks/pre-compact.sh",
        "hooks/post-tool-use.sh",
        "hooks/user-prompt-submit.sh",
    ]

    for file in required_files:
        filepath = plugin_dir / file
        if filepath.exists():
            if not quiet:
                print(f"  [OK] {file}")
        else:
            print(f"  [ERROR] Missing: {file}")
            errors += 1

    # Check Python syntax
    try:
        py_compile.compile(str(plugin_dir / "plan.py"), doraise=True)
        if not quiet:
            print("  [OK] plan.py syntax")
    except py_compile.PyCompileError:
        print("  [ERROR] plan.py has syntax errors")
        errors += 1

    # Check shell script syntax
    for script in (plugin_dir / "hooks").glob("*.sh"):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
        if result.returncode == 0:
            if not quiet:
                print(f"  [OK] {script.name} syntax")
        else:
            print(f"  [ERROR] {script.name} has syntax errors")
            errors += 1

    # Check JSON validity
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    try:
        json.loads(hooks_json.read_text())
        if not quiet:
            print("  [OK] hooks.json valid")
    except (json.JSONDecodeError, FileNotFoundError):
        print("  [ERROR] hooks.json is invalid JSON")
        errors += 1

    # Check CLI works
    result = subprocess.run(["uv", "run", str(plugin_dir / "plan.py"), "--help"], capture_output=True)
    if result.returncode == 0:
        if not quiet:
            print("  [OK] CLI works")
    else:
        print("  [ERROR] CLI failed to run")
        errors += 1

    # Check for hardcoded paths in shell scripts
    hardcoded_files = []
    for script in (plugin_dir / "hooks").glob("*.sh"):
        content = script.read_text()
        if "~/.claude-plugins/jons-plan" in content:
            hardcoded_files.append(script.name)

    if hardcoded_files:
        print("  [WARN] Hardcoded paths found in:")
        for f in hardcoded_files:
            print(f"    - {f}")

    print()

    if errors == 0:
        if not quiet:
            print("All checks passed!")
        return 0
    else:
        print(f"{errors} error(s) found")
        return 1


if __name__ == "__main__":
    sys.exit(main())
