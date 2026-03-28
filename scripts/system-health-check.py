#!/usr/bin/env python3
"""System health check for OpenClaw gateway.

Checks gateway status, disk space, and recent error logs.
Outputs ALERT lines only if something needs attention.
Produces no output if everything is fine (silent success).

Exit codes: 0 = healthy, 1 = one or more alerts (for scripts/automation).
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta

issues = []

# WhatsApp: only alert if restores are still happening recently (not stale all-day totals)
_WHATSAPP_CREDS_RECENT_WINDOW = timedelta(hours=2)
_WHATSAPP_CREDS_RECENT_THRESHOLD = 5


def check_gateway():
    try:
        r = subprocess.run(["openclaw", "gateway", "status"],
                           capture_output=True, text=True, timeout=10)
        output = r.stdout + r.stderr
        if "not loaded" in output.lower() or "not found" in output.lower():
            issues.append("Gateway LaunchAgent not loaded or not found")
        elif r.returncode != 0:
            issues.append(f"Gateway status check failed (exit {r.returncode})")
    except FileNotFoundError:
        issues.append("openclaw CLI not found in PATH")
    except subprocess.TimeoutExpired:
        issues.append("Gateway status check timed out")


def check_disk():
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024**3)
    pct_used = (usage.used / usage.total) * 100
    if free_gb < 10:
        issues.append(f"Low disk space: {free_gb:.0f} GB free ({pct_used:.0f}% used)")


def check_recent_errors():
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        issues.append("Today's log file missing")
        return

    try:
        r = subprocess.run(
            ["grep", '"logLevelName":"ERROR"', log_path],
            capture_output=True, text=True, timeout=15)
        lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
        real_errors = [
            l for l in lines
            if "connection closed" not in l
            and "Retry " not in l
            and "punycode" not in l
            and "DeprecationWarning" not in l
            and "gateway closed" not in l
            and "No pages available" not in l
            and "status 499" not in l
            and "WhatsApp Web connection closed" not in l
        ]
        if len(real_errors) > 10:
            issues.append(f"High error count in today's log: {len(real_errors)} non-transient ERROR entries")
    except Exception:
        pass


def check_whatsapp_creds_corruption():
    """Alert only if creds restores cluster in the recent window (avoids all-day stale totals)."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        return
    needle = "restored corrupted WhatsApp creds"
    now = datetime.now().astimezone()
    cutoff = now - _WHATSAPP_CREDS_RECENT_WINDOW
    recent = 0
    total = 0
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if needle not in line:
                    continue
                total += 1
                try:
                    obj = json.loads(line)
                    ts = obj.get("time")
                    if not ts:
                        continue
                    ev = datetime.fromisoformat(ts)
                    if ev >= cutoff:
                        recent += 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    except OSError:
        return

    if recent >= _WHATSAPP_CREDS_RECENT_THRESHOLD:
        issues.append(
            "WhatsApp creds.json restore loop in the last "
            f"{int(_WHATSAPP_CREDS_RECENT_WINDOW.total_seconds() // 3600)}h: "
            f"{recent} events (also {total} total today in log). Re-pair WhatsApp "
            "(`openclaw channels add --channel whatsapp`) and ensure only one "
            "gateway instance is running."
        )


def check_chrome_orphans():
    try:
        r = subprocess.run(
            ["pgrep", "-f", "openclaw/browser.*user-data"],
            capture_output=True, text=True, timeout=5)
        pids = [p for p in r.stdout.strip().split("\n") if p]
        if len(pids) > 10:
            issues.append(f"Possible Chrome orphan processes: {len(pids)} openclaw browser processes")
    except Exception:
        pass


def main():
    check_gateway()
    check_disk()
    check_whatsapp_creds_corruption()
    check_recent_errors()
    check_chrome_orphans()

    if issues:
        print("ALERT: System health issues detected:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
