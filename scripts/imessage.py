#!/usr/bin/env python3
"""iMessage/SMS helper for OpenClaw agent.

Usage:
    imessage.py chats [--limit N]          List recent chats
    imessage.py read <identifier> [--limit N]  Read messages (phone or chat id)
    imessage.py search <query> [--limit N]     Search message text
    imessage.py send <number> <message>        Send via Messages.app (AppleScript)

Requires Full Disk Access for read/search/chats operations.
"""

import sqlite3
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
APPLE_EPOCH = 978307200  # seconds between Unix epoch and Apple epoch (2001-01-01)
ET = ZoneInfo("America/New_York")


def apple_ts_to_str(ts):
    """Convert Apple's nanosecond timestamp to human-readable ET string."""
    if ts is None or ts == 0:
        return "unknown"
    unix_ts = ts / 1e9 + APPLE_EPOCH
    dt = datetime.fromtimestamp(unix_ts, tz=ET)
    return dt.strftime("%Y-%m-%d %H:%M")


def extract_text(text, attributed_body):
    """Extract message text, falling back to attributedBody blob if needed."""
    if text:
        return text
    if not attributed_body:
        return "(no text / attachment)"
    try:
        blob = bytes(attributed_body)
        marker = b"NSString\x01\x94\x84\x01+"
        idx = blob.find(marker)
        if idx != -1:
            start = idx + len(marker)
            length_byte = blob[start]
            if length_byte & 0x80:
                # Multi-byte length: high bit set means the low 7 bits encode
                # the number of following bytes that hold the actual length.
                n_bytes = length_byte & 0x7F
                length = int.from_bytes(blob[start + 1 : start + 1 + n_bytes], "big")
                text_bytes = blob[start + 1 + n_bytes : start + 1 + n_bytes + length]
            else:
                length = length_byte
                text_bytes = blob[start + 1 : start + 1 + length]
            return text_bytes.decode("utf-8", errors="replace")
    except Exception:
        pass
    return "(encoded message)"


def get_db():
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        if "authorization denied" in str(e) or "unable to open" in str(e):
            print("ERROR: Full Disk Access required.", file=sys.stderr)
            print("Grant it to the python3 binary or Terminal in:", file=sys.stderr)
            print("  System Settings > Privacy & Security > Full Disk Access", file=sys.stderr)
            sys.exit(1)
        raise


def cmd_chats(limit=20):
    db = get_db()
    rows = db.execute("""
        SELECT
            c.chat_identifier,
            c.display_name,
            c.service_name,
            MAX(m.date) as last_date,
            COUNT(m.ROWID) as msg_count
        FROM chat c
        LEFT JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
        LEFT JOIN message m ON cmj.message_id = m.ROWID
        GROUP BY c.ROWID
        ORDER BY last_date DESC
        LIMIT ?
    """, (limit,)).fetchall()

    print(f"{'Last Active':<18} {'Type':<10} {'Identifier':<30} {'Name':<20} {'Msgs':>5}")
    print("-" * 90)
    for r in rows:
        ts = apple_ts_to_str(r["last_date"])
        svc = r["service_name"] or "?"
        ident = r["chat_identifier"] or "?"
        name = r["display_name"] or ""
        count = r["msg_count"] or 0
        print(f"{ts:<18} {svc:<10} {ident:<30} {name:<20} {count:>5}")
    db.close()


def resolve_chat_identifier(identifier):
    """Resolve a phone number or email to possible chat identifiers."""
    clean = identifier.strip()
    # chat.db stores the bare identifier (e.g. "+19176997436"), not the
    # AppleScript-style prefixed form ("iMessage;-;+19176997436")
    if clean.startswith("iMessage;") or clean.startswith("SMS;") or clean.startswith("RCS;"):
        bare = clean.split(";")[-1]
        return [bare, clean]
    return [clean]


