#!/usr/bin/env bash
# One-command offline demo (no AWS, no network after install): replay the recorded live Bedrock runs for the
# Nagoya port warehouse task into a fresh sealed store, verify it, build the UI and serve it.
#   scripts/demo.sh                 # store out/demo/store, port 8790
#   STORE=out/x PORT=8800 scripts/demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
STORE=${STORE:-out/demo/store}
PORT=${PORT:-8790}

uv sync --locked --all-extras -q
if [ ! -d "$STORE/runs" ]; then   # replay refuses a store that already holds the run
  for run in exp-nagoya-sonnet-1 exp-nagoya-nova-1; do
    uv run python scripts/replay_live.py "$run" --store "$STORE"
  done
fi
uv run treehouse verify --store "$STORE"
[ -d ui/node_modules ] || npm --prefix ui ci
npm --prefix ui run build

echo
echo "Treehouse demo: http://127.0.0.1:$PORT/   (use 127.0.0.1; the server rejects other host names)"
echo "  Dev view:     http://127.0.0.1:$PORT/dev?run=exp-nagoya-nova-1"
echo
exec uv run --extra api treehouse ui serve --store "$STORE" --port "$PORT"
