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
from datetime import datetime, timedelta, timezone

issues = []

# WhatsApp: only alert if restores are still happening recently (not stale all-day totals)
_WHATSAPP_CREDS_RECENT_WINDOW = timedelta(hours=2)
_WHATSAPP_CREDS_RECENT_THRESHOLD = 5
_WHATSAPP_499_RECENT_WINDOW = timedelta(hours=2)
_WHATSAPP_499_RECENT_THRESHOLD = 12
_BROWSER_NO_PAGES_WINDOW = timedelta(hours=3)
_BROWSER_NO_PAGES_THRESHOLD = 3
_RECENT_ERROR_WINDOW = timedelta(hours=1)
_RECENT_ERROR_THRESHOLD = 10


def check_gateway():
    try:
        r = subprocess.run(["openclaw", "gateway", "status"],
                           capture_output=True, text=True, timeout=30)
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
        now = datetime.now().astimezone()
        rolling_cutoff = now - _RECENT_ERROR_WINDOW
        session_start = _latest_gateway_start_time(log_path)
        cutoff = rolling_cutoff
        if session_start is not None and session_start > cutoff:
            cutoff = session_start
        total_today = 0
        recent = 0

        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"logLevelName":"ERROR"' not in line:
                    continue
                if (
                    "connection closed" in line
                    or "Retry " in line
                    or "punycode" in line
                    or "DeprecationWarning" in line
                    or "gateway closed" in line
                    or "No pages available" in line
                    or "status 499" in line
                    or "WhatsApp Web connection closed" in line
                    or "QR refs attempts ended" in line
                    or "Channel login failed" in line
                ):
                    continue

                total_today += 1
                try:
                    obj = json.loads(line)
                    ts = obj.get("time")
                    if not ts:
                        continue
                    ev = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ev.tzinfo is None:
                        ev = ev.replace(tzinfo=timezone.utc)
                    if ev >= cutoff:
                        recent += 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        if recent > _RECENT_ERROR_THRESHOLD:
            if cutoff == rolling_cutoff:
                scope = f"in the last {int(_RECENT_ERROR_WINDOW.total_seconds() // 3600)}h"
            else:
                scope = "since the latest gateway restart"
            issues.append(
                f"High error count {scope}: "
                f"{recent} non-transient ERROR entries ({total_today} total today)."
            )
    except Exception:
        pass


def _count_recent_log_events(log_path, needle, window, latest_start_cutoff=False):
    """Count occurrences of `needle` in log JSON lines within rolling window.

    When `latest_start_cutoff` is true, ignore events that predate the most
    recent gateway listener startup so restart churn does not look like an
    active loop in the current session.
    """
    now = datetime.now().astimezone()
    cutoff = now - window
    if latest_start_cutoff:
        session_start = _latest_gateway_start_time(log_path)
        if session_start is not None and session_start > cutoff:
            cutoff = session_start
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
                    ev = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ev.tzinfo is None:
                        ev = ev.replace(tzinfo=timezone.utc)
                    if ev >= cutoff:
                        recent += 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    except OSError:
        return 0, 0
    return recent, total


def _latest_gateway_start_time(log_path):
    """Best-effort timestamp of the latest gateway listener startup in today's log."""
    latest = None
    startup_markers = (
        '"listening on ws://',
        '"ready (',
        '"Browser control listening on http://127.0.0.1:18791/',
        '"cron: started"',
    )
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not any(marker in line for marker in startup_markers):
                    continue
                try:
                    obj = json.loads(line)
                    ts = obj.get("time")
                    if not ts:
                        continue
                    ev = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ev.tzinfo is None:
                        ev = ev.replace(tzinfo=timezone.utc)
                    if latest is None or ev > latest:
                        latest = ev
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    except OSError:
        return None
    return latest


def check_whatsapp_creds_corruption():
    """Alert only if creds restores cluster in the recent window (avoids all-day stale totals)."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        return
    needle = "restored corrupted WhatsApp creds"
    recent, total = _count_recent_log_events(
        log_path,
        needle,
        _WHATSAPP_CREDS_RECENT_WINDOW,
        latest_start_cutoff=True,
    )

    if recent >= _WHATSAPP_CREDS_RECENT_THRESHOLD:
        issues.append(
            "WhatsApp creds.json restore loop in the last "
            f"{int(_WHATSAPP_CREDS_RECENT_WINDOW.total_seconds() // 3600)}h: "
            f"{recent} events (also {total} total today in log). Re-pair WhatsApp "
            "(`openclaw channels add --channel whatsapp`) and ensure only one "
            "gateway instance is running."
        )


def check_whatsapp_disconnect_storm():
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        return
    needle = "WhatsApp Web connection closed (status 499)"
    recent, total = _count_recent_log_events(log_path, needle, _WHATSAPP_499_RECENT_WINDOW)
    if recent >= _WHATSAPP_499_RECENT_THRESHOLD:
        issues.append(
            "WhatsApp disconnect storm in the last "
            f"{int(_WHATSAPP_499_RECENT_WINDOW.total_seconds() // 3600)}h: "
            f"{recent} status-499 events ({total} total today)."
        )


def check_browser_no_pages_loop():
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"/tmp/openclaw/openclaw-{today}.log"
    if not os.path.exists(log_path):
        return
    needle = "No pages available in the connected browser"
    recent, total = _count_recent_log_events(
        log_path,
        needle,
        _BROWSER_NO_PAGES_WINDOW,
        latest_start_cutoff=True,
    )
    if recent >= _BROWSER_NO_PAGES_THRESHOLD:
        issues.append(
            "Browser 'No pages available' repeated in the last "
            f"{int(_BROWSER_NO_PAGES_WINDOW.total_seconds() // 3600)}h: "
            f"{recent} events ({total} total today)."
        )


def check_cron_jobs_binding():
    """Validate live cron jobs exist and still contain the repo's expected job ids."""
    expected = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "cron", "jobs.json")
    live = os.path.expanduser("~/.openclaw/cron/jobs.json")
    if not os.path.exists(live):
        issues.append("Live cron config missing: ~/.openclaw/cron/jobs.json")
        return
    try:
        with open(expected, "r", encoding="utf-8") as fh:
            expected_job_ids = {job["id"] for job in json.load(fh).get("jobs", [])}
        with open(live, "r", encoding="utf-8") as fh:
            live_job_ids = {job["id"] for job in json.load(fh).get("jobs", [])}
    except Exception as exc:
        issues.append(f"Unable to parse cron job config: {exc}")
        return
    missing = sorted(expected_job_ids - live_job_ids)
    if missing:
        issues.append("Live cron config missing expected jobs: " + ", ".join(missing))


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
    check_whatsapp_disconnect_storm()
    check_browser_no_pages_loop()
    check_cron_jobs_binding()
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
