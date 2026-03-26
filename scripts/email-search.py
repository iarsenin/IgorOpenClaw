#!/usr/bin/env python3
"""Email search wrapper for OpenClaw agent.

Uses himalaya for Gmail and Python imaplib for Yahoo (himalaya's SASL
AUTHENTICATE PLAIN triggers Yahoo rate-limit lockouts; raw LOGIN works).

Searches BOTH Gmail and Yahoo by default.

Usage:
    email-search.py search --from acme
    email-search.py search --from acme --after 2025-10-01
    email-search.py search --subject invoice --before 2026-01-01
    email-search.py search --body nationwide --account yahoo
    email-search.py search --to someone --folder sent
    email-search.py search --from acme --folder all
    email-search.py read --account yahoo --id 395956
"""

import argparse
import email
import email.header
import email.utils
import imaplib
import os
import re
import subprocess
import sys
from datetime import datetime

HIMALAYA = "himalaya"

GMAIL_FOLDERS = {
    "inbox": "INBOX",
    "sent": "[Gmail]/Sent Mail",
    "all": "[Gmail]/All Mail",
    "drafts": "[Gmail]/Drafts",
    "trash": "[Gmail]/Trash",
    "spam": "[Gmail]/Spam",
}

YAHOO_FOLDERS = {
    "inbox": "Inbox",
    "sent": "Sent",
    "all": "Inbox",
    "drafts": "Draft",
    "trash": "Trash",
}

# --------------- IMAP helpers for Yahoo ---------------

YAHOO_IMAP_HOST = "imap.mail.yahoo.com"
YAHOO_IMAP_PORT = 993


def _yahoo_creds():
    """Return (user, password) for Yahoo IMAP, reading from env or .env file."""
    user = os.environ.get("YAHOO_USER", "")
    pw = os.environ.get("YAHOO_APP_PASSWORD", "")
    if not user or not pw:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("YAHOO_USER=") and not user:
                        user = line.split("=", 1)[1].strip()
                    elif line.startswith("YAHOO_APP_PASSWORD=") and not pw:
                        pw = line.split("=", 1)[1].strip()
    return user or None, pw or None


