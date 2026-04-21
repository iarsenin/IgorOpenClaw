#!/usr/bin/env python3
"""Vapi AI phone call helper for OpenClaw agent.

Task instructions should include callback authorization lines when relevant:
    Owner authorizes leaving callback number: YES
    Callback to provide: +1...
  or: Owner authorizes leaving callback number: NO
See config/riley-voice-behavior.md and workspace/TOOLS.md.

Usage:
    vapi-call.py call <number> <task_instructions>   Make an outbound call
    vapi-call.py status <call_id>                    Check call status/transcript
    vapi-call.py list [--limit N]                    List recent calls
    vapi-call.py inbound-check                       Check for new inbound calls (for cron)

Environment variables (from .env):
    VAPI_API_KEY          Private API key
    VAPI_ASSISTANT_ID     Default assistant ID
    VAPI_PHONE_NUMBER_ID  Outbound phone number ID
"""

import json
import os
import ssl
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.vapi.ai"

# Appended to every outbound call's assistantOverrides system message (see
# config/riley-voice-behavior.md — keep in sync).
OUTBOUND_VOICE_RULES = """
VOICEMAIL / IVR (outbound calls):
- If you detect voicemail or a prompt-only greeting asking you to leave a message (beep, "leave a message", "at the tone", etc.), switch to voicemail mode.
- Leave a VERY short message (aim under ~20 seconds): identify yourself as Riley, Igor Arsenin's assistant; one sentence on why you're calling (from the task).
- Callback number: ONLY if the TASK FOR THIS CALL section above includes the exact line "Owner authorizes leaving callback number: YES" and a following line starting with "Callback to provide:", then speak that number slowly and clearly at the end (group digits for clarity).
- If the task includes "Owner authorizes leaving callback number: NO" or omits the YES line, do NOT speak any phone number on voicemail; end politely (e.g. Igor will follow up) without reciting a number.
- With a live human, follow the task; do not volunteer Igor's personal number unless the task authorizes it with the YES line and "Callback to provide:" line.

Never commit to payments or final decisions. Follow your base system prompt for tone and inbound rules.
""".strip()


def get_env(key):
    val = os.environ.get(key)
    if not val:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key}="):
                        val = line.split("=", 1)[1]
                        break
    if not val:
        print(f"ERROR: {key} not set in environment or .env", file=sys.stderr)
        sys.exit(1)
    return val


