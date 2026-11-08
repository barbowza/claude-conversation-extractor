#!/usr/bin/env python3
"""
Local web viewer for Claude Code conversations.

Serves a single page on 127.0.0.1 that lists every session under
~/.claude/projects and renders the selected one in the browser, using
ClaudeConversationExtractor for parsing and exporting.

Run:  claude-web [--port 8765] [--no-browser]
"""

import argparse
import json
import os
import shutil
import tempfile
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

try:
    from .claude_web_page import PAGE
    from .extract_claude_logs import ClaudeConversationExtractor
except ImportError:
    from claude_web_page import PAGE
    from extract_claude_logs import ClaudeConversationExtractor

PROJECTS_DIR = (Path.home() / ".claude" / "projects").resolve()
EXPORT_FORMATS = {
    "markdown": ("text/markdown; charset=utf-8", ".md"),
    "json": ("application/json; charset=utf-8", ".json"),
    "html": ("text/html; charset=utf-8", ".html"),
}

# Temp dir for exports; also stops the extractor creating ~/Desktop/Claude logs.
_EXPORT_DIR = Path(tempfile.mkdtemp(prefix="claude-web-"))
_extractor = ClaudeConversationExtractor(output_dir=_EXPORT_DIR)
_meta_cache: Dict[str, Tuple[Tuple[float, int], dict]] = {}
_cache_lock = threading.Lock()


def _desktop_app_sessions() -> Dict[str, dict]:
    """Map CLI session id -> {title, archived} from the Claude desktop app, if present."""
    found: Dict[str, dict] = {}
    roots = []
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "Claude-Data")
    roots.append(Path.home() / "Library" / "Application Support" / "Claude-Data")
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.glob("*/claude-code-sessions/**/local_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            cli_id = data.get("cliSessionId")
            if cli_id:
                found[cli_id] = {
                    "title": data.get("title") or "",
                    "archived": bool(data.get("isArchived")),
                }
    return found


def _scan_meta(path: Path) -> dict:
    """One pass over a JSONL file for cwd, title, counts and time range."""
    meta = {
        "cwd": "",
        "title": "",
        "user": 0,
        "assistant": 0,
        "first": "",
        "last": "",
        "branch": "",
    }
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            kind = entry.get("type")
            if kind == "custom-title" and entry.get("customTitle"):
                meta["title"] = entry["customTitle"]
            elif kind == "summary" and entry.get("summary") and not meta["title"]:
                meta["title"] = entry["summary"]
            if not meta["cwd"] and entry.get("cwd"):
                meta["cwd"] = entry["cwd"]
            if entry.get("gitBranch"):
                meta["branch"] = entry["gitBranch"]
            ts = entry.get("timestamp")
            if isinstance(ts, str) and ts:
                meta["first"] = meta["first"] or ts
                meta["last"] = ts
            if kind in ("user", "assistant"):
                msg = entry.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    # Tool results arrive as user entries; don't count them as prompts.
                    if kind == "user" and isinstance(content, list) and all(
                        isinstance(c, dict) and c.get("type") == "tool_result" for c in content
                    ):
                        continue
                    meta[kind] += 1
    return meta


def _session_info(path: Path, desktop: Dict[str, dict]) -> dict:
    stat = path.stat()
    rel = path.relative_to(PROJECTS_DIR).as_posix()
    key = (stat.st_mtime, stat.st_size)
    with _cache_lock:
        cached = _meta_cache.get(rel)
    if cached and cached[0] == key:
        info = dict(cached[1])
    else:
        meta = _scan_meta(path)
        preview, _ = _extractor.get_conversation_preview(path)
        info = {
            "path": rel,
            "id": path.stem,
            "project": path.relative_to(PROJECTS_DIR).parts[0],
            "subagent": len(path.relative_to(PROJECTS_DIR).parts) > 2,
            "cwd": meta["cwd"],
            "branch": meta["branch"],
            "jsonlTitle": meta["title"],
            "preview": "" if preview == "No preview available" else preview,
            "userCount": meta["user"],
            "assistantCount": meta["assistant"],
            "first": meta["first"],
            "last": meta["last"],
        }
        with _cache_lock:
            _meta_cache[rel] = (key, info)
        info = dict(info)
    app = desktop.get(path.stem, {})
    info["title"] = app.get("title") or info["jsonlTitle"]
    info["archived"] = app.get("archived", False)
    info["inDesktopApp"] = bool(app)
    info["modified"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    info["size"] = stat.st_size
    return info


def list_sessions() -> list:
    desktop = _desktop_app_sessions()
    out = []
    if PROJECTS_DIR.is_dir():
        for p in PROJECTS_DIR.rglob("*.jsonl"):
            try:
                out.append(_session_info(p, desktop))
            except OSError:
                continue
    out.sort(key=lambda s: s["modified"], reverse=True)
    return out


def resolve_session(rel: Optional[str]) -> Optional[Path]:
    """Turn a client-supplied relative path into a JSONL file inside PROJECTS_DIR, or None."""
    if not rel:
        return None
    try:
        p = (PROJECTS_DIR / rel).resolve()
        p.relative_to(PROJECTS_DIR)
    except (ValueError, OSError):
        return None
    if p.suffix != ".jsonl" or not p.is_file():
        return None
    return p


class Handler(BaseHTTPRequestHandler):
    server_version = "ClaudeWeb/1.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _host_ok(self) -> bool:
        # Reject other hostnames to block DNS-rebinding access from web pages.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _send(self, status, body: bytes, ctype: str, extra: Optional[dict] = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=HTTPStatus.OK):
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status, message):
        self._json({"error": message}, status)

    def do_GET(self):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "Bad Host header")
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        detailed = q.get("detailed") == "1"

        if url.path == "/":
            return self._send(
                HTTPStatus.OK,
                PAGE.encode("utf-8"),
                "text/html; charset=utf-8",
                {
                    "Content-Security-Policy": (
                        "default-src 'none'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
                        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
                    )
                },
            )

        if url.path == "/api/sessions":
            return self._json({"root": str(PROJECTS_DIR), "sessions": list_sessions()})

        if url.path == "/api/session":
            path = resolve_session(q.get("path"))
            if not path:
                return self._error(HTTPStatus.NOT_FOUND, "Session not found")
            messages = _extractor.extract_conversation(path, detailed=detailed)
            return self._json({"path": q["path"], "messages": messages})

        if url.path == "/api/export":
            path = resolve_session(q.get("path"))
            fmt = q.get("format", "markdown")
            if not path:
                return self._error(HTTPStatus.NOT_FOUND, "Session not found")
            if fmt not in EXPORT_FORMATS:
                return self._error(HTTPStatus.BAD_REQUEST, "Unknown format")
            conversation = _extractor.extract_conversation(path, detailed=detailed)
            out = _extractor.save_conversation(conversation, path.stem, fmt)
            if not out:
                return self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "Conversation is empty")
            body = Path(out).read_bytes()
            Path(out).unlink(missing_ok=True)
            ctype, ext = EXPORT_FORMATS[fmt]
            name = f"claude-{path.stem[:8]}{ext}"
            return self._send(
                HTTPStatus.OK,
                body,
                ctype,
                {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
            )

        return self._error(HTTPStatus.NOT_FOUND, "Not found")


def main():
    parser = argparse.ArgumentParser(description="Browse Claude Code conversations in your browser")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Claude conversation viewer: {url}")
    print(f"Reading sessions from {PROJECTS_DIR}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shutil.rmtree(_EXPORT_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
