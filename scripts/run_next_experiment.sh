#!/bin/bash
# run_next_experiment.sh — not_executed → executing → done/failed
# 決定論的。Claude不要、トークン消費ゼロ。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 1. Pick next executable job
EXP_ID=$(python -m src.tools_for_skills.job_queue pick-next)

if [ "$EXP_ID" = "実行可能なジョブなし" ]; then
    echo "[runner] No jobs to run"
    exit 0
fi

echo "[runner] Starting: $EXP_ID"

# 2. Transition to executing
python -m src.tools_for_skills.job_queue transition "$EXP_ID" executing

# 3. Run the experiment
if bash "experiments/$EXP_ID/run.sh"; then
    python -m src.tools_for_skills.job_queue transition "$EXP_ID" done
    echo "[runner] $EXP_ID → done"
else
    python -m src.tools_for_skills.job_queue transition "$EXP_ID" failed
    echo "[runner] $EXP_ID → failed"
fi
