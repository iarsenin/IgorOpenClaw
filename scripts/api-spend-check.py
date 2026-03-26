#!/usr/bin/env python3
"""Daily API spend report: OpenAI, Vapi, Cursor plan status.

Usage:
    python3 scripts/api-spend-check.py

Reads credentials from .env (OPENAI_ADMIN_KEY, VAPI_API_KEY).
Reads Cursor token from local Cursor SQLite.
Prints a short plaintext summary to stdout.
"""

import json
import os
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO, ".env")


# ── Credentials ──────────────────────────────────────────────────────────────

def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    # env vars override file
    for k in list(env.keys()):
        env[k] = os.environ.get(k, env[k])
    return env


def ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(url, headers, ctx, timeout=30):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:200]}")


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _sum_costs(cost_data):
    return sum(
        float((r.get("amount") or {}).get("value", 0))
        for b in cost_data.get("data", [])
        for r in b.get("results", [])
    )


def openai_spend(admin_key, ctx):
    """Return (yesterday_total, prev_day_total, mtd_total, model_str)."""
    hdrs = {"Authorization": f"Bearer {admin_key}"}
    now = datetime.now(timezone.utc)
    today_midnight = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    yesterday_midnight = today_midnight - 86400
    prev_day_midnight = yesterday_midnight - 86400
    month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())

    yesterday_costs = fetch(
        f"https://api.openai.com/v1/organization/costs"
        f"?start_time={yesterday_midnight}&end_time={today_midnight}&limit=100",
        hdrs, ctx)
    prev_day_costs = fetch(
        f"https://api.openai.com/v1/organization/costs"
        f"?start_time={prev_day_midnight}&end_time={yesterday_midnight}&limit=100",
        hdrs, ctx)
    mtd_costs = fetch(
        f"https://api.openai.com/v1/organization/costs"
        f"?start_time={month_start}&end_time={today_midnight}&limit=100",
        hdrs, ctx)

    yesterday_total = _sum_costs(yesterday_costs)
    prev_day_total = _sum_costs(prev_day_costs)
    mtd_total = _sum_costs(mtd_costs)

    usage_data = fetch(
        f"https://api.openai.com/v1/organization/usage/completions"
        f"?start_time={yesterday_midnight}&end_time={today_midnight}"
        f"&bucket_width=1d&group_by=model&limit=31",
        hdrs, ctx)
    by_model = {}
    for b in usage_data.get("data", []):
        for r in b.get("results", []):
            m = r.get("model") or "unknown"
            by_model[m] = (
                by_model.get(m, (0, 0))[0] + (r.get("input_tokens") or 0),
                by_model.get(m, (0, 0))[1] + (r.get("output_tokens") or 0),
            )

    model_str = ", ".join(
        f"{m}: {round(i/1000)}k in/{round(o/1000)}k out"
        for m, (i, o) in sorted(by_model.items(), key=lambda x: -(x[1][0] + x[1][1]))
    ) or "no model detail"

    return yesterday_total, prev_day_total, mtd_total, model_str


# ── Vapi ──────────────────────────────────────────────────────────────────────

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def vapi_spend(api_key, ctx):
    calls = fetch(
        "https://api.vapi.ai/call?limit=100",
        {"Authorization": f"Bearer {api_key}", "User-Agent": BROWSER_UA}, ctx)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    total = 0.0
    count = 0
    for c in (calls if isinstance(calls, list) else []):
        ts_str = c.get("startedAt") or c.get("createdAt", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= cutoff:
            total += float(c.get("cost") or 0)
            count += 1
    return total, count


# ── Cursor ────────────────────────────────────────────────────────────────────

def cursor_status(ctx):
    db_path = os.path.expanduser(
        "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    )
    if not os.path.exists(db_path):
        return None, None, False, None
    db = sqlite3.connect(db_path)
    try:
        row = db.execute(
            "SELECT value FROM ItemTable WHERE key='cursorAuth/accessToken'"
        ).fetchone()
    finally:
        db.close()
    if not row:
        return None, None, False, None
    token = row[0]

    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(
        "https://api2.cursor.sh/auth/full_stripe_profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    with opener.open(req, timeout=8) as r:
        cp = json.loads(r.read())

    plan     = cp.get("individualMembershipType") or cp.get("membershipType", "?")
    status   = cp.get("subscriptionStatus", "?")
    failed   = cp.get("lastPaymentFailed", False)
    cancels  = cp.get("pendingCancellationDate")
    return plan, status, failed, cancels


# ── Main ──────────────────────────────────────────────────────────────────────

def _delta_str(current, previous):
    diff = current - previous
    if diff == 0:
        return "flat"
    sign = "+" if diff > 0 else ""
    return f"{sign}${diff:.2f}"


def main():
    env = load_env()
    ctx = ssl_ctx()

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime("%b %-d")

    lines = [f"💰 API Spend Report"]

    oai_yesterday = 0.0
    vapi_yesterday = 0.0

    # OpenAI
    admin_key = env.get("OPENAI_ADMIN_KEY", "")
    if admin_key:
        try:
            yday, prev, mtd, models = openai_spend(admin_key, ctx)
            oai_yesterday = yday
            lines.append(
                f"OpenAI yesterday ({yesterday}): ${yday:.2f}"
                f"  ({_delta_str(yday, prev)} vs prior day)"
            )
            lines.append(f"  MTD: ${mtd:.2f}  |  Models: {models}")
        except Exception as e:
            lines.append(f"OpenAI: fetch error ({e})")
    else:
        lines.append("OpenAI: OPENAI_ADMIN_KEY not set")

    # Vapi
    vapi_key = env.get("VAPI_API_KEY", "")
    if vapi_key:
        try:
            total, count = vapi_spend(vapi_key, ctx)
            vapi_yesterday = total
            lines.append(f"Vapi (last 24h): ${total:.2f}  ({count} call(s))")
        except Exception as e:
            lines.append(f"Vapi: fetch error ({e})")
    else:
        lines.append("Vapi: VAPI_API_KEY not set")

    # Cursor
    try:
        plan, status, failed, cancels = cursor_status(ctx)
        if plan:
            note = ""
            if failed:
                note = "  ⚠️ PAYMENT FAILED"
            elif cancels:
                note = f"  ⚠️ cancels {cancels[:10]}"
            lines.append(f"Cursor: {plan} / {status}{note}")
        else:
            lines.append("Cursor: token unavailable (open Cursor to refresh)")
    except Exception as e:
        lines.append(f"Cursor: fetch error ({e})")

    lines.append("Gemini: check GCP Console (no billing API via key)")

    total = oai_yesterday + vapi_yesterday
    if total > 0:
        lines.append(f"Total yesterday (OpenAI+Vapi): ${total:.2f}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
