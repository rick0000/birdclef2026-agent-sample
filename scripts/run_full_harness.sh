#!/bin/bash
# CLAUDE.md記載の本番構成（bash runner + 5つの/loop）を1つのtmux windowに6 paneでまとめて起動する。
#
# 使い方:
#   bash scripts/run_full_harness.sh                  # 本番値 (10m/10m/10m/30m, runner sleep 10s)
#   ANALYZE_INTERVAL=1m UPDATE_INTERVAL=1m \
#     PLAN_INTERVAL=1m WHOLE_REPORT_INTERVAL=2m \
#     RUNNER_SLEEP=10 \
#     bash scripts/run_full_harness.sh                # 検証用に短縮
#
#   tmux attach -t birdclef                           # アタッチ
#   ctrl-b o / ctrl-b 矢印                            # pane切替
#   ctrl-b z                                          # アクティブpane最大化/復帰
#   tmux kill-session -t birdclef                     # 全停止

set -euo pipefail

echo "起動中..."
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="${SESSION:-birdclef}"

ANALYZE_INTERVAL="${ANALYZE_INTERVAL:-10m}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-10m}"
PLAN_INTERVAL="${PLAN_INTERVAL:-10m}"
WHOLE_REPORT_INTERVAL="${WHOLE_REPORT_INTERVAL:-30m}"
DECIDE_SUBMISSION_INTERVAL="${DECIDE_SUBMISSION_INTERVAL:-6h}"
RUNNER_SLEEP="${RUNNER_SLEEP:-10}"
CLAUDE_BOOT_WAIT="${CLAUDE_BOOT_WAIT:-10}"

tmux kill-session -t "$SESSION" 2>/dev/null || true

# 1 window, 6 panes (tiled)
# split-windowは直前のpaneを分割するため、毎回tiledで再分配しないと
# 末端paneが縮みすぎて "no space for new pane" になる。
tmux new-session -d -s "$SESSION" -n "harness" -x "$(tput cols 2>/dev/null || echo 200)" -y "$(tput lines 2>/dev/null || echo 50)" -c "$PROJECT_ROOT"
for _ in 1 2 3 4 5; do
    tmux split-window -t "$SESSION:harness" -c "$PROJECT_ROOT"
    tmux select-layout -t "$SESSION:harness" tiled
done

# pane境界に名前を表示
tmux set-option -t "$SESSION:harness" pane-border-status top
tmux select-pane -t "$SESSION:harness.0" -T "runner"
tmux select-pane -t "$SESSION:harness.1" -T "analyze"
tmux select-pane -t "$SESSION:harness.2" -T "update"
tmux select-pane -t "$SESSION:harness.3" -T "whole-report"
tmux select-pane -t "$SESSION:harness.4" -T "plan"
tmux select-pane -t "$SESSION:harness.5" -T "notebook"

# pane 0: bash runner
tmux send-keys -t "$SESSION:harness.0" \
  "while true; do bash scripts/run_next_experiment.sh; sleep $RUNNER_SLEEP; done" Enter

# pane 1-5: claudeを並列で起動
for pane in 1 2 3 4 5; do
    tmux send-keys -t "$SESSION:harness.$pane" "claude" Enter
done
sleep "$CLAUDE_BOOT_WAIT"

# 各paneに /loop を送信
tmux send-keys -t "$SESSION:harness.1" "/loop $ANALYZE_INTERVAL /analyze-results" Enter
tmux send-keys -t "$SESSION:harness.2" "/loop $UPDATE_INTERVAL /update-knowledge" Enter
tmux send-keys -t "$SESSION:harness.3" "/loop $WHOLE_REPORT_INTERVAL /cron-update-whole-report" Enter
tmux send-keys -t "$SESSION:harness.4" "/loop $PLAN_INTERVAL /plan-next" Enter
tmux send-keys -t "$SESSION:harness.5" "/loop $DECIDE_SUBMISSION_INTERVAL /decide-submission" Enter

cat <<EOF

tmux session '$SESSION' を起動しました（1 window, 6 panes / tiled）。

  panes:
    0: runner        (bash run_next_experiment.sh ループ, sleep ${RUNNER_SLEEP}s)
    1: analyze       (/loop $ANALYZE_INTERVAL /analyze-results)
    2: update        (/loop $UPDATE_INTERVAL /update-knowledge)
    3: whole-report  (/loop $WHOLE_REPORT_INTERVAL /cron-update-whole-report)
    4: plan          (/loop $PLAN_INTERVAL /plan-next)
    5: notebook      (/loop $DECIDE_SUBMISSION_INTERVAL /decide-submission)

  attach:  tmux attach -t $SESSION
  switch:  ctrl-b o (順次) / ctrl-b 矢印 (方向)
  zoom:    ctrl-b z (現在のpaneを最大化/復帰)
  kill:    tmux kill-session -t $SESSION
EOF