def _ssl_context():
    """Build an SSL context using certifi, falling back to macOS system keychain."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class VapiError(RuntimeError):
    """Raised when a Vapi API call fails."""


def api_request(method, path, data=None):
    api_key = get_env("VAPI_API_KEY")
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenClaw/1.0",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise VapiError(f"API returned {e.code}: {error_body[:200]}")
    except urllib.error.URLError as e:
        raise VapiError(f"Network error: {e.reason}")


def cmd_call(number, task_instructions):
    """Make an outbound call with task-specific instructions."""
    assistant_id = get_env("VAPI_ASSISTANT_ID")
    phone_number_id = get_env("VAPI_PHONE_NUMBER_ID")

    number = number.strip()
    if not number.startswith("+"):
        number = f"+1{number}" if len(number) == 10 else f"+{number}"

    first_sentence = task_instructions.split(".")[0].strip()

    payload = {
        "assistantId": assistant_id,
        "assistantOverrides": {
            "firstMessage": f"Hi, I'm calling on behalf of Igor Arsenin. {first_sentence}.",
            "model": {
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"TASK FOR THIS CALL:\n{task_instructions}\n\n"
                            f"{OUTBOUND_VOICE_RULES}\n\n"
                            "Follow your base system prompt rules. Never commit to payments or final decisions."
                        )
                    }
                ]
            }
        },
        "phoneNumberId": phone_number_id,
        "customer": {
            "number": number
        }
    }

    try:
        result = api_request("POST", "/call", payload)
    except VapiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    call_id = result.get("id", "unknown")
    status = result.get("status", "unknown")

    _add_pending(call_id, number)

    print(f"Call initiated!")
    print(f"  Call ID: {call_id}")
    print(f"  Status: {status}")
    print(f"  To: {number}")
    print(f"\nCall will be tracked automatically. The next inbound-check cycle will report the outcome.")
    return call_id


def cmd_status(call_id):
    """Get call status, transcript, and structured output."""
    try:
        result = api_request("GET", f"/call/{call_id}")
    except VapiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    status = result.get("status", "unknown")
    duration = result.get("duration")
    ended_reason = result.get("endedReason", "")
    transcript = result.get("transcript", "")
    analysis = result.get("analysis", {})
    structured = analysis.get("structuredData", {})
    summary = analysis.get("summary", "")
    cost = result.get("cost")
    recording_url = result.get("recordingUrl")

    print(f"Call ID: {call_id}")
    print(f"Status: {status}")
    if duration:
        print(f"Duration: {duration}s ({duration/60:.1f} min)")
    if ended_reason:
        print(f"Ended: {ended_reason}")
    if cost:
        print(f"Cost: ${cost:.4f}")
    if recording_url:
        print(f"Recording: {recording_url}")

    if summary:
        print(f"\n--- Summary ---\n{summary}")

    if structured:
        print(f"\n--- Structured Output ---")
        for key, val in structured.items():
            print(f"  {key}: {val}")

    if transcript:
        print(f"\n--- Transcript ---\n{transcript}")
    elif result.get("messages"):
        print(f"\n--- Transcript ---")
        for msg in result["messages"]:
            role = msg.get("role", "?")
            text = msg.get("message") or msg.get("content", "")
            if text:
                label = "Riley" if role in ("assistant", "bot") else "Caller"
                print(f"  [{label}]: {text}")


def cmd_list(limit=10):
    """List recent calls."""
    try:
        result = api_request("GET", f"/call?limit={limit}")
    except VapiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not result:
        print("No calls found.")
        return

    calls = result if isinstance(result, list) else result.get("results", result.get("data", []))

    print(f"{'ID':<40} {'Status':<12} {'To':<16} {'Duration':>8}  {'Cost':>8}")
    print("-" * 90)
    for call in calls[:limit]:
        cid = call.get("id", "?")[:38]
        status = call.get("status", "?")
        customer = call.get("customer", {})
        to_num = customer.get("number", "?") if isinstance(customer, dict) else "?"
        dur = call.get("duration")
        dur_str = f"{dur}s" if dur else "-"
        cost = call.get("cost")
        cost_str = f"${cost:.4f}" if cost else "-"
        print(f"{cid:<40} {status:<12} {to_num:<16} {dur_str:>8}  {cost_str:>8}")


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Runtime state must live outside the Google Drive–synced repo, otherwise the
# Drive daemon can return EDEADLK (Errno 11 "Resource deadlock avoided") while
# it syncs the file and crons then fail. ~/.openclaw/state/ is local-only.
_STATE_DIR = os.path.join(os.path.expanduser("~"), ".openclaw", "state")
os.makedirs(_STATE_DIR, exist_ok=True)

SEEN_FILE = os.path.join(_STATE_DIR, "vapi-seen-calls")
PENDING_FILE = os.path.join(_STATE_DIR, "vapi-pending-outbound")

# One-time migration: copy legacy repo-root state into ~/.openclaw/state/
for _legacy_name, _dest in (
    (".vapi-seen-calls", SEEN_FILE),
    (".vapi-pending-outbound", PENDING_FILE),
):
    _legacy = os.path.join(_REPO_ROOT, _legacy_name)
    if os.path.exists(_legacy) and not os.path.exists(_dest):
        try:
            with open(_legacy, "rb") as _src, open(_dest, "wb") as _dst:
                _dst.write(_src.read())
        except OSError:
            pass


def _load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    return set()


MAX_SEEN = 200


def _save_seen(seen):
    entries = sorted(seen)
    if len(entries) > MAX_SEEN:
        entries = entries[-MAX_SEEN:]
    with open(SEEN_FILE, "w") as f:
        for cid in entries:
            f.write(cid + "\n")


def _add_pending(call_id, to_number):
    """Track an outbound call that needs follow-up."""
    entry = {
        "call_id": call_id,
        "to_number": to_number,
        "failures": 0,
        "last_error": "",
    }
    with open(PENDING_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_pending():
    """Return pending outbound call entries (supports legacy line format)."""
    if not os.path.exists(PENDING_FILE):
        return []
    entries = []
    with open(PENDING_FILE) as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith("{"):
                try:
                    item = json.loads(raw)
                    entries.append({
                        "call_id": item.get("call_id", ""),
                        "to_number": item.get("to_number", "?"),
                        "failures": int(item.get("failures", 0) or 0),
                        "last_error": str(item.get("last_error", "") or ""),
                    })
                    continue
                except Exception:
                    pass
            # Legacy compatibility: "<call_id> <to_number>"
            parts = raw.split(None, 1)
            if not parts:
                continue
            entries.append({
                "call_id": parts[0],
                "to_number": parts[1] if len(parts) > 1 else "?",
                "failures": 0,
                "last_error": "",
            })
    return entries


def _save_pending(entries):
    with open(PENDING_FILE, "w") as f:
        for e in entries:
            f.write(json.dumps({
                "call_id": e.get("call_id", ""),
                "to_number": e.get("to_number", "?"),
                "failures": int(e.get("failures", 0) or 0),
                "last_error": str(e.get("last_error", "") or "")[:160],
            }) + "\n")


def cmd_inbound_check():
    """Check for new inbound calls AND completed outbound calls pending report."""
    try:
        result = api_request("GET", "/call?limit=20")
    except VapiError as e:
        print(f"ERROR: Cannot reach Vapi API: {e}", file=sys.stderr)
        sys.exit(1)
    calls = result if isinstance(result, list) else result.get("results", result.get("data", []))

    has_output = False

    # --- Inbound calls ---
    seen = _load_seen()
    new_inbound = []

    for call in calls:
        cid = call.get("id", "")
        call_type = call.get("type", "")
        status = call.get("status", "")

        if call_type != "inboundPhoneCall":
            continue
        if status not in ("ended",):
            continue
        if cid in seen:
            continue

        new_inbound.append(call)
        seen.add(cid)

    if new_inbound:
        has_output = True
        print(f"ALERT: NEW INBOUND CALLS: {len(new_inbound)}\n")
        for call in new_inbound:
            cid = call.get("id", "?")
            customer = call.get("customer", {})
            caller_num = customer.get("number", "unknown") if isinstance(customer, dict) else "unknown"
            duration = call.get("duration")
            analysis = call.get("analysis", {})
            summary = analysis.get("summary", "")
            structured = analysis.get("structuredData", {})

            print(f"  Call ID: {cid}")
            print(f"  From: {caller_num}")
            if duration:
                print(f"  Duration: {duration}s")
            if summary:
                print(f"  Summary: {summary}")
            if structured:
                for key, val in structured.items():
                    print(f"  {key}: {val}")
            print()

    _save_seen(seen)

    # --- Pending outbound calls ---
    pending = _load_pending()
    still_pending = []

    for p in pending:
        cid = p.get("call_id", "")
        to_num = p.get("to_number", "?")
        failures = int(p.get("failures", 0) or 0)
        try:
            call_data = api_request("GET", f"/call/{cid}")
        except VapiError as e:
            failures += 1
            last_error = str(e)
            still_pending.append({
                "call_id": cid,
                "to_number": to_num,
                "failures": failures,
                "last_error": last_error,
            })
            if failures >= 3:
                has_output = True
                print("ALERT: PENDING OUTBOUND CALL CHECK FAILING")
                print(f"  Call ID: {cid}")
                print(f"  To: {to_num}")
                print(f"  Consecutive status-check failures: {failures}")
                print(f"  Last error: {last_error[:180]}")
                print("  Action: check Vapi/API connectivity; call will remain pending.")
                print()
            continue

        status = call_data.get("status", "unknown")
        if status not in ("ended",):
            still_pending.append({
                "call_id": cid,
                "to_number": to_num,
                "failures": 0,
                "last_error": "",
            })
            continue

        has_output = True
        duration = call_data.get("duration")
        ended_reason = call_data.get("endedReason", "")
        analysis = call_data.get("analysis", {})
        summary = analysis.get("summary", "")
        transcript = call_data.get("transcript", "")
        cost = call_data.get("cost")

        print(f"ALERT: COMPLETED OUTBOUND CALL:")
        print(f"  Call ID: {cid}")
        print(f"  To: {to_num}")
        if duration:
            print(f"  Duration: {duration}s ({duration/60:.1f} min)")
        if ended_reason:
            print(f"  Ended: {ended_reason}")
        if cost:
            print(f"  Cost: ${cost:.4f}")
        if summary:
            print(f"  Summary: {summary}")
        if transcript:
            print(f"  Transcript: {transcript[:500]}")
        elif call_data.get("messages"):
            lines = []
            for msg in call_data["messages"]:
                role = msg.get("role", "?")
                text = msg.get("message") or msg.get("content", "")
                if text:
                    label = "Riley" if role in ("assistant", "bot") else "Caller"
                    lines.append(f"    [{label}]: {text}")
            if lines:
                print(f"  Transcript:\n" + "\n".join(lines[:20]))
        print()

    _save_pending(still_pending)

    if not has_output:
        return


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "call":
        if len(sys.argv) < 4:
            print("Usage: vapi-call.py call <number> <task_instructions>")
            print('Example: vapi-call.py call "+12125551234" "Schedule a fridge repair estimate for Tuesday"')
            sys.exit(1)
        cmd_call(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "status":
        if len(sys.argv) < 3:
            print("Usage: vapi-call.py status <call_id>")
            sys.exit(1)
        cmd_status(sys.argv[2])
    elif cmd == "list":
        limit = 10
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 >= len(sys.argv):
                print("ERROR: --limit requires a numeric argument", file=sys.stderr)
                sys.exit(1)
            try:
                limit = int(sys.argv[idx + 1])
            except ValueError:
                print(f"ERROR: --limit value must be an integer, got: {sys.argv[idx + 1]}", file=sys.stderr)
                sys.exit(1)
        cmd_list(limit)
    elif cmd == "inbound-check":
        cmd_inbound_check()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
