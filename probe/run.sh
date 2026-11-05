#!/usr/bin/env bash
# Run a probe in the Workshop and push its result back to this branch. usage: probe/run.sh k1
set -u
n=$1; cd /workshop/Treehouse && git fetch -q origin lead/k1-probe
rm -rf /tmp/probewt; git worktree prune; git worktree add -q -f /tmp/probewt origin/lead/k1-probe || exit 1
cd /tmp/probewt && git checkout -q -B lead/k1-probe origin/lead/k1-probe
(cd /workshop/Treehouse && timeout 900 uv run python /tmp/probewt/probe/$n.py) > probe/$n.result.json 2> probe/$n.stderr.txt
sed -i -E 's/\b[0-9]{12}\b/<acct>/g' probe/$n.result.json probe/$n.stderr.txt
git add probe && git commit -qm "probe $n result (Workshop)" && git push -q origin lead/k1-probe && echo "PUSHED $n"