def cmd_read(identifier, limit=20):
    db = get_db()
    possible_ids = resolve_chat_identifier(identifier)
    placeholders = ",".join("?" * len(possible_ids))

    rows = db.execute(f"""
        SELECT
            m.date,
            m.is_from_me,
            m.text,
            m.attributedBody,
            h.id as sender_id,
            c.chat_identifier,
            c.service_name
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE c.chat_identifier IN ({placeholders})
        ORDER BY m.date DESC
        LIMIT ?
    """, (*possible_ids, limit)).fetchall()

    if not rows:
        print(f"No messages found for: {identifier}")
        db.close()
        return

    # Print newest-last (reverse the DESC order)
    rows = list(reversed(rows))
    service = rows[0]["service_name"] or "?"
    print(f"--- {identifier} ({service}) — last {len(rows)} messages ---\n")

    for r in rows:
        ts = apple_ts_to_str(r["date"])
        direction = "→ Me" if r["is_from_me"] else f"← {r['sender_id'] or 'them'}"
        text = extract_text(r["text"], r["attributedBody"])
        # Truncate very long messages
        if len(text) > 300:
            text = text[:300] + "..."
        print(f"[{ts}] {direction}: {text}")

    db.close()


def cmd_search(query, limit=20):
    db = get_db()
    rows = db.execute("""
        SELECT
            m.date,
            m.is_from_me,
            m.text,
            m.attributedBody,
            h.id as sender_id,
            c.chat_identifier
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.text LIKE ?
        ORDER BY m.date DESC
        LIMIT ?
    """, (f"%{query}%", limit)).fetchall()

    if not rows:
        print(f"No messages matching: {query}")
        db.close()
        return

    rows = list(reversed(rows))
    print(f"--- Search: '{query}' — {len(rows)} results ---\n")

    for r in rows:
        ts = apple_ts_to_str(r["date"])
        chat = r["chat_identifier"]
        direction = "→ Me" if r["is_from_me"] else f"← {r['sender_id'] or 'them'}"
        text = extract_text(r["text"], r["attributedBody"])
        if len(text) > 200:
            text = text[:200] + "..."
        print(f"[{ts}] ({chat}) {direction}: {text}")

    db.close()


def _escape_applescript(s):
    """Escape a string for safe embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def cmd_send(number, message):
    """Send a message via Messages.app AppleScript.

    Tries existing chat-id first, then buddy-of-service for new threads.
    Service order: iMessage, SMS — covers iMessage, SMS, and RCS.
    """
    safe_number = _escape_applescript(number)
    safe_message = _escape_applescript(message)
    last_err = ""

    # SMS first for phone numbers (routes to RCS when available).
    # iMessage buddy-send can silently fail for non-Apple recipients.
    for service in ("SMS", "iMessage"):
        # Attempt 1: existing chat thread
        script = (
            'tell application "Messages"\n'
            f'    set targetChat to a reference to chat id "{service};-;{safe_number}"\n'
            f'    send "{safe_message}" to targetChat\n'
            'end tell'
        )
        ok, err = _run_osascript(script)
        if ok:
            print(f"Sent to {number} via {service}")
            return
        last_err = err

        # Attempt 2: buddy of service (creates new thread)
        script = (
            'tell application "Messages"\n'
            f'    set targetService to 1st service whose service type is {service}\n'
            f'    send "{safe_message}" to buddy "{safe_number}" of targetService\n'
            'end tell'
        )
        ok, err = _run_osascript(script)
        if ok:
            print(f"Sent to {number} via {service} (new thread)")
            return
        last_err = err

    print(f"ERROR: Could not send via iMessage or SMS. {last_err}", file=sys.stderr)
    sys.exit(1)


def _run_osascript(script):
    """Run an AppleScript, return (success: bool, stderr: str)."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    limit = 20

    # Parse --limit flag
    args = sys.argv[2:]
    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 >= len(args):
            print("ERROR: --limit requires a numeric argument", file=sys.stderr)
            sys.exit(1)
        try:
            limit = int(args[idx + 1])
        except ValueError:
            print(f"ERROR: --limit value must be an integer, got: {args[idx + 1]}", file=sys.stderr)
            sys.exit(1)
        args = args[:idx] + args[idx + 2:]

    if cmd == "chats":
        cmd_chats(limit)
    elif cmd == "read":
        if not args:
            print("Usage: imessage.py read <phone-or-chat-id> [--limit N]")
            sys.exit(1)
        cmd_read(args[0], limit)
    elif cmd == "search":
        if not args:
            print("Usage: imessage.py search <query> [--limit N]")
            sys.exit(1)
        cmd_search(" ".join(args), limit)
    elif cmd == "send":
        if len(args) < 2:
            print("Usage: imessage.py send <number> <message>")
            sys.exit(1)
        cmd_send(args[0], " ".join(args[1:]))
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
