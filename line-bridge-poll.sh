#!/usr/bin/env bash
# Hook polling script for the LINE bridge.
# Runs poll.py; if new events were queued, wakes the agent with their payload.
# Place at ~/hooks/scripts/line-bridge-poll.sh and register a hook that points
# here (see README.md, Phase 6). BRIDGE_DIR defaults to ~/workspace/line-bridge.
set -euo pipefail
source "$HATCH_HOOK_RUNTIME"

BRIDGE_DIR="${LINE_BRIDGE_DIR:-$HOME/workspace/line-bridge}"

# Dry runs must not consume real events from the Worker queue.
if [ "${HATCH_HOOK_DRY_RUN:-0}" = "1" ]; then
  silent "dry run: poll skipped" '{}'
  exit 0
fi

OUT="$(python3 "$BRIDGE_DIR/poll.py" 2>/tmp/line-poll.err || true)"
if ! printf '%s' "$OUT" | grep -qE '^[0-9]+$'; then
  log "poll failed" "$(jq -nc --arg e "$(tail -c 300 /tmp/line-poll.err 2>/dev/null || echo unknown)" '{error:$e}')"
  silent "poll error" '{}'
  exit 0
fi

if [ "$OUT" = "0" ]; then
  silent "no new events" '{}'
  exit 0
fi

PAYLOAD="$(BRIDGE_DIR="$BRIDGE_DIR" python3 - "$OUT" <<'PYEOF'
import json, os, sys
n = int(sys.argv[1])
queue = os.path.join(os.environ['BRIDGE_DIR'], 'state', 'queue.jsonl')
lines = open(queue).read().splitlines()[-n:]
events = []
for line in lines:
    d = json.loads(line)
    e = d.get('event', {})
    item = {
        'type': e.get('type'),
        'userId': (e.get('source') or {}).get('userId'),
        'replyToken': e.get('replyToken'),
        'timestamp': e.get('timestamp'),
    }
    msg = e.get('message') or {}
    if msg:
        item['messageType'] = msg.get('type')
        item['text'] = msg.get('text')
    events.append(item)
print(json.dumps({'events': events}, ensure_ascii=False))
PYEOF
)"
log "new events" "$PAYLOAD"
wake "New LINE events: ${OUT}" "$PAYLOAD"
