#!/usr/bin/env python3
"""LINE sender for the bridge: reply or push text messages via the Messaging API.

Usage:
  send.py reply <replyToken> <text> [text ...]
  send.py push  <userId>     <text> [text ...]
  send.py --dry-run reply <replyToken> <text> [text ...]

Multiple texts are batched into one request (max 5 message objects) to save the
free-plan push quota. The channel access token is read from
~/.config/line-bridge/secrets.env (mode 600); it is never printed.
"""
import json
import sys
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".config" / "line-bridge" / "secrets.env"
API = "https://api.line.me/v2/bot/message"


def load_token() -> str:
    if SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if line.startswith("LINE_CHANNEL_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    args = sys.argv[1:]
    dry_run = False
    if args and args[0] == "--dry-run":
        dry_run = True
        args = args[1:]
    if len(args) < 3 or args[0] not in ("reply", "push"):
        print(__doc__)
        return 2
    mode, target, texts = args[0], args[1], args[2:]
    if len(texts) > 5:
        print("too many messages in one request (max 5)", file=sys.stderr)
        return 2
    messages = [{"type": "text", "text": t} for t in texts]
    if mode == "reply":
        url = f"{API}/reply"
        payload = {"replyToken": target, "messages": messages}
    else:
        url = f"{API}/push"
        payload = {"to": target, "messages": messages}
    if dry_run:
        print(json.dumps({"url": url, "payload": payload}, ensure_ascii=False, indent=2))
        return 0
    token = load_token()
    if not token:
        print("LINE_CHANNEL_ACCESS_TOKEN not set in secrets.env", file=sys.stderr)
        return 1
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"sent: HTTP {resp.status}")
            return 0
    except urllib.error.HTTPError as e:
        print(f"failed: HTTP {e.code} {e.read().decode(errors='replace')[:300]}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
