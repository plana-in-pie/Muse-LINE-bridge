#!/usr/bin/env python3
"""Poll the LINE bridge Worker for queued webhook events.

GET {WORKER_URL}/pending (Bearer POLL_KEY) -> append each event payload as a
JSON line to state/queue.jsonl -> POST /ack.

WORKER_URL is read from state/worker-url.txt (one line, set after deploy).
POLL_KEY is read from ~/.config/line-bridge/secrets.env.
Prints the number of newly queued events; exit 0 always on HTTP success.
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
QUEUE = STATE / "queue.jsonl"
SECRETS = Path.home() / ".config" / "line-bridge" / "secrets.env"
USER_AGENT = "muse-line-bridge/1.0"


def load_env_file(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    url_file = STATE / "worker-url.txt"
    if not url_file.exists():
        print("worker-url.txt not set", file=sys.stderr)
        return 1
    worker_url = url_file.read_text().strip().rstrip("/")
    poll_key = load_env_file(SECRETS).get("POLL_KEY", "")
    if not poll_key:
        print("POLL_KEY missing in secrets.env", file=sys.stderr)
        return 1

    req = urllib.request.Request(
        worker_url + "/pending",
        headers={
            "Authorization": f"Bearer {poll_key}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    items = data.get("items", [])
    if not items:
        print(0)
        return 0

    STATE.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("a") as f:
        for item in items:
            f.write(json.dumps(item["payload"], ensure_ascii=False) + "\n")

    ack = urllib.request.Request(
        worker_url + "/ack",
        data=json.dumps({"ids": [i["id"] for i in items]}).encode(),
        headers={
            "Authorization": f"Bearer {poll_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(ack, timeout=30) as resp:
        resp.read()
    print(len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
