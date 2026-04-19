#!/usr/bin/env python3
"""Archive OpenClaw main-agent session state and start fresh.

Why: the long-lived direct WhatsApp session can grow until model context windows
are exceeded. This script preserves the old files as timestamped backups, then
recreates an empty session index so the next turn starts cleanly.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
INDEX_FILE = SESSIONS_DIR / "sessions.json"


def backup_name(path: Path, stamp: str) -> Path:
    return path.with_name(f"{path.name}.reset.{stamp}")


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    moved = []

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    sessions = {}
    if INDEX_FILE.exists():
        try:
            sessions = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sessions = {}

    # Move currently-indexed active session files out of the way first.
    for meta in sessions.values():
        session_file = meta.get("sessionFile")
        if not session_file:
            continue
        path = Path(session_file).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            continue
        if resolved.parent != SESSIONS_DIR.resolve():
            continue
        target = backup_name(resolved, stamp)
        resolved.rename(target)
        moved.append((resolved.name, target.name))

    if INDEX_FILE.exists():
        target = backup_name(INDEX_FILE, stamp)
        INDEX_FILE.rename(target)
        moved.append((INDEX_FILE.name, target.name))

    INDEX_FILE.write_text("{}\n", encoding="utf-8")

    print(f"Reset main-agent sessions in {SESSIONS_DIR}")
    if moved:
        for src, dst in moved:
            print(f"- archived {src} -> {dst}")
    else:
        print("- no active session files found; wrote a fresh sessions.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