def _decode_header(raw):
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _imap_date(iso_date):
    """Convert YYYY-MM-DD to IMAP date format (e.g. 01-Oct-2025)."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def _build_imap_search(args):
    """Build IMAP SEARCH criteria from parsed args."""
    criteria = []
    if args.from_addr:
        criteria.append(f'FROM "{args.from_addr}"')
    if args.to_addr:
        criteria.append(f'TO "{args.to_addr}"')
    if args.subject:
        criteria.append(f'SUBJECT "{args.subject}"')
    if args.body:
        criteria.append(f'BODY "{args.body}"')
    if args.after:
        criteria.append(f"SINCE {_imap_date(args.after)}")
    if args.before:
        criteria.append(f"BEFORE {_imap_date(args.before)}")
    return " ".join(criteria) if criteria else "ALL"


def _yahoo_search(args):
    """Search Yahoo via direct IMAP LOGIN (bypasses himalaya SASL issue)."""
    user, pw = _yahoo_creds()
    if not user or not pw:
        return None, "yahoo: YAHOO_USER or YAHOO_APP_PASSWORD not set"

    folder = YAHOO_FOLDERS.get((args.folder or "inbox").lower(), args.folder)
    page_size = args.page_size or 20

    try:
        conn = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT)
        conn.login(user, pw)
    except imaplib.IMAP4.error as e:
        err_str = str(e)
        if "UNAVAILABLE" in err_str or "Server error" in err_str:
            return None, "yahoo: temporarily unavailable (Yahoo rate limit)"
        return None, f"yahoo: auth error — {err_str[:200]}"
    except Exception as e:
        return None, f"yahoo: connection error — {str(e)[:200]}"

    try:
        ok, _ = conn.select(f'"{folder}"' if " " in folder else folder, readonly=True)
        if ok != "OK":
            conn.logout()
            return None, f"yahoo: cannot open folder '{folder}'"

        search_criteria = _build_imap_search(args)
        ok, data = conn.search(None, search_criteria)
        if ok != "OK":
            conn.logout()
            return None, f"yahoo: search failed"

        msg_ids = data[0].split()
        if not msg_ids:
            conn.logout()
            return None, None  # no results, not an error

        msg_ids = msg_ids[-page_size:]
        msg_ids.reverse()

        rows = []
        for mid in msg_ids:
            ok, msg_data = conn.fetch(mid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if ok != "OK":
                continue
            raw_headers = msg_data[0][1] if msg_data and msg_data[0] else b""
            flags_raw = msg_data[0][0] if msg_data and msg_data[0] else b""

            parsed = email.message_from_bytes(raw_headers)
            subj = _decode_header(parsed.get("Subject", ""))[:100]
            from_raw = _decode_header(parsed.get("From", ""))
            from_name = email.utils.parseaddr(from_raw)[0] or from_raw.split("<")[0].strip() or from_raw
            date_str = parsed.get("Date", "")

            flag_str = ""
            if isinstance(flags_raw, bytes):
                flags_text = flags_raw.decode("utf-8", errors="replace")
                if "\\Seen" not in flags_text:
                    flag_str += " *"
                if "\\Answered" in flags_text:
                    flag_str += " R"

            rows.append((mid.decode(), flag_str.strip(), subj, from_name[:25], date_str[:24]))

        conn.logout()

        if not rows:
            return None, None

        lines = []
        id_w = max(len(r[0]) for r in rows)
        fl_w = max((len(r[1]) for r in rows), default=5)
        su_w = min(max((len(r[2]) for r in rows), default=20), 100)
        fr_w = min(max((len(r[3]) for r in rows), default=10), 25)
        dt_w = max((len(r[4]) for r in rows), default=10)

        hdr = f"| {'ID':<{id_w}} | {'FLAGS':<{fl_w}} | {'SUBJECT':<{su_w}} | {'FROM':<{fr_w}} | {'DATE':<{dt_w}} |"
        sep = f"|{'-'*(id_w+2)}|{'-'*(fl_w+2)}|{'-'*(su_w+2)}|{'-'*(fr_w+2)}|{'-'*(dt_w+2)}|"
        lines.append(hdr)
        lines.append(sep)
        for r in rows:
            lines.append(f"| {r[0]:<{id_w}} | {r[1]:<{fl_w}} | {r[2]:<{su_w}} | {r[3]:<{fr_w}} | {r[4]:<{dt_w}} |")

        return "\n".join(lines), None

    except Exception as e:
        try:
            conn.logout()
        except Exception:
            pass
        return None, f"yahoo: {str(e)[:200]}"


def _yahoo_read(msg_id, folder=None):
    """Read a full email from Yahoo via IMAP."""
    user, pw = _yahoo_creds()
    if not user or not pw:
        print("Error: YAHOO_USER or YAHOO_APP_PASSWORD not set", file=sys.stderr)
        sys.exit(1)

    try:
        conn = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT)
        conn.login(user, pw)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    primary_folder = YAHOO_FOLDERS.get((folder or "inbox").lower(), folder or "Inbox")
    fallback_folders = [f for f in ["Inbox", "Sent", "Draft"] if f != primary_folder]

    try:
        conn.select(primary_folder, readonly=True)
        ok, data = conn.fetch(msg_id.encode(), "(BODY.PEEK[])")
        if ok != "OK" or not data or not data[0]:
            for fb in fallback_folders:
                conn.select(fb, readonly=True)
                ok, data = conn.fetch(msg_id.encode(), "(BODY.PEEK[])")
                if ok == "OK" and data and data[0]:
                    break
        if ok != "OK" or not data or not data[0]:
            conn.logout()
            print(f"Error: message {msg_id} not found", file=sys.stderr)
            sys.exit(1)

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        print(f"From: {_decode_header(msg.get('From', ''))}")
        print(f"To: {_decode_header(msg.get('To', ''))}")
        if msg.get("Cc"):
            print(f"Cc: {_decode_header(msg['Cc'])}")
        print(f"Subject: {_decode_header(msg.get('Subject', ''))}")
        print(f"Date: {msg.get('Date', '')}")
        print()

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        print(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
                    break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                print(payload.decode(msg.get_content_charset() or "utf-8", errors="replace"))

        conn.logout()
    except Exception as e:
        try:
            conn.logout()
        except Exception:
            pass
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# --------------- Himalaya for Gmail ---------------

def build_himalaya_query_args(args):
    """Return a list of CLI arguments for himalaya's positional query DSL."""
    parts = []
    if args.from_addr:
        parts += ["from", args.from_addr]
    if args.to_addr:
        parts += ["to", args.to_addr]
    if args.subject:
        parts += ["subject", args.subject]
    if args.body:
        parts += ["body", args.body]
    if args.after:
        parts += ["after", args.after]
    if args.before:
        parts += ["before", args.before]
    return parts


