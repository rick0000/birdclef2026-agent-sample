#!/bin/bash
# run_full_harness.sh で起動した tmux セッションを停止する。
SESSION="${SESSION:-birdclef}"
tmux kill-session -t "$SESSION"
