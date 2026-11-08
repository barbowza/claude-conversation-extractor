"""Pytest configuration for Claude Conversation Extractor tests."""

import os
import sys
from pathlib import Path

import pytest

# Add src directory to Python path for testing
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point the home directory at a temp dir for every test.

    Without this, tests read the real ~/.claude/projects and the extractor
    creates ~/Desktop/Claude logs on the developer's machine. Path.home()
    reads HOME on POSIX and USERPROFILE on Windows, so both are set.
    Tests that patch Path.home themselves still take precedence.
    """
    home = tmp_path / "home"
    (home / ".claude" / "projects").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # Run with the temp dir as cwd so "./claude-logs" fallbacks stay inside it.
    monkeypatch.chdir(tmp_path)
    # Never let a test clear the developer's terminal.
    monkeypatch.setattr(os, "system", lambda *args, **kwargs: 0)
    yield home