def run_gmail_search(args):
    query_args = build_himalaya_query_args(args)
    folder = GMAIL_FOLDERS.get((args.folder or "inbox").lower(), args.folder)
    page_size = str(args.page_size or 20)

    cmd = [HIMALAYA, "envelope", "list",
           "--account", "gmail",
           "--folder", folder,
           "--page-size", page_size]
    if query_args:
        cmd += query_args

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        if "UNAVAILABLE" in stderr or "Server error" in stderr:
            return None, "gmail: temporarily unavailable"
        return None, f"gmail: error — {stderr[:200]}"
    return stdout, None


def run_gmail_read(msg_id):
    cmd = [HIMALAYA, "message", "read", "--account", "gmail", msg_id]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"Error: {result.stderr[:300]}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout)


# --------------- CLI ---------------

def folder_label(account, alias):
    alias = (alias or "inbox").lower()
    if account == "gmail":
        return GMAIL_FOLDERS.get(alias, alias)
    return YAHOO_FOLDERS.get(alias, alias)


def main():
    parser = argparse.ArgumentParser(description="Search emails across Gmail and Yahoo")
    sub = parser.add_subparsers(dest="command")

    search_p = sub.add_parser("search", help="Search emails")
    search_p.add_argument("--from", dest="from_addr", help="Filter by sender")
    search_p.add_argument("--to", dest="to_addr", help="Filter by recipient")
    search_p.add_argument("--subject", help="Filter by subject")
    search_p.add_argument("--body", help="Filter by body text")
    search_p.add_argument("--after", help="Only after date (YYYY-MM-DD)")
    search_p.add_argument("--before", help="Only before date (YYYY-MM-DD)")
    search_p.add_argument("--account", choices=["gmail", "yahoo", "both"], default="both",
                          help="Which account (default: both)")
    search_p.add_argument("--folder", default="inbox",
                          help="Folder: inbox, sent, all, drafts, trash (default: inbox)")
    search_p.add_argument("--page-size", type=int, default=20, help="Max results (default: 20)")

    read_p = sub.add_parser("read", help="Read a specific email")
    read_p.add_argument("--account", choices=["gmail", "yahoo"], required=True)
    read_p.add_argument("--id", required=True, help="Email ID to read")
    read_p.add_argument("--folder", default="inbox",
                        help="Folder the message is in (default: inbox)")

    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        args = search_p.parse_args(sys.argv[1:])
        args.command = "search"
    else:
        args = parser.parse_args()

    if args.command == "read":
        if args.account == "yahoo":
            _yahoo_read(args.id, getattr(args, "folder", None))
        else:
            run_gmail_read(args.id)
        return

    accounts = []
    if args.account in ("both", "gmail"):
        accounts.append("gmail")
    if args.account in ("both", "yahoo"):
        accounts.append("yahoo")

    for acct in accounts:
        if acct == "gmail":
            output, err = run_gmail_search(args)
        else:
            output, err = _yahoo_search(args)

        if err:
            print(f"[{acct}] {err}")
        elif output:
            header = f"[{acct}] ({folder_label(acct, args.folder)})"
            print(header)
            print(output)
        else:
            print(f"[{acct}] No results")
        print()


if __name__ == "__main__":
    main()
