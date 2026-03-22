#!/usr/bin/env python3
"""WhatsApp message history reader for OpenClaw agent.

Reads WhatsApp messages from OpenClaw gateway log files.

Usage:
    whatsapp.py chats [--limit N] [--days N]       List recent chats
    whatsapp.py read <number> [--limit N] [--days N]  Read messages with contact
    whatsapp.py search <query> [--limit N] [--days N] Search message text

Sending is done via `openclaw message send`, NOT this script.
"""

import json
import glob
import sys
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

LOG_DIR = "/tmp/openclaw"
ET = timezone(timedelta(hours=-4))
OWNER = "+19179752041"


def parse_log_files(days=7):
    """Parse WhatsApp messages from OpenClaw log files."""
    messages = []
    cutoff = datetime.now(tz=ET) - timedelta(days=days)

    log_files = sorted(glob.glob(os.path.join(LOG_DIR, "openclaw-*.log")))
    for log_file in log_files:
        with open(log_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "web-inbound" not in line and "auto-reply sent" not in line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                meta = entry.get("_meta", {})
                ts_str = meta.get("date")
                if not ts_str:
                    continue

                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(ET)
                if ts < cutoff:
                    continue

                data = entry.get("1", {})
                module_str = entry.get("0", "")

                if "web-inbound" in module_str:
                    body = data.get("body", "")
                    sender = data.get("from", "")
                    target = data.get("to", "")
                    messages.append({
                        "time": ts,
                        "direction": "in",
                        "from": sender,
                        "to": target,
                        "text": body,
                    })
                elif "auto-reply sent" in entry.get("2", ""):
                    text = data.get("text", "")
                    target = data.get("to", "")
                    messages.append({
                        "time": ts,
                        "direction": "out",
                        "from": OWNER,
                        "to": target,
                        "text": text,
                    })

    return messages


def get_contact(msg):
    """Get the non-owner contact number from a message."""
    if msg["direction"] == "in":
        return msg["from"] if msg["from"] != OWNER else msg["to"]
    else:
        return msg["to"] if msg["to"] != OWNER else msg["from"]


def cmd_chats(limit=20, days=7):
    messages = parse_log_files(days)
    chats = defaultdict(lambda: {"count": 0, "last_time": None, "last_text": ""})

    for msg in messages:
        contact = get_contact(msg)
        chats[contact]["count"] += 1
        if chats[contact]["last_time"] is None or msg["time"] > chats[contact]["last_time"]:
            chats[contact]["last_time"] = msg["time"]
            preview = msg["text"][:60].replace("\n", " ")
            chats[contact]["last_text"] = preview

    sorted_chats = sorted(chats.items(), key=lambda x: x[1]["last_time"] or datetime.min.replace(tzinfo=ET), reverse=True)

    print(f"{'Last Active':<18} {'Contact':<20} {'Msgs':>5}  {'Last Message'}")
    print("-" * 90)
    for contact, info in sorted_chats[:limit]:
        ts = info["last_time"].strftime("%Y-%m-%d %H:%M") if info["last_time"] else "unknown"
        print(f"{ts:<18} {contact:<20} {info['count']:>5}  {info['last_text']}")


def cmd_read(number, limit=20, days=7):
    messages = parse_log_files(days)
    # Filter to messages involving this number
    filtered = [m for m in messages if number in (m["from"], m["to"]) or get_contact(m) == number]

    if not filtered:
        print(f"No WhatsApp messages found for: {number}")
        return

    # Take last N
    filtered = filtered[-limit:]

    print(f"--- WhatsApp: {number} — last {len(filtered)} messages (past {days} days) ---\n")
    for msg in filtered:
        ts = msg["time"].strftime("%Y-%m-%d %H:%M")
        if msg["direction"] == "in":
            direction = f"← {msg['from']}"
        else:
            direction = "→ Clawd"
        text = msg["text"]
        if len(text) > 300:
            text = text[:300] + "..."
        text = text.replace("\n", "\n    ")
        print(f"[{ts}] {direction}: {text}")


def cmd_search(query, limit=20, days=7):
    messages = parse_log_files(days)
    query_lower = query.lower()
    matches = [m for m in messages if query_lower in m["text"].lower()]

    if not matches:
        print(f"No WhatsApp messages matching: {query}")
        return

    matches = matches[-limit:]
    print(f"--- WhatsApp search: '{query}' — {len(matches)} results (past {days} days) ---\n")
    for msg in matches:
        ts = msg["time"].strftime("%Y-%m-%d %H:%M")
        contact = get_contact(msg)
        direction = "←" if msg["direction"] == "in" else "→ Clawd"
        text = msg["text"]
        if len(text) > 200:
            text = text[:200] + "..."
        text = text.replace("\n", " ")
        print(f"[{ts}] ({contact}) {direction}: {text}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    limit = 20
    days = 7

    args = sys.argv[2:]
    # Parse --limit and --days flags
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1
    args = filtered_args

    if cmd == "chats":
        cmd_chats(limit, days)
    elif cmd == "read":
        if not args:
            print("Usage: whatsapp.py read <phone-number> [--limit N] [--days N]")
            sys.exit(1)
        cmd_read(args[0], limit, days)
    elif cmd == "search":
        if not args:
            print("Usage: whatsapp.py search <query> [--limit N] [--days N]")
            sys.exit(1)
        cmd_search(" ".join(args), limit, days)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
