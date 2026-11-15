"""Tests for reading Claude desktop app session titles."""

import json
import os
from pathlib import Path

from extract_claude_logs import desktop_app_sessions


def _write_session(app_dir: Path, cli_id: str, title: str, archived: bool = False,
                   mtime: float = None) -> Path:
    f = app_dir / "claude-code-sessions" / "org" / "acct" / f"local_{cli_id}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"cliSessionId": cli_id, "title": title,
                             "isArchived": archived}), encoding="utf-8")
    if mtime is not None:
        os.utime(f, (mtime, mtime))
    return f


def test_no_desktop_app_returns_empty(isolated_home):
    assert desktop_app_sessions() == {}


def test_reads_standard_windows_install(isolated_home):
    """Standard installer keeps sessions in %APPDATA%\\Claude."""
    _write_session(isolated_home / "AppData" / "Roaming" / "Claude", "aaa", "Roaming title", True)
    assert desktop_app_sessions() == {"aaa": {"title": "Roaming title", "archived": True}}


def test_reads_packaged_windows_install(isolated_home):
    """Packaged install keeps sessions in %LOCALAPPDATA%\\Claude-Data\\<id>."""
    _write_session(isolated_home / "AppData" / "Local" / "Claude-Data" / "pkg", "bbb", "Local title")
    assert desktop_app_sessions() == {"bbb": {"title": "Local title", "archived": False}}


def test_reads_macos_and_linux_locations(isolated_home):
    support = isolated_home / "Library" / "Application Support"
    _write_session(support / "Claude", "mac1", "Mac")
    _write_session(support / "Claude-Data" / "x", "mac2", "Mac data")
    _write_session(isolated_home / ".config" / "Claude", "lin", "Linux")
    assert {k: v["title"] for k, v in desktop_app_sessions().items()} == {
        "mac1": "Mac", "mac2": "Mac data", "lin": "Linux"}


def test_same_session_in_two_installs_keeps_newest(isolated_home):
    _write_session(isolated_home / "AppData" / "Roaming" / "Claude", "dup", "Old", mtime=1_000)
    _write_session(isolated_home / "AppData" / "Local" / "Claude-Data" / "p", "dup", "New", mtime=2_000)
    assert desktop_app_sessions()["dup"]["title"] == "New"


def test_skips_unreadable_and_idless_files(isolated_home):
    app = isolated_home / "AppData" / "Roaming" / "Claude"
    _write_session(app, "good", "Good")
    bad = app / "claude-code-sessions" / "local_bad.json"
    bad.write_text("{not json", encoding="utf-8")
    (app / "claude-code-sessions" / "local_noid.json").write_text("{}", encoding="utf-8")
    (app / "claude-code-sessions" / "local_list.json").write_text("[]", encoding="utf-8")
    assert list(desktop_app_sessions()) == ["good"]
