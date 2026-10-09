#!/usr/bin/env python3
"""Install the separate /shrink queue worker without resetting gateway state."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
launch_agents = Path.home() / "Library/LaunchAgents"
logs = Path.home() / ".openclaw/logs"
launch_agents.mkdir(parents=True, exist_ok=True)
logs.mkdir(parents=True, exist_ok=True)
target = launch_agents / "ai.openclaw.shrink-worker.plist"
if target.exists():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], capture_output=True)
payload = {
    "Label": "ai.openclaw.shrink-worker",
    "ProgramArguments": [sys.executable, str(REPO / "scripts/shrink_original.py"), "worker-loop"],
    "WorkingDirectory": str(REPO),
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 20,
    "EnvironmentVariables": {
        "PATH": "/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "SHRINK_WORKER_MODE": "launchd",
    },
    "StandardOutPath": str(logs / "shrink-worker.out.log"),
    "StandardErrorPath": str(logs / "shrink-worker.err.log"),
}
with target.open("wb") as stream:
    plistlib.dump(payload, stream)
target.chmod(0o600)
subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=True)
print(f"Installed /shrink queue worker: {target}")
