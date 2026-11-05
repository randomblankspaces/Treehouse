#!/usr/bin/env bash
# Live real-data runs in the Workshop. usage: RUNS="1 2" MODEL=claude-sonnet-5-5 TAG=sonnet bash live1.sh
set -u
cd /workshop/Treehouse
GIT_TERMINAL_PROMPT=0 git pull -q --ff-only https://github.com/randomblankspaces/Treehouse.git main || { echo PULL-FAIL; exit 1; }
uv sync -q --locked --all-extras || { echo SYNC-FAIL; exit 1; }
uv run treehouse budget status >/tmp/budget.txt 2>&1; rc=$?; tail -3 /tmp/budget.txt; [ $rc -ge 2 ] && { echo BUDGET-STOP; exit 2; }
CARD=${CARD:-tasks/t1-nagoya-warehouses-real.yaml}; MODEL=${MODEL:-claude-sonnet-5-5}; TAG=${TAG:-sonnet}; NAME=${NAME:-nagoya-real}
mkdir -p out/live out/store
for i in ${RUNS:-1}; do
  id=live-$NAME-$TAG-$i
  [ -e out/live/$id.model.jsonl ] && { echo "SKIP $id exists"; continue; }
  uv run python scripts/make_live_config.py $CARD $MODEL strands --output out/live/$id.json || { echo CFG-FAIL; continue; }
  TREEHOUSE_CASSETTE_OUT=$PWD/out/live/$id.model.jsonl timeout 2400 uv run treehouse sandbox run --task $CARD \
    --config out/live/$id.json --provider treehouse.providers.factories:bedrock_recording --run-id $id --store out/store > out/live/$id.log 2>&1
  echo "RUN $id rc=$?"; tail -2 out/live/$id.log | cut -c1-200
  uv run python /tmp/summ.py out/store $id
done
uv run treehouse budget status 2>&1 | tail -3
