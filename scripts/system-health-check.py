#!/usr/bin/env python3
"""System health check for OpenClaw gateway.

Checks gateway status, disk space, and recent error logs.
Outputs ALERT lines only if something needs attention.
Produces no output if everything is fine (silent success).
"""

import os
import shutil
import subprocess
from datetime import datetime

issues = []


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
    """Detect repeated creds.json restore — log evidence: web-session WARN spam."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        return 0
    try:
        needle = "restored corrupted WhatsApp creds"
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            n = sum(1 for line in f if needle in line)
        if n >= 5:
            issues.append(
                "WhatsApp creds.json was restored from backup many times today ("
                f"{n} occurrences in log). Session is unstable — re-pair WhatsApp "
                "(`openclaw channels add --channel whatsapp`) and ensure only one "
                "gateway instance is running."
            )
        return n
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0


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


if __name__ == "__main__":
    main()
