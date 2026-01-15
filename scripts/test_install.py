#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for install/uninstall scripts using isolated test directories."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

SCRIPTS_DIR = Path(__file__).parent
PLUGIN_DIR = SCRIPTS_DIR.parent


class TestInstallUninstall:
    """Test install and uninstall scripts in isolation."""

    def test_install_creates_expected_files(self, tmp_path: Path):
        """Install script creates marketplace and settings entries."""
        # Run install with temp HOME, auto-answer 'y'
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "install.py")],
            env={**os.environ, "HOME": str(tmp_path)},
            input="y\n",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Check marketplace file
        marketplaces_file = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        assert marketplaces_file.exists(), "known_marketplaces.json not created"

        marketplaces = json.loads(marketplaces_file.read_text())
        assert "jons-plan-local" in marketplaces
        assert marketplaces["jons-plan-local"]["source"]["source"] == "directory"

        # Check settings file
        settings_file = tmp_path / ".claude" / "settings.json"
        assert settings_file.exists(), "settings.json not created"

        settings = json.loads(settings_file.read_text())
        assert "enabledPlugins" in settings
        assert settings["enabledPlugins"].get("jons-plan@jons-plan-local") is True

        # Hooks are now defined in plugin's hooks.json, not settings.json
        # (bug #12151 was fixed in Claude Code v2.1.3)

    def test_install_is_idempotent(self, tmp_path: Path):
        """Running install twice doesn't duplicate entries."""
        env = {**os.environ, "HOME": str(tmp_path)}

        # Install twice
        for _ in range(2):
            result = subprocess.run(
                ["uv", "run", str(SCRIPTS_DIR / "install.py")],
                env=env,
                input="y\n",
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

        # Check no duplicate plugin entries
        settings_file = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text())

        # Should have exactly one plugin entry
        assert settings["enabledPlugins"].get("jons-plan@jons-plan-local") is True

    def test_uninstall_removes_entries(self, tmp_path: Path):
        """Uninstall removes all plugin entries."""
        env = {**os.environ, "HOME": str(tmp_path)}

        # Install first
        subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "install.py")],
            env=env,
            input="y\n",
            capture_output=True,
            text=True,
        )

        # Then uninstall
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "uninstall.py")],
            env=env,
            input="y\n",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"

        # Check marketplace entry removed
        marketplaces_file = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        marketplaces = json.loads(marketplaces_file.read_text())
        assert "jons-plan-local" not in marketplaces

        # Check plugin removed from settings
        settings_file = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text())
        assert "jons-plan@jons-plan-local" not in settings.get("enabledPlugins", {})

        # Check hooks removed
        for hook_name in settings.get("hooks", {}):
            for entry in settings["hooks"][hook_name]:
                for hook in entry.get("hooks", []):
                    assert "jons-plan" not in hook.get("command", ""), f"Hook not removed from {hook_name}"

    def test_install_preserves_existing_settings(self, tmp_path: Path):
        """Install doesn't clobber existing settings."""
        # Create existing settings
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)

        existing_settings = {
            "apiKey": "sk-test-key",
            "enabledPlugins": {"other-plugin@marketplace": True},
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hello"}]}]},
        }
        settings_file = claude_dir / "settings.json"
        settings_file.write_text(json.dumps(existing_settings))

        # Run install
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "install.py")],
            env={**os.environ, "HOME": str(tmp_path)},
            input="y\n",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Verify existing settings preserved
        settings = json.loads(settings_file.read_text())
        assert settings.get("apiKey") == "sk-test-key"
        assert settings["enabledPlugins"].get("other-plugin@marketplace") is True

        # Verify existing hooks preserved (install no longer modifies hooks)
        session_hooks = settings["hooks"]["SessionStart"]
        echo_hooks = [h for h in session_hooks for hook in h.get("hooks", []) if "echo hello" in hook.get("command", "")]
        assert len(echo_hooks) == 1

    def test_install_cancelled(self, tmp_path: Path):
        """Install can be cancelled without changes."""
        # Run install and decline
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "install.py")],
            env={**os.environ, "HOME": str(tmp_path)},
            input="n\n",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "cancelled" in result.stdout.lower()

        # No files created
        assert not (tmp_path / ".claude" / "settings.json").exists()


class TestVerify:
    """Test verification script."""

    def test_verify_passes(self):
        """Verify script passes on valid installation."""
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "verify.py")],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "All checks passed" in result.stdout

    def test_verify_quiet_mode(self):
        """Verify --quiet suppresses output on success."""
        result = subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "verify.py"), "--quiet"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should have minimal output in quiet mode
        assert "Verifying" not in result.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
